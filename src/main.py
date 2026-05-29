"""WYCA - Daily Hot Topics Aggregator.

Main entry point for collecting, processing, and rendering daily digests.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from src.config import load_config
from src.database import (
    get_connection,
    get_recent_items,
    get_summaries_by_urls,
    init_db,
    insert_items,
)
from src.models import DailyDigest
from src.output.html_renderer import render_html
from src.output.markdown_renderer import render_markdown

logger = logging.getLogger("wyca")

# Mapping from config source key to collector class and module path
COLLECTOR_REGISTRY: dict[str, tuple[str, str]] = {
    "hacker_news": ("src.sources.hacker_news", "HackerNewsCollector"),
    "reddit": ("src.sources.reddit", "RedditCollector"),
    "arxiv": ("src.sources.arxiv_collector", "ArxivCollector"),
    "github_trending": ("src.sources.github_trending", "GitHubTrendingCollector"),
    "rss": ("src.sources.rss_collector", "RSSCollector"),
    "newsapi": ("src.sources.newsapi_source", "NewsAPICollector"),
    "finnhub": ("src.sources.finnhub", "FinnhubCollector"),
    "rsshub": ("src.sources.rsshub_collector", "RSSHubCollector"),
    "dailyhot": ("src.sources.dailyhot_collector", "DailyHotCollector"),
}


def _import_collector(module_path: str, class_name: str) -> type:
    """Dynamically import a collector class."""
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def _run_collector_safe(collector_cls: type, config: dict) -> list:
    """Run a single collector with error isolation."""
    source_key = None
    for key, (_, cls) in COLLECTOR_REGISTRY.items():
        if cls == collector_cls.__name__:
            source_key = key
            break

    try:
        collector = collector_cls(config)
        items = await collector.collect()
        await collector.close()
        return items
    except Exception:
        logger.error(
            "Collector %s failed unexpectedly",
            source_key or collector_cls.__name__,
            exc_info=True,
        )
        return []


async def run_daily_digest(config: dict, date_override: str | None = None) -> None:
    """Execute the full daily digest pipeline.

    Steps:
        1. Initialize the database
        2. Create and run all enabled collectors in parallel
        3. Insert collected items into the database
        4. Retrieve recent items from the database
        5. Deduplicate items
        6. Rank items by score
        7. Build a DailyDigest
        8. Render and save outputs (markdown, html)
        9. Optionally push to Telegram
    """
    date_str = date_override or datetime.now(UTC).strftime("%Y-%m-%d")
    logger.info("Starting daily digest pipeline for %s", date_str)

    # 1. Initialize database
    init_db()
    logger.info("Database initialized")

    # 2. Create enabled collectors and run in parallel
    sources_config = config.get("sources", {})
    collectors_to_run: list[tuple[str, type]] = []

    for source_key, registry_entry in COLLECTOR_REGISTRY.items():
        source_cfg = sources_config.get(source_key, {})
        if not source_cfg.get("enabled", False):
            logger.debug("Skipping disabled source: %s", source_key)
            continue
        module_path, class_name = registry_entry
        try:
            collector_cls = _import_collector(module_path, class_name)
            collectors_to_run.append((source_key, collector_cls))
        except (ImportError, AttributeError) as exc:
            logger.warning(
                "Could not import collector for %s: %s", source_key, exc
            )

    if not collectors_to_run:
        logger.warning("No enabled collectors found in config")
        return

    logger.info(
        "Running %d collectors: %s",
        len(collectors_to_run),
        [name for name, _ in collectors_to_run],
    )

    tasks = [
        _run_collector_safe(cls, config)
        for _, cls in collectors_to_run
    ]
    results = await asyncio.gather(*tasks)

    # 3. Insert items into database
    all_items = []
    for (source_key, _), items in zip(collectors_to_run, results):
        all_items.extend(items)
        logger.info("Source %s returned %d items", source_key, len(items))

    if not all_items:
        logger.warning("No items collected from any source")
        return

    conn = get_connection()
    try:
        inserted = insert_items(all_items, conn)
        logger.info(
            "Inserted %d new items (%d total collected)", inserted, len(all_items)
        )
    finally:
        conn.close()

    # 4. Get recent items from DB
    recent_items = get_recent_items(hours=24)
    logger.info("Retrieved %d recent items from DB", len(recent_items))

    # 5. Dedup
    try:
        from src.processing.dedup import deduplicate

        deduped = deduplicate(recent_items)
        logger.info("After dedup: %d items", len(deduped))
    except ImportError:
        logger.warning("Dedup module not available, skipping")
        deduped = recent_items
    except Exception as exc:
        logger.error("Dedup failed: %s", exc)
        deduped = recent_items

    # 5.5. Enrich items with missing descriptions
    try:
        from src.processing.enrichment import enrich_items

        proxy = config.get("proxy")
        deduped = await enrich_items(deduped, proxy=proxy)
        logger.info("Enrichment complete")
    except ImportError:
        logger.warning("Enrichment module not available, skipping")
    except Exception as exc:
        logger.error("Enrichment failed: %s", exc)

    # 6. Rank
    try:
        from src.processing.ranker import rank_items

        ranked_by_domain = rank_items(deduped, config)
        ranked = [item for items in ranked_by_domain.values() for item in items]
        logger.info("After ranking: %d items", len(ranked))
    except ImportError:
        logger.warning("Ranker module not available, skipping")
        ranked = sorted(deduped, key=lambda x: x.score, reverse=True)
    except Exception as exc:
        logger.error("Ranker failed: %s", exc)
        ranked = sorted(deduped, key=lambda x: x.score, reverse=True)

    # 7. Build DailyDigest
    digest = DailyDigest(date=date_str, items=ranked, item_count=len(ranked))
    logger.info(
        "Daily digest built: %d items for %s", digest.item_count, digest.date
    )

    # 7.5. AI Summarization (optional)
    ai_config = config.get("ai_summary", {})
    if ai_config.get("enabled", False):
        try:
            from src.processing.summarizer import summarize_digest

            digest = await summarize_digest(digest, config)
            logger.info("AI summarization complete")
        except ImportError:
            logger.warning("Summarizer module not available, skipping")
        except Exception as exc:
            logger.error("AI summarization failed: %s", exc)

    # 7.6. Persist summaries to DB (load any DB-cached summaries into digest)
    digest = _load_summaries_from_db(digest)
    logger.info("Summary persistence step complete")

    # 8. Render and save outputs
    output_config = config.get("output", {})
    output_dir = Path(output_config.get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    formats = output_config.get("formats", ["markdown", "html"])
    md_content: str | None = None
    html_content: str | None = None

    if "markdown" in formats:
        try:
            md_content = render_markdown(digest)
            md_path = output_dir / f"{date_str}.md"
            md_path.write_text(md_content, encoding="utf-8")
            logger.info("Markdown saved to %s", md_path)
        except Exception as exc:
            logger.error("Markdown rendering failed: %s", exc)

    if "html" in formats:
        try:
            html_content = render_html(digest)
            html_path = output_dir / f"{date_str}.html"
            html_path.write_text(html_content, encoding="utf-8")
            logger.info("HTML saved to %s", html_path)
        except Exception as exc:
            logger.error("HTML rendering failed: %s", exc)

    # 9. Optionally push to Telegram
    telegram_config = output_config.get("telegram", {})
    if telegram_config.get("enabled", False):
        from src.output.telegram_push import push_to_telegram

        bot_token = telegram_config.get("bot_token", "")
        chat_id = telegram_config.get("chat_id", "")

        if not bot_token or not chat_id:
            logger.error("Telegram enabled but bot_token or chat_id not configured")
        else:
            # Prefer markdown for Telegram; fall back to plain text summary
            tg_text = md_content or _build_plain_summary(digest)
            sent = await push_to_telegram(bot_token, chat_id, tg_text)
            if sent:
                logger.info("Telegram push completed successfully")
            else:
                logger.error("Telegram push had failures")

    logger.info("Daily digest pipeline complete for %s", date_str)


def _load_summaries_from_db(digest: DailyDigest) -> DailyDigest:
    """Load persisted summaries from SQLite for items missing summaries.

    After the summarizer runs, some items may have summaries in the DB
    (from a previous run) that were not in the in-memory cache. This
    function loads those and merges them into the digest using immutable
    replacement.
    """
    from dataclasses import replace

    items_without_summary = [item for item in digest.items if not item.summary]
    if not items_without_summary:
        return digest

    urls = [item.url for item in items_without_summary]
    try:
        conn = get_connection()
        try:
            url_summaries = get_summaries_by_urls(urls, conn)
        finally:
            conn.close()
    except Exception:
        logger.error("Failed to load summaries from DB", exc_info=True)
        return digest

    if not url_summaries:
        return digest

    updated_items: list[Item] = []
    loaded_count = 0
    for item in digest.items:
        if not item.summary and item.url in url_summaries:
            entry = url_summaries[item.url]
            updated_items.append(replace(
                item,
                summary=entry.get("summary", ""),
                summary_zh=entry.get("summary_zh", ""),
                title_zh=entry.get("title_zh", ""),
            ))
            loaded_count += 1
        else:
            updated_items.append(item)

    if loaded_count:
        logger.info("Loaded %d summaries from SQLite into digest", loaded_count)

    return DailyDigest(
        date=digest.date,
        items=updated_items,
        item_count=len(updated_items),
    )


def _build_plain_summary(digest: DailyDigest) -> str:
    """Build a simple plain-text summary when markdown is not available."""
    lines = [
        f"WYCA Daily Digest - {digest.date}",
        f"{digest.item_count} items collected",
        "",
    ]
    for item in digest.items[:20]:
        lines.append(f"- [{item.source}] {item.title}")
        lines.append(f"  {item.url}")
    return "\n".join(lines)


def _handle_init(config_path: str) -> None:
    """Initialize the database and create required directories."""
    logger.info("Initializing WYCA database...")
    init_db()
    logger.info("Database initialized successfully")

    config = load_config(config_path)
    output_dir = Path(config.get("output", {}).get("output_dir", "./output"))
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Output directory ready: %s", output_dir.resolve())

    logger.info("Initialization complete")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="wyca",
        description="WYCA - Daily Hot Topics Aggregator",
    )
    parser.add_argument(
        "command",
        choices=["run", "init"],
        help="Command to execute: 'run' to collect and render, 'init' to set up DB",
    )
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to config file (default: config.yaml)",
    )
    parser.add_argument(
        "--date",
        default=None,
        help="Date override in YYYY-MM-DD format",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()
    _setup_logging(verbose=args.verbose)

    try:
        config = load_config(args.config)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        sys.exit(1)
    except Exception as exc:
        logger.error("Failed to load config: %s", exc)
        sys.exit(1)

    if args.command == "init":
        _handle_init(args.config)
        return

    if args.command == "run":
        asyncio.run(run_daily_digest(config, date_override=args.date))


if __name__ == "__main__":
    main()
