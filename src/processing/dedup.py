"""Deduplication module for the daily hot topics aggregator.

Provides URL-exact and fuzzy title-based deduplication using
difflib.SequenceMatcher. All functions are pure (no side effects)
and follow immutable patterns.
"""

import logging
from difflib import SequenceMatcher
from typing import Sequence

from src.models import Item

logger = logging.getLogger(__name__)

__all__ = ["deduplicate"]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def deduplicate(
    items: Sequence[Item],
    threshold: float = 0.85,
    window_hours: int = 24,
) -> list[Item]:
    """Remove duplicate items from the list.

    Deduplication happens in two passes:
      1. **Exact URL dedup** -- identical URLs are collapsed immediately,
         keeping the item with the highest *score* (ties broken by
         original order).
      2. **Fuzzy title dedup** -- among items whose ``published_at``
         timestamps fall within *window_hours* of each other, titles that
         reach *threshold* similarity (0-1) are considered duplicates.
         The item with the highest *score* from each duplicate group is
         kept.

    Parameters
    ----------
    items:
        The raw item list.
    threshold:
        SequenceMatcher ratio at or above which two titles count as
        duplicates (default ``0.85``).
    window_hours:
        Only compare items whose ``published_at`` values are within this
        many hours of each other (default ``24``).

    Returns
    -------
    list[Item]
        De-duplicated list preserving the original score-descending order.
    """
    if not items:
        return []

    # 1. Exact URL dedup ---------------------------------------------------
    url_deduped = _dedup_by_url(list(items))
    logger.debug(
        "URL dedup: %d items -> %d items", len(items), len(url_deduped),
    )

    # 2. Fuzzy title dedup -------------------------------------------------
    result = _dedup_by_title_fuzzy(url_deduped, threshold, window_hours)
    logger.debug(
        "Title dedup (threshold=%.2f, window=%dh): %d items -> %d items",
        threshold,
        window_hours,
        len(url_deduped),
        len(result),
    )

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _dedup_by_url(items: list[Item]) -> list[Item]:
    """Collapse items with identical URLs, keeping the highest-scored one."""
    seen_hashes: dict[str, Item] = {}
    ordered_hashes: list[str] = []  # preserve insertion order

    for item in items:
        h = item.url_hash
        existing = seen_hashes.get(h)
        if existing is None:
            seen_hashes[h] = item
            ordered_hashes.append(h)
        else:
            # Keep the higher-scored item; ties keep the earlier one.
            if item.score > existing.score:
                seen_hashes[h] = item

    return [seen_hashes[h] for h in ordered_hashes]


def _dedup_by_title_fuzzy(
    items: list[Item],
    threshold: float,
    window_hours: int,
) -> list[Item]:
    """Group items by fuzzy title similarity within a time window and keep
    the highest-scored item from each group while preserving order."""

    if len(items) <= 1:
        return list(items)

    # Sort a working copy by score descending (highest first) so that when
    # we pick the representative of a group it is the best item.
    scored_items = sorted(enumerate(items), key=lambda p: p[1].score, reverse=True)

    # Union-Find to merge duplicate clusters ------------------------------
    parent: dict[int, int] = {idx: idx for idx, _ in scored_items}

    def _find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path compression
            x = parent[x]
        return x

    def _union(a: int, b: int) -> None:
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[ra] = rb

    # Compare titles pairwise ----------------------------------------------
    n = len(scored_items)
    for i in range(n):
        idx_i, item_i = scored_items[i]
        if item_i.published_at is None:
            continue
        for j in range(i + 1, n):
            idx_j, item_j = scored_items[j]
            if item_j.published_at is None:
                continue

            # Time-window gate
            delta = abs((item_i.published_at - item_j.published_at).total_seconds())
            if delta > window_hours * 3600:
                continue

            # Early exit: if titles are identical strings, always merge
            if item_i.title == item_j.title:
                _union(idx_i, idx_j)
                continue

            ratio = SequenceMatcher(None, item_i.title, item_j.title).ratio()
            if ratio >= threshold:
                _union(idx_i, idx_j)

    # Build groups --------------------------------------------------------
    groups: dict[int, list[int]] = {}
    for idx, _ in scored_items:
        root = _find(idx)
        groups.setdefault(root, []).append(idx)

    # One representative per group (the item with highest score, which is
    # the first in scored_items because of the descending sort).
    representative_indices: set[int] = set()
    for members in groups.values():
        representative_indices.add(min(members))  # min = highest score index

    # Return in the *original* order --------------------------------------
    original_order = sorted(representative_indices)
    return [items[i] for i in original_order]
