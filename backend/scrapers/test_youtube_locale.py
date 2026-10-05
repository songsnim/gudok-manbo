"""YouTube 목록 요청은 영어로 간다 — 한국어로 요청하면 제목이 기계 번역되고 가끔 헛나온다.

실행: python -m scrapers.test_youtube_locale (backend/ 에서)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import search, youtube  # noqa: E402

assert youtube._INNERTUBE_CTX["client"]["hl"] == "en", youtube._INNERTUBE_CTX
assert youtube._INNERTUBE_CTX["client"]["gl"] == "US", youtube._INNERTUBE_CTX
assert youtube._HEADERS["Accept-Language"].startswith("en"), youtube._HEADERS
assert search._YT_HEADERS["Accept-Language"].startswith("en"), search._YT_HEADERS

pr = youtube.published_from_relative
today = str(__import__("datetime").date.today())
# 영어 목록의 축약형("14h ago")도 환산된다 — 못 읽으면 영상 페이지를 매번 다시 긁는다
assert pr("14h ago") == today, pr("14h ago")
assert pr("3 days ago") == str(__import__("datetime").date.today() - __import__("datetime").timedelta(days=3))
assert pr("1d ago") == str(__import__("datetime").date.today() - __import__("datetime").timedelta(days=1))
assert pr("14시간 전") == today
# 오차가 큰 단위는 환산하지 않는다. mo(개월)가 m(분)으로 읽히면 안 된다
assert pr("1mo ago") == ""
assert pr("2 weeks ago") == ""
assert pr("3주 전") == ""

print("ok")
