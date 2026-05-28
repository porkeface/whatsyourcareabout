from __future__ import annotations

from abc import ABC, abstractmethod

import aiohttp

from src.models import Item


class BaseCollector(ABC):
    def __init__(self, config: dict):
        self.config = config
        self._session: aiohttp.ClientSession | None = None

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
        session = await self._get_session()
        async with session.get(url, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _fetch_text(self, url: str) -> str:
        session = await self._get_session()
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.text()

    @abstractmethod
    async def collect(self) -> list[Item]:
        ...

    @abstractmethod
    def source_name(self) -> str:
        ...

    @abstractmethod
    def domain(self) -> str:
        ...
