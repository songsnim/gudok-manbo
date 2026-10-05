"""Feed는 mtime이 아니라 수집일 최신순. 실행: python vault/test_order.py"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings  # noqa: E402
from vault.reader import get_all_items  # noqa: E402

with tempfile.TemporaryDirectory() as tmp:
    settings.vault_path = Path(tmp)
    settings.articles_path.mkdir(parents=True)
    for i, (slug, date) in enumerate([("new", "2026-10-05"), ("old", "2026-08-16"), ("mid", "2026-09-25")]):
        f = settings.articles_path / f"{slug}.md"
        f.write_text(f"---\nslug: {slug}\ndate: {date}\n---\n본문", encoding="utf-8")
        os.utime(f, (1000 + i, 1000 + i))  # old가 가장 최근에 수정된 것처럼
    assert [i["slug"] for i in get_all_items()] == ["new", "mid", "old"]

print("ok")
