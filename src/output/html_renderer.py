"""Render DailyDigest as a responsive HTML page with dark/light theme support."""

import logging
from collections import defaultdict
from datetime import datetime, timezone
from html import escape

from jinja2 import Template

from src.domain_constants import DOMAIN_EMOJI, DOMAIN_LABEL
from src.models import DailyDigest, Item

logger = logging.getLogger(__name__)

HTML_TEMPLATE = Template(
    """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WYCA Daily Digest - {{ date }}</title>
<style>
  :root {
    --bg: #ffffff;
    --bg-card: #f8f9fa;
    --bg-section: #f0f2f5;
    --text: #1a1a2e;
    --text-muted: #6c757d;
    --text-link: #0969da;
    --border: #e1e4e8;
    --accent: #0969da;
    --score-bg: #e8f5e9;
    --score-text: #2e7d32;
    --source-bg: #e3f2fd;
    --source-text: #1565c0;
    --shadow: 0 1px 3px rgba(0,0,0,0.08);
    --shadow-hover: 0 4px 12px rgba(0,0,0,0.12);
    --radius: 10px;
    --max-width: 900px;
  }
  @media (prefers-color-scheme: dark) {
    :root {
      --bg: #0d1117;
      --bg-card: #161b22;
      --bg-section: #0d1117;
      --text: #e6edf3;
      --text-muted: #8b949e;
      --text-link: #58a6ff;
      --border: #30363d;
      --accent: #58a6ff;
      --score-bg: #1a3a2a;
      --score-text: #7ee787;
      --source-bg: #1a2a3a;
      --source-text: #79c0ff;
      --shadow: 0 1px 3px rgba(0,0,0,0.3);
      --shadow-hover: 0 4px 12px rgba(0,0,0,0.4);
    }
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
                 "Helvetica Neue", Arial, "Noto Sans", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    padding: 1rem;
  }
  .container { max-width: var(--max-width); margin: 0 auto; }
  header {
    text-align: center;
    padding: 2rem 0 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 2rem;
  }
  header h1 {
    font-size: clamp(1.5rem, 4vw, 2.2rem);
    font-weight: 700;
    letter-spacing: -0.02em;
  }
  header .subtitle {
    color: var(--text-muted);
    font-size: 0.95rem;
    margin-top: 0.4rem;
  }
  nav.toc {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.5rem;
    margin-bottom: 2rem;
    box-shadow: var(--shadow);
  }
  nav.toc h2 {
    font-size: 1rem;
    margin-bottom: 0.5rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  nav.toc ul { list-style: none; display: flex; flex-wrap: wrap; gap: 0.5rem; }
  nav.toc a {
    display: inline-block;
    padding: 0.3rem 0.8rem;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    text-decoration: none;
    color: var(--text);
    font-size: 0.9rem;
    transition: background 0.2s, box-shadow 0.2s;
  }
  nav.toc a:hover {
    background: var(--accent);
    color: #fff;
    box-shadow: var(--shadow-hover);
  }
  .domain-section {
    margin-bottom: 2.5rem;
  }
  .domain-header {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    font-size: 1.4rem;
    font-weight: 700;
    padding-bottom: 0.5rem;
    border-bottom: 2px solid var(--accent);
    margin-bottom: 1rem;
  }
  .domain-header .count {
    font-size: 0.85rem;
    font-weight: 400;
    color: var(--text-muted);
  }
  .item-card {
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
    box-shadow: var(--shadow);
    transition: box-shadow 0.2s, transform 0.15s;
  }
  .item-card:hover {
    box-shadow: var(--shadow-hover);
    transform: translateY(-1px);
  }
  .item-title {
    font-size: 1.05rem;
    font-weight: 600;
    margin-bottom: 0.35rem;
  }
  .item-title a {
    color: var(--text-link);
    text-decoration: none;
  }
  .item-title a:hover { text-decoration: underline; }
  .item-meta {
    display: flex;
    align-items: center;
    gap: 0.6rem;
    flex-wrap: wrap;
    margin-top: 0.4rem;
  }
  .badge {
    display: inline-block;
    padding: 0.15rem 0.55rem;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 500;
  }
  .badge-source {
    background: var(--source-bg);
    color: var(--source-text);
  }
  .badge-score {
    background: var(--score-bg);
    color: var(--score-text);
  }
  .item-desc {
    color: var(--text-muted);
    font-size: 0.88rem;
    margin-top: 0.4rem;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }
  footer {
    text-align: center;
    padding: 2rem 0 1rem;
    border-top: 1px solid var(--border);
    color: var(--text-muted);
    font-size: 0.85rem;
  }
  @media (max-width: 600px) {
    .item-card { padding: 0.75rem 1rem; }
    nav.toc ul { flex-direction: column; }
  }
</style>
</head>
<body>
<div class="container">
  <header>
    <h1>\U0001f4e1 WYCA Daily Digest</h1>
    <div class="subtitle">{{ date }} &middot; {{ item_count }} items from {{ source_count }} sources</div>
  </header>

  <nav class="toc">
    <h2>\U0001f4d1 Contents</h2>
    <ul>
      {% for domain, items in groups.items() %}
      <li>
        <a href="#{{ domain }}">
          {{ domain_emoji.get(domain, '\U0001f4cc') }}
          {{ domain_label.get(domain, domain|title) }}
          ({{ items|length }})
        </a>
      </li>
      {% endfor %}
    </ul>
  </nav>

  {% for domain, items in groups.items() %}
  <section class="domain-section" id="{{ domain }}">
    <div class="domain-header">
      {{ domain_emoji.get(domain, '\U0001f4cc') }}
      {{ domain_label.get(domain, domain|title) }}
      <span class="count">{{ items|length }} items</span>
    </div>
    {% for item in items %}
    <div class="item-card">
      <div class="item-title">
        <a href="{{ item.url }}" target="_blank" rel="noopener noreferrer">
          {{ item.title|e }}
        </a>
      </div>
      <div class="item-meta">
        <span class="badge badge-source">{{ item.source }}</span>
        {% if item.score %}
        <span class="badge badge-score">{{ "%.0f"|format(item.score) }} pts</span>
        {% endif %}
      </div>
      {% if item.summary %}
      <div class="item-desc">{{ item.summary[:200]|e }}</div>
      {% elif item.raw_text %}
      <div class="item-desc">{{ item.raw_text[:200]|e }}</div>
      {% endif %}
    </div>
    {% endfor %}
  </section>
  {% endfor %}

  <footer>
    Generated at {{ generated_at }} by WYCA (What's Your Care About?)
  </footer>
</div>
</body>
</html>""",
    autoescape=True,
)


def _group_by_domain(items: list[Item]) -> dict[str, list[Item]]:
    """Group items by domain."""
    groups: dict[str, list[Item]] = defaultdict(list)
    for item in items:
        groups[item.domain].append(item)
    return dict(groups)


def render_html(digest: DailyDigest) -> str:
    """Render a DailyDigest into a responsive HTML page.

    Args:
        digest: The daily digest to render.

    Returns:
        A complete HTML document string.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    groups = _group_by_domain(digest.items)
    source_count = len({i.source for i in digest.items})

    result = HTML_TEMPLATE.render(
        date=digest.date,
        item_count=digest.item_count,
        source_count=source_count,
        groups=groups,
        domain_emoji=DOMAIN_EMOJI,
        domain_label=DOMAIN_LABEL,
        generated_at=now,
    )

    logger.info(
        "HTML rendered: %d items across %d domains",
        digest.item_count,
        len(groups),
    )
    return result
