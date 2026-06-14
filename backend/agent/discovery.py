import logging
import uuid
import feedparser
import httpx

from agent.curator import load_subscriptions, add_subscription

logger = logging.getLogger(__name__)

_YT_RSS = "https://www.youtube.com/feeds/videos.xml?channel_id={}"
_HEADERS = {"User-Agent": "Mozilla/5.0"}


def _validate(source: dict) -> bool:
    """소스 피드가 실제로 동작하는지 확인. Playwright 기반 플랫폼은 건너뜀."""
    platform = source.get("platform", "")
    try:
        if platform == "youtube":
            # LLM이 channel_id를 만들어내므로 항상 검색으로 실제 ID 검증
            from scrapers.search import search_youtube
            results = search_youtube(source.get("author", ""), limit=1)
            if not results:
                return False
            source["channel_id"] = results[0]["channel_id"]
            logger.info(f"YouTube 채널ID 해결: {source.get('author')} → {source['channel_id']}")
            return True

        if platform == "medium":
            username = source.get("username", "")
            url = f"https://medium.com/feed/{username}"
            feed = feedparser.parse(url)
            return len(feed.entries) > 0

        if platform == "substack":
            pub = source.get("username", "").rstrip("/")
            if "." not in pub:
                pub = f"{pub}.substack.com"
            feed = feedparser.parse(f"https://{pub}/feed")
            return len(feed.entries) > 0

        if platform == "devto":
            username = source.get("username", "").lstrip("@")
            feed = feedparser.parse(f"https://dev.to/feed/{username}")
            return len(feed.entries) > 0

        if platform == "hackernews":
            return True  # hnrss.org는 항상 유효

        if platform == "rss":
            feed_url = source.get("feed_url", "")
            if not feed_url:
                return False
            feed = feedparser.parse(feed_url)
            return len(feed.entries) > 0

        # threads, twitter, linkedin: 검증 생략 (브라우저 필요)
        return True

    except Exception as e:
        logger.warning(f"검증 실패 ({source.get('author', '')}): {e}")
        return False


def _already_subscribed(source: dict, existing: list[dict]) -> bool:
    for sub in existing:
        if sub.get("platform") != source.get("platform"):
            continue
        if source.get("channel_id") and sub.get("channel_id") == source["channel_id"]:
            return True
        if source.get("username") and sub.get("username") == source.get("username"):
            return True
        if source.get("feed_url") and sub.get("feed_url") == source.get("feed_url"):
            return True
    return False


def discover_and_subscribe(query: str) -> dict:
    """LLM 추천 → 검증 → 구독 추가. 결과 요약 반환."""
    from llm.openrouter_client import discover_sources

    existing = load_subscriptions()
    logger.info(f"Discovery 시작: {query!r}")

    candidates = discover_sources(query, existing)
    logger.info(f"LLM 추천: {len(candidates)}개")

    added = []
    skipped = []

    for src in candidates:
        author = src.get("author", "unknown")
        platform = src.get("platform", "")

        if _already_subscribed(src, existing):
            logger.info(f"이미 구독: {author}")
            skipped.append({"author": author, "reason": "이미 구독 중"})
            continue

        if not _validate(src):
            logger.warning(f"검증 실패, 건너뜀: {author}")
            skipped.append({"author": author, "reason": "피드 검증 실패"})
            continue

        sub = {
            "id": str(uuid.uuid4()),
            "platform": platform,
            "author": author,
            "channel_id": src.get("channel_id"),
            "feed_url": src.get("feed_url"),
            "username": src.get("username"),
            "discovered_by": "agent",
            "discovery_reason": src.get("reason", ""),
        }
        add_subscription(sub)
        added.append({"author": author, "platform": platform, "reason": src.get("reason", "")})
        logger.info(f"구독 추가: {author} ({platform})")

    return {
        "query": query,
        "added": len(added),
        "sources": added,
        "skipped": skipped,
    }
