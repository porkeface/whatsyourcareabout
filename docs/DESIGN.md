# Daily Global Hot Topics Aggregator - Design Document

## Project Overview

**Project Name**: WhatsYourCareAbout (WYCA)
**Goal**: Build a daily global hot topics aggregator that breaks information silos across domains (AI, finance, academic, tech, general news, RSS).
**MVP Timeline**: 2 days
**Date**: 2026-05-27

---

## Architecture

### Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.11+ | Best ecosystem for scraping, APIs, AI SDKs |
| Database | SQLite (MVP) | Zero config, single file, sufficient for single-user |
| Scheduler | APScheduler | In-process, no external dependencies |
| Templates | Jinja2 | Lightweight, flexible for HTML/Markdown |
| AI Layer | Claude API (optional) | Summarization + translation |
| Deployment | Docker Compose | Reproducible, easy to deploy |

### Data Flow

```
Sources                  Ingestion            Processing            Output
--------                ----------           -----------           --------
Hacker News API ─┐                           ┌─ Dedup (fuzzy       ┌─ Web UI (daily page)
Reddit API ──────┤                           │  title matching)    │
TechCrunch RSS ──┤     ┌──────────┐          │                    ├─ Markdown daily report
arXiv API ───────┼────>│ Collector│─────────>│  Rank & Categorize │
GitHub Trending ─┤     │ Workers  │          │  (domain buckets)  ├─ Telegram bot
Weibo (RSSHub) ──┤     └──────────┘          │                    │
Zhihu (RSSHub) ──┤          │                │  AI Summarize      ├─ Email digest
Finance APIs ────┤          v                │  + Translate       │
RSS (generic) ───┘     SQLite Store <────────│                    └─ RSS output
NewsAPI ──────────      (staging table)      └─ Score & Rank
```

---

## Core Components

### 1. Source Collectors (`src/sources/`)

Each source implements a common interface:

```python
class BaseCollector(ABC):
    async def collect(self) -> list[Item]
    def source_name(self) -> str
    def domain(self) -> str  # ai, finance, academic, tech, general, social
```

Normalized Item model:
```python
@dataclass
class Item:
    title: str
    url: str
    source: str          # e.g., "hacker_news", "arxiv"
    domain: str          # e.g., "ai", "finance", "academic"
    score: float         # engagement signal (upvotes, citations, etc.)
    raw_text: str        # description/abstract/snippet
    lang: str            # "en" or "zh"
    timestamp: datetime  # when the item was published
    collected_at: datetime
```

#### Planned Sources (Phase 1 - MVP)

| Source | Domain | API Type | Auth Required |
|--------|--------|----------|---------------|
| Hacker News | Tech/AI | Firebase API | No |
| Reddit (r/MachineLearning, r/artificial) | AI | OAuth API | Yes (free) |
| arXiv | Academic | REST API | No |
| GitHub Trending | Tech | Scrape | No |
| TechCrunch | Tech | RSS | No |
| NewsAPI | General | REST API | Yes (free tier) |
| Finnhub | Finance | REST API | Yes (free tier) |

#### Planned Sources (Phase 2)

| Source | Domain | Method |
|--------|--------|--------|
| Weibo Hot | Social (CN) | RSSHub |
| Zhihu Hot | Social (CN) | RSSHub |
| Bilibili Hot | Social (CN) | RSSHub |
| Product Hunt | Tech | GraphQL API |
| Semantic Scholar | Academic | REST API |
| Alpha Vantage | Finance | REST API |

### 2. Processing Pipeline (`src/processing/`)

#### Deduplication
- Fuzzy title matching using `difflib.SequenceMatcher`
- Threshold: 0.85 similarity within 24h window
- URL normalization for exact matches

#### Categorization
Domain buckets: `ai`, `finance`, `academic`, `tech`, `general`, `social`
- Source-based primary classification
- Keyword-based secondary classification for cross-domain items

#### Ranking Algorithm
```
score = source_weight * engagement_signal * recency_decay(hours)
```
- `source_weight`: configurable per source (default 1.0)
- `engagement_signal`: normalized per source (upvotes, citation count, etc.)
- `recency_decay`: exponential decay, half-life = 12 hours

### 3. AI Layer (`src/processing/summarizer.py`) - Optional

- Batch top N items per domain to Claude API
- System prompt for bilingual (EN/ZH) 2-sentence summaries
- Cache summaries by URL hash to avoid re-processing
- Behind a feature flag (`ENABLE_AI_SUMMARY=false` by default)

### 4. Output Renderers (`src/output/`)

| Output | Format | Description |
|--------|--------|-------------|
| Markdown | `.md` | Daily digest file, one per day |
| HTML | `.html` | Styled web page with categories |
| RSS | XML | Generated RSS feed of daily digest |
| Telegram | Bot API | Push to channel/chat |

