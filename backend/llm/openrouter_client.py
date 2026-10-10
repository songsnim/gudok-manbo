import json
import logging
import re
import unicodedata
import httpx
from config import settings

logger = logging.getLogger(__name__)

_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 한글·영어 알파벳이 아닌 글자(한자, 가나, 키릴, 아랍, 태국, 악센트 라틴 등). 숫자·기호·이모지는 글자가 아니라 안 걸린다.
# 단어 = 공백·ASCII 기호로 끊은 덩어리. \w로 끊으면 태국어 모음 같은 결합 부호에서 단어가 쪼개진다.
_TOKEN = re.compile(r"[^\s!-/:-@\[-`{-~]+")


def _is_foreign(ch: str) -> bool:
    return unicodedata.category(ch)[0] in "LM" and not (
        ch.isascii() or "가" <= ch <= "힣" or "ᄀ" <= ch <= "ᇿ" or "㄰" <= ch <= "㆏"
    )


_ARTICLE_PROMPT = {
    "ko": (
        "다음은 영상의 자막(트랜스크립트)이다. 이 내용을 빠짐없이 읽기 좋은 글로 재구성하라.\n\n"
        "규칙:\n"
        "- 내용을 요약하거나 줄이지 마라. 모든 정보·논점·디테일·예시를 보존하라.\n"
        "- 자막을 그대로 받아쓰지 마라. 구어체·말더듬·반복은 다듬되 의미는 그대로 유지하라.\n"
        "- 제목(##)과 소제목, 단락, 필요한 경우 리스트로 내용을 구조화하라.\n"
        "- 인사말, 광고, 구독·좋아요 요청 등 본문과 무관한 부분만 제거하라.\n"
        "- 한국어 마크다운으로 작성하라.\n"
        "- 마지막에 '## 핵심 인사이트' 섹션을 덧붙여라. 이 섹션에서는:\n"
        "  · 작성자가 이 영상을 만든 이유와 의도가 무엇인지 짚어라.\n"
        "  · 이 글이 어떤 인사이트를 제공하는지 밝혀라.\n"
        "  · 독자가 자신의 삶에 적용해 도움받을 수 있는 핵심 정수(가장 본질적인 인사이트)를 골라, "
        "독자 입장에서 바로 쓸 수 있도록 refine해서 제시하라.\n\n"
        "자막:\n"
    ),
    "en": (
        "The following is a video transcript. Rewrite it as a well-structured, readable article.\n\n"
        "Rules:\n"
        "- Do NOT summarize or shorten. Preserve all information, arguments, details, and examples.\n"
        "- Do NOT copy the transcript verbatim. Clean up filler, stutters, and repetition while keeping the meaning.\n"
        "- Structure with a title (##), subheadings, paragraphs, and lists where appropriate.\n"
        "- Remove only greetings, ads, and like/subscribe requests.\n"
        "- Write in English markdown.\n"
        "- End with a '## Key Insight' section. In this section:\n"
        "  · State why the author made this video and what their intent is.\n"
        "  · Spell out what insight this piece offers.\n"
        "  · Pick the essential core insight the reader can apply to their own life, "
        "refined and framed so the reader can act on it directly.\n\n"
        "Transcript:\n"
    ),
}

_SUMMARY_PROMPT = {
    "ko": (
        "다음은 웹 아티클의 본문이다(메뉴·광고 등 잡텍스트가 섞여 있을 수 있다). "
        "핵심 내용만 골라 읽기 좋은 마크다운으로 구조화해 요약하라.\n\n"
        "규칙:\n"
        "- 본문과 무관한 메뉴·네비게이션·광고·저작권 문구는 무시하라.\n"
        "- 아래 형식을 그대로 따르라:\n"
        "  ## 한 줄 요약\n"
        "  (핵심을 한 문장으로)\n\n"
        "  ## 핵심 포인트\n"
        "  - (불릿 3~6개)\n\n"
        "  ## 상세\n"
        "  (소제목 ###과 단락으로 정리, 중요한 수치·예시·논점 포함)\n"
        "- 원문에 없는 내용을 지어내지 마라.\n"
        "- 한국어 마크다운으로 작성하라. 전문 용어나 고유명사는 영어 원어 그대로 두어도 된다.\n"
        "- 단, 한국어와 영어 단어만 사용.\n"
        "- 일본어/한자 단어는 한국어로 번역하고 유럽권 언어의 단어는 영어로 번역하여 사용.\n\n"
        "본문:\n"
    ),
    "en": (
        "The following is the body of a web article (it may contain menu/ad noise). "
        "Extract the essential content and summarize it as well-structured markdown.\n\n"
        "Rules:\n"
        "- Ignore navigation, menus, ads, and copyright boilerplate.\n"
        "- Follow this exact format:\n"
        "  ## TL;DR\n"
        "  (one sentence)\n\n"
        "  ## Key Points\n"
        "  - (3-6 bullets)\n\n"
        "  ## Details\n"
        "  (### subheadings and paragraphs; keep important figures, examples, arguments)\n"
        "- Do NOT fabricate anything not in the source.\n"
        "- Write in English markdown only.\n\n"
        "Article:\n"
    ),
}

