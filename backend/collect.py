"""독립 수집 엔트리포인트.

Windows 작업 스케줄러가 정해진 시각에 PC를 깨워 이 스크립트를 1회 실행한다.
실행 중에는 PC가 다시 슬립에 들어가지 않도록 막고, 끝나면 해제한다.
FastAPI 서버와 분리되어 있어 서버 상태와 무관하게 수집이 돌고, 끝나면 즉시 종료한다.

작업 스케줄러는 작업 디렉터리를 backend/ 로 설정해 실행해야 한다
(config가 .env를, 모듈들이 backend 루트를 기준으로 import 하기 때문).
"""
import ctypes
import logging
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


def main() -> None:
    _setup_logging()
    log = logging.getLogger("collect")
    _prevent_sleep()
    log.info("수집 시작 (슬립 차단)")
    try:
        from agent.curator import run_scheduled_collection
        n = run_scheduled_collection()
        log.info(f"수집 완료: {n}개")
    except Exception:
        log.exception("수집 중 오류")
    finally:
        _allow_sleep()
        log.info("종료 (슬립 허용)")


if __name__ == "__main__":
    main()
