import hashlib
import re
import feedparser
import httpx
from bs4 import BeautifulSoup

from llm.openrouter_client import generate_title, summarize_article
from vault.writer import write_item


def _make_slug(url: str, platform: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    prefix = platform[:2]
    return f"{prefix}-{h}"


def _html_to_text(html: str) -> str:
    """HTML에서 본문 텍스트만 추출. script/style 등 비콘텐츠 요소는 제거."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup
    text = container.get_text(separator=" ")
    return re.sub(r"\s+", " ", text).strip()


def _fetch_article_body(url: str) -> str | None:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return _html_to_text(r.text)[:20000]
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
        summary = summarize_article(body)
        write_item(
            slug=slug,
            title=title,
            platform=platform,
            source_url=url,
            author=author,
            body=summary,
            subscription=subscription,
        )
        saved.append(slug)

    return saved
