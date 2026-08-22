"""파일명/slug 매핑 자체 점검. 실행: python vault/test_paths.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from vault.reader import (  # noqa: E402
    get_all_items, get_collection_items, get_item, item_path, safe_title,
)
from vault.writer import (  # noqa: E402
    delete_item, expire_feed_items, move_to_collection, write_item,
)

assert safe_title('a/b:c*d?e"f<g>h|i') == "a b c d e f g h i"
assert safe_title("  . 제목 .  ") == "제목"
assert safe_title("") == "untitled"
assert len(safe_title("x" * 200)) == 60

with tempfile.TemporaryDirectory() as tmp:
    settings.vault_path = Path(tmp)

    write_item("rs-abc123", "AI: 다 바꾼다?", "rss", "http://x", "me", "본문", True)
    assert (settings.articles_path / "AI 다 바꾼다-rs-abc123.md").exists()

    item = get_item("rs-abc123")
    assert item["slug"] == "rs-abc123" and item["title"] == "AI: 다 바꾼다?"

    # 제목이 바뀌어도 기존 파일을 덮어쓴다(중복 생성 금지)
    write_item("rs-abc123", "새 제목", "rss", "http://x", "me", "본문2", True)
    assert len(list(settings.articles_path.glob("*.md"))) == 1

    # 구형 '<slug>.md'도 읽고 지울 수 있어야 한다
    (settings.articles_path / "yt-old99.md").write_text(
        "---\ntitle: 옛날글\n---\n본문", encoding="utf-8"
    )
    assert get_item("yt-old99")["slug"] == "yt-old99"
    assert delete_item("yt-old99") and not delete_item("yt-old99")

    assert delete_item("rs-abc123")
    assert get_item("rs-abc123") is None

# ── Collection 이동 ───────────────────────────────────────────────────────────
with tempfile.TemporaryDirectory() as tmp:
    settings.vault_path = Path(tmp)

    write_item("yt-keep", "남길 글", "youtube", "http://x", "me", "본문", True)
    assert len(get_all_items()) == 1 and get_collection_items() == []

    assert move_to_collection("yt-keep")
    assert get_all_items() == [] and len(get_collection_items()) == 1
    # 이동 후에도 slug로 찾을 수 있어야 한다 (미리보기 in_feed 판정이 이걸 쓴다)
    assert get_item("yt-keep")["title"] == "남길 글"
    # Obsidian이 폴더와 함께 만드는 빈 노트는 Item으로 세지 않는다
    (settings.collections_path / "collections.md").write_text("", encoding="utf-8")
    assert len(get_collection_items()) == 1
    assert get_item("collections") is None

    assert move_to_collection("yt-keep")      # 멱등
    assert not move_to_collection("없는slug")

    # Collection에서 빼는 것은 완전 삭제 — articles/로 돌아가지 않는다
    assert delete_item("yt-keep")
    assert get_item("yt-keep") is None

# ── 만료 ──────────────────────────────────────────────────────────────────────
with tempfile.TemporaryDirectory() as tmp:
    settings.vault_path = Path(tmp)
    settings.articles_path.mkdir(parents=True)
    settings.collections_path.mkdir(parents=True)

    def _put(folder, name, date_line):
        (folder / name).write_text(f"---\nslug: {name[:-3]}\n{date_line}---\n본문", encoding="utf-8")

    _put(settings.articles_path, "old.md", "date: 2020-01-01\n")
    _put(settings.articles_path, "fresh.md", "date: 2999-01-01\n")
    _put(settings.articles_path, "nodate.md", "")            # 판정 불가 → 보존
    _put(settings.articles_path, "baddate.md", "date: 언제였지\n")  # 판정 불가 → 보존
    _put(settings.collections_path, "old-collected.md", "date: 2020-01-01\n")

    assert expire_feed_items(0) == []      # 기능 꺼짐 — 아무것도 안 지운다
    assert expire_feed_items(-1) == []

    assert expire_feed_items(30) == ["old.md"]
    names = {p.name for p in settings.articles_path.glob("*.md")}
    assert names == {"fresh.md", "nodate.md", "baddate.md"}, names
    # Collection은 아무리 오래돼도 만료되지 않는다
    assert (settings.collections_path / "old-collected.md").exists()

print("ok")
