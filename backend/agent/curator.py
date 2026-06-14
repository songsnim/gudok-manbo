import json
import logging
from pathlib import Path

from config import settings
from vault.reader import count_today
from scrapers.youtube import scrape_channel
from scrapers.rss import scrape_feed

logger = logging.getLogger(__name__)

_SUBS_FILE = Path(__file__).parent.parent / "data" / "subscriptions.json"


def load_subscriptions() -> list[dict]:
    if not _SUBS_FILE.exists():
        return []
    return json.loads(_SUBS_FILE.read_text(encoding="utf-8"))


def save_subscriptions(subs: list[dict]) -> None:
    _SUBS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SUBS_FILE.write_text(json.dumps(subs, ensure_ascii=False, indent=2), encoding="utf-8")


def add_subscription(sub: dict) -> None:
    subs = load_subscriptions()
    if not any(s.get("channel_id") == sub.get("channel_id") and s.get("feed_url") == sub.get("feed_url") for s in subs):
        if not sub.get("avatar_url"):
            from scrapers.avatar import fetch_avatar
            sub["avatar_url"] = fetch_avatar(sub)
        subs.append(sub)
        save_subscriptions(subs)


def enrich_avatars() -> list[dict]:
    """아바타가 없는 구독에 프로필 이미지를 채워 저장. 갱신된 목록 반환."""
    from scrapers.avatar import fetch_avatar

    subs = load_subscriptions()
    changed = False
    for sub in subs:
        if not sub.get("avatar_url"):
            avatar = fetch_avatar(sub)
            if avatar:
                sub["avatar_url"] = avatar
                changed = True
    if changed:
        save_subscriptions(subs)
    return subs


def remove_subscription(sub_id: str) -> bool:
    subs = load_subscriptions()
    new_subs = [s for s in subs if s.get("id") != sub_id]
    if len(new_subs) == len(subs):
        return False
    save_subscriptions(new_subs)
    return True


def update_subscription(sub_id: str, fields: dict) -> dict | None:
    """구독의 일부 필드(예: priority)를 갱신."""
    subs = load_subscriptions()
    for sub in subs:
        if sub.get("id") == sub_id:
            sub.update({k: v for k, v in fields.items() if v is not None})
            save_subscriptions(subs)
            return sub
    return None


def run_scheduled_collection(respect_quota: bool = True, per_source: int = 3) -> int:
    """구독 소스에서 최신글 수집. 수집된 아이템 수 반환.

    respect_quota=True  : 스케줄 자동수집 — 일일 할당량까지만.
    respect_quota=False : 수동 실행 — 할당량 무시, 모든 구독에서 최신글 수집.
    """
    if respect_quota:
        from app_settings import load_app_settings
        quota = load_app_settings()["daily_quota"]
        remaining = quota - count_today()
        if remaining <= 0:
            logger.info("오늘 할당량 달성, 수집 건너뜀")
            return 0
    else:
        remaining = None  # 무제한

    collected = 0
    # 우선순위 높은 순(작은 숫자)으로 정렬 — 상위 채널부터 할당량 채움
    subs = sorted(load_subscriptions(), key=lambda s: s.get("priority", 2))

    for sub in subs:
        if remaining is not None and collected >= remaining:
            break

        limit = per_source if remaining is None else min(per_source, remaining - collected)
        platform = sub.get("platform", "")
        author = sub.get("author", "")

        try:
            if platform == "youtube":
                slugs = scrape_channel(
                    channel_id=sub["channel_id"],
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif platform == "threads":
                from scrapers.threads import scrape_profile as scrape_threads
                slugs = scrape_threads(
                    username=sub["username"],
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif platform in ("twitter", "x"):
                from scrapers.twitter import scrape_user
                slugs = scrape_user(
                    username=sub["username"],
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif platform == "linkedin":
                from scrapers.linkedin import scrape_profile as scrape_linkedin
                slugs = scrape_linkedin(
                    profile_url=sub["feed_url"],
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif platform == "medium":
                from scrapers.medium import scrape_profile as scrape_medium
                slugs = scrape_medium(
                    handle=sub.get("username") or sub["feed_url"],
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif platform == "substack":
                from scrapers.substack import scrape_publication
                slugs = scrape_publication(
                    publication=sub.get("username") or sub["feed_url"],
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif platform == "devto":
                from scrapers.devto import scrape_user as scrape_devto
                slugs = scrape_devto(
                    username=sub["username"],
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif platform == "hackernews":
                from scrapers.hackernews import scrape_feed_type
                slugs = scrape_feed_type(
                    feed_type=sub.get("username", "frontpage"),
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            elif sub.get("feed_url"):
                slugs = scrape_feed(
                    feed_url=sub["feed_url"],
                    platform=platform,
                    author=author,
                    subscription=True,
                    limit=limit,
                )
            else:
                continue

            collected += len(slugs)
            logger.info(f"{author}: {len(slugs)}개 수집")

        except Exception as e:
            logger.error(f"{author} 수집 실패: {e}")

    return collected
