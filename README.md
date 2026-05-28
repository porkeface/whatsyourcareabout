# WhatsYourCareAbout (WYCA)

Daily Global Hot Topics Aggregator - Break information silos across domains.

## Features

- Multi-domain aggregation: AI, Finance, Academic, Tech, General News
- 5+ data sources: Hacker News, Reddit, arXiv, GitHub Trending, RSS
- Smart deduplication with fuzzy title matching
- Ranking by engagement, source weight, and recency decay
- Beautiful HTML output with dark/light theme
- Markdown daily digest generation
- Telegram push support
- Optional AI summarization via Claude API

## Quick Start

```bash
pip install -r requirements.txt
python -m src.main init
python -m src.main run
```

## Configuration

Edit `config.yaml` to enable/disable sources, set API keys, and customize output formats.

## Architecture

```
Sources -> Collectors (async) -> SQLite -> Dedup -> Rank -> Render (MD/HTML) -> Push
```

See [docs/DESIGN.md](docs/DESIGN.md) for full design document.
