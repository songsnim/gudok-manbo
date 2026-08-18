"""피드 엔트리 본문 추출 점검(네트워크 없음). 실행: python scrapers/test_entry_body.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import rss  # noqa: E402

rss._fetch_article_body = lambda url: "HTTP로 긁은 " + "긴본문 " * 300  # 네트워크 차단

long_html = "<p>" + "본문 " * 400 + "</p>"

# content가 전문이면 그걸 쓴다 — HTTP 요청 안 함
body = rss.entry_body({"content": [{"value": long_html}], "link": "http://x/a"})
assert body.startswith("본문") and "HTTP로 긁은" not in body

# content 없으면 summary
assert rss.entry_body({"summary": long_html, "link": "http://x/a"}).startswith("본문")

# 티저뿐이면 원문 HTTP로 보강
assert rss.entry_body({"summary": "<p>맛보기</p>", "link": "http://x/a"}).startswith("HTTP로 긁은")

# HTTP도 실패하면 티저라도 반환, 아무것도 없으면 None
rss._fetch_article_body = lambda url: None
assert rss.entry_body({"summary": "<p>맛보기</p>", "link": "http://x/a"}) == "맛보기"
assert rss.entry_body({"link": "http://x/a"}) is None

# ── 원문 보존: 이미지·제목·링크가 Markdown으로 남아야 한다 ──
html = (
    "<script>evil()</script>"
    "<h2>소제목</h2>"
    "<p>글 <strong>강조</strong> <a href='/rel/link'>링크</a></p>"
    "<figure><img src='/img/photo.png' alt='사진'></figure>"
    "<pre><code>print(1)</code></pre>"
)
md = rss._html_to_markdown(html, "https://blog.example.com/posts/hello")
assert "## 소제목" in md
assert "**강조**" in md
# 상대 경로는 원문 주소 기준으로 절대화 — 안 하면 앱에서 못 불러온다
assert "![사진](https://blog.example.com/img/photo.png)" in md
assert "(https://blog.example.com/rel/link)" in md
assert "evil()" not in md
assert "print(1)" in md

# 상한 적용
assert len(rss._html_to_markdown("<p>" + "가" * 200000 + "</p>")) == rss._MAX_BODY

print("ok")
