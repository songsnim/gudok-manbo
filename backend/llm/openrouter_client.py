import json
import re
import httpx
from config import settings

_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# 한국어/영어 외 문자(CJK 한자, 일본어 가나 등). 요약에 섞이면 안 됨.
_FORBIDDEN_CHARS = re.compile(r"[぀-ヿ㐀-䶿一-鿿豈-﫿ｦ-ﾟ]")

_ARTICLE_PROMPT = {
    "ko": (
        "다음은 영상의 자막(트랜스크립트)이다. 이 내용을 빠짐없이 읽기 좋은 글로 재구성하라.\n\n"
        "규칙:\n"
        "- 내용을 요약하거나 줄이지 마라. 모든 정보·논점·디테일·예시를 보존하라.\n"
        "- 자막을 그대로 받아쓰지 마라. 구어체·말더듬·반복은 다듬되 의미는 그대로 유지하라.\n"
        "- 제목(##)과 소제목, 단락, 필요한 경우 리스트로 내용을 구조화하라.\n"
        "- 인사말, 광고, 구독·좋아요 요청 등 본문과 무관한 부분만 제거하라.\n"
        "- 한국어 마크다운으로 작성하라.\n\n"
        "자막:\n"
    ),
    "en": (
        "The following is a video transcript. Rewrite it as a well-structured, readable article.\n\n"
        "Rules:\n"
        "- Do NOT summarize or shorten. Preserve all information, arguments, details, and examples.\n"
        "- Do NOT copy the transcript verbatim. Clean up filler, stutters, and repetition while keeping the meaning.\n"
        "- Structure with a title (##), subheadings, paragraphs, and lists where appropriate.\n"
        "- Remove only greetings, ads, and like/subscribe requests.\n"
        "- Write in English markdown.\n\n"
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
        "- 단, 한국어와 영어 외의 문자(한자·일본어 가나 등 다른 언어 문자)는 절대 사용하지 마라.\n\n"
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


def _chat(prompt: str, model: str, temperature: float = 0.3) -> str:
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
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
        },
        timeout=300,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"].strip()


def transcribe_to_article(transcript: str) -> str:
    """영상 자막을 내용 손실 없이 구조화된 글로 재구성."""
    prompt = _ARTICLE_PROMPT[settings.summary_language] + transcript[:60000]
    return _chat(prompt, settings.openrouter_summary_model)


def summarize_article(body: str) -> str:
    """웹 아티클 본문을 구조화된 마크다운으로 요약.

    모델이 가끔 한자·가나를 섞으므로, 검출되면 재생성(최대 2회)하고
    그래도 남으면 해당 문자를 제거해 한국어/영어만 남긴다.
    """
    prompt = _SUMMARY_PROMPT[settings.summary_language] + body[:60000]
    md = _chat(prompt, settings.openrouter_summary_model)
    for _ in range(2):
        if not _FORBIDDEN_CHARS.search(md):
            return md
        md = _chat(prompt, settings.openrouter_summary_model)
    return _FORBIDDEN_CHARS.sub("", md)


def generate_title(content: str) -> str:
    """글 내용으로 제목 생성."""
    prompt = _TITLE_PROMPT[settings.summary_language] + content[:3000]
    return _chat(prompt, settings.openrouter_summary_model)


_DISCOVER_PROMPT = """\
당신은 개인 컨텐츠 큐레이터 AI입니다. 사용자 요청에 맞는 고품질 컨텐츠 소스를 추천해주세요.

지원 플랫폼:
- youtube   : channel_id 필요 (예: UCXv...)
- medium    : username 필요 (예: @username 또는 pub/publication-name)
- substack  : username 필요 (예: stratechery — .substack.com 제외)
- devto     : username 필요 (예: tiangolo)
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
      "platform": "youtube|medium|substack|devto|hackernews|rss",
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
    if not settings.openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")

    existing_summary = ", ".join(
        f"{s.get('author', '')} ({s.get('platform', '')})"
        for s in existing
    ) or "없음"

    prompt = _DISCOVER_PROMPT.format(query=query, existing=existing_summary)

    resp = httpx.post(
        _API_URL,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "HTTP-Referer": "https://github.com/contents-curator",
            "X-Title": "Contents Curator",
        },
        json={
            "model": settings.openrouter_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.4,
        },
        timeout=120,
    )
    resp.raise_for_status()

    content = resp.json()["choices"][0]["message"]["content"].strip()

    # JSON 블록 추출 (```json ... ``` 래핑 대응)
    if "```" in content:
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    data = json.loads(content)
    return data.get("sources", [])
