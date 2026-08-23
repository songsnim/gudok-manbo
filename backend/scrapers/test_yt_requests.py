"""요청을 아끼는 두 경로: 자막 없음 캐시, 상대 날짜 환산.
실행: python scrapers/test_yt_requests.py"""
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import youtube, yt_cache  # noqa: E402
from scrapers.youtube import IP_BLOCKED  # noqa: E402

yt_cache._FILE = Path(tempfile.mkdtemp()) / "yt_cache.json"
yt_cache._state = None


# ── 1. "자막 없음"은 한 번만 묻는다 ──────────────────────────────────────────
fetches = []


class NoTranscriptApi:
    def fetch(self, video_id, languages):
        fetches.append(video_id)
        raise youtube.TranscriptsDisabled(video_id)


youtube.YouTubeTranscriptApi = NoTranscriptApi

assert youtube.transcript_or_reason("v1") == (None, "자막 없음")
assert fetches == ["v1"], fetches

# 두 번째부터는 요청 없이 같은 답
assert youtube.transcript_or_reason("v1") == (None, "자막 없음")
assert fetches == ["v1"], fetches

# 파일로 살아남는다 — 다음 실행(다른 프로세스)에서도 요청이 나가지 않는다
yt_cache._state = None
assert yt_cache.has_no_transcript("v1")


# ── 2. IP 차단은 캐시하지 않는다 ─────────────────────────────────────────────
blocked_fetches = []


class BlockedApi:
    def fetch(self, video_id, languages):
        blocked_fetches.append(video_id)
        raise youtube.IpBlocked(video_id)


youtube.YouTubeTranscriptApi = BlockedApi

assert youtube.transcript_or_reason("v2") == (None, IP_BLOCKED)
assert not yt_cache.has_no_transcript("v2")
# 차단이 풀리면 다시 시도되어야 한다
assert youtube.transcript_or_reason("v2") == (None, IP_BLOCKED)
assert blocked_fetches == ["v2", "v2"], blocked_fetches


# ── 3. 상대 날짜: 일 단위 이하만 환산, 나머지는 빈 문자열 ────────────────────
today = date.today()
assert youtube.published_from_relative("3일 전") == str(today - timedelta(days=3))
assert youtube.published_from_relative("14시간 전") == str(today)
assert youtube.published_from_relative("45초 전") == str(today)
assert youtube.published_from_relative("2 days ago") == str(today - timedelta(days=2))
assert youtube.published_from_relative("스트리밍 시간: 5일 전") == str(today - timedelta(days=5))

# 오차가 큰 단위는 환산하지 않는다 — 호출자가 watch 페이지로 확인한다
assert youtube.published_from_relative("3주 전") == ""
assert youtube.published_from_relative("1개월 전") == ""
assert youtube.published_from_relative("2년 전") == ""
assert youtube.published_from_relative("3 weeks ago") == ""
assert youtube.published_from_relative("") == ""
assert youtube.published_from_relative("어제") == ""

print("ok")
