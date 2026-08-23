import json
import logging
from pathlib import Path

from config import settings
from vault.reader import count_today
from scrapers.youtube import IpBlockedError, scrape_channel
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


def run_scheduled_collection(respect_quota: bool = True, per_source: int = 3, count: int | None = None) -> dict:
    """구독 소스에서 최신글 수집.

    반환: {"collected": 개수, "slugs": [...], "failures": [{"author","reason"}, ...]}
    실패 목록은 실행 로그(run_log)와 통계에서 "왜 이 채널은 안 들어왔지"에 답하기 위한 것이다.

    count 지정         : 이번 실행에서 새 아이템을 그 개수만큼만 수집(할당량 무시).
    respect_quota=True : 스케줄 자동수집 — 일일 할당량까지만.
    respect_quota=False: 수동 실행 — 할당량 무시, 모든 구독에서 최신글 수집.
    """
    all_slugs: list[str] = []
    failures: list[dict] = []

    if count is not None:
        remaining = count  # 이번 실행 목표치
    elif respect_quota:
        from app_settings import load_app_settings
        quota = load_app_settings()["daily_quota"]
        remaining = quota - count_today()
        if remaining <= 0:
            logger.info("오늘 할당량 달성, 수집 건너뜀")
            return {"collected": 0, "slugs": [], "failures": []}
    else:
        remaining = None  # 무제한

    collected = 0
    # 우선순위 높은 순(작은 숫자)으로 정렬 — 상위 채널부터 할당량 채움
    subs = sorted(load_subscriptions(), key=lambda s: s.get("priority", 2))
    # 자막 IP 차단은 채널별 사정이 아니라 실행 전체의 사정이다. 한 번 걸리면 남은
    # YouTube 채널은 열지 않는다 — 열어봐야 채널당 RSS 1 + 쇼츠 판별 최대 15회를
    # 막힌 IP로 더 쏘고 0개를 담는다. 다른 플랫폼은 영향 없으므로 계속 돈다.
    yt_blocked = ""

    for sub in subs:
        if remaining is not None and collected >= remaining:
            break

        limit = per_source if remaining is None else min(per_source, remaining - collected)
        platform = sub.get("platform", "")
        author = sub.get("author", "")

        if platform == "youtube" and yt_blocked:
            failures.append({"author": author, "reason": yt_blocked})
            continue

        try:
            if platform == "youtube":
                slugs = scrape_channel(
                    channel_id=sub["channel_id"],
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
            all_slugs.extend(slugs)
            logger.info(f"{author}: {len(slugs)}개 수집")

        except IpBlockedError as e:
            yt_blocked = str(e)
            logger.error(f"YouTube 자막 IP 차단 — 남은 YouTube 채널 건너뜀 ({author})")
            failures.append({"author": author, "reason": yt_blocked})

        except Exception as e:
            logger.error(f"{author} 수집 실패: {e}")
            failures.append({"author": author, "reason": f"{type(e).__name__}: {e}"})

    return {"collected": collected, "slugs": all_slugs, "failures": failures}
