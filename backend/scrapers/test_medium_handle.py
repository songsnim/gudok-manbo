"""Medium 글 URL → 구독 handle 추출 점검. 실행: python scrapers/test_medium_handle.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers.search import medium_handle  # noqa: E402

# 개인 프로필 — @ 포함해야 medium.com/feed/@user로 이어진다
assert medium_handle("https://medium.com/@dabit3/some-title-abc123") == "@dabit3"
assert medium_handle("https://medium.com/@dabit3/t-abc?source=rss----x") == "@dabit3"

# 퍼블리케이션 — 경로형과 서브도메인형 둘 다
assert medium_handle("https://medium.com/netflix-techblog/t-abc123") == "netflix-techblog"
assert medium_handle("https://netflix-techblog.medium.com/t-abc123") == "netflix-techblog"

# 커스텀 도메인은 medium.com/feed/로 못 받으므로 제외
assert medium_handle("https://towardsdatascience.com/t-abc123") is None
assert medium_handle("") is None

print("ok")
