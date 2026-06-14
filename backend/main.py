import logging
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from vault.reader import get_all_items, get_today_items, get_item
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
def feed_items(date: Optional[str] = None):
    items = get_all_items()
    if date:
        items = [i for i in items if i["date"] == date]
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
def preview_subscription(sub_id: str):
    """구독 소스의 최신 글/영상 목록 (저장 없음)"""
    sub = next((s for s in load_subscriptions() if s.get("id") == sub_id), None)
    if not sub:
        raise HTTPException(status_code=404, detail="구독을 찾을 수 없음")
    from scrapers.preview import preview_source
    return {"items": preview_source(sub)}


class AddItemIn(BaseModel):
    platform: str
    source_url: str
    author: str = ""
    title: str = ""
    type: str = "article"
    video_id: Optional[str] = None
    body: str = ""  # LinkedIn 등 포스트 자체가 본문인 경우


@app.post("/feed/add")
def add_feed_item(body: AddItemIn):
    """미리보기 아이템을 피드로 옮김 (영상=요약, 글=원본)"""
    from scrapers.preview import add_item
    return add_item(body.model_dump())


# ── Agent ─────────────────────────────────────────────────────────────────────

@app.post("/agent/collect")
def trigger_collect():
    """수동 수집 — 할당량 무시, 모든 구독에서 최신글 수집"""
    from agent.curator import run_scheduled_collection
    n = run_scheduled_collection(respect_quota=False)
    return {"collected": n}


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
    """키워드로 구독 가능한 채널/계정 검색 (youtube | substack | devto)"""
    from scrapers.search import search_platform
    return {"results": search_platform(q, platform)}


# ── Settings ──────────────────────────────────────────────────────────────────

class SettingsIn(BaseModel):
    daily_quota: Optional[int] = None


@app.get("/settings")
def get_settings():
    from app_settings import load_app_settings
    return load_app_settings()


@app.put("/settings")
def put_settings(body: SettingsIn):
    from app_settings import save_app_settings
    return save_app_settings(body.model_dump())
