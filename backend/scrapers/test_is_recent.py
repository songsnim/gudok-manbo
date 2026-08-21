"""최근 1개월 필터 점검. 실행: python scrapers/test_is_recent.py"""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.rss import is_recent, recent_entries  # noqa: E402


def days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


assert is_recent(days_ago(0))
assert is_recent(days_ago(29))
assert is_recent(days_ago(30))
assert not is_recent(days_ago(31))
assert not is_recent(days_ago(400))

# 타임스탬프가 붙어도 앞 10자만 본다
assert is_recent(days_ago(1) + "T09:00:00+00:00")

# 날짜를 못 읽으면 통과 (LinkedIn 등 게시일 없는 소스)
assert is_recent("")
assert is_recent("14시간 전")
assert is_recent("Tue, 18 Aug 2026 10:00:00 +0000")  # RFC822 원문
assert is_recent("2026-13-45")  # 숫자 모양이지만 존재하지 않는 날짜 — 예외 대신 통과

# UTC 피드 날짜가 서버 로컬보다 하루 앞설 수 있다 — 미래 날짜를 버리면 최신글을 놓친다
assert is_recent((date.today() + timedelta(days=1)).isoformat())

# 오래된 글이 섞여 있으면 걸러내고, limit은 필터 뒤에 적용
entries = [
    {"published": days_ago(200)},
    {"published": days_ago(2)},
    {"published": days_ago(3)},
    {"published": days_ago(4)},
]
picked = recent_entries(entries, limit=2)
assert [e["published"] for e in picked] == [days_ago(2), days_ago(3)], picked

print("ok")
