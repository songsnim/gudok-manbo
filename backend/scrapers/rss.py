import hashlib
import re
import time
from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify

from llm.openrouter_client import generate_title
from vault.writer import write_item


def _make_slug(url: str, platform: str) -> str:
    h = hashlib.md5(url.encode()).hexdigest()[:12]
    prefix = platform[:2]
    return f"{prefix}-{h}"


def entry_date(entry) -> str:
    """피드 엔트리의 게시일을 YYYY-MM-DD로. 파싱 못하면 원문, 없으면 빈 문자열."""
    for key in ("published", "updated", "created"):
        parsed = entry.get(f"{key}_parsed")
        if parsed:
            return time.strftime("%Y-%m-%d", parsed)
        val = entry.get(key)
        if val:
            return str(val)[:25]
    return ""


# 원문을 그대로 보관한다. 비정상적으로 큰 페이지만 막는 상한
_MAX_BODY = 100000


def _html_to_markdown(html: str, base_url: str = "") -> str:
    """본문 HTML을 Markdown으로. 이미지·링크·제목·코드블록을 원문대로 남긴다."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "nav", "header", "footer", "aside", "form"]):
        tag.decompose()
    container = soup.find("article") or soup.find("main") or soup.body or soup

    # 상대 경로면 앱에서 못 불러오므로 원문 주소 기준으로 절대화
    if base_url:
        for tag_name, attr in (("img", "src"), ("a", "href")):
            for tag in container.find_all(tag_name):
                value = tag.get(attr)
                if value:
                    tag[attr] = urljoin(base_url, value)

    md = markdownify(str(container), heading_style="ATX")
    return re.sub(r"\n{3,}", "\n\n", md).strip()[:_MAX_BODY]


def _fetch_article_body(url: str) -> str | None:
    try:
        r = httpx.get(url, timeout=10, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return _html_to_markdown(r.text, url)
    except Exception:
        return None


# 이보다 짧으면 전문이 아니라 티저로 본다 (Substack 유료글 등)
_TEASER_LEN = 500


def entry_body(entry) -> str | None:
    """엔트리 본문을 Markdown으로. 피드가 전문을 담으면 그걸 쓰고, 티저뿐이면 원문 HTTP로 보강.

    Medium은 글 URL 직접 요청에 403을 주므로 피드 본문이 유일한 경로다.
    """
    html = ""
    content = entry.get("content")
    if content:
        html = content[0].get("value", "")
    if not html:
        html = entry.get("summary", "")

    link = entry.get("link", "")
    body = _html_to_markdown(html, link) if html else ""
    if len(body) >= _TEASER_LEN:
        return body

    fetched = _fetch_article_body(link)
    if fetched and len(fetched) > len(body):
        return fetched
    return body or None


def feed_entry_body(feed_url: str, link: str) -> str | None:
    """피드에서 해당 글의 본문을 Markdown으로. 미리보기에서 담을 때 쓴다."""
    for entry in feedparser.parse(feed_url).entries:
        if entry.get("link") == link:
            return entry_body(entry)
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

        body = entry_body(entry)
        if not body:
            continue

        title = entry.get("title") or generate_title(body)
        write_item(
            slug=slug,
            title=title,
            platform=platform,
            source_url=url,
            author=author,
            body=body,  # 글은 요약하지 않고 원문 그대로 보관
            subscription=subscription,
            published=entry_date(entry),
        )
        saved.append(slug)

    return saved
