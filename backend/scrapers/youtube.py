import re
import feedparser
import httpx
from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled

from llm.openrouter_client import transcribe_to_article, generate_title
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
        )
        saved.append(slug)

    return saved
