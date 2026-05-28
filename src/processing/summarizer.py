"""AI-powered summarization module for the daily hot topics aggregator.

Supports any OpenAI-compatible API (MiMo, DeepSeek, GPT, Claude via proxy, etc.)
Configure via config.yaml ai_summary section with provider, base_url, api_key, model.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace

from openai import AsyncOpenAI

from src.models import DailyDigest, Item

logger = logging.getLogger(__name__)

__all__ = ["summarize_digest"]

_DEFAULT_MODEL = "MiMo"
_DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
_DEFAULT_MAX_ITEMS_PER_DOMAIN = 5

_SYSTEM_PROMPT = (
    "You are a news summarizer. For each item, write a 1-2 sentence "
    "summary in the SAME LANGUAGE as the title. Be concise and informative."
)

# In-memory summary cache keyed by URL hash (bounded to prevent memory leak)
_summary_cache: dict[str, str] = {}
_CACHE_MAX_SIZE = 500


async def summarize_digest(
    digest: DailyDigest, config: dict
) -> DailyDigest:
    """Add AI-generated summaries to digest items.

    Parameters
    ----------
    digest:
        The daily digest whose items should be summarized.
    config:
        Full application configuration.  Expected key::

            config["ai_summary"] = {
                "enabled": bool,
                "api_key": str,
                "base_url": str,           # default "https://api.siliconflow.cn/v1"
                "model": str,              # default "MiMo"
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

    base_url = ai_cfg.get("base_url", _DEFAULT_BASE_URL)
    model = ai_cfg.get("model", _DEFAULT_MODEL)
    max_per_domain: int = ai_cfg.get("max_items_per_domain", _DEFAULT_MAX_ITEMS_PER_DOMAIN)

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # Group items by domain and take the top N per domain
    domain_groups: dict[str, list[Item]] = {}
    for item in digest.items:
        domain_groups.setdefault(item.domain, []).append(item)

    # Process each domain: batch into a single API call per domain
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


async def _summarize_batch(
    items: list[Item],
    client: AsyncOpenAI,
    model: str,
) -> dict[str, str]:
    """Send a batch of items to the LLM for summarization.

    Returns dict mapping item.url_hash -> summary text.
    """
    if not items:
        return {}

    user_payload: list[dict[str, str]] = [
        {"title": item.title, "url": item.url, "raw_text": item.raw_text}
        for item in items
    ]

    try:
        response = await client.chat.completions.create(
            model=model,
            max_tokens=1024,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Summarize each of the following news items. "
                        "Return a JSON object mapping each URL to its summary.\n\n"
                        f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
                    ),
                },
            ],
        )
    except Exception as exc:
        logger.error("LLM API error during summarization: %s", exc)
        return {}

    # Extract text from the response
    response_text = response.choices[0].message.content or ""
    if not response_text:
        logger.warning("Empty response from LLM API")
        return {}

    # Parse the JSON mapping from the response
    summaries = _parse_summary_response(response_text, items)
    return summaries


def _parse_summary_response(
    response_text: str, items: list[Item]
) -> dict[str, str]:
    """Parse the JSON summary response, mapping URLs to summaries.

    Falls back to assigning the full response text to each item if
    JSON parsing fails.
    """
    text = response_text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON, using fallback")
        return {item.url_hash: response_text[:200] for item in items}

    url_to_hash = {item.url: item.url_hash for item in items}
    result: dict[str, str] = {}

    for key, summary in parsed.items():
        url_hash = url_to_hash.get(key)
        if url_hash is not None:
            result[url_hash] = str(summary)
        else:
            for url, h in url_to_hash.items():
                if key in url or url in key:
                    result[h] = str(summary)
                    break

    return result
