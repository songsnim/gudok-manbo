from datetime import date
from pathlib import Path
import frontmatter

from config import settings


def write_item(
    slug: str,
    title: str,
    platform: str,
    source_url: str,
    author: str,
    body: str,
    subscription: bool,
) -> Path:
    settings.articles_path.mkdir(parents=True, exist_ok=True)
    path = settings.articles_path / f"{slug}.md"

    post = frontmatter.Post(
        body,
        title=title,
        platform=platform,
        source_url=source_url,
        author=author,
        date=date.today(),
        subscription=subscription,
    )
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


def delete_item(slug: str) -> bool:
    """Vault에서 아이템(.md) 삭제. 성공 시 True."""
    path = settings.articles_path / f"{slug}.md"
    if path.exists():
        path.unlink()
        return True
    return False
