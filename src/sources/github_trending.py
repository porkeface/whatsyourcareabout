import logging
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from src.models import Item
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

GITHUB_TRENDING_URL = "https://github.com/trending"


class GitHubTrendingCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self._source_config = config.get("sources", {}).get("github_trending", {})
        self._max_items: int = self._source_config.get("max_items", 15)
        self._languages: list[str] = self._source_config.get("languages", [])

    def source_name(self) -> str:
        return "github_trending"

    def domain(self) -> str:
        return "tech"

    async def collect(self) -> list[Item]:
        url = f"{GITHUB_TRENDING_URL}?since=daily"
        if self._languages:
            url += f"&spoken_language_code=en"

        logger.info("Collecting GitHub trending repositories")

        try:
            html = await self._fetch_text(url)
        except Exception:
            logger.error("Failed to fetch GitHub trending page", exc_info=True)
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
        except Exception:
            logger.error("Failed to parse GitHub trending HTML")
            return []

        repo_articles = soup.select("article.Box-row")
        items: list[Item] = []

        for article in repo_articles:
            try:
                item = self._parse_repo(article)
                if item is not None:
                    items.append(item)
            except Exception:
                logger.debug("Failed to parse a trending repo entry", exc_info=True)

        if self._languages:
            filtered = [
                i for i in items
                if self._extract_language(i.raw_text).lower()
                in [lang.lower() for lang in self._languages]
            ]
            items = filtered if filtered else items

        collected = items[: self._max_items]
        logger.info("Collected %d GitHub trending repos", len(collected))
        return collected

    def _parse_repo(self, article) -> Item | None:
        h2 = article.select_one("h2 a")
        if h2 is None:
            return None

        repo_path = h2.get("href", "").strip("/")
        parts = repo_path.split("/")
        if len(parts) < 2:
            return None

        owner, repo_name = parts[0], parts[1]
        repo_url = f"https://github.com/{owner}/{repo_name}"

        desc_el = article.select_one("p")
        description = desc_el.get_text(strip=True) if desc_el else ""

        stars_today = ""
        stars_el = article.select_one("span.d-inline-block.float-sm-right")
        if stars_el:
            stars_text = stars_el.get_text(strip=True)
            if "stars" in stars_text:
                stars_today = stars_text

        lang_el = article.select_one("[itemprop='programmingLanguage']")
        language = lang_el.get_text(strip=True) if lang_el else ""

        total_stars = ""
        star_links = article.select("a.Link--muted")
        for link in star_links:
            href = link.get("href", "")
            if "/stargazers" in href:
                total_stars = link.get_text(strip=True)
                break

        raw_text = f"language={language}; stars_today={stars_today}; total_stars={total_stars}; {description}"

        return Item(
            title=f"{owner}/{repo_name}",
            url=repo_url,
            source=self.source_name(),
            domain=self.domain(),
            raw_text=raw_text,
            published_at=datetime.now(timezone.utc),
        )

    @staticmethod
    def _extract_language(raw_text: str) -> str:
        if raw_text.startswith("language="):
            end = raw_text.find(";")
            if end != -1:
                return raw_text[len("language=") : end]
        return ""
