import asyncio
import json
import logging
import re
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_YT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

_COOKIES_FILE = Path(__file__).parent.parent / "data" / "linkedin_cookies.json"
_TWITTER_DB = Path(__file__).parent.parent / "data" / "twitter_accounts.db"


def _yt_initial_data(html: str) -> dict:
    m = re.search(r'var ytInitialData\s*=\s*({.+?});\s*</script>', html, re.DOTALL)
    if not m:
        return {}
    try:
        return json.loads(m.group(1))
    except json.JSONDecodeError:
        return {}


def search_youtube(query: str, limit: int = 8) -> list[dict]:
    """YouTube 채널 검색 (API 키 불필요 — HTML 파싱)"""
    try:
        r = httpx.get(
            "https://www.youtube.com/results",
            params={"search_query": query, "sp": "EgIQAg=="},
            headers=_YT_HEADERS,
            timeout=15,
            follow_redirects=True,
        )
        r.raise_for_status()
    except Exception as e:
        logger.warning(f"YouTube 검색 실패: {e}")
        return []

    data = _yt_initial_data(r.text)
    if not data:
        return []

    channels = []
    try:
        sections = (
            data["contents"]["twoColumnSearchResultsRenderer"]
            ["primaryContents"]["sectionListRenderer"]["contents"]
        )
        for section in sections:
            for item in section.get("itemSectionRenderer", {}).get("contents", []):
                cr = item.get("channelRenderer")
                if not cr:
                    continue
                channel_id = cr.get("channelId", "")
                name = cr.get("title", {}).get("simpleText", "")
                handle = (
                    cr.get("navigationEndpoint", {})
                    .get("browseEndpoint", {})
                    .get("canonicalBaseUrl", "")
                    .lstrip("/")
                )
                sub_text = cr.get("subscriberCountText", {}).get("simpleText", "")
                desc = "".join(
                    r.get("text", "")
                    for r in cr.get("descriptionSnippet", {}).get("runs", [])
                )
                thumbnails = cr.get("thumbnail", {}).get("thumbnails", [])
                avatar = next(
                    (("https:" + t["url"]) if t["url"].startswith("//") else t["url"]
                     for t in reversed(thumbnails) if t.get("url")),
                    None
                )
                if channel_id and name:
                    channels.append({
                        "platform": "youtube",
                        "name": name,
                        "channel_id": channel_id,
                        "handle": handle,
                        "description": desc[:150],
                        "subscriber_count": sub_text,
                        "avatar_url": avatar,
                    })
                if len(channels) >= limit:
                    break
            if len(channels) >= limit:
                break
    except (KeyError, TypeError) as e:
        logger.warning(f"YouTube 결과 파싱 실패: {e}")

    return channels


def search_devto(query: str, limit: int = 8) -> list[dict]:
    """Dev.to 아티클 검색 → 작성자 목록 반환"""
    try:
        r = httpx.get(
            "https://dev.to/api/articles",
            params={"q": query, "per_page": limit * 2},
            headers={"Accept": "application/json"},
            timeout=10,
        )
        r.raise_for_status()
        articles = r.json()
    except Exception as e:
        logger.warning(f"Dev.to 검색 실패: {e}")
        return []

    seen = set()
    results = []
    for article in articles:
        user = article.get("user", {})
        username = user.get("username", "")
        if not username or username in seen:
            continue
        seen.add(username)
        results.append({
            "platform": "devto",
            "name": user.get("name", username),
            "channel_id": None,
            "handle": username,
            "description": article.get("description", "")[:150],
            "subscriber_count": "",
            "avatar_url": user.get("profile_image_90") or user.get("profile_image"),
        })
        if len(results) >= limit:
            break
    return results


def search_linkedin(query: str, limit: int = 8) -> list[dict]:
    """LinkedIn 인물 검색 — Playwright sync가 서버 asyncio와 충돌하므로 별도 프로세스로 실행."""
    if not _COOKIES_FILE.exists():
        logger.warning("LinkedIn 쿠키 없음 — python -m scrapers.linkedin_setup 실행 필요")
        return []
    import subprocess
    import sys
    backend_dir = Path(__file__).parent.parent
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "scrapers.linkedin_search", query, str(limit)],
            cwd=str(backend_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=60,
        )
        if proc.returncode != 0:
            logger.warning(f"LinkedIn 검색 실패: {proc.stderr[-300:]}")
            return []
        return json.loads(proc.stdout.strip() or "[]")
    except Exception as e:
        logger.warning(f"LinkedIn 검색 실패: {e}")
        return []


def _user_dict(user) -> dict:
    return {
        "platform": "twitter",
        "name": user.displayname,
        "channel_id": None,
        "handle": user.username,
        "description": (user.rawDescription or "")[:150],
        "subscriber_count": f"{user.followersCount:,}명",
        "avatar_url": user.profileImageUrl,
    }


async def _twitter_search_async(query: str, limit: int) -> list[dict]:
    import twscrape
    api = twscrape.API(str(_TWITTER_DB))

    handle = query.lstrip("@")
    results: list[dict] = []
    seen: set[str] = set()

    # 1) 정확한 핸들이면 그 계정을 맨 위에
    try:
        exact = await api.user_by_login(handle)
        if exact:
            seen.add(exact.username.lower())
            results.append(_user_dict(exact))
    except Exception:
        pass

    # 2) 키워드로 최근 트윗 검색 → 작성자 추출 (비슷한 계정)
    try:
        async for tweet in api.search(query, limit=limit * 5):
            uname = tweet.user.username.lower()
            if uname in seen:
                continue
            seen.add(uname)
            results.append(_user_dict(tweet.user))
            if len(results) >= limit:
                break
    except Exception as e:
        logger.warning(f"Twitter 검색 실패: {e}")

    return results[:limit]


def search_twitter(query: str, limit: int = 8) -> list[dict]:
    """X/Twitter 계정 검색 — 정확한 핸들 + 키워드 관련 작성자."""
    if not _TWITTER_DB.exists():
        logger.warning("Twitter 계정 DB 없음 — twscrape 계정 설정 필요")
        return []
    return asyncio.run(_twitter_search_async(query, limit))


def search_platform(query: str, platform: str, limit: int = 8) -> list[dict]:
    if platform == "youtube":
        return search_youtube(query, limit)
    if platform == "devto":
        return search_devto(query, limit)
    if platform == "linkedin":
        return search_linkedin(query, limit)
    if platform in ("twitter", "x"):
        return search_twitter(query, limit)
    return []
