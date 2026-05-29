"""AI-powered summarization module for the daily hot topics aggregator.

Supports any OpenAI-compatible API (MiMo, DeepSeek, GPT, Claude via proxy, etc.)
Configure via config.yaml ai_summary section with provider, base_url, api_key, model.

Caching strategy:
    L1: in-memory dict (_summary_cache) keyed by url_hash for fast lookups
    L2: SQLite items.summary column for persistence across restarts
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import replace

from openai import AsyncOpenAI

from src.models import DailyDigest, Item

logger = logging.getLogger(__name__)

__all__ = ["summarize_digest"]

# Lock to protect os.environ proxy mutation from concurrent threads
_proxy_lock = threading.Lock()

_DEFAULT_MODEL = "mimo-v2.5-pro"
_DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"
_DEFAULT_MAX_ITEMS_PER_DOMAIN = 50

_SYSTEM_PROMPT = (
    "你是一个新闻摘要助手。对于每条新闻，你需要完成三个任务：\n"
    "1. 将标题翻译为中文（title_zh）\n"
    "2. 用英文写1-2句摘要（summary），简洁、信息丰富，聚焦关键事实或影响\n"
    "3. 用中文写1-2句摘要（summary_zh），简洁、信息丰富，聚焦关键事实或影响\n"
    "如果只有标题没有正文，根据标题推断主题并写一句简要背景。\n"
    "summary必须是英文，summary_zh必须是中文。"
)

# L1: In-memory summary cache keyed by URL hash (bounded to prevent memory leak)
_summary_cache: dict[str, str] = {}
# Mapping from url_hash -> url, needed for SQLite L2 lookups/persistence
_hash_to_url: dict[str, str] = {}
_CACHE_MAX_SIZE = 2000

# Threshold below which raw_text is considered too short for summarization
_MIN_RAW_TEXT_LENGTH = 50


async def summarize_digest(
    digest: DailyDigest, config: dict
) -> DailyDigest:
    """Add AI-generated summaries to digest items.

    Caching layers:
        1. Pre-populate L1 (in-memory) from L2 (SQLite) for items in this digest
        2. Check L1 before calling AI
        3. After AI generates summaries, write to both L1 and L2

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

    # Pre-populate L1 cache from L2 (SQLite) for items in this digest
    _hydrate_cache_from_db(digest.items)

    base_url = ai_cfg.get("base_url", _DEFAULT_BASE_URL)
    model = ai_cfg.get("model", _DEFAULT_MODEL)
    max_per_domain: int = ai_cfg.get("max_items_per_domain", _DEFAULT_MAX_ITEMS_PER_DOMAIN)
    proxy = config.get("proxy")

    client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    # Group items by domain and take the top N per domain
    domain_groups: dict[str, list[Item]] = {}
    for item in digest.items:
        domain_groups.setdefault(item.domain, []).append(item)

    # Process each domain: batch into a single API call per domain
    all_results: dict[str, dict[str, str]] = {}

    for domain, items in domain_groups.items():
        # Skip items that already have a cached summary (L1 hit)
        uncached_items: list[Item] = []
        for item in items[:max_per_domain]:
            cached = _summary_cache.get(item.url_hash)
            if cached is not None:
                all_results[item.url_hash] = cached
            else:
                uncached_items.append(item)

        if not uncached_items:
            continue

        try:
            results = await _summarize_batch(uncached_items, client, model, proxy)
            for url_hash, entry in results.items():
                if len(_summary_cache) >= _CACHE_MAX_SIZE:
                    evicted_hash = next(iter(_summary_cache))
                    _summary_cache.pop(evicted_hash)
                    _hash_to_url.pop(evicted_hash, None)
                _summary_cache[url_hash] = entry
                all_results[url_hash] = entry
        except Exception:
            logger.error(
                "Failed to summarize batch for domain '%s', skipping",
                domain,
                exc_info=True,
            )

    # Persist newly generated summaries to L2 (SQLite)
    _persist_new_summaries(all_results)

    # Build a new DailyDigest with updated items (immutable pattern)
    updated_items: list[Item] = []
    for item in digest.items:
        result = all_results.get(item.url_hash)
        if result is not None:
            updated_items.append(replace(
                item,
                summary=result.get("summary", ""),
                summary_zh=result.get("summary_zh", ""),
                title_zh=result.get("title_zh", ""),
            ))
        else:
            updated_items.append(item)

    return DailyDigest(
        date=digest.date,
        items=updated_items,
        item_count=len(updated_items),
    )


