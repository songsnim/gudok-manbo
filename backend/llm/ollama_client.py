import ollama
from config import settings

_SUMMARIZE_PROMPT = {
    "ko": "다음 영상 트랜스크립트를 한국어로 핵심 내용 중심으로 요약해줘. 불필요한 인사말, 광고, 중복 내용은 제거하고 3~5개의 핵심 포인트를 마크다운 리스트로 작성해줘.\n\n",
    "en": "Summarize the following video transcript in English. Remove greetings, ads, and repetition. Write 3-5 key points as a markdown list.\n\n",
}

_TITLE_PROMPT = {
    "ko": "다음 글의 내용을 보고 간결하고 명확한 한국어 제목을 한 줄로 만들어줘. 제목만 출력해.\n\n",
    "en": "Generate a concise English title for the following content. Output the title only.\n\n",
}


def summarize(transcript: str) -> str:
    prompt = _SUMMARIZE_PROMPT[settings.summary_language] + transcript[:12000]
    response = ollama.chat(
        model=settings.ollama_model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
    )
    return response["message"]["content"].strip()


def generate_title(content: str) -> str:
    prompt = _TITLE_PROMPT[settings.summary_language] + content[:3000]
    response = ollama.chat(
        model=settings.ollama_model,
        messages=[{"role": "user", "content": prompt}],
        options={"temperature": 0.3},
    )
    return response["message"]["content"].strip()
