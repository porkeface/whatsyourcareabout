import logging
from datetime import datetime, timedelta, timezone

from src.models import Item
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self._source_config = config.get("sources", {}).get("finnhub", {})
        self._max_items: int = self._source_config.get("max_items", 30)
        self._api_key: str = self._source_config.get("api_key", "")
        self._symbols: list[str] = self._source_config.get("symbols", [])

    def source_name(self) -> str:
        return "finnhub"

    def domain(self) -> str:
        return "finance"

    async def _fetch_general_news(self) -> list[Item]:
        url = f"{FINNHUB_BASE_URL}/news?category=general"
        headers = {"X-Finnhub-Token": self._api_key}

        try:
            data = await self._fetch_json(url, headers=headers)
        except Exception:
            logger.error("Failed to fetch Finnhub general news", exc_info=True)
            return []

        if not isinstance(data, list):
            logger.error("Unexpected Finnhub general news response type: %s", type(data))
            return []

        return self._parse_articles(data)

    async def _fetch_company_news(self, symbol: str) -> list[Item]:
        now = datetime.now(timezone.utc)
        from_date = (now - timedelta(days=7)).strftime("%Y-%m-%d")
        to_date = now.strftime("%Y-%m-%d")

        url = (
            f"{FINNHUB_BASE_URL}/company-news"
            f"?symbol={symbol}&from={from_date}&to={to_date}"
        )
        headers = {"X-Finnhub-Token": self._api_key}

        try:
            data = await self._fetch_json(url, headers=headers)
        except Exception:
            logger.error(
                "Failed to fetch Finnhub company news for '%s'", symbol,
                exc_info=True,
            )
            return []

        if not isinstance(data, list):
            logger.error(
                "Unexpected Finnhub company news response for '%s': %s",
                symbol, type(data),
            )
            return []

        return self._parse_articles(data)

    def _parse_articles(self, articles: list[dict]) -> list[Item]:
        items: list[Item] = []

        for article in articles:
            title = article.get("headline", "")
            url = article.get("url", "")

            if not title or not url:
                continue

            summary = article.get("summary", "") or ""
            source_name = article.get("source", "")
            raw_text = f"source={source_name}; {summary}" if source_name else summary

            timestamp = article.get("datetime")
            published_at = self._parse_timestamp(timestamp)

            items.append(
                Item(
                    title=title,
                    url=url,
                    source=self.source_name(),
                    domain=self.domain(),
                    score=1.0,
                    raw_text=raw_text,
                    published_at=published_at,
                )
            )

        return items

    @staticmethod
    def _parse_timestamp(timestamp) -> datetime | None:
        if timestamp is None:
            return None

        try:
            ts = int(timestamp)
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (ValueError, TypeError, OSError):
            return None

    async def collect(self) -> list[Item]:
        if not self._api_key:
            logger.error(
                "Finnhub API key not configured. Set sources.finnhub.api_key "
                "in your config.yaml."
            )
            return []

        logger.info("Collecting from Finnhub")

        if self._symbols:
            all_items: list[Item] = []
            for symbol in self._symbols:
                items = await self._fetch_company_news(symbol)
                all_items.extend(items)
                logger.debug(
                    "Symbol '%s' returned %d articles", symbol, len(items),
                )
        else:
            all_items = await self._fetch_general_news()

        collected = all_items[: self._max_items]
        logger.info("Collected %d Finnhub articles", len(collected))
        return collected
