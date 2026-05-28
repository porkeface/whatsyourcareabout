import asyncio
import logging
from datetime import datetime, timezone

from src.models import Item
from src.processing.cleaner import clean_text
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

HN_TOP_STORIES_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"


class HackerNewsCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self._source_config = config.get("sources", {}).get("hacker_news", {})
        self._max_items: int = self._source_config.get("max_items", 20)

    def source_name(self) -> str:
        return "hacker_news"

    def domain(self) -> str:
        return "tech"

    async def _fetch_item(self, item_id: int) -> Item | None:
        try:
            data = await self._fetch_json(HN_ITEM_URL.format(item_id))
        except Exception:
            logger.debug("Failed to fetch HN item %d", item_id)
            return None

        if not data or data.get("type") != "story":
            return None

        title = data.get("title", "")
        url = data.get("url", f"https://news.ycombinator.com/item?id={item_id}")
        score = float(data.get("score", 0))
        timestamp = data.get("time")
        published_at = (
            datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None
        )

        return Item(
            title=title,
            url=url,
            source=self.source_name(),
            domain=self.domain(),
            score=score,
            raw_text=clean_text(data.get("text", ""), max_len=500),
            published_at=published_at,
        )

    async def collect(self) -> list[Item]:
        logger.info("Collecting Hacker News top stories")
        try:
            story_ids = await self._fetch_json(HN_TOP_STORIES_URL)
        except Exception:
            logger.error("Failed to fetch HN top stories list", exc_info=True)
            return []

        if not isinstance(story_ids, list):
            logger.error("Unexpected response type for HN top stories")
            return []

        ids_to_fetch = story_ids[: self._max_items]
        tasks = [self._fetch_item(sid) for sid in ids_to_fetch]
        results = await asyncio.gather(*tasks)

        items = [item for item in results if item is not None]
        logger.info("Collected %d Hacker News stories", len(items))
        return items
