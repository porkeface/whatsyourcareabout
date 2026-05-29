"""Shared domain constants for WYCA.

Used by renderers (markdown, html) and the frontend.
"""

DOMAIN_EMOJI: dict[str, str] = {
    "ai": "\U0001f916",
    "finance": "\U0001f4b0",
    "academic": "\U0001f4da",
    "tech": "\U0001f4bb",
    "general": "\U0001f4f0",
    "social": "\U0001f310",
}

DOMAIN_LABEL: dict[str, str] = {
    "ai": "AI / Machine Learning",
    "finance": "Finance",
    "academic": "Academic",
    "tech": "Technology",
    "general": "General",
    "social": "Social",
}

DOMAIN_ORDER = ["ai", "finance", "academic", "tech", "general", "social"]
