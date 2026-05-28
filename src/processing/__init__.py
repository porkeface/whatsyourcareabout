"""Processing pipeline for the daily hot topics aggregator."""

from src.processing.dedup import deduplicate
from src.processing.ranker import normalize_scores, rank_items

__all__ = ["deduplicate", "normalize_scores", "rank_items"]
