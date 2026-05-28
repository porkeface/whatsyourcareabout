import logging
from datetime import datetime, timezone

from src.models import Item
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

AI_SUBREDDITS = {"machinelearning", "artificial", "deeplearning", "ml", "artificialintelligence"}

DEFAULT_SUBREDDITS = ["MachineLearning", "artificial", "technology"]


class RedditCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self._source_config = config.get("sources", {}).get("reddit", {})
        self._max_items: int = self._source_config.get("max_items", 20)
        self._subreddits: list[str] = self._source_config.get(
            "subreddits", DEFAULT_SUBREDDITS
        )

    def source_name(self) -> str:
        return "reddit"

    def domain(self) -> str:
        return "tech"

    async def _fetch_subreddit(self, subreddit: str) -> list[Item]:
        url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
        custom_headers = {
            "User-Agent": "python:wyca-daily-aggregator:v1.0 (by /u/wyca_bot)"
        }

        try:
            data = await self._fetch_json(url, headers=custom_headers)
        except Exception:
            logger.error("Failed to fetch r/%s", subreddit, exc_info=True)
            return []

        children = data.get("data", {}).get("children", [])
        items: list[Item] = []

        for child in children:
            post = child.get("data", {})
            if post.get("stickied"):
                continue

            title = post.get("title", "")
            post_url = post.get("url", "")
            permalink = f"https://reddit.com{post.get('permalink', '')}"

            score = float(post.get("score", 0))
            created_utc = post.get("created_utc")
            published_at = (
                datetime.fromtimestamp(created_utc, tz=timezone.utc)
                if created_utc
                else None
            )

            domain = "ai" if subreddit.lower() in AI_SUBREDDITS else "tech"

            items.append(
                Item(
                    title=title,
                    url=post_url or permalink,
                    source=self.source_name(),
                    domain=domain,
                    score=score,
                    raw_text=post.get("selftext", ""),
                    published_at=published_at,
                )
            )

        logger.debug("Collected %d posts from r/%s", len(items), subreddit)
        return items

    async def collect(self) -> list[Item]:
        logger.info("Collecting Reddit posts from subreddits: %s", self._subreddits)
        all_items: list[Item] = []

        for subreddit in self._subreddits:
            try:
                items = await self._fetch_subreddit(subreddit)
                all_items.extend(items)
            except Exception:
                logger.error(
                    "Unexpected error collecting from r/%s", subreddit, exc_info=True
                )

        all_items.sort(key=lambda x: x.score, reverse=True)
        collected = all_items[: self._max_items]
        logger.info("Collected %d Reddit posts total", len(collected))
        return collected
