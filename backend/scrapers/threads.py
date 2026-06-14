import hashlib
import logging
from vault.writer import write_item
from vault.reader import get_item

logger = logging.getLogger(__name__)


def _slug(url: str) -> str:
    return f"th-{hashlib.md5(url.encode()).hexdigest()[:12]}"


def scrape_profile(username: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """Threads 공개 프로필에서 최신 포스트를 가져와 Vault에 저장."""
    from playwright.sync_api import sync_playwright

    profile_url = f"https://www.threads.net/@{username}"
    saved = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        articles = page.query_selector_all("article")
        logger.info(f"Threads @{username}: {len(articles)}개 포스트 발견")

        for article in articles[:limit]:
            text = article.inner_text().strip()
            if not text:
                continue

            link_el = article.query_selector("a[href*='/post/']")
            if link_el:
                href = link_el.get_attribute("href") or ""
                post_url = f"https://www.threads.net{href}" if href.startswith("/") else href
            else:
                post_url = f"{profile_url}#{hashlib.md5(text[:50].encode()).hexdigest()[:8]}"

            slug = _slug(post_url)
            if get_item(slug):
                continue

            write_item(
                slug=slug,
                title=text[:100].replace("\n", " "),
                platform="threads",
                source_url=post_url,
                author=author,
                body=text,
                subscription=subscription,
            )
            saved.append(slug)
            logger.info(f"저장: {slug}")

        browser.close()

    return saved
