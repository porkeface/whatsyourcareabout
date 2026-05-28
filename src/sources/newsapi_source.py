import logging
from datetime import datetime, timezone
from urllib.parse import quote

from src.models import Item
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

NEWSAPI_BASE_URL = "https://newsapi.org/v2"
DEFAULT_QUERIES = ["artificial intelligence", "stock market", "technology"]


class NewsAPICollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self._source_config = config.get("sources", {}).get("newsapi", {})
        self._max_items: int = self._source_config.get("max_items", 30)
        self._api_key: str = self._source_config.get("api_key", "")
        self._queries: list[str] = self._source_config.get("queries", DEFAULT_QUERIES)

    def source_name(self) -> str:
        return "newsapi"

    def domain(self) -> str:
        return "general"

    async def _fetch_top_headlines(self) -> list[Item]:
        url = f"{NEWSAPI_BASE_URL}/top-headlines?country=us"
        headers = {"X-Api-Key": self._api_key}

        try:
            data = await self._fetch_json(url, headers=headers)
        except Exception:
            logger.error("Failed to fetch NewsAPI top headlines", exc_info=True)
            return []

        if data.get("status") != "ok":
            code = data.get("code", "unknown")
            message = data.get("message", "No details")
            logger.error("NewsAPI top-headlines error: %s - %s", code, message)
            return []

        return self._parse_articles(data.get("articles", []))

    async def _fetch_everything(self, query: str) -> list[Item]:
        encoded_query = quote(query)
        url = (
            f"{NEWSAPI_BASE_URL}/everything?q={encoded_query}"
            f"&sortBy=publishedAt&pageSize={self._max_items}"
        )
        headers = {"X-Api-Key": self._api_key}

        try:
            data = await self._fetch_json(url, headers=headers)
        except Exception:
            logger.error(
                "Failed to fetch NewsAPI everything for query '%s'", query,
                exc_info=True,
            )
            return []

        if data.get("status") != "ok":
            code = data.get("code", "unknown")
            message = data.get("message", "No details")
            logger.error(
                "NewsAPI everything error for '%s': %s - %s", query, code, message,
            )
            return []

        return self._parse_articles(data.get("articles", []))

    def _parse_articles(self, articles: list[dict]) -> list[Item]:
        items: list[Item] = []

        for article in articles:
            title = article.get("title", "")
            url = article.get("url", "")

            if not title or not url:
                continue

            description = article.get("description", "") or ""
            published_at_str = article.get("publishedAt")
            published_at = self._parse_iso_date(published_at_str)

            items.append(
                Item(
                    title=title,
                    url=url,
                    source=self.source_name(),
                    domain=self.domain(),
                    score=1.0,
                    raw_text=description,
                    published_at=published_at,
                )
            )

        return items

    @staticmethod
    def _parse_iso_date(date_str: str | None) -> datetime | None:
        if not date_str:
            return None

        for fmt in (
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%fZ",
        ):
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue

        return None

    async def collect(self) -> list[Item]:
        if not self._api_key:
            logger.error(
                "NewsAPI API key not configured. Set sources.newsapi.api_key "
                "in your config.yaml."
            )
            return []

        logger.info("Collecting from NewsAPI")

        if self._queries:
            all_items: list[Item] = []
            for query in self._queries:
                items = await self._fetch_everything(query)
                all_items.extend(items)
                logger.debug(
                    "Query '%s' returned %d articles", query, len(items),
                )
        else:
            all_items = await self._fetch_top_headlines()

        collected = all_items[: self._max_items]
        logger.info("Collected %d NewsAPI articles", len(collected))
        return collected
