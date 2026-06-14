from scrapers.rss import scrape_feed


def _feed_url(handle: str) -> str:
    """
    handle 예시:
      @username       → 개인 블로그
      pub/name        → 퍼블리케이션 (https://medium.com/feed/name)
      tag/python      → 태그 피드
    """
    handle = handle.strip()
    if handle.startswith("@"):
        return f"https://medium.com/feed/{handle}"
    return f"https://medium.com/feed/{handle}"


def scrape_profile(handle: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """Medium 개인/퍼블리케이션/태그 피드에서 최신 아티클 저장."""
    return scrape_feed(
        feed_url=_feed_url(handle),
        platform="medium",
        author=author,
        subscription=subscription,
        limit=limit,
    )
