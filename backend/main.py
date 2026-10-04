import logging
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from vault.reader import get_all_items, get_today_items, get_item, get_collection_items
from agent.curator import load_subscriptions, add_subscription, remove_subscription, enrich_avatars

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# 수집 스케줄은 Windows 작업 스케줄러 + collect.py 가 담당한다 (슬립 중에도 PC를 깨워 실행).
# 서버는 Vault 서빙만 하므로 인프로세스 스케줄러를 두지 않는다.
app = FastAPI(title="Contents Curator")


# ── Feed ──────────────────────────────────────────────────────────────────────

@app.get("/feed/today")
def feed_today():
    return get_today_items()


@app.get("/feed/items")
def feed_items(date: Optional[str] = None, lite: bool = False):
    items = get_all_items()
    if date:
        items = [i for i in items if i["date"] == date]
    if lite:  # 위젯용 — 본문 없이 목록만
        items = [{**i, "body": ""} for i in items]
    return items


@app.get("/feed/items/{slug}")
def feed_item(slug: str):
    item = get_item(slug)
    if not item:
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없음")
    return item


@app.delete("/feed/items/{slug}", status_code=204)
def delete_feed_item(slug: str):
    """피드(Vault)에서 아이템 삭제 — 삭제 후 같은 영상을 다시 담을 수 있음"""
    from vault.writer import delete_item
    if not delete_item(slug):
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없음")


# ── Collections ───────────────────────────────────────────────────────────────

@app.get("/collections")
def list_collections():
    return get_collection_items()


@app.post("/collections/{slug}", status_code=204)
def collect_item(slug: str):
    """Feed(articles/) → Collection(collections/) 파일 이동. 되돌릴 수 없다."""
    from vault.writer import move_to_collection
    if not move_to_collection(slug):
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없음")


@app.delete("/collections/{slug}", status_code=204)
def delete_collection_item(slug: str):
    """Collection에서 제거 = 완전 삭제. Feed로 되돌리지 않는다."""
    from vault.writer import delete_item
    if not delete_item(slug):
        raise HTTPException(status_code=404, detail="아이템을 찾을 수 없음")


# ── Subscriptions ─────────────────────────────────────────────────────────────

class SubscriptionIn(BaseModel):
    platform: str
    author: str
    channel_id: Optional[str] = None
    feed_url: Optional[str] = None
    username: Optional[str] = None
    avatar_url: Optional[str] = None
    priority: int = 2  # 1=높음, 2=보통, 3=낮음


class SubscriptionPatch(BaseModel):
    priority: Optional[int] = None


@app.get("/subscriptions")
def list_subscriptions():
    return enrich_avatars()


@app.post("/subscriptions", status_code=201)
def create_subscription(body: SubscriptionIn):
    sub = body.model_dump()
    sub["id"] = str(uuid.uuid4())
    add_subscription(sub)
    return sub


@app.patch("/subscriptions/{sub_id}")
def patch_subscription(sub_id: str, body: SubscriptionPatch):
    from agent.curator import update_subscription
    updated = update_subscription(sub_id, body.model_dump())
    if not updated:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없음")
    return updated


@app.delete("/subscriptions/{sub_id}", status_code=204)
def delete_subscription(sub_id: str):
    if not remove_subscription(sub_id):
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없음")


@app.get("/subscriptions/{sub_id}/preview")
def preview_subscription(sub_id: str, cursor: Optional[str] = None):
    """구독 소스의 글/영상 목록 (저장 없음). cursor로 이전 영상 이어 로드."""
    sub = next((s for s in load_subscriptions() if s.get("id") == sub_id), None)
    if not sub:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없음")
    from scrapers.preview import preview_source
    return preview_source(sub, cursor=cursor)


class AddItemIn(BaseModel):
    platform: str
    source_url: str
    author: str = ""
    title: str = ""
    type: str = "article"
    date: str = ""  # 미리보기에서 본 게시일
    video_id: Optional[str] = None
    body: str = ""  # LinkedIn 등 포스트 자체가 본문인 경우
    feed_url: str = ""  # 본문을 되찾을 RSS 피드 (원문 직접 요청이 막힌 경우용)


@app.post("/feed/add")
def add_feed_item(body: AddItemIn):
    """미리보기 아이템을 피드로 옮김 (영상=재구성, 글=원문 그대로)"""
    from scrapers.preview import add_item
    try:
        return add_item(body.model_dump())
    except Exception as e:
        # 500을 그대로 던지면 앱에 "HTTP 500"만 뜨고 원인이 로그에도 안 남는다
        logging.exception("피드 추가 실패")
        return {"status": "error", "reason": f"{type(e).__name__}: {e}"}


# ── Agent ─────────────────────────────────────────────────────────────────────

@app.post("/agent/collect")
def trigger_collect():
    """수동 수집 — 할당량 무시, 모든 구독에서 최신글 수집. 만료 정리는 하지 않는다."""
    from agent.curator import run_scheduled_collection
    from run_log import append_run
    result = run_scheduled_collection(respect_quota=False)
    append_run(
        target=None,
        collected=result["collected"],
        slugs=result["slugs"],
        failures=result["failures"],
        trigger="manual",
    )
    return {"collected": result["collected"]}


class DiscoverIn(BaseModel):
    query: str


@app.post("/agent/discover")
def agent_discover(body: DiscoverIn):
    """AI가 쿼리에 맞는 새 소스를 발견해 구독에 추가"""
    from agent.discovery import discover_and_subscribe
    return discover_and_subscribe(body.query)


# ── Search ────────────────────────────────────────────────────────────────────

@app.get("/search")
def search_sources(q: str, platform: str = "youtube"):
    """키워드로 구독 가능한 채널/계정 검색 (youtube | medium | linkedin)"""
    from scrapers.search import search_platform
    return {"results": search_platform(q, platform)}


@app.get("/search/videos")
def search_videos(q: str):
    """키워드로 YouTube 영상 검색 — 피드에 담을 수 있는 미리보기 아이템으로 반환"""
    from scrapers.search import search_youtube_videos
    return {"items": search_youtube_videos(q)}


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsIn(BaseModel):
    daily_quota: Optional[int] = None
    auto_collect: Optional[bool] = None
    schedule: Optional[dict[str, int]] = None
    expire_days: Optional[int] = None


@app.get("/settings")
def get_settings():
    from app_settings import load_app_settings
    return load_app_settings()


@app.put("/settings")
def put_settings(body: SettingsIn):
    from app_settings import save_app_settings
    return save_app_settings(body.model_dump())


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/stats")
def stats(days: int = 30):
    """수집 통계. 성공분은 Vault frontmatter에서, 실패·만료는 실행 로그에서 온다."""
    from collections import Counter
    from datetime import date, timedelta
    from run_log import recent_runs

    items = get_all_items() + get_collection_items()
    cutoff = str(date.today() - timedelta(days=days))
    recent = [i for i in items if i["date"] >= cutoff]

    return {
        "total_feed": len(get_all_items()),
        "total_collection": len(get_collection_items()),
        # 최근 days일의 날짜별 수집 개수 (최신 날짜부터)
        "by_date": [
            {"date": d, "count": n}
            for d, n in sorted(Counter(i["date"] for i in recent).items(), reverse=True)
        ],
        "by_author": [
            {"author": a, "count": n}
            for a, n in Counter(i["author"] for i in recent if i["author"]).most_common(10)
        ],
        "by_platform": [
            {"platform": p, "count": n}
            for p, n in Counter(i["platform"] for i in recent if i["platform"]).most_common()
        ],
        "recent_runs": recent_runs(10),
    }
