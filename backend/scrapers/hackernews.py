from scrapers.rss import scrape_feed


_FEEDS = {
    "frontpage": "https://hnrss.org/frontpage",
    "newest": "https://hnrss.org/newest",
    "best": "https://hnrss.org/best",
    "ask": "https://hnrss.org/ask",
    "show": "https://hnrss.org/show",
}


def scrape_feed_type(feed_type: str = "frontpage", author: str = "HackerNews", subscription: bool = True, limit: int = 5) -> list[str]:
    """HackerNews 피드 저장. feed_type: frontpage | newest | best | ask | show"""
    feed_url = _FEEDS.get(feed_type, _FEEDS["frontpage"])
    return scrape_feed(
        feed_url=feed_url,
        platform="hackernews",
        author=author,
        subscription=subscription,
        limit=limit,
    )