_TITLE_PROMPT = {
    "ko": "다음 글의 내용을 보고 간결하고 명확한 한국어 제목을 한 줄로 만들어줘. 제목만 출력해.\n\n",
    "en": "Generate a concise English title for the following content. Output the title only.\n\n",
}


def _chat(prompt: str, temperature: float = 0.3, **extra) -> str:
    """model_chain을 순서대로 시도. free tier는 429가 상시로 뜨고,
    reasoning 모델은 추론 토큰이 출력 예산을 다 먹으면 빈 content를 준다."""
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    errors = []
    for model in settings.model_chain:
        resp = httpx.post(
            _API_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key}",
                "HTTP-Referer": "https://github.com/contents-curator",
                "X-Title": "Contents Curator",
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature,
                **extra,
            },
            timeout=300,
        )
        if resp.status_code == 429:
            logger.warning(f"{model}: rate limited, 다음 모델로")
            errors.append(f"{model}: 429")
            continue
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        content = choice["message"]["content"].strip()
        if content:
            return content
        # 빈 응답을 그대로 넘기면 Vault에 빈 글이 저장된다
        logger.warning(f"{model}: 빈 응답 (finish={choice.get('finish_reason')}), 다음 모델로")
        errors.append(f"{model}: empty ({choice.get('finish_reason')})")

    raise RuntimeError(f"모든 모델 실패 — {', '.join(errors)}")


_GUARD_PROMPT = """아래 번호 붙은 단어들은 한글·영어가 아닌 글자가 섞인 단어다. 각 단어를 바꿀 말을 정하라.
- 한자·일본어(가나)가 섞였으면 한국어로 바꾼다. 붙은 한글 조사·어미는 그대로 살린다. 예: 重要한 → 중요한
- 그 외 글자(러시아어, 아랍어, 태국어, 악센트 붙은 라틴 등)는 영어 단어로 바꾼다. 예: café → cafe
- 결과에는 한글, 영어 알파벳, 숫자, 기호만 쓴다.
- 각 단어 옆 문맥은 뜻을 정하는 데만 참고한다.

반드시 아래 JSON만 출력하라 (다른 텍스트 없이). 키는 단어 번호:
{{"1": "바꾼 말", "2": "바꾼 말"}}

단어와 문맥:
{words}"""


def guard_language(md: str) -> str:
    """1차 draft에서 한글·영어 아닌 글자가 낀 단어만 골라 그 자리만 바꾼다.

    검출은 코드, 번역은 draft를 모르는 새 _chat 호출이 단어 목록만 보고 한다.
    치환도 코드가 단어 단위로 하므로 걸린 단어 밖은 한 글자도 바뀌지 않는다.
    """
    found = {}
    for line in md.splitlines():
        for m in _TOKEN.finditer(line):
            if any(map(_is_foreign, m.group(0))):
                found.setdefault(m.group(0), line.strip()[:200])
    if not found:
        return md

    words = list(found)
    listing = "\n".join(f"{i}. {w}  (문맥: {found[w]})" for i, w in enumerate(words, 1))
    try:
        content = _chat(_GUARD_PROMPT.format(words=listing), temperature=0, response_format={"type": "json_object"})
        match = re.search(r"\{.*\}", content, re.S)
        raw = json.loads(match.group(0) if match else content)
        # 모델이 단어를 키로 되받아 적으면 글자를 틀린다(非常に → 非常에). 그래서 번호로 받는다.
        fixes = {w: raw.get(str(i)) for i, w in enumerate(words, 1)}
    except Exception as e:  # 가드가 죽어도 draft는 살린다 — 아래에서 외국 글자 제거로 떨어진다
        logger.warning(f"언어 가드 실패, 외국 글자만 지운다: {e}")
        fixes = {}

    def fix(m: re.Match) -> str:
        w = m.group(0)
        if w not in found:
            return w
        r = fixes.get(w)
        # 번역이 없거나 비었거나 또 외국 글자를 뱉었으면 그 글자만 지운다
        if not isinstance(r, str) or not r.strip() or any(map(_is_foreign, r)):
            return "".join(c for c in w if not _is_foreign(c))
        return r.strip()

    logger.info(f"언어 가드: {len(found)}개 단어 치환")
    return _TOKEN.sub(fix, md)


