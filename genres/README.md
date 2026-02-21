# Book Genre Enrichment Pipeline

Async pipeline that enriches Goodreads export data with genre information from Goodreads scraping, Google Books, and Open Library APIs.

## Architecture

```
genres/
├── models/
│   ├── book.py           # BookInfo (input) and EnrichedBook (output)
│   └── analytics.py      # BookAnalytics and ReadingSession for dashboards
├── pipeline/
│   ├── csv_loader.py     # AnalyticsCSVProcessor — parses Goodreads CSV
│   ├── enricher.py       # AsyncGenreEnricher — concurrent genre lookups
│   └── exporter.py       # create_dashboard_json() — final JSON output
├── sources/
│   ├── goodreads.py      # Goodreads scraping (primary genre source)
│   ├── google.py         # Google Books API processor
│   └── openlibrary.py    # Open Library API processor
└── utils/                # Genre merging and normalization
```

## Quick Start

```python
from genres import AsyncGenreEnricher, BookInfo

books = [
    BookInfo(title="The Great Gatsby", author="F. Scott Fitzgerald", isbn13="9780743273565"),
]

async with AsyncGenreEnricher(max_concurrent=15, rate_limit_delay=0.05) as enricher:
    enriched = await enricher.enrich_books_batch(books)

print(enriched[0].final_genres)
```

## Genre Source Strategy

1. **Goodreads scraping** (primary) — community-curated genres, best quality
2. **Google Books + Open Library APIs** (fallback) — used when scraping fails, fetched in parallel

## Key Classes

- **`AsyncGenreEnricher`** — Core enricher with semaphore-based concurrency control and rate limiting
- **`AnalyticsCSVProcessor`** — Loads books from Goodreads CSV exports into `BookAnalytics` objects
- **`BookInfo`** / **`EnrichedBook`** — Input/output data models for the enrichment pipeline
- **`BookAnalytics`** — Enhanced book model with reading sessions and time-series data
- **`create_dashboard_json()`** — Generates the final dashboard JSON from enriched books
