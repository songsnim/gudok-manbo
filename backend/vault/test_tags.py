"""태그 체계 파싱·필터·저장 점검 (LLM 호출 없음). 실행: python vault/test_tags.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import frontmatter  # noqa: E402
import llm.openrouter_client as llm  # noqa: E402
from config import settings  # noqa: E402
from vault.writer import load_taxonomy, write_item  # noqa: E402

DOC = """# Vault 태그 체계

| 최상위 | 하위 태그 |
|---|---|
| `tech` | `ml` `agent` `coding-test` |
| `life` | `health` |

| 경계 | 기준 |
|---|---|
| `ml` / `agent` | 모델 내부는 ml |
"""

assert llm.clean_tags(["#Tech/Agent", "tech/agent", "ai", "life", "tech/ml"], {"tech/agent", "life", "tech/ml"}) == ["tech/agent", "life"]
assert llm.clean_tags("tech/ml", {"tech/ml"}) == []

with tempfile.TemporaryDirectory() as tmp:
    settings.vault_path = Path(tmp)

    # 문서가 없으면 태깅을 건너뛴다 — LLM을 부르지 않는다
    assert load_taxonomy() == ("", set())

    def never(*a):
        raise AssertionError("호출되면 안 됨")
    llm.pick_tags = never
    p = write_item("rs-1", "제목", "rss", "http://x", "me", "본문", True)
    assert "tags" not in frontmatter.load(str(p)).metadata

    (Path(tmp) / "CLAUDE.md").write_text(DOC, encoding="utf-8")
    _, allowed = load_taxonomy()
    assert allowed == {"tech", "tech/ml", "tech/agent", "tech/coding-test", "life", "life/health"}, allowed

    llm.pick_tags = lambda rules, allowed, title, body: ["tech/agent"]
    p = write_item("rs-2", "에이전트 글", "rss", "http://x", "me", "본문", True)
    assert frontmatter.load(str(p)).metadata["tags"] == ["tech/agent"]

    # 태그 고르기가 터져도 Item은 저장된다
    def boom(*a):
        raise RuntimeError("모든 모델 실패")
    llm.pick_tags = boom
    p = write_item("rs-3", "글", "rss", "http://x", "me", "본문", True)
    assert p.exists() and "tags" not in frontmatter.load(str(p)).metadata

print("ok")
