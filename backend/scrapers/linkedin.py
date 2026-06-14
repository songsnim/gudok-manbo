import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path

from vault.writer import write_item
from vault.reader import get_item

logger = logging.getLogger(__name__)

_COOKIE_FILE = Path(__file__).parent.parent / "data" / "linkedin_cookies.json"


def _slug(url: str) -> str:
    return f"li-{hashlib.md5(url.encode()).hexdigest()[:12]}"


def fetch_posts(profile_url: str, limit: int = 10) -> list[dict]:
    """프로필 최신 포스트 목록을 별도 프로세스로 수집. [{title, source_url, body, date}]."""
    if not _COOKIE_FILE.exists():
        raise RuntimeError(
            f"LinkedIn 쿠키 파일 없음: {_COOKIE_FILE}\n"
            "python -m scrapers.linkedin_setup 실행 후 브라우저에서 LinkedIn 로그인 완료"
        )
    backend_dir = Path(__file__).parent.parent
    proc = subprocess.run(
        [sys.executable, "-m", "scrapers.linkedin_posts", profile_url, str(limit)],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=90,
    )
    if proc.returncode != 0:
        logger.warning(f"LinkedIn 포스트 수집 실패: {proc.stderr[-300:]}")
        return []
    return json.loads(proc.stdout.strip() or "[]")


def scrape_profile(profile_url: str, author: str, subscription: bool, limit: int = 3) -> list[str]:
    """LinkedIn 프로필 최신 포스트를 Vault에 저장. 저장된 slug 목록 반환."""
    saved = []
    for post in fetch_posts(profile_url, limit):
        slug = _slug(post["source_url"])
        if get_item(slug):
            continue
        write_item(
            slug=slug,
            title=post["title"],
            platform="linkedin",
            source_url=post["source_url"],
            author=author,
            body=post["body"],
            subscription=subscription,
        )
        saved.append(slug)
    return saved
