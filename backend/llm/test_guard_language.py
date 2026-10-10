"""언어 가드 점검. 실행: python llm/test_guard_language.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from llm import openrouter_client as oc  # noqa: E402

prompts = []


def stub(replacements):
    def fake_chat(prompt, **_):
        prompts.append(prompt)
        if replacements is None:
            raise RuntimeError("모든 모델 실패")
        return json.dumps(replacements)
    oc._chat = fake_chat
    prompts.clear()


draft = "## AI 에이전트\n\n이는 重要한 문제다. **Привет** 세계, café 3개 😀 `code_x`\n- 둘째 줄 그대로 2026-10-10"

# 걸린 단어만 바뀌고 나머지는 한 글자도 안 바뀐다
stub({"1": "중요한", "2": "Hello", "3": "cafe"})
out = oc.guard_language(draft)
assert out == draft.replace("重要한", "중요한").replace("Привет", "Hello").replace("café", "cafe"), out
# 가드 호출은 draft 전체가 아니라 걸린 단어와 그 줄만 본다
assert len(prompts) == 1 and "둘째 줄" not in prompts[0], prompts

# 한글·영어뿐이면 LLM을 부르지 않는다
stub({})
clean = "## 제목\n\n한글과 English, 숫자 42, 기호 -> ! 이모지 😀"
assert oc.guard_language(clean) == clean
assert prompts == [], prompts

# 번역이 또 외국 글자를 뱉거나 빠지면 그 글자만 지운다
stub({"1": "重要"})
assert oc.guard_language("이는 重要한 문제") == "이는 한 문제"

# 태국어 결합 모음에서 단어가 쪼개지지 않는다
stub({"1": "hello"})
assert oc.guard_language("결과는 สวัสดี 수준") == "결과는 hello 수준"

# 가드 LLM이 죽어도 draft는 살아남는다
stub(None)
assert oc.guard_language("이는 重要한 문제") == "이는 한 문제"

print("ok")
