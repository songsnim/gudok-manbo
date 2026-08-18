import logging

import feedparser
import httpx

from vault.reader import get_item
from vault.writer import write_item

logger = logging.getLogger(__name__)


def _feed_url_for(sub: dict) -> str | None:
    """피드 기반 플랫폼의 RSS URL을 반환. 미지원 플랫폼은 None."""
    platform = sub.get("platform", "")
    if platform == "medium":
        from scrapers.medium import _feed_url
        return _feed_url(sub.get("username") or sub.get("feed_url") or "")
    if platform == "substack":
        from scrapers.substack import _feed_url
        return _feed_url(sub.get("username") or sub.get("feed_url") or "")
    if platform == "hackernews":
        from scrapers.hackernews import _FEEDS
        return _FEEDS.get(sub.get("username", "frontpage"), _FEEDS["frontpage"])
    if platform == "rss":
        return sub.get("feed_url")
    return None


def _substack_entries(feed_url: str, offset: int, limit: int) -> list[dict] | None:
    """Substack archive API로 과거 글까지 페이지네이션. 실패하면 None(→ RSS 폴백).

    RSS는 최근 20개뿐이라 그 너머로 스크롤하려면 이 API가 필요하다.
    """
    base = feed_url.rsplit("/feed", 1)[0]
    try:
        r = httpx.get(
            f"{base}/api/v1/archive",
            params={"sort": "new", "offset": offset, "limit": limit},
            headers={"User-Agent": "Mozilla/5.0"}, timeout=15, follow_redirects=True,
        )
        r.raise_for_status()
        posts = r.json()
    except Exception as e:
        logger.warning(f"Substack archive 조회 실패 ({base}): {e}")
        return None
    return [{
        "link": p.get("canonical_url", ""),
        "title": p.get("title", ""),
        "published": (p.get("post_date") or "")[:10],
    } for p in posts]


def preview_source(sub: dict, limit: int = 10, cursor: str | None = None) -> dict:
    """구독 소스의 글/영상 목록 + 다음 커서 (저장·요약 없음).

    YouTube는 innertube continuation 토큰, 피드 기반 플랫폼은 오프셋 커서를 쓴다.
    LinkedIn만 페이지네이션 없음.
    """
    platform = sub.get("platform", "")
    author = sub.get("author", "")

    if platform == "youtube":
        from scrapers.youtube import fetch_videos, _make_slug
        try:
            videos, next_cursor = fetch_videos(sub["channel_id"], cursor)
        except Exception as e:
            logger.warning(f"YouTube 미리보기 실패: {e}")
            return {"items": [], "next_cursor": None}
        items = [{
            "title": v["title"],
            "source_url": f"https://www.youtube.com/watch?v={v['video_id']}",
            "date": v["date"],
            "platform": "youtube",
            "author": author,
            "type": "video",
            "video_id": v["video_id"],
            "thumbnail": f"https://i.ytimg.com/vi/{v['video_id']}/hqdefault.jpg",
            "in_feed": get_item(_make_slug(v["video_id"])) is not None,
        } for v in videos]
        return {"items": items, "next_cursor": next_cursor}

    if platform == "linkedin":
        if cursor:
            return {"items": [], "next_cursor": None}  # 스크래핑이라 페이지네이션 없음
        from scrapers.linkedin import fetch_posts, _slug
        try:
            posts = fetch_posts(sub.get("feed_url", ""), limit)
        except Exception as e:
            logger.warning(f"LinkedIn 미리보기 실패: {e}")
            return {"items": [], "next_cursor": None}
        return {"items": [{
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
        } for post in posts], "next_cursor": None}

    feed_url = _feed_url_for(sub)
    if not feed_url:
        return {"items": [], "next_cursor": None}  # 피드 URL 없는 플랫폼

    from scrapers.rss import _make_slug, entry_date
    offset = int(cursor) if cursor and cursor.isdigit() else 0

    entries = _substack_entries(feed_url, offset, limit) if platform == "substack" else None
    if entries is None:
        # ponytail: 페이지마다 피드 전체를 다시 파싱한다. 피드가 수십 개 규모라 캐시 불필요
        entries = feedparser.parse(feed_url).entries[offset:offset + limit]

    items = []
    for entry in entries:
        url = entry.get("link", "")
        if not url:
            continue
        slug = _make_slug(url, platform)
        items.append({
            "title": entry.get("title", ""),
            "source_url": url,
            "date": entry_date(entry),
            "platform": platform,
            "author": author,
            "type": "article",
            "video_id": None,
            "thumbnail": None,
            # 담을 때 원문 직접 요청이 막히는 경우(Medium 403)가 있어 피드로 되돌아올 길을 남긴다.
            # 본문 자체를 실으면 목록 응답이 수백 KB로 불어난다
            "feed_url": feed_url,
            "in_feed": get_item(slug) is not None,
        })
    # 한 페이지를 꽉 채웠으면 더 있을 수 있다고 본다
    next_cursor = str(offset + limit) if len(entries) == limit else None
    return {"items": items, "next_cursor": next_cursor}


def add_item(item: dict) -> dict:
    """미리보기 아이템을 피드(Vault)로 옮김. 영상은 재구성, 글은 요약, LinkedIn은 원문."""
    platform = item.get("platform", "")
    url = item.get("source_url", "")
    author = item.get("author", "")

    if platform == "youtube":
        from scrapers.youtube import _make_slug, _get_transcript, video_published
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
        # 미리보기의 date는 "3일 전" 같은 상대 표기라 저장용으로 못 쓴다
        write_item(slug, title, "youtube", url, author, body, subscription=True,
                   published=video_published(video_id))
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
        write_item(slug, title, "linkedin", url, author, body, subscription=True,
                   published=item.get("date", ""))
        return {"status": "added", "slug": slug}

    from scrapers.rss import _make_slug, _fetch_article_body, feed_entry_body
    from llm.openrouter_client import generate_title
    slug = _make_slug(url, platform)
    if get_item(slug):
        return {"status": "exists", "slug": slug}
    feed_url = item.get("feed_url", "")
    body = (feed_entry_body(feed_url, url) if feed_url else None) or _fetch_article_body(url)
    if not body:
        return {"status": "error", "reason": "본문 수집 실패"}
    title = item.get("title") or generate_title(body)
    # 글은 요약하지 않고 원문 그대로 보관
    write_item(slug, title, platform, url, author, body, subscription=True,
               published=item.get("date", ""))
    return {"status": "added", "slug": slug}
