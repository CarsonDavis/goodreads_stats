# Genre Enrichment Process

This document describes how the pipeline enriches books with genre data.

## Overview

The genre enrichment pipeline uses a **primary/fallback strategy**:

1. **Primary**: Goodreads web scraping (best genre quality)
2. **Fallback**: Google Books + Open Library APIs (when scraping fails)

```
BookInfo (with goodreads_id from CSV)
    │
    ▼
┌─────────────────────────────────────┐
│  PRIMARY: Goodreads Web Scraping    │
│  - Fetch goodreads.com/book/show/   │
│  - Parse HTML for genre list        │
│  - Retry with exponential backoff   │
└─────────────────────────────────────┘
    │
    ├─── SUCCESS (genres found) ────────▶ EnrichedBook.final_genres
    │
    ▼ FAILURE (empty/error)
┌─────────────────────────────────────┐
│  FALLBACK: API Sources (parallel)   │
│  ├── Google Books API               │
│  └── Open Library API               │
│  - merge_and_normalize() results    │
└─────────────────────────────────────┘
    │
    ▼
EnrichedBook.final_genres
```

## Why This Approach

| Factor | Goodreads Scraping | Google Books API | Open Library API |
|--------|-------------------|------------------|------------------|
| Genre Quality | User-curated, community-voted | Academic/library categories | Subject headings |
| Match Accuracy | Exact (goodreads_id from CSV) | ISBN/title lookup | ISBN/title lookup |
| Availability | Most CSV books have goodreads_id | Depends on ISBN | Generous |
| Rate Limits | Stricter (web scraping) | Generous API quota | Generous |

## Genre Source Priority

1. **Goodreads (Primary)** - Best genre quality, exact book match via `goodreads_id`
2. **Google Books + Open Library (Fallback)** - Used only when:
   - `goodreads_id` is missing/empty
   - Scraping returns empty genres (HTTP error, rate limited, page structure changed)
   - Scraping times out after retries

## Goodreads Scraping

### URL Pattern

```
https://www.goodreads.com/book/show/{goodreads_id}
```

### Retry Strategy

```python
for attempt in 1..3:
    response = GET url

    if response.status == 200:
        genres = parse_genres(response.html)
        if genres:
            return genres  # SUCCESS

    if response.status == 429:  # Rate limited
        sleep(2^attempt + jitter)
    else:
        sleep(0.5 * attempt)

return []  # FAILURE - trigger fallback
```

### HTML Parsing

**Primary selector** (modern Goodreads pages):
```css
[data-testid="genresList"] a[href*="/genres/"]
```

**Fallback selector** (older pages):
```css
a[href*="/genres/"]
```
With length filter (< 50 chars) to exclude navigation links.

## API Fallback

When Goodreads scraping fails, the pipeline falls back to parallel API calls:

### Google Books API
- Endpoint: `https://www.googleapis.com/books/v1/volumes`
- Lookup: ISBN (preferred) or title+author search
- Returns: Categories/subjects + book thumbnails

### Open Library API
- Endpoint: `https://openlibrary.org/api/books`
- Lookup: ISBN (preferred) or title+author search
- Returns: Subjects from edition and work records

Results are merged and normalized using `merge_and_normalize()`.

## Data Model

The `EnrichedBook` class tracks genre data from all sources:

```python
@dataclass
class EnrichedBook:
    # Processed genre data
    processed_goodreads_genres: List[str]  # From scraping
    processed_google_genres: List[str]      # From Google Books API
    processed_openlib_genres: List[str]     # From Open Library API
    final_genres: List[str]                 # Final merged result

    # Source tracking
    goodreads_scrape_success: bool          # True if Goodreads provided genres
```

## Processing Log

Each book's `processing_log` tracks which sources were used:

```
# Goodreads success case:
Starting async enrichment
Goodreads: 5 genres (primary)
Final: 5 genres from Goodreads
Google Books: Thumbnails extracted

# Fallback case:
Starting async enrichment
Goodreads: No genres found
Using API fallback (Google Books + Open Library)
Google Books: 3 genres
Open Library: 4 subjects
Final: 6 merged genres (API fallback)
```

## Standalone Scraper Usage

The Goodreads scraping logic originated from a separate `book-recommendations` repository and can also be used standalone for batch genre lookups:

```bash
# From the book-recommendations repo
uv run python -m goodreads genres input.csv output.csv --concurrency 5 --retry 3
```

**Python API (single book):**
```python
import asyncio
import aiohttp
from goodreads.scrape import fetch_genres

async def get_genres(book_id: str):
    timeout = aiohttp.ClientTimeout(total=30)
    headers = {"User-Agent": "Mozilla/5.0 ..."}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        return await fetch_genres(session, book_id)

genres = asyncio.run(get_genres("123456"))
# ["Fiction", "Mystery", "Thriller"]
```

**Input/Output:** CSV with `goodreads_id` column; output adds pipe-separated `genres` column.

**Dependencies:** `aiohttp`, `beautifulsoup4`, `lxml`, `tqdm`

Within the goodreads_stats pipeline, this logic is integrated directly in `genres/sources/goodreads.py` and called by the `AsyncGenreEnricher`.

## Configuration

The `AsyncGenreEnricher` class accepts these parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_concurrent` | 10 | Maximum concurrent enrichment tasks |
| `rate_limit_delay` | 0.1 | Delay between tasks (seconds) |

## Files

| File | Purpose |
|------|---------|
| `genres/sources/goodreads.py` | Goodreads scraping implementation |
| `genres/sources/google.py` | Google Books API processing |
| `genres/sources/openlibrary.py` | Open Library API processing |
| `genres/pipeline/enricher.py` | Main enrichment pipeline |
| `genres/models/book.py` | Data models |
| `genres/utils/genre_merger.py` | Genre merging and normalization |