def transcribe_to_article(transcript: str) -> str:
    """영상 자막을 내용 손실 없이 구조화된 글로 재구성."""
    prompt = _ARTICLE_PROMPT[settings.summary_language] + transcript[:60000]
    return guard_language(_chat(prompt))


def summarize_article(body: str) -> str:
    """웹 아티클 본문을 구조화된 마크다운으로 요약."""
    prompt = _SUMMARY_PROMPT[settings.summary_language] + body[:60000]
    return guard_language(_chat(prompt))


def generate_title(content: str) -> str:
    """글 내용으로 제목 생성."""
    prompt = _TITLE_PROMPT[settings.summary_language] + content[:3000]
    return guard_language(_chat(prompt))


_TAG_PROMPT = """\
아래 태그 체계 문서를 따라 이 글에 맞는 태그를 1~2개 골라라.
문서의 태그 표에 있는 태그만 쓴다. 형식은 `최상위/하위`. 그 영역 전체를 다루는 글만 최상위 단독.

반드시 아래 JSON만 출력하라 (다른 텍스트 없이):
{{"tags": ["tech/agent"]}}

태그 체계 문서:
{rules}

제목: {title}

본문:
{body}"""


def clean_tags(raw, allowed: set[str]) -> list[str]:
    """LLM이 고른 태그를 정규화하고 허용 목록 밖은 버린다. 최대 2개."""
    if not isinstance(raw, list):
        return []
    tags = (str(t).strip().lstrip("#").lower() for t in raw)
    return [t for t in dict.fromkeys(tags) if t in allowed][:2]


def pick_tags(rules: str, allowed: set[str], title: str, body: str) -> list[str]:
    """태그 체계 문서 안에서 Item 태그를 고른다. 새 태그를 지어내지 못하게 allowed로 거른다."""
    prompt = _TAG_PROMPT.format(rules=rules, title=title, body=body[:4000])
    content = _chat(prompt, temperature=0, response_format={"type": "json_object"})
    # 모델이 ```json 펜스로 감싸 줄 때가 있다
    match = re.search(r"\{.*\}", content, re.S)
    return clean_tags(json.loads(match.group(0) if match else content).get("tags"), allowed)


_DISCOVER_PROMPT = """\
당신은 개인 컨텐츠 큐레이터 AI입니다. 사용자 요청에 맞는 고품질 컨텐츠 소스를 추천해주세요.

지원 플랫폼:
- youtube   : channel_id 필요 (예: UCXv...)
- medium    : username 필요 (예: @username 또는 pub/publication-name)
- substack  : username 필요 (예: stratechery — .substack.com 제외)
- hackernews: username에 피드 타입 (frontpage|best|ask|show)
- rss       : feed_url 필요 (직접 RSS URL)

현재 구독 중인 작가/채널:
{existing}

사용자 요청:
{query}

위 요청에 맞는 새로운 소스를 최대 6개 추천하세요. 이미 구독 중인 것은 제외하세요.
실제로 존재하는 계정/채널만 추천하세요.

반드시 아래 JSON만 출력하세요 (다른 텍스트 없이):
{{
  "sources": [
    {{
      "platform": "youtube|medium|substack|hackernews|rss",
      "author": "표시될 이름",
      "username": "유저명 (youtube 제외)",
      "channel_id": "채널 ID (youtube만, 나머지는 null)",
      "feed_url": "RSS URL (rss 플랫폼만, 나머지는 null)",
      "reason": "추천 이유 (한국어, 1줄)"
    }}
  ]
}}"""


def discover_sources(query: str, existing: list[dict]) -> list[dict]:
    """OpenRouter LLM에 소스 추천 요청. 파싱된 source 목록 반환."""
    existing_summary = ", ".join(
        f"{s.get('author', '')} ({s.get('platform', '')})"
        for s in existing
    ) or "없음"

    prompt = _DISCOVER_PROMPT.format(query=query, existing=existing_summary)
    content = _chat(prompt, temperature=0.4, response_format={"type": "json_object"})

    data = json.loads(content)
    return data.get("sources", [])
