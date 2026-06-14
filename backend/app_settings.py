import json
from pathlib import Path

from config import settings

_FILE = Path(__file__).parent / "data" / "app_settings.json"


def load_app_settings() -> dict:
    defaults = {"daily_quota": settings.daily_quota}
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
