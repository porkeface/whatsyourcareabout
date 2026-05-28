"""AI-powered summarization module for the daily hot topics aggregator.

Uses the Anthropic Claude API to generate concise summaries for top
items per domain. Summaries are cached by URL hash to avoid redundant
API calls within a session.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import Any

import anthropic

from src.models import DailyDigest, Item

logger = logging.getLogger(__name__)

__all__ = ["summarize_digest"]

_DEFAULT_MODEL = "claude-haiku-4-5-20251001"
_DEFAULT_MAX_ITEMS_PER_DOMAIN = 5

_SYSTEM_PROMPT = (
    "You are a news summarizer. For each item, write a 1-2 sentence "
    "summary in the SAME LANGUAGE as the title. Be concise and informative."
)

# ---------------------------------------------------------------------------
# In-memory summary cache keyed by URL hash (bounded to prevent memory leak)
# ---------------------------------------------------------------------------
_summary_cache: dict[str, str] = {}
_CACHE_MAX_SIZE = 500


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def summarize_digest(
    digest: DailyDigest, config: dict
) -> DailyDigest:
    """Add AI-generated summaries to digest items.

    Parameters
    ----------
    digest:
        The daily digest whose items should be summarized.
    config:
        Full application configuration.  Expected key:

        ``config["ai_summary"]``::

            {
                "enabled": bool,
                "api_key": str,
                "model": str,              # default "claude-haiku-4-5-20251001"
                "max_items_per_domain": int # default 5
            }

    Returns
    -------
    DailyDigest
        A **new** DailyDigest with ``summary`` fields populated on items
        that were summarized.  Original digest is never mutated.
    """
    ai_cfg = config.get("ai_summary", {})

    if not ai_cfg.get("enabled", False):
        logger.debug("AI summarization disabled, skipping")
        return digest

    api_key = ai_cfg.get("api_key", "")
    if not api_key:
        logger.warning("AI summarization enabled but no api_key configured, skipping")
        return digest

    model = ai_cfg.get("model", _DEFAULT_MODEL)
    max_per_domain: int = ai_cfg.get("max_items_per_domain", _DEFAULT_MAX_ITEMS_PER_DOMAIN)

    client = anthropic.AsyncAnthropic(api_key=api_key)

    # Group items by domain and take the top N per domain
    domain_groups: dict[str, list[Item]] = {}
    for item in digest.items:
        domain_groups.setdefault(item.domain, []).append(item)

    # Build a map from url_hash -> Item for all items in the digest
    item_by_hash: dict[str, Item] = {item.url_hash: item for item in digest.items}

    # Process each domain in parallel would be ideal, but we batch per domain
    # into a single API call for efficiency.
    all_summaries: dict[str, str] = {}

    for domain, items in domain_groups.items():
        # Skip items that already have a cached summary
        uncached_items: list[Item] = []
        for item in items[:max_per_domain]:
            cached = _summary_cache.get(item.url_hash)
            if cached is not None:
                all_summaries[item.url_hash] = cached
            else:
                uncached_items.append(item)

        if not uncached_items:
            continue

        try:
            summaries = await _summarize_batch(uncached_items, client, model)
            for url_hash, summary in summaries.items():
                if len(_summary_cache) >= _CACHE_MAX_SIZE:
                    _summary_cache.pop(next(iter(_summary_cache)))
                _summary_cache[url_hash] = summary
                all_summaries[url_hash] = summary
        except Exception:
            logger.error(
                "Failed to summarize batch for domain '%s', skipping",
                domain,
                exc_info=True,
            )

    # Build a new DailyDigest with updated items (immutable pattern)
    updated_items: list[Item] = []
    for item in digest.items:
        summary_text = all_summaries.get(item.url_hash)
        if summary_text is not None:
            updated_items.append(replace(item, summary=summary_text))
        else:
            updated_items.append(item)

    return DailyDigest(
        date=digest.date,
        items=updated_items,
        item_count=len(updated_items),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _summarize_batch(
    items: list[Item],
    client: anthropic.AsyncAnthropic,
    model: str,
) -> dict[str, str]:
    """Send a batch of items to Claude for summarization.

    Parameters
    ----------
    items:
        Items to summarize (should be a single domain's top items).
    client:
        An ``anthropic.AsyncAnthropic`` client instance.
    model:
        Model identifier to use.

    Returns
    -------
    dict[str, str]
        Mapping of ``item.url_hash`` -> summary text.
    """
    if not items:
        return {}

    user_payload: list[dict[str, str]] = [
        {"title": item.title, "url": item.url, "raw_text": item.raw_text}
        for item in items
    ]

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Summarize each of the following news items. "
                        "Return a JSON object mapping each URL to its summary.\n\n"
                        f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
                    ),
                }
            ],
        )
    except anthropic.APIError as exc:
        logger.error("Anthropic API error during summarization: %s", exc)
        return {}
    except Exception as exc:
        logger.error("Unexpected error calling Claude API: %s", exc)
        return {}

    # Extract text from the response
    response_text = _extract_response_text(response)
    if not response_text:
        logger.warning("Empty response from Claude API")
        return {}

    # Parse the JSON mapping from the response
    summaries = _parse_summary_response(response_text, items)
    return summaries


def _extract_response_text(response: Any) -> str:
    """Extract the text content from a Claude API response."""
    try:
        content_blocks = response.content
        text_parts: list[str] = []
        for block in content_blocks:
            if getattr(block, "type", "") == "text":
                text_parts.append(block.text)
        return "\n".join(text_parts)
    except Exception:
        return ""


def _parse_summary_response(
    response_text: str, items: list[Item]
) -> dict[str, str]:
    """Parse the JSON summary response, mapping URLs to summaries.

    Falls back to assigning the full response text to each item if
    JSON parsing fails.
    """
    # Try to extract JSON from the response (may be wrapped in markdown)
    text = response_text.strip()
    if text.startswith("```"):
        # Strip markdown code fences
        lines = text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse Claude response as JSON, using fallback")
        # Fallback: assign a generic summary to each item
        return {item.url_hash: response_text[:200] for item in items}

    # Build the url_hash -> summary mapping
    # The response may use full URLs as keys; map them back to url_hashes
    url_to_hash = {item.url: item.url_hash for item in items}
    result: dict[str, str] = {}

    for key, summary in parsed.items():
        url_hash = url_to_hash.get(key)
        if url_hash is not None:
            result[url_hash] = str(summary)
        else:
            # Key might be a URL that doesn't exactly match; try substring match
            for url, h in url_to_hash.items():
                if key in url or url in key:
                    result[h] = str(summary)
                    break

    return result
