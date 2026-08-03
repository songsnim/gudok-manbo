"""파일명/slug 매핑 자체 점검. 실행: python vault/test_paths.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from vault.reader import get_item, item_path, safe_title  # noqa: E402
from vault.writer import delete_item, write_item  # noqa: E402

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

print("ok")