def _hydrate_cache_from_db(items: list[Item]) -> None:
    """Load existing summaries from SQLite into the in-memory L1 cache.

    Only fetches summaries for items not already in L1, using a single
    bulk query to avoid N+1 lookups.
    """
    # Build hash->url mapping for all items (cap _hash_to_url to prevent leak)
    for item in items:
        if len(_hash_to_url) >= _CACHE_MAX_SIZE * 2:
            _hash_to_url.pop(next(iter(_hash_to_url)))
        _hash_to_url[item.url_hash] = item.url

    # Identify items missing from L1
    missing_hashes = [item.url_hash for item in items if item.url_hash not in _summary_cache]
    if not missing_hashes:
        return

    missing_urls = [_hash_to_url[h] for h in missing_hashes]
    logger.debug("Hydrating L1 cache from SQLite for %d items", len(missing_urls))

    try:
        from src.database import get_connection, get_summaries_by_urls

        conn = get_connection()
        try:
            url_summaries = get_summaries_by_urls(missing_urls, conn)
        finally:
            conn.close()

        # Build reverse mapping url->hash for populating cache
        url_to_hash = {v: k for k, v in _hash_to_url.items()}
        hydrated = 0
        for url, entry in url_summaries.items():
            url_hash = url_to_hash.get(url)
            if url_hash and url_hash not in _summary_cache:
                # Skip old entries missing title_zh or summary_zh — they need re-summarization
                if not entry.get("title_zh") or not entry.get("summary_zh"):
                    continue
                _summary_cache[url_hash] = entry
                hydrated += 1

        if hydrated:
            logger.info("Hydrated %d summaries from SQLite into L1 cache", hydrated)
    except Exception:
        logger.error("Failed to hydrate cache from SQLite", exc_info=True)


def _persist_new_summaries(all_results: dict[str, dict[str, str]]) -> None:
    """Persist summaries and title_zh that were newly generated to SQLite.

    Only writes entries whose URL is known in _hash_to_url and that were
    not already present in the DB.
    """
    try:
        from src.database import get_connection, update_item_summary_and_title

        conn = get_connection()
        try:
            persisted = 0
            for url_hash, entry in all_results.items():
                url = _hash_to_url.get(url_hash)
                if url and update_item_summary_and_title(
                    url,
                    entry.get("summary", ""),
                    entry.get("summary_zh", ""),
                    entry.get("title_zh", ""),
                    conn,
                ):
                    persisted += 1
            conn.commit()
            if persisted:
                logger.info("Persisted %d new summaries to SQLite", persisted)
        finally:
            conn.close()
    except Exception:
        logger.error("Failed to persist summaries to SQLite", exc_info=True)


async def _fetch_article_text(url: str, proxy: str | None = None) -> str:
    """Fetch and extract article body text from URL using trafilatura.

    Used as fallback when an item has no raw_text (enrichment failed or
    was skipped). Returns first 800 chars of extracted body, or '' on failure.
    """
    try:
        import os

        import trafilatura

        def _download() -> str | None:
            if not proxy:
                return trafilatura.fetch_url(url)
            with _proxy_lock:
                old_http = os.environ.get("HTTP_PROXY")
                old_https = os.environ.get("HTTPS_PROXY")
                try:
                    os.environ["HTTP_PROXY"] = proxy
                    os.environ["HTTPS_PROXY"] = proxy
                    return trafilatura.fetch_url(url)
                finally:
                    if old_http is None:
                        os.environ.pop("HTTP_PROXY", None)
                    else:
                        os.environ["HTTP_PROXY"] = old_http
                    if old_https is None:
                        os.environ.pop("HTTPS_PROXY", None)
                    else:
                        os.environ["HTTPS_PROXY"] = old_https

        downloaded: str | None = await asyncio.to_thread(_download)
        if not downloaded:
            return ""

        def _extract() -> str:
            return trafilatura.extract(downloaded, include_comments=False) or ""

        text: str = await asyncio.to_thread(_extract)
        if text:
            return text[:800]
    except Exception:
        logger.debug("Could not fetch article text from %s", url)

    return ""


_BATCH_SIZE = 10  # Items per LLM API call to avoid token limits


