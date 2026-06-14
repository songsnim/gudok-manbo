import hashlib
import re
import feedparser
import httpx

from llm.openrouter_client import generate_title
from vault.writer import write_item


def _make_slug(url: str, platform: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    prefix = platform[:2]
    return f"{prefix}-{h}"


def _fetch_article_body(url: str) -> str | None:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        # 최소한의 HTML → 텍스트 변환 (태그 제거)
        text = re.sub(r"<[^>]+>", " ", r.text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:20000]
    except Exception:
        return None


def scrape_feed(feed_url: str, platform: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """RSS 피드에서 최신 아티클을 가져와 Vault에 저장. 저장된 slug 목록 반환."""
    feed = feedparser.parse(feed_url)
    saved = []

    for entry in feed.entries[:limit]:
        url = entry.get("link", "")
        if not url:
            continue

        slug = _make_slug(url, platform)

        from vault.reader import get_item
        if get_item(slug):
            continue

        body = _fetch_article_body(url)
        if not body:
            continue

        title = entry.get("title") or generate_title(body)
        write_item(
            slug=slug,
            title=title,
            platform=platform,
            source_url=url,
            author=author,
            body=body,
            subscription=subscription,
        )
        saved.append(slug)

    return saved
