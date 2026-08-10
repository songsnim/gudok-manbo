import json
import re
import feedparser
import httpx
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

from llm.openrouter_client import transcribe_to_article, generate_title
from scrapers.rss import entry_date
from vault.writer import write_item


_RSS_URL = "https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _fetch_feed(channel_id: str):
    import logging
    url = _RSS_URL.format(channel_id=channel_id)
    r = httpx.get(url, headers=_HEADERS, timeout=10, follow_redirects=True)
    r.raise_for_status()
    logging.getLogger(__name__).info(f"RSS 응답 길이: {len(r.content)} bytes, 앞부분: {r.content[:80]}")
    return feedparser.parse(r.content)


# ── 채널 영상 목록 (RSS는 15개 고정 → 페이지네이션은 innertube continuation 사용) ──

_INNERTUBE_KEY = "AIzaSyAO_FJ2SlqU8Q4STEHLGCilw_Y9_11qcW8"  # YouTube 웹 공개 키
_INNERTUBE_CTX = {"client": {"clientName": "WEB", "clientVersion": "2.20240101.00.00",
                             "hl": "ko", "gl": "KR"}}


def _grid_items(data: dict) -> list[dict]:
    """첫 페이지(richGridRenderer) / 다음 페이지(appendContinuationItemsAction) 공통 추출."""
    for action in data.get("onResponseReceivedActions", []):
        items = action.get("appendContinuationItemsAction", {}).get("continuationItems")
        if items:
            return items
    tabs = (data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {})
            .get("tabs", []))
    for tab in tabs:
        grid = tab.get("tabRenderer", {}).get("content", {}).get("richGridRenderer")
        if grid:
            return grid.get("contents", [])
    return []


def fetch_videos(channel_id: str, cursor: str | None = None) -> tuple[list[dict], str | None]:
    """채널 영상 한 페이지와 다음 커서를 반환. cursor=None이면 첫 페이지."""
    if cursor:
        r = httpx.post(
            "https://www.youtube.com/youtubei/v1/browse",
            params={"key": _INNERTUBE_KEY},
            json={"context": _INNERTUBE_CTX, "continuation": cursor},
            headers=_HEADERS, timeout=15,
        )
        r.raise_for_status()
        data = r.json()
    else:
        r = httpx.get(f"https://www.youtube.com/channel/{channel_id}/videos",
                      headers=_HEADERS, timeout=15, follow_redirects=True)
        r.raise_for_status()
        m = re.search(r'var ytInitialData\s*=\s*({.+?});\s*</script>', r.text, re.DOTALL)
        if not m:
            return [], None
        data = json.loads(m.group(1))

    videos, next_cursor = [], None
    for item in _grid_items(data):
        cont = item.get("continuationItemRenderer")
        if cont:
            next_cursor = (cont.get("continuationEndpoint", {})
                           .get("continuationCommand", {}).get("token"))
            continue
        lv = item.get("richItemRenderer", {}).get("content", {}).get("lockupViewModel")
        if not lv or not lv.get("contentId"):
            continue
        meta = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
        rows = (meta.get("metadata", {}).get("contentMetadataViewModel", {})
                .get("metadataRows", []))
        parts = rows[0].get("metadataParts", []) if rows else []
        videos.append({
            "video_id": lv["contentId"],
            "title": meta.get("title", {}).get("content", ""),
            # 마지막 파트가 업로드 시점("14시간 전"), 앞은 조회수
            "date": parts[-1].get("text", {}).get("content", "") if parts else "",
        })
    return videos, next_cursor


_PUBLISHED_RE = re.compile(r'itemprop="datePublished" content="([^"]+)"|"publishDate":"([^"]+)"')


def video_published(video_id: str) -> str:
    """영상 게시일(YYYY-MM-DD). 실패 시 빈 문자열.

    채널 RSS는 최신 15개만 담으므로, 오래된 영상은 watch 페이지에서 직접 읽는다.
    """
    try:
        r = httpx.get(f"https://www.youtube.com/watch?v={video_id}",
                      headers=_HEADERS, timeout=10, follow_redirects=True)
        m = _PUBLISHED_RE.search(r.text)
        return (m.group(1) or m.group(2))[:10] if m else ""
    except Exception:
        return ""


_yt_api = YouTubeTranscriptApi()

def _get_transcript(video_id: str) -> str | None:
    try:
        transcript = _yt_api.fetch(video_id, languages=["ko", "en"])
        return " ".join(s.text for s in transcript)
    except Exception:
        return None


def _make_slug(video_id: str) -> str:
    return f"yt-{video_id}"


def scrape_channel(channel_id: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """채널 RSS에서 최신 영상을 가져와 요약 후 Vault에 저장. 저장된 slug 목록 반환."""
    feed = _fetch_feed(channel_id)
    saved = []

    import logging
    log = logging.getLogger(__name__)
    log.info(f"피드 엔트리 수: {len(feed.entries)}")

    for entry in feed.entries[:limit]:
        video_id = entry.get("yt_videoid") or re.search(r"v=([^&]+)", entry.link).group(1)
        slug = _make_slug(video_id)
        log.info(f"처리 중: {video_id} / {entry.get('title', '')[:40]}")

        from vault.reader import get_item
        if get_item(slug):
            log.info(f"이미 저장됨: {slug}")
            continue

        transcript = _get_transcript(video_id)
        if not transcript:
            log.warning(f"자막 없음, 건너뜀: {video_id}")
            continue

        title = entry.get("title") or generate_title(transcript)
        body = transcribe_to_article(transcript)

        write_item(
            slug=slug,
            title=title,
            platform="youtube",
            source_url=entry.link,
            author=author,
            body=body,
            subscription=subscription,
            published=entry_date(entry),
        )
        saved.append(slug)

    return saved
