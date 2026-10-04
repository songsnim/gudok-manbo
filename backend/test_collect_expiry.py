"""auto_collect를 꺼도 만료는 expire_days대로 돈다. 실행: python test_collect_expiry.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import app_settings  # noqa: E402
import collect  # noqa: E402
import run_log  # noqa: E402
from config import settings  # noqa: E402

runs = []
collect._setup_logging = lambda: None  # 실제 collect.log 오염 방지
run_log.append_run = lambda **kw: runs.append(kw)

with tempfile.TemporaryDirectory() as tmp:
    settings.vault_path = Path(tmp)
    settings.articles_path.mkdir(parents=True)
    (settings.articles_path / "old.md").write_text("---\ndate: 2020-01-01\n---\n본문", encoding="utf-8")
    (settings.articles_path / "fresh.md").write_text("---\ndate: 2999-01-01\n---\n본문", encoding="utf-8")

    app_settings.load_app_settings = lambda: {"auto_collect": False, "expire_days": 50}
    collect.main()

    assert not (settings.articles_path / "old.md").exists()
    assert (settings.articles_path / "fresh.md").exists()
    assert runs[-1]["trigger"] == "skipped" and runs[-1]["expired"] == ["old.md"], runs[-1]

print("ok")
