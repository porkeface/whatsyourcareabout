"""Render DailyDigest as a Markdown document with domain grouping."""

import logging
from datetime import datetime, timezone
from collections import defaultdict

from src.domain_constants import DOMAIN_EMOJI, DOMAIN_LABEL
from src.models import DailyDigest, Item

logger = logging.getLogger(__name__)


def _group_by_domain(items: list[Item]) -> dict[str, list[Item]]:
    """Group items by domain, preserving domain key order."""
    groups: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        groups[item.domain].append(item)
    return dict(groups)


def _score_bar(score: float) -> str:
    """Render a tiny visual score indicator."""
    if score <= 0:
        return ""
    filled = min(int(score / 50), 5)
    if filled < 1:
        return "▌"
    return "▌" * filled


def _format_item(item: Item) -> str:
    """Format a single item as a Markdown line."""
    score_str = f" **{item.score:.0f}**" if item.score else ""
    source_tag = f"`{item.source}`" if item.source else ""
    parts = [f"[{item.title}]({item.url})"]
    if source_tag:
        parts.append(source_tag)
    if score_str:
        parts.append(score_str)
    line = " ".join(parts)

    description = (item.summary or item.raw_text).strip()
    if description:
        description = description[:160]
        if len(item.summary or item.raw_text) > 160:
            description += " ..."
        line += f"\n  > {description}"

    return line


def render_markdown(digest: DailyDigest) -> str:
    """Render a DailyDigest into a Markdown string grouped by domain.

    Args:
        digest: The daily digest to render.

    Returns:
        A complete Markdown document.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    groups = _group_by_domain(digest.items)

    lines: list[str] = []
    lines.append(f"# \U0001f4e1 WYCA Daily Digest - {digest.date}")
    lines.append("")
    lines.append(
        f"> {digest.item_count} items collected from "
        f"{len({i.source for i in digest.items})} sources"
    )
    lines.append("")

    # Table of contents
    lines.append("## \U0001f4d1 Contents")
    lines.append("")
    for domain, items in groups.items():
        emoji = DOMAIN_EMOJI.get(domain, "\U0001f4cc")
        label = DOMAIN_LABEL.get(domain, domain.title())
        lines.append(f"- [{emoji} {label}](#{domain}) ({len(items)} items)")
    lines.append("")

    # Domain sections
    for domain, items in groups.items():
        emoji = DOMAIN_EMOJI.get(domain, "\U0001f4cc")
        label = DOMAIN_LABEL.get(domain, domain.title())
        lines.append(f"---")
        lines.append("")
        lines.append(f"## {emoji} {label}")
        lines.append("")

        sorted_items = sorted(items, key=lambda x: x.score, reverse=True)
        for idx, item in enumerate(sorted_items, 1):
            lines.append(f"{idx}. {_format_item(item)}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated at {now} by WYCA (What's Your Care About?)*")

    result = "\n".join(lines)
    logger.info(
        "Markdown rendered: %d items across %d domains",
        digest.item_count,
        len(groups),
    )
    return result
