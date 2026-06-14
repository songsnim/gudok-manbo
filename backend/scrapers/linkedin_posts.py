"""LinkedIn 프로필 최신 포스트 수집 (별도 프로세스 — Playwright sync는 서버 asyncio와 충돌).

사용: python -m scrapers.linkedin_posts "<profile_url>" [limit]
결과 JSON([{title, source_url, body, date}])을 stdout으로 출력.
"""
import hashlib
import json
import sys
from pathlib import Path

_COOKIE_FILE = Path(__file__).parent.parent / "data" / "linkedin_cookies.json"


def run(profile_url: str, limit: int = 10) -> list[dict]:
    if not _COOKIE_FILE.exists():
        return []
    from playwright.sync_api import sync_playwright

    cookies = json.loads(_COOKIE_FILE.read_text(encoding="utf-8"))
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        )
        context.add_cookies(cookies)
        page = context.new_page()

        posts_url = profile_url.rstrip("/") + "/recent-activity/all/"
        page.goto(posts_url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(3000)

        if "authwall" in page.url or "/login" in page.url:
            browser.close()
            return []

        posts = page.query_selector_all("[data-urn^='urn:li:activity']")
        if not posts:
            posts = page.query_selector_all(".feed-shared-update-v2")

        seen = set()
        for post in posts:
            text_el = (
                post.query_selector(".update-components-text")
                or post.query_selector(".break-words")
            )
            text = text_el.inner_text().strip() if text_el else post.inner_text().strip()
            if not text:
                continue

            link_el = (
                post.query_selector("a[href*='/posts/']")
                or post.query_selector("a[href*='/feed/update/']")
            )
            if link_el:
                href = link_el.get_attribute("href") or ""
                post_url = f"https://www.linkedin.com{href}" if href.startswith("/") else href
                post_url = post_url.split("?")[0]
            else:
                post_url = f"https://www.linkedin.com/#{hashlib.md5(text[:50].encode()).hexdigest()[:8]}"

            if post_url in seen:
                continue
            seen.add(post_url)

            results.append({
                "title": text[:100].replace("\n", " "),
                "source_url": post_url,
                "body": text,
                "date": "",
            })
            if len(results) >= limit:
                break
        browser.close()
    return results


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(run(url, n), ensure_ascii=False))
