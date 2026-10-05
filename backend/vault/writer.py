from datetime import date, datetime, timedelta
from pathlib import Path
import logging
import re
import frontmatter

from config import settings
from vault.reader import item_path, find_item_path

logger = logging.getLogger(__name__)


def write_item(
    slug: str,
    title: str,
    platform: str,
    source_url: str,
    author: str,
    body: str,
    subscription: bool,
    published: str = "",
) -> Path:
    settings.articles_path.mkdir(parents=True, exist_ok=True)
    path = item_path(slug, title)

    meta = {}
    tags = _pick_tags(title, body)
    if tags:
        meta["tags"] = tags
    post = frontmatter.Post(
        body,
        slug=slug,
        title=title,
        platform=platform,
        source_url=source_url,
        author=author,
        date=date.today(),
        published=published,  # 매체에 실제 게시된 날짜 (date는 수집일)
        subscription=subscription,
        **meta,
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def load_taxonomy() -> tuple[str, set[str]]:
    """Vault 루트 CLAUDE.md의 태그 체계 → (문서 원문, 허용 태그 집합).

    태그 체계의 SSOT는 그 문서다. 사용자가 표를 고치면 다음 수집부터 그대로 따른다.
    문서가 없으면 ("", set()) — 태깅을 건너뛴다.
    """
    path = settings.vault_path / "CLAUDE.md"
    if not path.exists():
        return "", set()
    text = path.read_text(encoding="utf-8")
    allowed = set()
    # 태그 표의 한 행: | `tech` | `ml` `agent` ... |
    for top, subs in re.findall(r"^\|\s*`([a-z-]+)`\s*\|(.*)\|\s*$", text, re.M):
        allowed.add(top)
        allowed.update(f"{top}/{s}" for s in re.findall(r"`([a-z-]+)`", subs))
    return text, allowed


def _pick_tags(title: str, body: str) -> list[str]:
    """태그는 덤이다 — 고르다 실패해도 Item 저장은 막지 않는다."""
    rules, allowed = load_taxonomy()
    if not allowed:
        return []
    try:
        from llm.openrouter_client import pick_tags
        return pick_tags(rules, allowed, title, body)
    except Exception as e:
        logger.warning(f"태그 선택 실패 ({title}): {type(e).__name__}: {e}")
        return []


def tag_untagged_items() -> int:
    """tags가 없는 Item(Feed·Collection)에 태그를 단다. 태그를 단 개수 반환.

    기존 Item 일괄 태깅용. 실행: cd backend && python -m vault.writer
    """
    done = 0
    for folder in (settings.articles_path, settings.collections_path):
        for f in sorted(folder.glob("*.md")) if folder.exists() else []:
            post = frontmatter.load(str(f))
            if post.metadata.get("tags") or not post.metadata.get("slug"):
                continue
            tags = _pick_tags(post.metadata.get("title", ""), post.content)
            if not tags:
                continue
            post.metadata["tags"] = tags
            f.write_text(frontmatter.dumps(post), encoding="utf-8")
            done += 1
            logger.info(f"태그 {tags}: {f.name}")
    return done


def delete_item(slug: str) -> bool:
    """Vault에서 아이템(.md) 삭제. Feed든 Collection이든. 성공 시 True."""
    path = find_item_path(slug)
    if path:
        path.unlink()
        return True
    return False


def move_to_collection(slug: str) -> bool:
    """articles/ → collections/ 로 파일 이동. 이미 collections/에 있으면 True(멱등)."""
    path = find_item_path(slug)
    if not path:
        return False
    if path.parent == settings.collections_path:
        return True
    settings.collections_path.mkdir(parents=True, exist_ok=True)
    path.rename(settings.collections_path / path.name)
    return True


def expire_feed_items(days: int) -> list[str]:
    """수집일(frontmatter date)로부터 days 초과한 Feed 아이템을 삭제. 지운 파일명 목록 반환.

    collections/ 는 열지 않는다 — Collection은 만료되지 않는다.
    days<=0 이면 아무것도 하지 않는다 (기능 꺼진 상태).
    """
    if days <= 0 or not settings.articles_path.exists():
        return []

    cutoff = date.today() - timedelta(days=days)
    deleted = []
    for f in settings.articles_path.glob("*.md"):
        collected = _collected_date(f)
        # 날짜를 못 읽으면 판정 불가 — 보존 쪽으로 기운다
        if collected is None or collected >= cutoff:
            continue
        f.unlink()
        deleted.append(f.name)
        logger.info(f"만료 삭제: {f.name} (수집일 {collected})")
    return deleted


def _collected_date(path: Path):
    """frontmatter의 date를 date로 파싱. 못 읽으면 None (파일 mtime은 쓰지 않는다 —
    Obsidian Sync나 편집이 mtime을 건드린다)."""
    try:
        value = frontmatter.load(str(path)).metadata.get("date")
    except Exception:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except Exception:
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    print(f"태그 단 Item: {tag_untagged_items()}개")
