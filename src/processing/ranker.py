"""Scoring and ranking module for the daily hot topics aggregator.

Computes a composite final score for each item combining source weight,
engagement signal, and recency decay. Items are then grouped by domain
and sorted by final score within each domain.
"""

import logging
from dataclasses import replace
from datetime import datetime, timezone
from typing import Sequence

from src.models import Item

logger = logging.getLogger(__name__)

__all__ = ["normalize_scores", "rank_items"]

# Default domain buckets for grouping
_DOMAIN_ORDER: list[str] = [
    "ai",
    "finance",
    "academic",
    "tech",
    "general",
    "social",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def normalize_scores(items: Sequence[Item]) -> list[Item]:
    """Normalize item scores to the 0-1 range.

    The normalization is performed per-source: within each source group the
    highest score becomes 1.0 and the lowest becomes 0.0.  Items with
    identical scores receive the same normalized value.

    Parameters
    ----------
    items:
        The item list.

    Returns
    -------
    list[Item]
        New list with ``score`` values normalized to [0, 1].  The original
        items are **never** mutated.
    """
    if not items:
        return []

    # Group by source
    source_groups: dict[str, list[tuple[int, Item]]] = {}
    for idx, item in enumerate(items):
        source_groups.setdefault(item.source, []).append((idx, item))

    normalized: list[tuple[int, float]] = []

    for source_items in source_groups.values():
        scores = [item.score for _, item in source_items]
        min_score = min(scores)
        max_score = max(scores)
        spread = max_score - min_score

        for idx, item in source_items:
            if spread == 0:
                norm = 0.0 if max_score == 0 else 1.0
            else:
                norm = (item.score - min_score) / spread
            normalized.append((idx, norm))

    # Rebuild list in original order with new scores
    norm_map = {idx: val for idx, val in normalized}
    return [
        replace(item, score=norm_map[i])
        for i, item in enumerate(items)
    ]


def rank_items(items: Sequence[Item], config: dict) -> dict[str, list[Item]]:
    """Score, rank, group, and limit items per domain.

    The composite score is::

        final_score = source_weight * engagement_signal * recency_decay

    where:

    * ``source_weight`` comes from ``config["sources"][source]["weight"]``
      (default ``1.0``).
    * ``engagement_signal`` is the item's score normalized to 0-1 within
      its source group (via :func:`normalize_scores`).
    * ``recency_decay = 2 ** (-(hours_since_publish / half_life))`` with
      ``half_life`` from ``config["processing"]["recency_half_life_hours"]``
      (default ``12``).

    After scoring, items are bucketed by ``domain``, sorted by
    ``final_score`` descending, and each domain is capped at
    ``max_items_per_domain`` (default ``10``).

    Parameters
    ----------
    items:
        The deduplicated item list.
    config:
        The full application configuration dictionary.

    Returns
    -------
    dict[str, list[Item]]
        Mapping of domain name to a sorted (highest first) list of Items,
        each carrying a ``final_score`` attribute attached via a ``replace``
        call (score field is reused for the final score since there is only
        one score field on the dataclass).
    """
    if not items:
        return {d: [] for d in _DOMAIN_ORDER}

    processing_cfg = config.get("processing", {})
    sources_cfg = config.get("sources", {})

    half_life: float = processing_cfg.get("recency_half_life_hours", 12)
    max_per_domain: int = processing_cfg.get("max_items_per_domain", 10)

    # 1. Normalize engagement signal per source ---------------------------
    normalized = normalize_scores(items)

    # 2. Compute final score for each item --------------------------------
    now = datetime.now(timezone.utc)
    scored_items: list[tuple[Item, str, float]] = []

    for item in normalized:
        base_source = item.source.split(":")[0]
        source_cfg = sources_cfg.get(base_source, {})
        source_weight: float = source_cfg.get("weight", 1.0)
        engagement = item.score  # already 0-1 after normalization

        recency = _recency_decay(item.published_at, now, half_life)

        final_score = source_weight * engagement * recency
        scored_items.append((item, item.domain, final_score))

    # 3. Group by domain ---------------------------------------------------
    domain_groups: dict[str, list[tuple[Item, float]]] = {d: [] for d in _DOMAIN_ORDER}
    for item, domain, final_score in scored_items:
        bucket = domain if domain in domain_groups else "general"
        domain_groups[bucket].append((item, final_score))

    # 4. Sort each group and apply limit -----------------------------------
    result: dict[str, list[Item]] = {}
    for domain, pairs in domain_groups.items():
        pairs.sort(key=lambda p: p[1], reverse=True)
        limited = pairs[:max_per_domain]
        # Attach final_score to the item via immutable replace
        ranked = [
            replace(item, score=fs) for item, fs in limited
        ]
        result[domain] = ranked

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _recency_decay(
    published_at: datetime | None,
    now: datetime,
    half_life: float,
) -> float:
    """Compute exponential recency decay.

    ``decay = 2 ** (-(hours / half_life))``

    Items without a ``published_at`` timestamp receive a decay of ``1.0``
    (treated as freshly published) so they are not unfairly penalized.
    """
    if published_at is None or half_life <= 0:
        return 1.0

    # Ensure both datetimes are timezone-aware for correct subtraction
    pub = published_at if published_at.tzinfo is not None else published_at.replace(tzinfo=timezone.utc)

    hours = max((now - pub).total_seconds() / 3600.0, 0.0)
    return 2 ** (-(hours / half_life))
