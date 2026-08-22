from datetime import date, datetime, timedelta
from pathlib import Path
import logging
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
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


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
