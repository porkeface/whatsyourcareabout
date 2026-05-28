"""Processing pipeline for the daily hot topics aggregator."""

from src.processing.dedup import deduplicate
from src.processing.enrichment import enrich_items
from src.processing.ranker import normalize_scores, rank_items

__all__ = ["deduplicate", "enrich_items", "normalize_scores", "rank_items"]
