import json
import re
import feedparser
import httpx
from youtube_transcript_api import (
    YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, IpBlocked,
)

from llm.openrouter_client import transcribe_to_article, generate_title
from scrapers.rss import entry_date, recent_entries
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


def _get_transcript(video_id: str) -> str | None:
    transcript, reason = transcript_or_reason(video_id)
    if reason:
        import logging
        logging.getLogger(__name__).warning(f"자막 조회 실패 ({video_id}): {reason}")
    return transcript


def transcript_or_reason(video_id: str) -> tuple[str | None, str]:
    """자막과 실패 이유. 짧은 시간에 많이 담으면 YouTube가 IP를 막으므로 구분해서 알린다.

    인스턴스를 재사용하면 내부 requests.Session이 스레드 간 공유되므로 매번 새로 만든다.
    """
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=["ko", "en"])
        return " ".join(s.text for s in transcript), ""
    except IpBlocked:
        return None, "YouTube가 이 IP를 일시 차단했습니다. 잠시 후 다시 담아주세요"
    except (NoTranscriptFound, TranscriptsDisabled):
        return None, "자막 없음"
    except Exception as e:
        return None, f"자막 조회 실패: {type(e).__name__}"


def _make_slug(video_id: str) -> str:
    return f"yt-{video_id}"


def _video_id(entry) -> str:
    return entry.get("yt_videoid") or re.search(r"v=([^&]+)", entry.link).group(1)


def is_short(video_id: str) -> bool:
    """쇼츠 여부. /shorts/<id>는 쇼츠면 200, 일반 영상이면 /watch로 리다이렉트한다."""
    try:
        r = httpx.head(f"https://www.youtube.com/shorts/{video_id}",
                       headers=_HEADERS, timeout=10, follow_redirects=False)
        return r.status_code == 200
    except Exception:
        return False  # 판별 실패는 일반 영상으로 취급


def shorts_last(entries):
    """일반 영상 먼저, 쇼츠는 맨 뒤로. 담을 게 없을 때의 최후 수단으로만 쇼츠가 쓰인다.

    제너레이터라서 소비자가 limit을 채우고 멈추면 나머지는 쇼츠 판별 요청도 하지 않는다.
    """
    deferred = []
    for entry in entries:
        if is_short(_video_id(entry)):
            deferred.append(entry)
        else:
            yield entry
    yield from deferred


def scrape_channel(channel_id: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """채널 RSS에서 최신 영상을 가져와 요약 후 Vault에 저장. 저장된 slug 목록 반환."""
    feed = _fetch_feed(channel_id)
    saved = []

    import logging
    log = logging.getLogger(__name__)
    log.info(f"피드 엔트리 수: {len(feed.entries)}")

    # limit은 쇼츠 후순위 정렬 뒤에 적용해야 한다. 먼저 자르면 앞쪽 쇼츠 때문에 일반 영상을 놓친다
    for entry in shorts_last(recent_entries(feed.entries, len(feed.entries))):
        if len(saved) >= limit:
            break
        video_id = _video_id(entry)
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
