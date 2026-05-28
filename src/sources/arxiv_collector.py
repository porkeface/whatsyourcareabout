import logging
from datetime import datetime, timezone
from xml.etree import ElementTree

from src.models import Item
from src.sources.base import BaseCollector

logger = logging.getLogger(__name__)

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "http://www.w3.org/2005/Atom"


class ArxivCollector(BaseCollector):
    def __init__(self, config: dict):
        super().__init__(config)
        self._source_config = config.get("sources", {}).get("arxiv", {})
        self._max_items: int = self._source_config.get("max_items", 15)
        self._categories: list[str] = self._source_config.get(
            "categories", ["cs.AI", "cs.CL", "cs.CV", "cs.LG"]
        )

    def source_name(self) -> str:
        return "arxiv"

    def domain(self) -> str:
        return "academic"

    async def collect(self) -> list[Item]:
        category_query = "+OR+".join(f"cat:{cat}" for cat in self._categories)
        params = (
            f"search_query={category_query}"
            f"&sortBy=submittedDate"
            f"&sortOrder=descending"
            f"&max_results={self._max_items}"
        )
        url = f"{ARXIV_API_URL}?{params}"

        logger.info("Collecting arXiv papers for categories: %s", self._categories)

        try:
            xml_text = await self._fetch_text(url)
        except Exception:
            logger.error("Failed to fetch arXiv API", exc_info=True)
            return []

        try:
            root = ElementTree.fromstring(xml_text)
        except ElementTree.ParseError:
            logger.error("Failed to parse arXiv XML response")
            return []

        items: list[Item] = []

        for entry in root.findall(f"{{{ATOM_NS}}}entry"):
            title_el = entry.find(f"{{{ATOM_NS}}}title")
            title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else ""

            link_el = entry.find(f"{{{ATOM_NS}}}link[@rel='alternate']")
            if link_el is None:
                link_el = entry.find(f"{{{ATOM_NS}}}link")
            url_val = link_el.get("href", "") if link_el is not None else ""

            summary_el = entry.find(f"{{{ATOM_NS}}}summary")
            summary = summary_el.text.strip().replace("\n", " ") if summary_el is not None and summary_el.text else ""

            published_el = entry.find(f"{{{ATOM_NS}}}published")
            published_at = None
            if published_el is not None and published_el.text:
                try:
                    published_at = datetime.fromisoformat(
                        published_el.text.replace("Z", "+00:00")
                    )
                except ValueError:
                    pass

            if not title or not url_val:
                continue

            items.append(
                Item(
                    title=title,
                    url=url_val,
                    source=self.source_name(),
                    domain=self.domain(),
                    raw_text=summary,
                    published_at=published_at,
                )
            )

        logger.info("Collected %d arXiv papers", len(items))
        return items
