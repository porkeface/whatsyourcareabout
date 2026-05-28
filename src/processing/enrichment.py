"""Content enrichment using trafilatura for items with missing descriptions."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace

import trafilatura

from src.models import Item
from src.processing.cleaner import clean_text

logger = logging.getLogger(__name__)

# Concurrency limit for fetching pages
_MAX_CONCURRENT = 5

# Threshold below which raw_text is considered "too short" to be useful
_MIN_TEXT_LENGTH = 20

# Maximum length for extracted descriptions
_MAX_DESCRIPTION_LENGTH = 300


def _should_enrich(item: Item) -> bool:
    """Check if an item needs enrichment (raw_text is empty or too short).

    Returns True when raw_text is missing or shorter than _MIN_TEXT_LENGTH,
    meaning the item has no meaningful description yet.
    """
    return len(item.raw_text.strip()) < _MIN_TEXT_LENGTH


async def _extract_description(url: str, proxy: str | None = None) -> str:
    """Extract a meaningful description from a URL using trafilatura.

    Strategy:
    1. Fetch the page with trafilatura.fetch_url.
    2. Try metadata extraction first (often yields a concise description).
    3. Fall back to plain text extraction and take the first paragraph.
    4. Truncate to _MAX_DESCRIPTION_LENGTH.

    Returns an empty string when extraction fails for any reason.
    Uses asyncio.to_thread so the synchronous trafilatura calls never
    block the event loop.
    """
    try:
        # Step 1 — fetch the raw HTML (sync, offloaded to thread).
        downloaded: str | None = await asyncio.to_thread(
            _fetch_page, url, proxy
        )
        if not downloaded:
            logger.debug("trafilatura could not fetch: %s", url)
            return ""

        # Step 2 — try metadata description first.
        meta_desc: str = await asyncio.to_thread(
            _extract_metadata_description, downloaded
        )
        if meta_desc and len(meta_desc.strip()) >= _MIN_TEXT_LENGTH:
            return clean_text(meta_desc, max_len=_MAX_DESCRIPTION_LENGTH)

        # Step 3 — fall back to body text (first chunk).
        body_text: str = await asyncio.to_thread(
            _extract_body_text, downloaded
        )
        if body_text:
            return clean_text(body_text, max_len=_MAX_DESCRIPTION_LENGTH)

    except Exception:
        logger.warning("Failed to extract description from %s", url, exc_info=True)

    return ""


# ---- synchronous helpers (run inside asyncio.to_thread) ----


def _fetch_page(url: str, proxy: str | None = None) -> str | None:
    """Download a page via trafilatura, optionally through a proxy."""
    import os

    old_http = os.environ.get("HTTP_PROXY")
    old_https = os.environ.get("HTTPS_PROXY")
    try:
        if proxy:
            os.environ["HTTP_PROXY"] = proxy
            os.environ["HTTPS_PROXY"] = proxy
        return trafilatura.fetch_url(url)
    finally:
        # Restore original env vars
        if old_http is None:
            os.environ.pop("HTTP_PROXY", None)
        else:
            os.environ["HTTP_PROXY"] = old_http
        if old_https is None:
            os.environ.pop("HTTPS_PROXY", None)
        else:
            os.environ["HTTPS_PROXY"] = old_https


def _extract_metadata_description(html: str) -> str:
    """Return the meta description extracted by trafilatura, or ''."""
    result = trafilatura.extract(
        html,
        output_format="json",
        with_metadata=True,
        include_comments=False,
    )
    if not result:
        return ""
    # trafilatura returns a JSON string; parse it.
    import json

    try:
        data: dict = json.loads(result)
    except (json.JSONDecodeError, TypeError):
        return ""
    return data.get("description", "") or ""


def _extract_body_text(html: str) -> str:
    """Return the first paragraph of the main body text, or ''."""
    text = trafilatura.extract(
        html,
        output_format="txt",
        include_comments=False,
    )
    if not text:
        return ""
    # Take only the first paragraph to keep descriptions concise.
    first_paragraph = text.split("\n\n", 1)[0].strip()
    return first_paragraph


async def enrich_items(
    items: list[Item],
    proxy: str | None = None,
) -> list[Item]:
    """Enrich items that have empty raw_text by extracting content from source URLs.

    Uses trafilatura to extract meta descriptions and first paragraphs.
    Only processes items where raw_text is empty or very short (< _MIN_TEXT_LENGTH).
    Returns a **new** list (immutable pattern — never mutates the originals).

    Args:
        items: The collected items to potentially enrich.
        proxy: Optional HTTP/HTTPS proxy URL for trafilatura fetches.

    Returns:
        A new list of Item instances, with enriched raw_text where applicable.
    """
    if not items:
        return []

    items_to_enrich = [(i, item) for i, item in enumerate(items) if _should_enrich(item)]
    if not items_to_enrich:
        logger.debug("All items already have descriptions — skipping enrichment")
        return list(items)

    logger.info(
        "Enriching %d of %d items with missing descriptions",
        len(items_to_enrich),
        len(items),
    )

    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _enrich_one(idx: int, item: Item) -> tuple[int, str]:
        async with semaphore:
            description = await _extract_description(item.url, proxy)
            return idx, description

    # Build a map of index -> enriched raw_text.
    enriched_map: dict[int, str] = {}
    tasks = [_enrich_one(idx, item) for idx, item in items_to_enrich]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    enriched_count = 0
    for result in results:
        if isinstance(result, BaseException):
            logger.warning("Enrichment task failed: %s", result)
            continue
        idx, description = result
        if description:
            enriched_map[idx] = description
            enriched_count += 1

    # Build the new list — replace only the items that got new text.
    new_items: list[Item] = []
    for i, item in enumerate(items):
        if i in enriched_map:
            new_items.append(replace(item, raw_text=enriched_map[i]))
        else:
            new_items.append(item)

    logger.info("Enrichment complete: %d items updated", enriched_count)
    return new_items
