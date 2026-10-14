"""YouTube 홈 피드 추천 중 AI/ML/Data/Dev/Math/Agent 영상만 모아 둔 목록 — 가상 구독 "추천 영상".

수집 스케줄에 맞춰 목록만 갱신한다. Feed(Vault)에는 아무것도 쓰지 않는다 — 텍스트화는
사용자가 미리보기에서 담기를 눌러야 일어난다(preview.add_item).

홈 피드는 공개 API가 없어서 PC 브라우저에서 내보낸 로그인 쿠키(data/youtube_cookies.txt)로
innertube를 부른다. 쿠키가 죽으면 목록은 그대로 두고 앱에 배너로 알린다.
"""
import hashlib
import http.cookiejar
import json
import logging
import re
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

from scrapers.youtube import _HEADERS, _INNERTUBE_CTX, _make_slug, published_from_relative
from vault.reader import get_item

logger = logging.getLogger(__name__)

RECOMMENDED_ID = "recommended"
RECOMMENDED_NAME = "추천 영상"
KEEP_DAYS = 7
PAGES = 10  # 한 페이지 약 20개. 홈은 주제가 섞여 있어 많이 받아야 하루 2번 수집에 10여 개가 걸린다
CHUNK = 50  # 판정 한 번에 보낼 영상 수 — 너무 길면 무료 모델이 번호를 빠뜨린다

_DATA = Path(__file__).parent.parent / "data"
_COOKIES = _DATA / "youtube_cookies.txt"
_STORE = _DATA / "recommended.json"
COOKIE_DEAD = "YouTube 쿠키가 만료됐습니다. PC 브라우저에서 youtube.com 쿠키를 다시 내보내 backend/data/youtube_cookies.txt에 넣어 주세요."

# 라이브 중·예정·지난 라이브. 지난 라이브는 길고 잡담이 많아 요약 가치가 낮다
_LIVE_RE = re.compile(r"watching|Streamed|Scheduled for|Premieres|LIVE", re.I)


class CookieDead(RuntimeError):
    pass


# ── 저장소 ────────────────────────────────────────────────────────────────────

