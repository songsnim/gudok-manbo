"""IP 차단은 영상 하나를 건너뛰는 게 아니라 실행을 멈춘다.
실행: python scrapers/test_ip_blocked.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import youtube  # noqa: E402
from scrapers.youtube import IP_BLOCKED, IpBlockedError  # noqa: E402


# ── 1. 이유는 문자열이 아니라 상수 동일성으로 전달된다 ────────────────────────
class FakeApi:
    def fetch(self, video_id, languages):
        raise youtube.IpBlocked(video_id)


youtube.YouTubeTranscriptApi = FakeApi
transcript, reason = youtube.transcript_or_reason("x")
assert transcript is None, transcript
assert reason is IP_BLOCKED, reason


# ── 2. 한 채널이 막히면 남은 YouTube 채널은 열지 않는다 ──────────────────────
from agent import curator  # noqa: E402

opened = []


def fake_scrape_channel(channel_id, author, subscription, limit):
    opened.append(author)
    raise IpBlockedError(IP_BLOCKED)


def fake_scrape_feed(feed_url, platform, author, subscription, limit):
    opened.append(author)
    return ["rss-1"]


curator.scrape_channel = fake_scrape_channel
curator.scrape_feed = fake_scrape_feed
curator.load_subscriptions = lambda: [
    {"platform": "youtube", "author": "yt-1", "channel_id": "c1", "priority": 1},
    {"platform": "youtube", "author": "yt-2", "channel_id": "c2", "priority": 1},
    {"platform": "rss", "author": "rss-1", "feed_url": "https://e.com/f", "priority": 2},
]

result = curator.run_scheduled_collection(respect_quota=False)

# 두 번째 YouTube 채널은 열리지 않는다 — 막힌 IP로 요청을 더 쏘지 않는다
assert opened == ["yt-1", "rss-1"], opened
# 다른 플랫폼은 영향 없이 계속 돈다
assert result["collected"] == 1, result
# Vault에는 흔적이 없으므로 둘 다 사유와 함께 실행 로그에 남아야 한다
assert [f["author"] for f in result["failures"]] == ["yt-1", "yt-2"], result["failures"]
assert all(f["reason"] == IP_BLOCKED for f in result["failures"]), result["failures"]

print("ok")
