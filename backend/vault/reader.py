from datetime import date
from pathlib import Path
from typing import Optional
import random
import re
import frontmatter

from config import settings

_UNSAFE = re.compile(r'[\\/:*?"<>|#^\[\]]')


def safe_title(title: str) -> str:
    """제목을 파일명에 쓸 수 있게 정제. 빈 문자열이면 'untitled'."""
    name = _UNSAFE.sub(" ", title)
    name = re.sub(r"\s+", " ", name).strip(" .")
    return name[:60].strip(" .") or "untitled"


def find_item_path(slug: str) -> Optional[Path]:
    """slug의 .md를 articles/와 collections/ 양쪽에서 찾는다. 없으면 None."""
    for folder in (settings.articles_path, settings.collections_path):
        hits = sorted(folder.glob(f"*-{slug}.md"))
        if hits:
            return hits[0]
        legacy = folder / f"{slug}.md"
        if legacy.exists():
            return legacy
    return None


def item_path(slug: str, title: str = "") -> Path:
    """slug에 해당하는 .md 경로. 없으면 articles/ 아래 새 경로를 만들어 반환."""
    return find_item_path(slug) or settings.articles_path / f"{safe_title(title)}-{slug}.md"


def _parse_file(path: Path) -> Optional[dict]:
    try:
        post = frontmatter.load(str(path))
        meta = post.metadata
        # Obsidian은 폴더를 만들 때 같은 이름의 빈 노트를 함께 만든다. Item이 아니므로
        # 목록에서 걸러낸다 — Item은 항상 frontmatter에 slug나 title을 갖는다.
        if not meta.get("slug") and not meta.get("title"):
            return None
        return {
            # 신형 파일은 frontmatter에 slug가 있고, 구형은 파일명 자체가 slug다
            "slug": meta.get("slug") or path.stem,
            "title": meta.get("title", ""),
            "platform": meta.get("platform", ""),
            "source_url": meta.get("source_url", ""),
            "author": meta.get("author", ""),
            "date": str(meta.get("date", "")),
            "published": str(meta.get("published", "")),
            "subscription": bool(meta.get("subscription", False)),  # 추천에서 담은 것은 "추천 영상"
            "body": post.content,
        }
    except Exception:
        return None


def _items_in(path: Path) -> list[dict]:
    if not path.exists():
        return []
    items = []
    for f in sorted(path.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
        item = _parse_file(f)
        if item:
            items.append(item)
    # 수집일 최신순. mtime은 Obsidian 편집·동기화로 바뀌므로 같은 날 안에서만 쓴다 (stable sort).
    items.sort(key=lambda i: i["date"], reverse=True)
    return items


def get_all_items() -> list[dict]:
    """Feed — articles/ 만. collections/ 는 별도 탭이라 섞지 않는다."""
    return _items_in(settings.articles_path)


def get_collection_items() -> list[dict]:
    return _items_in(settings.collections_path)


def get_today_items() -> list[dict]:
    today = str(date.today())
    return [i for i in get_all_items() if i["date"] == today]


def get_item(slug: str) -> Optional[dict]:
    """Feed든 Collection이든 slug로 찾는다 (미리보기의 in_feed 판정에도 쓰인다)."""
    path = find_item_path(slug)
    return _parse_file(path) if path else None


def count_today() -> int:
    return len(get_today_items())


_TAG_LINE = re.compile(r"^(#[^\s#]+\s*)+$")


def note_text(content: str) -> str:
    """Fleeting 노트 본문. '### Idea' 절이 있으면 그 절만, 없으면 전체 — 태그만 있는 줄은 뺀다."""
    idea = re.search(r"^#+ Idea[ \t]*\n(.*?)(?=^#+ |\Z)", content, re.M | re.S)
    text = idea.group(1) if idea else content
    text = "\n".join(l for l in text.splitlines() if not _TAG_LINE.match(l.strip()))
    # 폰에선 Vault 첨부를 못 여니 임베드는 빼고, 위키링크는 보이는 글자만 남긴다
    text = re.sub(r"!\[\[[^\]]*\]\]", "", text)
    text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", text)
    return text.strip()


def random_note() -> Optional[dict]:
    """내가 쓴 Fleeting 노트 하나를 무작위로 (I'm feeling lucky). 빈 노트는 건너뛴다."""
    notes = list((settings.vault_path / "Zettelkasten" / "Fleeting").glob("*.md"))
    random.shuffle(notes)
    for f in notes:
        try:
            post = frontmatter.load(str(f))
        except Exception:
            continue
        body = note_text(post.content)
        if len(body) >= 20:
            return {"title": f.stem, "date": str(post.metadata.get("create", ""))[:10], "body": body}
    return None
