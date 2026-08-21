"""쇼츠 후순위 정렬 점검. 실행: python scrapers/test_shorts_last.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import youtube  # noqa: E402

SHORTS = {"s1", "s2"}
calls = []


def fake_is_short(video_id: str) -> bool:
    calls.append(video_id)
    return video_id in SHORTS


youtube.is_short = fake_is_short

entries = [{"yt_videoid": v} for v in ("s1", "a", "s2", "b")]
assert [e["yt_videoid"] for e in youtube.shorts_last(entries)] == ["a", "b", "s1", "s2"]

# limit만큼만 소비하면 뒤쪽은 판별 요청도 하지 않는다
calls.clear()
picked = []
for entry in youtube.shorts_last(entries):
    picked.append(entry["yt_videoid"])
    if len(picked) >= 1:
        break
assert picked == ["a"], picked
assert calls == ["s1", "a"], calls

print("ok")