async def _summarize_batch(
    items: list[Item],
    client: AsyncOpenAI,
    model: str,
    proxy: str | None = None,
) -> dict[str, dict[str, str]]:
    """Send a batch of items to the LLM for summarization.

    For items with empty/short raw_text, fetches article content first.
    Splits into sub-batches of _BATCH_SIZE to avoid token limits.
    Returns dict mapping item.url_hash -> {"title_zh": ..., "summary": ...}.
    """
    if not items:
        return {}

    # Fetch article text for items with insufficient raw_text
    enriched_items: list[Item] = []
    for item in items:
        if len(item.raw_text.strip()) < _MIN_RAW_TEXT_LENGTH:
            article_text = await _fetch_article_text(item.url, proxy)
            if article_text:
                enriched_items.append(replace(item, raw_text=article_text))
            else:
                enriched_items.append(item)
        else:
            enriched_items.append(item)

    # Split into sub-batches to avoid exceeding LLM context window
    all_results: dict[str, dict[str, str]] = {}
    for i in range(0, len(enriched_items), _BATCH_SIZE):
        sub_batch = enriched_items[i : i + _BATCH_SIZE]
        result = await _call_llm(sub_batch, client, model)
        all_results.update(result)

    return all_results


async def _call_llm(
    items: list[Item],
    client: AsyncOpenAI,
    model: str,
) -> dict[str, dict[str, str]]:
    """Call LLM API for a single sub-batch of items.

    Returns dict mapping url_hash -> {"title_zh": ..., "summary": ...}.
    """
    user_payload: list[dict[str, str]] = [
        {"title": item.title, "url": item.url, "raw_text": item.raw_text}
        for item in items
    ]

    prompt = (
        "将以下每条新闻翻译标题为中文，并分别用英文和中文写摘要。\n"
        "返回一个JSON对象，key为URL，value为对象包含title_zh、summary、summary_zh三个字段。\n"
        "summary用英文写，summary_zh用中文写。\n"
        "示例: {\"https://example.com\": {\"title_zh\": \"中文标题\", \"summary\": \"English summary\", \"summary_zh\": \"中文摘要\"}}\n"
        "只返回JSON，不要markdown，不要解释。\n\n"
        f"{json.dumps(user_payload, ensure_ascii=False, indent=2)}"
    )

    for attempt in range(2):
        try:
            response = await client.chat.completions.create(
                model=model,
                max_tokens=8192,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            logger.error("LLM API error during summarization: %s", exc)
            return {}

        response_text = response.choices[0].message.content or ""
        if not response_text:
            logger.warning("Empty LLM response, attempt %d/2", attempt + 1)
            continue

        result = _parse_summary_response(response_text, items)
        if result:
            return result
        logger.warning("JSON parse failed on attempt %d/2, retrying", attempt + 1)

    return {}


def _parse_summary_response(
    response_text: str, items: list[Item]
) -> dict[str, dict[str, str]]:
    """Parse the JSON summary response, mapping URLs to {title_zh, summary}.

    Handles markdown code blocks, extra text around JSON, and fuzzy URL matching.
    Returns empty dict if parsing fails completely.
    """
    text = response_text.strip()

    # Strip markdown code blocks
    if "```" in text:
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines).strip()

    # Try to extract JSON object from surrounding text
    if not text.startswith("{"):
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Failed to parse LLM response as JSON: %s...", text[:100])
        return {}

    if not isinstance(parsed, dict):
        return {}

    url_to_hash = {item.url: item.url_hash for item in items}
    result: dict[str, dict[str, str]] = {}

    def _normalize_entry(entry):
        """Accept both new {title_zh, summary, summary_zh} and old formats."""
        if isinstance(entry, str):
            return {"title_zh": "", "summary": entry, "summary_zh": ""}
        if isinstance(entry, dict):
            return {
                "title_zh": str(entry.get("title_zh", "")),
                "summary": str(entry.get("summary", "")),
                "summary_zh": str(entry.get("summary_zh", "")),
            }
        return None

    # Strategy 1: Exact URL match
    for key, entry in parsed.items():
        normalized = _normalize_entry(entry)
        if not normalized or not normalized["summary"]:
            continue
        url_hash = url_to_hash.get(key)
        if url_hash is not None:
            result[url_hash] = normalized

    # Strategy 2: Partial URL match (last path segment)
    if len(result) < len(items):
        unmatched = [i for i in items if i.url_hash not in result]
        for key, entry in parsed.items():
            normalized = _normalize_entry(entry)
            if not normalized or not normalized["summary"]:
                continue
            key_parts = key.rstrip("/").split("/")
            key_tail = key_parts[-1] if key_parts else ""
            if len(key_tail) < 10:
                continue
            for item in unmatched:
                if item.url_hash in result:
                    continue
                if key_tail in item.url:
                    result[item.url_hash] = normalized
                    break

    # Never return partial results that are too small
    if len(result) < len(items) // 2:
        logger.debug(
            "Only matched %d/%d items, discarding partial result",
            len(result), len(items),
        )
        return {}

    return result
