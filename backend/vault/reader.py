from datetime import date
from pathlib import Path
from typing import Optional
import frontmatter

from config import settings


def _parse_file(path: Path) -> Optional[dict]:
    try:
        post = frontmatter.load(str(path))
        meta = post.metadata
        return {
            "slug": path.stem,
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
    path = settings.articles_path / f"{slug}.md"
    if not path.exists():
        return None
    return _parse_file(path)


def count_today() -> int:
    return len(get_today_items())
