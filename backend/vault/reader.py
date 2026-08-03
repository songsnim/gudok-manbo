from datetime import date
from pathlib import Path
from typing import Optional
import re
import frontmatter

from config import settings

_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]]')


def safe_title(title: str) -> str:
    """제목을 파일명에 쓸 수 있게 정제. 빈 문자열이면 'untitled'."""
    name = _UNSAFE.sub(" ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:60].strip(" .") or "untitled"


def item_path(slug: str, title: str = "") -> Path:
    """slug에 해당하는 .md 경로. 없으면 title 기반 새 경로를 만들어 반환."""
    hits = sorted(settings.articles_path.glob(f"*-{slug}.md"))
    if hits:
        return hits[0]
    legacy = settings.articles_path / f"{slug}.md"
    if legacy.exists():
        return legacy
    return settings.articles_path / f"{safe_title(title)}-{slug}.md"


def _parse_file(path: Path) -> Optional[dict]:
    try:
        post = frontmatter.load(str(path))
        meta = post.metadata
        return {
            # 신형 파일은 frontmatter에 slug가 있고, 구형은 파일명 자체가 slug다
            "slug": meta.get("slug") or path.stem,
            "title": meta.get("title", ""),
            "platform": meta.get("platform", ""),
            "source_url": meta.get("source_url", ""),
            "author": meta.get("author", ""),
            "date": str(meta.get("date", "")),
            "subscription": meta.get("subscription", False),
            "body": post.content,
        }
    except Exception:
        return None


def get_all_items() -> list[dict]:
    path = settings.articles_path
    if not path.exists():
        return []
    items = []
    for f in sorted(path.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = _parse_file(f)
        if item:
            items.append(item)
    return items


def get_today_items() -> list[dict]:
    today = str(date.today())
    return [i for i in get_all_items() if i["date"] == today]


def get_item(slug: str) -> Optional[dict]:
    path = item_path(slug)
    if not path.exists():
        return None
    return _parse_file(path)


def count_today() -> int:
    return len(get_today_items())
