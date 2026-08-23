"""같은 video_id에 같은 답을 두 번 묻지 않기 위한 영구 캐시.

캐시하는 건 두 가지뿐이고, 둘 다 사실상 변하지 않는 성질이다.

- 자막 없음: 업로더가 나중에 자막을 붙이는 일은 드물다. 이게 없으면 자막 없는 영상은
  Vault에 아무것도 남기지 않으므로 **매 실행마다 다시 시도된다** — 반복 요청의 최대 출처.
- 쇼츠 여부: 영상의 성질이라 바뀌지 않는다.

IP 차단과 일시적 오류는 절대 캐시하지 않는다. 그건 영상의 성질이 아니라 그 순간의
사정이고, 캐시하면 차단이 풀린 뒤에도 영원히 건너뛴다.

ponytail: 두 프로세스(서버·collect.py)가 동시에 쓰면 마지막 쓰기가 이긴다. 잃는 건
캐시 항목이고 대가는 요청 몇 번이라 잠금을 두지 않았다. 손실이 눈에 띄면 SQLite로.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_FILE = Path(__file__).parent.parent / "data" / "yt_cache.json"
_state: dict | None = None


def _load() -> dict:
    global _state
    if _state is None:
        try:
            data = json.loads(_FILE.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        _state = {
            "no_transcript": set(data.get("no_transcript") or []),
            "shorts": dict(data.get("shorts") or {}),
        }
    return _state


def _save() -> None:
    s = _load()
    try:
        _FILE.parent.mkdir(parents=True, exist_ok=True)
        _FILE.write_text(
            json.dumps(
                {"no_transcript": sorted(s["no_transcript"]), "shorts": s["shorts"]},
                ensure_ascii=False, indent=1,
            ),
            encoding="utf-8",
        )
    except Exception as e:
        # 캐시를 못 써도 수집은 굴러가야 한다 — 요청만 더 나갈 뿐이다
        logger.warning(f"YouTube 캐시 저장 실패: {e}")


# ── 자막 없음 ─────────────────────────────────────────────────────────────────

def has_no_transcript(video_id: str) -> bool:
    return video_id in _load()["no_transcript"]


def remember_no_transcript(video_id: str) -> None:
    s = _load()
    if video_id not in s["no_transcript"]:
        s["no_transcript"].add(video_id)
        _save()


# ── 쇼츠 여부 ─────────────────────────────────────────────────────────────────

def known_short(video_id: str) -> bool | None:
    """캐시된 쇼츠 여부. 모르면 None (False와 구분해야 한다)."""
    return _load()["shorts"].get(video_id)


def remember_shorts(verdicts: dict[str, bool]) -> None:
    """{video_id: 쇼츠인지} 를 한 번에 기록."""
    if not verdicts:
        return
    s = _load()
    changed = False
    for video_id, is_short in verdicts.items():
        if s["shorts"].get(video_id) != is_short:
            s["shorts"][video_id] = is_short
            changed = True
    if changed:
        _save()
