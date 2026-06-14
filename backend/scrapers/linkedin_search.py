"""LinkedIn 인물 검색 (별도 프로세스 실행 — Playwright sync는 서버 asyncio와 충돌).

사용: python -m scrapers.linkedin_search "query" [limit]
결과 JSON을 stdout으로 출력.
"""
import json
import sys
from pathlib import Path

_COOKIES_FILE = Path(__file__).parent.parent / "data" / "linkedin_cookies.json"

_SKIP_LINES = {
    "메시지", "연결", "팔로우", "팔로잉", "팔로우 취소",
    "Message", "Connect", "Follow", "Following",
}


def _parse_lines(lines: list[str]) -> dict:
    name = (lines[0] if lines else "").split("•")[0].strip()
    follower = next(
        (l for l in lines if l.startswith("팔로워") or l.startswith("Followers")), ""
    )
    content = [
        l for l in lines[1:]
        if l not in _SKIP_LINES
        and not l.startswith("•")
        and "촌" not in l
        and not l.startswith("팔로워")
        and not l.startswith("Followers")
    ]
    headline = content[0] if content else ""
    location = content[1] if len(content) > 1 else ""
    desc = headline if not location else f"{headline} · {location}"
    return {"name": name, "description": desc[:150], "follower": follower}


def run(query: str, limit: int = 8) -> list[dict]:
    if not _COOKIES_FILE.exists():
        return []
    from playwright.sync_api import sync_playwright

    cookies = json.loads(_COOKIES_FILE.read_text(encoding="utf-8"))
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        ctx.add_cookies(cookies)
        page = ctx.new_page()
        page.goto(
            f"https://www.linkedin.com/search/results/people/?keywords={query}&origin=GLOBAL_SEARCH_HEADER",
            timeout=30000,
        )
        page.wait_for_timeout(4000)

        seen = set()
        for a in page.query_selector_all("a[href*='/in/']"):
            href = (a.get_attribute("href") or "").split("?")[0]
            if not href or href in seen or not (a.inner_text() or "").strip():
                continue
            seen.add(href)
            container = a.evaluate_handle(
                "el => el.closest('li') || el.parentElement.parentElement.parentElement"
            )
            data = container.evaluate(
                "el => ({"
                " lines: el.innerText.split('\\n').map(s=>s.trim()).filter(Boolean),"
                " img: (el.querySelector('img') || {}).src || null })"
            )
            parsed = _parse_lines(data["lines"])
            if not parsed["name"]:
                continue
            results.append({
                "platform": "linkedin",
                "name": parsed["name"],
                "channel_id": None,
                "handle": href,
                "description": parsed["description"],
                "subscriber_count": parsed["follower"],
                "avatar_url": data["img"],
            })
            if len(results) >= limit:
                break
        browser.close()
    return results


if __name__ == "__main__":
    q = sys.argv[1] if len(sys.argv) > 1 else ""
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(run(q, n), ensure_ascii=False))
