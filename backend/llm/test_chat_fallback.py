"""_chat 폴백 체인 점검. 실행: python llm/test_chat_fallback.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402

from config import settings  # noqa: E402
from llm import openrouter_client as oc  # noqa: E402


class FakeResp:
    def __init__(self, status: int, content: str = "", finish: str = "stop"):
        self.status_code = status
        self._body = {"choices": [{"finish_reason": finish, "message": {"content": content}}]}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("boom", request=None, response=None)

    def json(self):
        return self._body


def stub(*responses):
    """httpx.post를 순서대로 정해진 응답을 주도록 교체. 호출된 모델 목록 반환."""
    seen = []
    it = iter(responses)

    def fake_post(url, headers=None, json=None, timeout=None):
        seen.append(json["model"])
        return next(it)

    oc.httpx.post = fake_post
    return seen


settings.openrouter_api_key = "test-key"
settings.openrouter_models = "model-a,model-b"

# 1순위 성공 → 2순위 안 부른다
seen = stub(FakeResp(200, "결과"))
assert oc._chat("p") == "결과"
assert seen == ["model-a"], seen

# 1순위 429 → 2순위로 폴백
seen = stub(FakeResp(429), FakeResp(200, "폴백 결과"))
assert oc._chat("p") == "폴백 결과"
assert seen == ["model-a", "model-b"], seen

# 빈 응답(추론 토큰이 예산 다 먹은 경우)도 폴백 대상 — Vault에 빈 글 저장 방지
seen = stub(FakeResp(200, "   ", finish="length"), FakeResp(200, "폴백 결과"))
assert oc._chat("p") == "폴백 결과"
assert seen == ["model-a", "model-b"], seen

# 전부 실패하면 에러. 조용히 빈 문자열 반환하면 안 된다
seen = stub(FakeResp(429), FakeResp(200, "", finish="length"))
try:
    oc._chat("p")
    raise AssertionError("전부 실패했는데 예외가 안 났다")
except RuntimeError as e:
    assert "model-a: 429" in str(e) and "model-b: empty" in str(e), str(e)

# extra 인자가 요청 본문으로 전달되는지 (discover_sources의 response_format)
captured = {}


def capture_post(url, headers=None, json=None, timeout=None):
    captured.update(json)
    return FakeResp(200, "ok")


oc.httpx.post = capture_post
oc._chat("p", temperature=0.4, response_format={"type": "json_object"})
assert captured["temperature"] == 0.4
assert captured["response_format"] == {"type": "json_object"}

# 키 없으면 네트워크 호출 전에 막는다
settings.openrouter_api_key = ""
try:
    oc._chat("p")
    raise AssertionError("키 없이 통과했다")
except RuntimeError as e:
    assert "OPENROUTER_API_KEY" in str(e)

print("OK")