def _load() -> dict:
    try:
        s = json.loads(_STORE.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        s = {}
    return {"items": [], "dismissed": {}, "seen": 0, "error": "", **s}


def _save(s: dict) -> None:
    # ponytail: collect.py(별도 프로세스)와 서버가 같은 파일을 쓴다. 쓰기는 하루 몇 번이라 잠금 없음
    _STORE.write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")


def is_recommended(video_id: str) -> bool:
    return any(i["video_id"] == video_id for i in _load()["items"])


def dismiss(video_id: str) -> None:
    s = _load()
    s["dismissed"][video_id] = str(date.today())
    s["items"] = [i for i in s["items"] if i["video_id"] != video_id]
    _save(s)


def _visible(s: dict) -> list[dict]:
    """담은 것(Vault에 있음)·치운 것은 빠진다. 최신 발견 순."""
    return [i for i in s["items"]
            if i["video_id"] not in s["dismissed"] and get_item(_make_slug(i["video_id"])) is None]


def new_count() -> int:
    s = _load()
    return sum(i["ts"] > s["seen"] for i in _visible(s))


def listing(mark_seen: bool = True) -> dict:
    """미리보기 응답 모양 그대로. 열어 보면 새 개수가 0이 된다."""
    s = _load()
    items = [{
        "title": i["title"],
        "source_url": f"https://www.youtube.com/watch?v={i['video_id']}",
        "date": i["date"],
        "platform": "youtube",
        "author": i["author"],
        "type": "video",
        "video_id": i["video_id"],
        "thumbnail": f"https://i.ytimg.com/vi/{i['video_id']}/hqdefault.jpg",
        "in_feed": False,
    } for i in _visible(s)]
    if mark_seen:
        s["seen"] = time.time()
        _save(s)
    return {"items": items, "next_cursor": None, "notice": s["error"] or None}


# ── 홈 피드 ───────────────────────────────────────────────────────────────────

def _auth_headers() -> dict:
    if not _COOKIES.exists():
        raise CookieDead("쿠키 파일 없음")
    jar = http.cookiejar.MozillaCookieJar(str(_COOKIES))
    jar.load(ignore_discard=True, ignore_expires=True)
    c = {k.name: k.value for k in jar if "youtube.com" in k.domain}
    sapisid = c.get("SAPISID") or c.get("__Secure-3PAPISID")
    if not sapisid:
        raise CookieDead("SAPISID 없음")
    ts = str(int(time.time()))
    digest = hashlib.sha1(f"{ts} {sapisid} https://www.youtube.com".encode()).hexdigest()
    return {
        **_HEADERS,
        "Authorization": f"SAPISIDHASH {ts}_{digest}",
        "X-Origin": "https://www.youtube.com",
        "Origin": "https://www.youtube.com",
        "X-Goog-AuthUser": "0",
        "Cookie": "; ".join(f"{k}={v}" for k, v in c.items()),
    }


def _parse(grid: list[dict]) -> tuple[list[dict], str | None]:
    """홈 그리드 → 일반 영상과 다음 커서. 쇼츠는 richSectionRenderer 선반에만 오므로 선반째 건너뛴다."""
    videos, cursor = [], None
    for it in grid:
        if "continuationItemRenderer" in it:
            cursor = (it["continuationItemRenderer"].get("continuationEndpoint", {})
                      .get("continuationCommand", {}).get("token"))
            continue
        lv = it.get("richItemRenderer", {}).get("content", {}).get("lockupViewModel")
        if not lv or lv.get("contentType") != "LOCKUP_CONTENT_TYPE_VIDEO":
            continue  # 선반(쇼츠·뉴스), 플레이리스트·믹스, 광고
        meta = lv.get("metadata", {}).get("lockupMetadataViewModel", {})
        rows = meta.get("metadata", {}).get("contentMetadataViewModel", {}).get("metadataRows", [])
        parts = [[p.get("text", {}).get("content", "") for p in r.get("metadataParts", [])] for r in rows]
        badges = json.dumps(lv.get("contentImage", {}))
        if any(_LIVE_RE.search(t) for row in parts[1:] for t in row) or "_LIVE" in badges:
            continue
        raw_date = parts[1][-1] if len(parts) > 1 and parts[1] else ""
        videos.append({
            "video_id": lv["contentId"],
            "title": meta.get("title", {}).get("content", ""),
            "author": parts[0][0] if parts and parts[0] else "",
            # 상대 표기("4 hours ago")는 며칠 지나면 틀린다 — 환산되면 날짜로 박아 둔다
            "date": published_from_relative(raw_date) or raw_date,
        })
    return videos, cursor


def fetch_home(pages: int = PAGES) -> list[dict]:
    headers = _auth_headers()
    body = {"context": _INNERTUBE_CTX, "browseId": "FEwhat_to_watch"}
    videos = []
    for _ in range(pages):
        r = httpx.post("https://www.youtube.com/youtubei/v1/browse", params={"prettyPrint": "false"},
                       json=body, headers=headers, timeout=20)
        if r.status_code in (401, 403):
            raise CookieDead(f"HTTP {r.status_code}")
        r.raise_for_status()
        data = r.json()
        if data.get("responseContext", {}).get("mainAppWebResponseContext", {}).get("loggedOut", True):
            raise CookieDead("loggedOut")
        grid = next((a["appendContinuationItemsAction"]["continuationItems"]
                     for a in data.get("onResponseReceivedActions", [])
                     if "appendContinuationItemsAction" in a), None)
        if grid is None:
            tabs = data.get("contents", {}).get("twoColumnBrowseResultsRenderer", {}).get("tabs", [])
            grid = (tabs[0].get("tabRenderer", {}).get("content", {})
                    .get("richGridRenderer", {}).get("contents", [])) if tabs else []
        page, cursor = _parse(grid)
        videos += page
        if not cursor:
            break
        body = {"context": _INNERTUBE_CTX, "continuation": cursor}
    return list({v["video_id"]: v for v in videos}.values())


# ── 주제 판정 ─────────────────────────────────────────────────────────────────

_TOPIC_PROMPT = """\
아래는 YouTube 영상 목록이다 (번호. 제목 — 채널).
AI, 머신러닝, 데이터(데이터 분석·엔지니어링), 소프트웨어 개발·프로그래밍, 수학, AI 에이전트 중
하나라도 영상의 주된 주제인 것만 골라라. 게임·요리·연예·스포츠·일상·재테크·자기계발 등은 제외.
IT 기기 리뷰나 테크 뉴스는 위 주제를 실제로 다룰 때만 포함.

{videos}

JSON으로만 답하라: {{"keep": [번호, ...]}}"""


def pick_topical(videos: list[dict]) -> list[dict]:
    """CHUNK개씩 나눠 판정. 한 묶음이 실패하면 그 묶음만 건너뛴다 — 다음 회차에 다시 묻는다."""
    picked = []
    for i in range(0, len(videos), CHUNK):
        try:
            picked += _pick_chunk(videos[i:i + CHUNK])
        except Exception as e:
            logger.warning(f"추천 영상: 주제 판정 실패, {len(videos[i:i + CHUNK])}개 건너뜀 ({e})")
    return picked


def _pick_chunk(videos: list[dict]) -> list[dict]:
    from llm.openrouter_client import _chat
    listing_ = "\n".join(f"{n}. {v['title']} — {v['author']}" for n, v in enumerate(videos, 1))
    content = _chat(_TOPIC_PROMPT.format(videos=listing_), temperature=0,
                    response_format={"type": "json_object"})
    match = re.search(r"\{.*\}", content, re.S)
    keep = {int(n) for n in json.loads(match.group(0) if match else content).get("keep", [])
            if str(n).isdigit()}
    return [v for n, v in enumerate(videos, 1) if n in keep]


# ── 갱신 (수집 스케줄에서 호출) ───────────────────────────────────────────────

def refresh() -> dict:
    s = _load()
    cutoff = str(date.today() - timedelta(days=KEEP_DAYS))
    s["items"] = [i for i in s["items"] if i["found"] >= cutoff]
    month = str(date.today() - timedelta(days=30))
    s["dismissed"] = {v: d for v, d in s["dismissed"].items() if d >= month}

    try:
        home = fetch_home()
        s["error"] = ""
    except CookieDead as e:
        logger.warning(f"추천 영상: 쿠키 만료 ({e})")
        s["error"] = COOKIE_DEAD
        _save(s)
        return {"added": 0, "error": s["error"]}

    known = {i["video_id"] for i in s["items"]} | set(s["dismissed"])
    fresh = [v for v in home if v["video_id"] not in known and get_item(_make_slug(v["video_id"])) is None]
    picked = pick_topical(fresh)
    now = time.time()
    s["items"] = [{**v, "found": str(date.today()), "ts": now} for v in picked] + s["items"]
    _save(s)
    logger.info(f"추천 영상: 홈 {len(home)}개 중 새것 {len(fresh)}개 판정, {len(picked)}개 추가")
    return {"added": len(picked), "error": ""}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(refresh())
