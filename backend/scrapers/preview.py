import logging

import feedparser

from vault.reader import get_item
from vault.writer import write_item

logger = logging.getLogger(__name__)


def _entry_date(entry) -> str:
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            return str(val)[:25]
    return ""


def _feed_url_for(sub: dict) -> str | None:
    """피드 기반 플랫폼의 RSS URL을 반환. 미지원 플랫폼은 None."""
    platform = sub.get("platform", "")
    if platform == "medium":
        from scrapers.medium import _feed_url
        return _feed_url(sub.get("username") or sub.get("feed_url") or "")
    if platform == "substack":
        from scrapers.substack import _feed_url
        return _feed_url(sub.get("username") or sub.get("feed_url") or "")
    if platform == "devto":
        username = (sub.get("username") or "").lstrip("@")
        return f"https://dev.to/feed/{username}"
    if platform == "hackernews":
        from scrapers.hackernews import _FEEDS
        return _FEEDS.get(sub.get("username", "frontpage"), _FEEDS["frontpage"])
    if platform == "rss":
        return sub.get("feed_url")
    return None


def preview_source(sub: dict, limit: int = 10) -> list[dict]:
    """구독 소스의 최신 글/영상 목록을 반환 (저장·요약 없음)."""
    platform = sub.get("platform", "")
    author = sub.get("author", "")

    if platform == "youtube":
        from scrapers.youtube import _fetch_feed, _make_slug
        try:
            feed = _fetch_feed(sub["channel_id"])
        except Exception as e:
            logger.warning(f"YouTube 미리보기 실패: {e}")
            return []
        items = []
        for entry in feed.entries[:limit]:
            video_id = entry.get("yt_videoid", "")
            if not video_id:
                continue
            slug = _make_slug(video_id)
            items.append({
                "title": entry.get("title", ""),
                "source_url": entry.get("link", ""),
                "date": _entry_date(entry),
                "platform": "youtube",
                "author": author,
                "type": "video",
                "video_id": video_id,
                "thumbnail": f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
                "in_feed": get_item(slug) is not None,
            })
        return items

    if platform == "linkedin":
        from scrapers.linkedin import fetch_posts, _slug
        try:
            posts = fetch_posts(sub.get("feed_url", ""), limit)
        except Exception as e:
            logger.warning(f"LinkedIn 미리보기 실패: {e}")
            return []
        return [{
            "title": post["title"],
            "source_url": post["source_url"],
            "date": post.get("date", ""),
            "platform": "linkedin",
            "author": author,
            "type": "article",
            "video_id": None,
            "thumbnail": None,
            "body": post["body"],
            "in_feed": get_item(_slug(post["source_url"])) is not None,
        } for post in posts]

    feed_url = _feed_url_for(sub)
    if not feed_url:
        return []  # threads/twitter: 미리보기 미지원

    from scrapers.rss import _make_slug
    feed = feedparser.parse(feed_url)
    items = []
    for entry in feed.entries[:limit]:
        url = entry.get("link", "")
        if not url:
            continue
        slug = _make_slug(url, platform)
        items.append({
            "title": entry.get("title", ""),
            "source_url": url,
            "date": _entry_date(entry),
            "platform": platform,
            "author": author,
            "type": "article",
            "video_id": None,
            "thumbnail": None,
            "in_feed": get_item(slug) is not None,
        })
    return items


def add_item(item: dict) -> dict:
    """미리보기 아이템을 피드(Vault)로 옮김. 영상은 요약, 글은 원본."""
    platform = item.get("platform", "")
    url = item.get("source_url", "")
    author = item.get("author", "")

    if platform == "youtube":
        from scrapers.youtube import _make_slug, _get_transcript
        from llm.openrouter_client import transcribe_to_article, generate_title
        video_id = item.get("video_id", "")
        slug = _make_slug(video_id)
        if get_item(slug):
            return {"status": "exists", "slug": slug}
        transcript = _get_transcript(video_id)
        if not transcript:
            return {"status": "error", "reason": "자막 없음"}
        body = transcribe_to_article(transcript)
        title = item.get("title") or generate_title(transcript)
        write_item(slug, title, "youtube", url, author, body, subscription=True)
        return {"status": "added", "slug": slug}

    if platform == "linkedin":
        from scrapers.linkedin import _slug
        slug = _slug(url)
        if get_item(slug):
            return {"status": "exists", "slug": slug}
        body = item.get("body", "")
        if not body:
            return {"status": "error", "reason": "본문 없음"}
        title = item.get("title") or body[:100].replace("\n", " ")
        write_item(slug, title, "linkedin", url, author, body, subscription=True)
        return {"status": "added", "slug": slug}

    from scrapers.rss import _make_slug, _fetch_article_body
    from llm.openrouter_client import generate_title
    slug = _make_slug(url, platform)
    if get_item(slug):
        return {"status": "exists", "slug": slug}
    body = _fetch_article_body(url)
    if not body:
        return {"status": "error", "reason": "본문 수집 실패"}
    title = item.get("title") or generate_title(body)
    write_item(slug, title, platform, url, author, body, subscription=True)
    return {"status": "added", "slug": slug}
