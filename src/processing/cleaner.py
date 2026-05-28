"""Content cleaning utilities for stripping HTML and normalizing text."""

from __future__ import annotations

import re
from html import unescape

from bs4 import BeautifulSoup


def strip_html(text: str) -> str:
    """Remove HTML tags and decode entities, preserving text content."""
    if not text:
        return ""
    soup = BeautifulSoup(text, "html.parser")
    # Remove script and style elements
    for tag in soup(["script", "style"]):
        tag.decompose()
    plain = soup.get_text(separator=" ", strip=True)
    return unescape(plain)


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/newlines into single space."""
    if not text:
        return ""
    return re.sub(r"\s+", " ", text).strip()


def smart_truncate(text: str, max_len: int = 300) -> str:
    """Truncate at sentence boundary (. or 。) or word boundary."""
    if not text or len(text) <= max_len:
        return text

    # Try to find sentence boundary before max_len
    truncated = text[:max_len]

    # Look for last sentence boundary
    last_period = max(
        truncated.rfind(". "),
        truncated.rfind("。"),
        truncated.rfind("！"),
        truncated.rfind("？"),
    )
    if last_period > max_len * 0.5:  # At least 50% of text preserved
        return truncated[: last_period + 1].rstrip() + "..."

    # Fall back to word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_len * 0.5:
        return truncated[:last_space].rstrip() + "..."

    # Hard cut
    return truncated.rstrip() + "..."


def clean_text(text: str, max_len: int = 0) -> str:
    """Full cleaning pipeline: strip HTML -> normalize whitespace -> truncate."""
    result = strip_html(text)
    result = normalize_whitespace(result)
    if max_len > 0:
        result = smart_truncate(result, max_len)
    return result
