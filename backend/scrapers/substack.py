from scrapers.rss import scrape_feed


def _feed_url(publication: str) -> str:
    """
    publication 예시:
      stratechery          → stratechery.substack.com
      levelup.substack.com → 그대로 사용
    """
    publication = publication.strip().rstrip("/")
    if "." not in publication:
        publication = f"{publication}.substack.com"
    return f"https://{publication}/feed"


def scrape_publication(publication: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """Substack 뉴스레터 최신 글 저장."""
    return scrape_feed(
        feed_url=_feed_url(publication),
        platform="substack",
        author=author,
        subscription=subscription,
        limit=limit,
    )