### 5. Scheduler

```python
# Run daily at 06:00 UTC
scheduler.add_job(run_daily_digest, CronTrigger(hour=6, minute=0))
```

---

## Database Schema

```sql
CREATE TABLE items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    domain TEXT NOT NULL,
    score REAL DEFAULT 0,
    raw_text TEXT,
    lang TEXT DEFAULT 'en',
    summary TEXT,
    published_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE daily_digests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE UNIQUE NOT NULL,
    rendered_md TEXT,
    rendered_html TEXT,
    item_count INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_items_collected ON items(collected_at);
CREATE INDEX idx_items_domain ON items(domain);
CREATE INDEX idx_items_source ON items(source);
```

---

## Configuration

```yaml
# config.yaml
sources:
  hacker_news:
    enabled: true
    weight: 1.0
    max_items: 20
  reddit:
    enabled: true
    weight: 1.0
    subreddits: ["MachineLearning", "artificial", "technology"]
    max_items: 20
  arxiv:
    enabled: true
    weight: 1.2
    categories: ["cs.AI", "cs.CL", "cs.CV", "cs.LG"]
    max_items: 15
  github_trending:
    enabled: true
    weight: 0.8
    languages: ["python", "typescript", "rust"]
    max_items: 15
  newsapi:
    enabled: false  # requires API key
    weight: 1.0
    api_key: "${NEWSAPI_KEY}"
  finnhub:
    enabled: false  # requires API key
    weight: 1.0
    api_key: "${FINNHUB_KEY}"

processing:
  dedup_threshold: 0.85
  dedup_window_hours: 24
  recency_half_life_hours: 12
  max_items_per_domain: 10

ai_summary:
  enabled: false
  provider: "claude"  # or "openai"
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-haiku-4-5-20251001"
  max_items_per_domain: 5

output:
  formats: ["markdown", "html"]
  output_dir: "./output"
  telegram:
    enabled: false
    bot_token: "${TELEGRAM_BOT_TOKEN}"
    chat_id: "${TELEGRAM_CHAT_ID}"

schedule:
  cron_hour: 6
  cron_minute: 0
  timezone: "UTC"
```

---

## Directory Structure

```
whatsyourcareabout/
├── docs/
│   └── DESIGN.md
├── src/
│   ├── __init__.py
│   ├── main.py              # Entry point + scheduler
│   ├── config.py            # Config loading
│   ├── models.py            # Item, Digest models
│   ├── database.py          # SQLite operations
│   ├── sources/
│   │   ├── __init__.py
│   │   ├── base.py          # BaseCollector ABC
│   │   ├── hacker_news.py
│   │   ├── reddit.py
│   │   ├── arxiv_collector.py
│   │   ├── github_trending.py
│   │   ├── newsapi_source.py
│   │   ├── finnhub.py
│   │   └── rss_collector.py
│   ├── processing/
│   │   ├── __init__.py
│   │   ├── dedup.py          # Deduplication logic
│   │   ├── ranker.py         # Scoring & ranking
│   │   └── summarizer.py     # AI summarization
│   ├── output/
│   │   ├── __init__.py
│   │   ├── markdown_renderer.py
│   │   ├── html_renderer.py
│   │   └── telegram_push.py
│   └── templates/
│       └── daily_digest.html.j2
├── tests/
│   ├── test_sources/
│   ├── test_processing/
│   └── test_output/
├── config.yaml
├── requirements.txt
├── Dockerfile
├── docker-compose.yaml
└── README.md
```

---

## Implementation Phases

### Phase 1: MVP (Current Sprint)
1. Project scaffolding + config
2. Database layer (SQLite)
3. 5 core collectors (HN, Reddit, arXiv, GitHub Trending, RSS)
4. Dedup + ranking
5. Markdown output
6. CLI runner (`python -m src.main run`)

### Phase 2: Polish
1. HTML output with styled template
2. AI summarization layer
3. Telegram push
4. Docker setup
5. More sources (NewsAPI, Finnhub, RSSHub)

### Phase 3: Scale
1. Web UI with history
2. User preferences / domain filtering
3. Multi-user support (PostgreSQL migration)
4. RSSHub integration for Chinese platforms
5. Email newsletter

---

## Key Design Decisions

1. **SQLite over PostgreSQL**: MVP is single-user, single-process. SQLite is zero-config and sufficient.
2. **Async collectors**: All source fetchers use `asyncio` for parallel execution. Target: all sources fetched in < 60s.
3. **Source-per-file**: Each collector is a separate module. Easy to add/remove sources.
4. **AI as optional layer**: Summarization is behind a flag. Core functionality works without AI.
5. **Static output first**: Markdown/HTML files before web server. Simpler, more portable.
6. **RSSHub as external dependency**: We don't implement Chinese platform scraping ourselves. RSSHub handles that.
