"""무작위 노트 자체 점검. 실행: python vault/test_lucky.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from vault.reader import note_text, random_note  # noqa: E402

TEXT = "하고 나서 기분 좋아지는 일을 하자. 공부가 그렇다."
idea = f"---\ncreate: 2025-10-06 Mon\n---\n#growth/mindset\n### Idea\n{TEXT}\n\n### Links\n- [[x]]\n"
assert note_text(idea.split("---\n", 2)[2]) == TEXT
assert note_text("#life #a/b\n그냥 쓴 일기, 절 없음") == "그냥 쓴 일기, 절 없음"
assert note_text("![[img.png]]\n[[노트|별칭]]과 [[노트2]]") == "별칭과 노트2"

with tempfile.TemporaryDirectory() as tmp:
    settings.vault_path = Path(tmp)
    assert random_note() is None  # 폴더 없음
    d = Path(tmp) / "Zettelkasten" / "Fleeting"
    d.mkdir(parents=True)
    (d / "빈 노트.md").write_text("---\ncreate: x\n---\n#life\n### Idea\n\n### Links\n", encoding="utf-8")
    assert random_note() is None  # 빈 노트만
    (d / "251006 좋은 일.md").write_text(idea, encoding="utf-8")
    n = random_note()
    assert n == {"title": "251006 좋은 일", "date": "2025-10-06", "body": TEXT}, n

print("ok")
