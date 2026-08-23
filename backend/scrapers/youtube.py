import json
import re
from datetime import date, timedelta

import feedparser
import httpx
from youtube_transcript_api import (
    YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled, IpBlocked,
)

from llm.openrouter_client import transcribe_to_article, generate_title
from scrapers import yt_cache
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

# 오차 없이 날짜로 환산되는 단위만. "3주 전"은 7~13일을 다 덮으므로 여기 없다 —
# 그런 표기는 watch 페이지에 물어본다.
_EXACT_UNIT_DAYS = {
    "초": 0, "분": 0, "시간": 0, "일": 1,
    "second": 0, "minute": 0, "hour": 0, "day": 1,
}
_RELATIVE_RE = re.compile(
    r"(\d+)\s*(초|분|시간|일|주|개월|년|seconds?|minutes?|hours?|days?|weeks?|months?|years?)"
)


def published_from_relative(text: str) -> str:
    """'3일 전' / '14시간 전' 같은 상대 표기를 YYYY-MM-DD로. 환산 못 하면 빈 문자열.

    미리보기·검색 목록이 이미 들고 있는 값이라, 이걸로 되는 경우 watch 페이지 요청이
    통째로 빠진다. 주·개월·년 표기는 오차가 커서 환산하지 않는다.
    """
    m = _RELATIVE_RE.search(text or "")
    if not m:
        return ""
    days = _EXACT_UNIT_DAYS.get(m.group(2).rstrip("s"))
    if days is None:
        return ""
    return str(date.today() - timedelta(days=int(m.group(1)) * days))


def video_published(video_id: str) -> str:
    """영상 게시일(YYYY-MM-DD). 실패 시 빈 문자열.

    채널 RSS는 최신 15개만 담으므로, 오래된 영상은 watch 페이지에서 직접 읽는다.
    상대 표기로 환산되는 경우엔 부르지 않는다 (published_from_relative 참고).
    """
    try:
        r = httpx.get(f"https://www.youtube.com/watch?v={video_id}",
                      headers=_HEADERS, timeout=10, follow_redirects=True)
        m = _PUBLISHED_RE.search(r.text)
        return (m.group(1) or m.group(2))[:10] if m else ""
    except Exception:
        return ""


IP_BLOCKED = "YouTube가 이 IP를 일시 차단했습니다. 잠시 후 다시 담아주세요"


class IpBlockedError(RuntimeError):
    """자막 요청이 IP 단위로 막힘 — 같은 실행 안의 다음 영상도 전부 막힌다."""


def transcript_or_reason(video_id: str) -> tuple[str | None, str]:
    """자막과 실패 이유. 짧은 시간에 많이 담으면 YouTube가 IP를 막으므로 구분해서 알린다.

    IP 차단은 영상별 사정이 아니라 실행 전체의 사정이라, 호출자가 구분할 수 있게
    이유를 IP_BLOCKED 상수 그대로 돌려준다 (문자열 비교 대신 `is` 로 판정).

    인스턴스를 재사용하면 내부 requests.Session이 스레드 간 공유되므로 매번 새로 만든다.
    """
    # 자막 없는 영상은 Vault에 아무것도 남기지 않으므로, 캐시가 없으면 매 실행마다
    # 같은 영상에 같은 요청을 다시 보낸다
    if yt_cache.has_no_transcript(video_id):
        return None, "자막 없음"
    try:
        transcript = YouTubeTranscriptApi().fetch(video_id, languages=["ko", "en"])
        return " ".join(s.text for s in transcript), ""
    except IpBlocked:
        return None, IP_BLOCKED
    except (NoTranscriptFound, TranscriptsDisabled):
        # 영상의 성질이라 기억해도 된다. 차단·일시 오류는 아래로 빠져 기억되지 않는다
        yt_cache.remember_no_transcript(video_id)
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


def channel_shorts(channel_id: str) -> set[str] | None:
    """채널 쇼츠 탭의 영상 ID 집합. 실패하면 None.

    영상 하나하나 /shorts/<id>를 두드리는 대신 채널당 1요청으로 끝낸다.

    ponytail: 첫 페이지(약 50개)만 읽는다. RSS는 최신 15개만 주므로 그 안의 쇼츠는
    사실상 다 덮인다. 쇼츠를 50개 넘게 몰아 올린 채널의 오래된 쇼츠는 일반 영상으로
    분류될 수 있다 — 그때는 continuation을 따라가면 된다.
    """
    try:
        r = httpx.get(f"https://www.youtube.com/channel/{channel_id}/shorts",
                      headers=_HEADERS, timeout=15, follow_redirects=True)
        r.raise_for_status()
        m = re.search(r'var ytInitialData\s*=\s*({.+?});\s*</script>', r.text, re.DOTALL)
        if not m:
            return None
        data = json.loads(m.group(1))
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"쇼츠 탭 조회 실패 ({channel_id}): {e}")
        return None

    ids = set()
    for item in _grid_items(data):
        lv = item.get("richItemRenderer", {}).get("content", {}).get("shortsLockupViewModel")
        if not lv:
            continue
        video_id = (lv.get("onTap", {}).get("innertubeCommand", {})
                    .get("reelWatchEndpoint", {}).get("videoId")
                    or lv.get("entityId", "").replace("shorts-shelf-item-", ""))
        if video_id:
            ids.add(video_id)
    return ids


def shorts_last(entries, channel_id: str | None = None):
    """일반 영상 먼저, 쇼츠는 맨 뒤로. 담을 게 없을 때의 최후 수단으로만 쇼츠가 쓰인다.

    판별은 캐시 → 채널 쇼츠 탭(1요청) → 영상별 HEAD 순으로 값이 싼 것부터 쓴다.
    """
    entries = list(entries)
    ids = [_video_id(e) for e in entries]

    verdicts = {v: yt_cache.known_short(v) for v in ids}
    unknown = [v for v in ids if verdicts[v] is None]

    # 모르는 게 하나라도 있으면 채널 탭 한 번으로 전부 해결한다
    if unknown and channel_id:
        shorts = channel_shorts(channel_id)
        if shorts is not None:
            for v in unknown:
                verdicts[v] = v in shorts
            yt_cache.remember_shorts({v: verdicts[v] for v in unknown})
            unknown = []

    # 채널 ID가 없거나 탭 조회가 실패한 경우만 영상별로 묻는다
    if unknown:
        fallback = {v: is_short(v) for v in unknown}
        verdicts.update(fallback)
        yt_cache.remember_shorts(fallback)

    deferred = []
    for entry, video_id in zip(entries, ids):
        if verdicts.get(video_id):
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
    for entry in shorts_last(recent_entries(feed.entries, len(feed.entries)), channel_id):
        if len(saved) >= limit:
            break
        video_id = _video_id(entry)
        slug = _make_slug(video_id)
        log.info(f"처리 중: {video_id} / {entry.get('title', '')[:40]}")

        from vault.reader import get_item
        if get_item(slug):
            log.info(f"이미 저장됨: {slug}")
            continue

        transcript, reason = transcript_or_reason(video_id)
        if not transcript:
            # 차단은 이 영상만의 사정이 아니다. 계속 돌면 막힌 IP로 요청만 더 쌓는다
            if reason is IP_BLOCKED:
                raise IpBlockedError(reason)
            log.warning(f"건너뜀 ({video_id}): {reason}")
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
