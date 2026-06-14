import json
import logging
import re
from pathlib import Path

import feedparser
import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}
_COOKIES_FILE = Path(__file__).parent.parent / "data" / "linkedin_cookies.json"

_OG_IMAGE = re.compile(
    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)


def _og_image(url: str, cookies: list | None = None) -> str | None:
    try:
        with httpx.Client(headers=_HEADERS, timeout=12, follow_redirects=True) as c:
            if cookies:
                for ck in cookies:
                    c.cookies.set(ck["name"], ck["value"], domain=ck.get("domain", ""))
            r = c.get(url)
            r.raise_for_status()
            m = _OG_IMAGE.search(r.text)
            return m.group(1) if m else None
    except Exception as e:
        logger.warning(f"og:image 조회 실패 ({url}): {e}")
        return None


def _devto_avatar(username: str) -> str | None:
    try:
        r = httpx.get(
            "https://dev.to/api/users/by_username",
            params={"url": username.lstrip("@")},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        return r.json().get("profile_image")
    except Exception as e:
        logger.warning(f"Dev.to 아바타 조회 실패 ({username}): {e}")
        return None


def _twitter_avatar(username: str) -> str | None:
    from scrapers.search import search_twitter
    results = search_twitter(username)
    return results[0].get("avatar_url") if results else None


def fetch_avatar(sub: dict) -> str | None:
    """구독 소스의 프로필 이미지 URL을 해석. 실패 시 None."""
    platform = sub.get("platform", "")

    if platform == "youtube" and sub.get("channel_id"):
        return _og_image(f"https://www.youtube.com/channel/{sub['channel_id']}")

    if platform == "medium":
        handle = (sub.get("username") or "").strip()
        if handle:
            return _og_image(f"https://medium.com/{handle}")

    if platform == "substack":
        pub = (sub.get("username") or "").strip().rstrip("/")
        if pub:
            if "." not in pub:
                pub = f"{pub}.substack.com"
            return _og_image(f"https://{pub}")

    if platform == "devto" and sub.get("username"):
        return _devto_avatar(sub["username"])

    if platform == "threads" and sub.get("username"):
        u = sub["username"].lstrip("@")
        return _og_image(f"https://www.threads.net/@{u}")

    if platform in ("twitter", "x") and sub.get("username"):
        return _twitter_avatar(sub["username"])

    if platform == "linkedin" and sub.get("feed_url"):
        cookies = None
        if _COOKIES_FILE.exists():
            cookies = json.loads(_COOKIES_FILE.read_text(encoding="utf-8"))
        return _og_image(sub["feed_url"], cookies=cookies)

    return None
