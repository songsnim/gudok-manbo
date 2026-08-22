import json
from pathlib import Path

from config import settings

_FILE = Path(__file__).parent / "data" / "app_settings.json"


def load_app_settings() -> dict:
    defaults = {
        "daily_quota": settings.daily_quota,
        # False면 collect.py가 즉시 종료한다 — 수집도 만료도 하지 않는다.
        "auto_collect": True,
        # 시각(로컬시간) → 그 실행에서 수집할 개수. 시각 추가·삭제는 register_tasks.ps1.
        "schedule": {"6": 10, "11": 5, "17": 10},
        # Feed 아이템을 수집일로부터 며칠 뒤 삭제할지. 0 = 만료 안 함(기본).
        "expire_days": 0,
    }
    if _FILE.exists():
        try:
            defaults.update(json.loads(_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return defaults


def save_app_settings(data: dict) -> dict:
    current = load_app_settings()
    current.update({k: v for k, v in data.items() if v is not None})
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")
    return current
