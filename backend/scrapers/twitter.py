import asyncio
import hashlib
import logging
from pathlib import Path
from vault.writer import write_item
from vault.reader import get_item

logger = logging.getLogger(__name__)

_ACCOUNTS_DB = Path(__file__).parent.parent / "data" / "twitter_accounts.db"


def _slug(tweet_id: int) -> str:
    return f"tw-{tweet_id}"


async def _fetch(username: str, limit: int) -> list[dict]:
    import twscrape

    api = twscrape.API(str(_ACCOUNTS_DB))

    # 계정이 없으면 게스트 토큰으로 시도 (rate limit 낮음)
    # 안정적인 스크래핑을 위해: twscrape accounts add <user> <pass> <email> <email_pass>
    user = await api.user_by_login(username)
    if not user:
        raise RuntimeError(f"Twitter 사용자 없음: @{username}")

    tweets = []
    async for tweet in api.user_tweets(user.id, limit=limit * 2):  # 리트윗 제외 위해 여유분 요청
        if tweet.retweetedTweet:
            continue
        tweets.append({
            "id": tweet.id,
            "text": tweet.rawContent,
            "url": tweet.url,
        })
        if len(tweets) >= limit:
            break

    return tweets


def scrape_user(username: str, author: str, subscription: bool, limit: int = 5) -> list[str]:
    """Twitter/X 사용자의 최신 트윗을 가져와 Vault에 저장.

    계정 추가 (안정성 향상):
        twscrape accounts add <username> <password> <email> <email_password>
        twscrape login_all
    """
    username = username.lstrip("@")
    try:
        tweets = asyncio.run(_fetch(username, limit))
    except Exception as e:
        raise RuntimeError(f"Twitter 스크래핑 실패 (@{username}): {e}")

    saved = []
    for tweet in tweets:
        slug = _slug(tweet["id"])
        if get_item(slug):
            continue
        write_item(
            slug=slug,
            title=tweet["text"][:100].replace("\n", " "),
            platform="twitter",
            source_url=tweet["url"],
            author=author,
            body=tweet["text"],
            subscription=subscription,
        )
        saved.append(slug)
        logger.info(f"저장: {slug}")

    return saved
