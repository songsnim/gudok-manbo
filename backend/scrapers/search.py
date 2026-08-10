import json
import logging
import re
from pathlib import Path

import feedparser
import httpx

logger = logging.getLogger(__name__)

_YT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

_COOKIES_FILE = Path(__file__).parent.parent / "data" / "linkedin_cookies.json"


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


_MEDIUM_LINK = re.compile(r"https?://(?:([^./]+)\.medium\.com|medium\.com/(@?[^/?]+))/")


def medium_handle(link: str) -> str | None:
    """Medium 글 URL에서 구독용 handle(@사용자 또는 퍼블리케이션명) 추출.

    커스텀 도메인(towardsdatascience.com 등)은 medium.com/feed/로 못 받으므로 None.
    """
    m = _MEDIUM_LINK.match(link)
    if not m:
        return None
    return m.group(1) or m.group(2)


def _medium_row(handle: str, name: str, description: str) -> dict:
    return {
        "platform": "medium",
        "name": name or handle,
        "channel_id": None,
        "handle": handle,
        "description": description[:150],
        "subscriber_count": "",
        "avatar_url": None,  # 아바타는 구독 추가 시 fetch_avatar가 채운다
    }


def _feed_title(feed) -> str:
    """'Stories by X on Medium' / 'X - Medium' 형태의 피드 제목을 이름만 남김."""
    title = feed.get("title", "")
    title = re.sub(r"^Stories by ", "", title)
    return re.sub(r"\s*(on Medium| - Medium)$", "", title).strip()


def search_medium(query: str, limit: int = 8) -> list[dict]:
    """Medium 검색 — 쿼리를 핸들(@저자/퍼블리케이션)로 먼저 시도, 그다음 태그 피드로 저자 발굴."""
    q = query.strip()
    is_handle = q.startswith("@")
    # 태그·퍼블리케이션 URL은 소문자 하이픈 슬러그만 받는다
    direct = q if is_handle else re.sub(r"[^a-z0-9]+", "-", q.lower()).strip("-")

    results: list[dict] = []
    seen: set[str] = set()

    # 1) 쿼리 자체가 유효한 핸들이면 최상단에. 피드 링크는 커스텀 도메인일 수 있어 파싱하지 않는다
    try:
        parsed = feedparser.parse(f"https://medium.com/feed/{direct}")
        if parsed.entries:
            seen.add(direct.lower())
            results.append(_medium_row(
                direct, _feed_title(parsed.feed), parsed.entries[0].get("title", "")
            ))
    except Exception as e:
        logger.warning(f"Medium 핸들 조회 실패 ({direct}): {e}")

    if is_handle:
        return results

    # 2) 태그 피드의 글쓴이들 — 태그 피드는 medium.com/@user 형태로 링크된다
    try:
        entries = feedparser.parse(f"https://medium.com/feed/tag/{direct}").entries
    except Exception as e:
        logger.warning(f"Medium 태그 검색 실패 ({direct}): {e}")
        entries = []

    for entry in entries:
        handle = medium_handle(entry.get("link", ""))
        if not handle or handle.lower() in seen:
            continue
        seen.add(handle.lower())
        results.append(_medium_row(handle, entry.get("author", ""), entry.get("title", "")))
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


def search_platform(query: str, platform: str, limit: int = 8) -> list[dict]:
    if platform == "youtube":
        return search_youtube(query, limit)
    if platform == "medium":
        return search_medium(query, limit)
    if platform == "linkedin":
        return search_linkedin(query, limit)
    return []
