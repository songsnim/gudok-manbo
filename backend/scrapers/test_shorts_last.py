"""쇼츠 거르기 점검. 실행: python scrapers/test_shorts_last.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import youtube, yt_cache  # noqa: E402

_TMP = Path(tempfile.mkdtemp())
_n = 0


def fresh_cache() -> None:
    """실제 캐시 파일을 건드리지 않고, 매번 빈 캐시에서 시작한다."""
    global _n
    _n += 1
    yt_cache._FILE = _TMP / f"cache-{_n}.json"
    yt_cache._state = None


fresh_cache()

SHORTS = {"s1", "s2"}
head_calls = []
tab_calls = []


def fake_is_short(video_id: str) -> bool:
    head_calls.append(video_id)
    return video_id in SHORTS


def fake_channel_shorts(channel_id: str):
    tab_calls.append(channel_id)
    return set(SHORTS)


youtube.is_short = fake_is_short
youtube.channel_shorts = fake_channel_shorts

entries = [{"yt_videoid": v} for v in ("s1", "a", "s2", "b")]


# ── 채널 ID가 없으면 영상별로 묻는다 ─────────────────────────────────────────
assert [e["yt_videoid"] for e in youtube.shorts_last(entries)] == ["a", "b"]
assert head_calls == ["s1", "a", "s2", "b"], head_calls
assert tab_calls == [], tab_calls

# 판별 결과는 기억된다 — 두 번째 호출은 요청이 0
head_calls.clear()
assert [e["yt_videoid"] for e in youtube.shorts_last(entries)] == ["a", "b"]
assert head_calls == [], head_calls


# ── 채널 ID가 있으면 탭 1요청으로 전부 해결한다 ──────────────────────────────
fresh_cache()
head_calls.clear()
order = [e["yt_videoid"] for e in youtube.shorts_last(entries, "UC-test")]
assert order == ["a", "b"], order
assert tab_calls == ["UC-test"], tab_calls
assert head_calls == [], head_calls  # 영상별 HEAD는 한 번도 나가지 않는다

# 캐시가 다 채워졌으면 탭도 부르지 않는다
tab_calls.clear()
assert [e["yt_videoid"] for e in youtube.shorts_last(entries, "UC-test")] == ["a", "b"]
assert tab_calls == [], tab_calls


# ── 탭 조회가 실패하면 영상별 HEAD로 내려간다 ────────────────────────────────
fresh_cache()
head_calls.clear()
tab_calls.clear()
youtube.channel_shorts = lambda channel_id: None
assert [e["yt_videoid"] for e in youtube.shorts_last(entries, "UC-test")] == ["a", "b"]
assert head_calls == ["s1", "a", "s2", "b"], head_calls

# ── 일반 영상이 하나도 없는 채널만 쇼츠를 받는다 ─────────────────────────────
only_shorts = [{"yt_videoid": v} for v in ("s1", "s2")]
assert [e["yt_videoid"] for e in youtube.shorts_last(only_shorts, "UC-test")] == ["s1", "s2"]

print("ok")
