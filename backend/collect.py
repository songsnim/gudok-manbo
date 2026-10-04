"""독립 수집 엔트리포인트.

Windows 작업 스케줄러가 정해진 시각에 PC를 깨워 이 스크립트를 1회 실행한다.
실행 중에는 PC가 다시 슬립에 들어가지 않도록 막고, 끝나면 해제한다.
FastAPI 서버와 분리되어 있어 서버 상태와 무관하게 수집이 돌고, 끝나면 즉시 종료한다.

작업 스케줄러는 작업 디렉터리를 backend/ 로 설정해 실행해야 한다
(config가 .env를, 모듈들이 backend 루트를 기준으로 import 하기 때문).
"""
import ctypes
import logging
import sys
from datetime import datetime
from pathlib import Path

# Windows SetThreadExecutionState 플래그 — 작업 동안 시스템 슬립 차단
ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001

_LOG_DIR = Path(__file__).parent / "data" / "logs"


def _setup_logging() -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(_LOG_DIR / "collect.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def _prevent_sleep() -> None:
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


def _allow_sleep() -> None:
    ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


def _target_count(cfg: dict) -> int | None:
    """이번 실행에서 수집할 개수. 인자로 주면 그 값, 없으면 설정의 시각별 개수.

    시각(트리거)은 register_tasks.ps1이, 개수는 앱이 정한다 — 개수만 앱에서 편집 가능.
    """
    if len(sys.argv) > 1:
        return int(sys.argv[1])
    schedule = cfg.get("schedule") or {}
    hour = str(datetime.now().hour)
    value = schedule.get(hour)
    return int(value) if value is not None else None  # 없으면 일일 할당량 로직으로


def main() -> None:
    _setup_logging()
    log = logging.getLogger("collect")

    from app_settings import load_app_settings
    from run_log import append_run
    cfg = load_app_settings()

    # 만료는 auto_collect와 독립 — expire_days 하나로만 켜고 끈다(0 = 만료 안 함).
    expired, error = [], ""
    try:
        from vault.writer import expire_feed_items
        expired = expire_feed_items(int(cfg.get("expire_days", 0)))
        if expired:
            log.info(f"만료 삭제: {len(expired)}개")
    except Exception as e:
        error = f"만료 정리 실패 — {type(e).__name__}: {e}"
        log.exception("만료 정리 중 오류")

    if not cfg.get("auto_collect", True):
        log.info("자동 수집 꺼짐 (auto_collect=false) — 수집 건너뜀")
        append_run(target=None, collected=0, trigger="skipped", expired=expired, error=error)
        return

    count = _target_count(cfg)
    _prevent_sleep()
    log.info(f"수집 시작 (슬립 차단, 목표 {count if count is not None else '할당량'}개)")
    result = {"collected": 0, "slugs": [], "failures": []}
    try:
        from agent.curator import run_scheduled_collection
        result = run_scheduled_collection(count=count)
        log.info(f"수집 완료: {result['collected']}개")
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        log.exception("수집 중 오류")
    finally:
        append_run(
            target=count,
            collected=result["collected"],
            slugs=result["slugs"],
            failures=result["failures"],
            expired=expired,
            error=error,
        )
        _allow_sleep()
        log.info("종료 (슬립 허용)")


if __name__ == "__main__":
    main()
