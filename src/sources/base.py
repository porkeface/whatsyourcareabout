from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

import aiohttp

from src.models import Item

logger = logging.getLogger(__name__)


class BaseCollector(ABC):
    def __init__(self, config: dict):
        self.config = config
        self._session: aiohttp.ClientSession | None = None
        self._proxy: str | None = config.get("proxy")

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"User-Agent": "WYCA/1.0 (Daily Hot Topics Aggregator)"},
            )
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _fetch_json(self, url: str, headers: dict | None = None) -> dict:
        return await self._fetch_with_retry(url, "json", headers=headers)

    async def _fetch_text(self, url: str) -> str:
        return await self._fetch_with_retry(url, "text")

    async def _fetch_with_retry(
        self, url: str, mode: str = "json", headers: dict | None = None, retries: int = 3
    ) -> dict | str:
        session = await self._get_session()
        for attempt in range(retries):
            try:
                async with session.get(url, headers=headers, proxy=self._proxy) as resp:
                    if resp.status == 429 and attempt < retries - 1:
                        wait = 2 ** attempt
                        logger.warning("Rate limited on %s, retrying in %ds", url, wait)
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    if mode == "json":
                        return await resp.json(content_type=None)
                    return await resp.text()
            except aiohttp.ClientResponseError:
                raise
            except Exception:
                if attempt < retries - 1:
                    await asyncio.sleep(1)
                    continue
                raise
        raise RuntimeError(f"Failed after {retries} retries: {url}")

    @abstractmethod
    async def collect(self) -> list[Item]:
        ...

    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def domain(self) -> str:
        ...
