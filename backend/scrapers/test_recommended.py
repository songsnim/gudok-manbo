"""추천 영상 점검. 실행: python scrapers/test_recommended.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scrapers import recommended as r  # noqa: E402


def lockup(vid, rows, kind="LOCKUP_CONTENT_TYPE_VIDEO", image=None):
    return {"richItemRenderer": {"content": {"lockupViewModel": {
        "contentId": vid, "contentType": kind, "contentImage": image or {},
        "metadata": {"lockupMetadataViewModel": {
            "title": {"content": f"title-{vid}"},
            "metadata": {"contentMetadataViewModel": {"metadataRows": [
                {"metadataParts": [{"text": {"content": t}} for t in row]} for row in rows]}},
        }},
    }}}}


grid = [
    lockup("v1", [["채널A"], ["1K views", "2 weeks ago"]]),
    {"richSectionRenderer": {"content": {"richShelfRenderer": {"contents": [lockup("short", [["S"]])]}}}},
    lockup("mix", [["X", "Playlist"]], kind="LOCKUP_CONTENT_TYPE_PLAYLIST"),
    lockup("live", [["L"], ["1.2K watching"]]),
    lockup("past", [["P"], ["380 views", "Streamed 3 days ago"]]),
    lockup("badge", [["B"], ["10 views"]], image={"badgeStyle": "THUMBNAIL_OVERLAY_BADGE_STYLE_LIVE"}),
    {"continuationItemRenderer": {"continuationEndpoint": {"continuationCommand": {"token": "T"}}}},
]

# 일반 영상만 남고 쇼츠 선반·믹스·라이브(진행·지난·배지)는 빠진다
videos, cursor = r._parse(grid)
assert [v["video_id"] for v in videos] == ["v1"], videos
assert videos[0]["author"] == "채널A" and videos[0]["date"] == "2 weeks ago"
assert cursor == "T"

# refresh: 판정 통과분만 쌓이고, 이미 있는 것·치운 것은 다시 판정하지 않는다
r._STORE = Path(tempfile.mkdtemp()) / "recommended.json"
r.get_item = lambda slug: None
home = [{"video_id": v, "title": v, "author": "c", "date": ""} for v in ("a", "b", "c")]
r.fetch_home = lambda: home
judged = []
r.pick_topical = lambda vs: judged.append([v["video_id"] for v in vs]) or [v for v in vs if v["video_id"] != "b"]
assert r.refresh()["added"] == 2
r.dismiss("a")
assert [i["video_id"] for i in r.listing()["items"]] == ["c"]
assert r.new_count() == 0  # 열어 봤으니 0
r.refresh()
assert judged[-1] == ["b"], judged  # a는 치움, c는 이미 있음 — b만 다시 묻는다

# 쿠키가 죽으면 목록은 남기고 배너만 띄운다
def dead():
    raise r.CookieDead("loggedOut")
r.fetch_home = dead
assert r.refresh()["error"] == r.COOKIE_DEAD
assert r.listing()["notice"] == r.COOKIE_DEAD and [i["video_id"] for i in r.listing()["items"]] == ["c"]

print("ok")
