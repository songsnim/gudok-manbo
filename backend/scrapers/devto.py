from scrapers.rss import scrape_feed


def scrape_user(username: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """Dev.to 사용자 최신 글 저장."""
    return scrape_feed(
        feed_url=f"https://dev.to/feed/{username.lstrip('@')}",
        platform="devto",
        author=author,
        subscription=subscription,
        limit=limit,
    )
