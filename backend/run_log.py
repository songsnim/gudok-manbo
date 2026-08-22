"""수집 실행 기록 (append-only JSONL).

Vault는 성공한 것만 남긴다 — 실패한 소스, 할당량으로 건너뛴 소스, 만료로 지운 파일은
흔적이 없다. 특히 만료 삭제는 파일이 사라진 뒤 무엇이 사라졌는지 알 수 있는 유일한 경로다.

하루 3~4줄이라 회전이 필요 없다.
"""
import json
from datetime import datetime
from pathlib import Path

_FILE = Path(__file__).parent / "data" / "collect_runs.jsonl"


def append_run(
    target: int | None,
    collected: int,
    slugs: list[str] | None = None,
    failures: list[dict] | None = None,
    expired: list[str] | None = None,
    trigger: str = "schedule",
    error: str = "",
) -> dict:
    entry = {
        "at": datetime.now().isoformat(timespec="seconds"),
        "trigger": trigger,          # schedule | manual | skipped
        "target": target,
        "collected": collected,
        "slugs": slugs or [],
        "failures": failures or [],  # [{"author": ..., "reason": ...}]
        "expired": expired or [],    # 만료로 지운 파일명
        "error": error,
    }
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    with _FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def recent_runs(limit: int = 10) -> list[dict]:
    """최근 실행을 새것부터. 깨진 줄은 조용히 건너뛴다 — 로그 하나 때문에 통계가 죽으면 안 된다."""
    if not _FILE.exists():
        return []
    runs = []
    for line in _FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            runs.append(json.loads(line))
        except Exception:
            continue
    return runs[::-1][:limit]
