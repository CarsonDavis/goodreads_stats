# Data Models

This document describes the core data models used throughout the Goodreads Stats pipeline.

## Overview

The system uses three primary data models that represent books at different stages of processing:

| Model | Purpose | Location |
|-------|---------|----------|
| `BookInfo` | Lightweight input for API lookups | `genres/models/book.py` |
| `EnrichedBook` | Accumulator during enrichment | `genres/models/book.py` |
| `BookAnalytics` | Final dashboard-ready model | `genres/models/analytics.py` |

## BookInfo

**Purpose:** Minimal book identification for API lookups.

**Source:** `genres/models/book.py:11-17`

```python
@dataclass
class BookInfo:
    """Standardized book information structure"""
    title: str
    author: str
    isbn13: Optional[str] = None
    isbn: Optional[str] = None
    goodreads_id: Optional[str] = None
```

### Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `title` | `str` | Yes | Book title |
| `author` | `str` | Yes | Primary author name |
| `isbn13` | `str` | No | 13-digit ISBN |
| `isbn` | `str` | No | 10-digit ISBN |
| `goodreads_id` | `str` | No | Goodreads book ID |

### Usage

```python
from genres.models.book import BookInfo

book = BookInfo(
    title="The Hobbit",
    author="J.R.R. Tolkien",
    isbn13="9780547928227"
)
```

---

## EnrichedBook

**Purpose:** Accumulates data from multiple API sources during the enrichment pipeline.

**Source:** `genres/models/book.py:20-74`

```python
@dataclass
class EnrichedBook:
    """Central data model that gets progressively enriched through the pipeline."""
    input_info: BookInfo

    # Raw API responses
    google_response: Optional[Dict] = None
    openlib_edition_response: Optional[Dict] = None
    openlib_work_response: Optional[Dict] = None

    # Processed genre data
    processed_goodreads_genres: List[str] = field(default_factory=list)
    processed_google_genres: List[str] = field(default_factory=list)
    processed_openlib_genres: List[str] = field(default_factory=list)
    final_genres: List[str] = field(default_factory=list)

    # Source tracking
    goodreads_scrape_success: bool = False

    # Image/thumbnail data
    thumbnail_url: Optional[str] = None
    small_thumbnail_url: Optional[str] = None

    # Processing metadata
    processing_log: List[str] = field(default_factory=list)
```

### Fields

| Field | Type | Description |
|-------|------|-------------|
| `input_info` | `BookInfo` | Original book identification |
| `google_response` | `Dict` | Raw Google Books API response |
| `openlib_edition_response` | `Dict` | Raw Open Library edition response |
| `openlib_work_response` | `Dict` | Raw Open Library work response |
| `processed_goodreads_genres` | `List[str]` | Genres scraped from Goodreads |
| `processed_google_genres` | `List[str]` | Genres extracted from Google Books |
| `processed_openlib_genres` | `List[str]` | Subjects extracted from Open Library |
| `final_genres` | `List[str]` | Merged and deduplicated genre list |
| `goodreads_scrape_success` | `bool` | True if Goodreads provided genres |
| `thumbnail_url` | `str` | Book cover image URL |
| `small_thumbnail_url` | `str` | Smaller cover thumbnail URL |
| `processing_log` | `List[str]` | Debug log of enrichment steps |

### Methods

```python
def add_log(self, message: str) -> None:
    """Add a message to the processing log"""

def get_success_status(self) -> bool:
    """Return True if we got any genre data from any source"""

def get_summary(self) -> Dict:
    """Get a summary dict for reporting"""
```

---

## BookAnalytics

**Purpose:** Comprehensive model for dashboard analytics and time-series analysis.

**Source:** `genres/models/analytics.py:11-159`

This is the primary model used by the dashboard. It contains all fields from the Goodreads CSV export plus enriched data.

### Core Fields

```python
@dataclass
class BookAnalytics:
    # Core identification
    goodreads_id: str
    title: str
    author: str
    author_lf: Optional[str] = None        # "Last, First" format
    additional_authors: Optional[str] = None

    # ISBN data
    isbn: Optional[str] = None
    isbn13: Optional[str] = None

    # Rating data
    my_rating: Optional[int] = None        # 0-5 stars, 0 = unrated
    average_rating: Optional[float] = None

    # Publication info
    publisher: Optional[str] = None
    binding: Optional[str] = None          # Kindle, Hardcover, Paperback
    num_pages: Optional[int] = None
    year_published: Optional[int] = None
    original_publication_year: Optional[int] = None

    # Reading timeline
    date_read: Optional[date] = None       # Latest read date
    date_added: Optional[date] = None
    reading_status: Optional[str] = None   # read, to-read, currently-reading, dnf

    # Organization
    bookshelves: List[str] = field(default_factory=list)
    bookshelves_with_positions: Optional[str] = None

    # User content
    my_review: Optional[str] = None
    private_notes: Optional[str] = None
    has_spoilers: bool = False

    # Metadata
    read_count_original: int = 1           # Store original but treat as 1 for analytics
    owned_copies: int = 0

    # Enriched data
    final_genres: List[str] = field(default_factory=list)
    genre_enrichment_success: bool = False
    genre_sources: List[str] = field(default_factory=list)
    enrichment_logs: List[str] = field(default_factory=list)
    thumbnail_url: Optional[str] = None
    small_thumbnail_url: Optional[str] = None
```

### Computed Properties

| Property | Return Type | Description |
|----------|-------------|-------------|
| `is_read` | `bool` | True if book has been read |
| `is_rated` | `bool` | True if user provided a rating > 0 |
| `reading_year` | `int` | Year the book was read |
| `reading_month_year` | `tuple` | (year, month) for time-series grouping |
| `page_category` | `str` | Length category: Short, Medium, Long, Very Long |

### Page Categories

```python
@property
def page_category(self) -> Optional[str]:
    if self.num_pages < 200:
        return "Short (<200)"
    elif self.num_pages < 350:
        return "Medium (200-350)"
    elif self.num_pages < 500:
        return "Long (350-500)"
    else:
        return "Very Long (500+)"
```

### Dashboard Export

The `to_dashboard_dict()` method converts the model to a JSON-serializable dictionary:

```python
def to_dashboard_dict(self) -> Dict:
    return {
        "goodreads_id": self.goodreads_id,
        "title": self.title,
        "author": self.author,
        "date_read": self.date_read.isoformat() if self.date_read else None,
        "reading_year": self.reading_year,
        "my_rating": self.my_rating,
        "average_rating": float(self.average_rating) if self.average_rating else None,
        "num_pages": self.num_pages,
        "genres": self.final_genres,
        "thumbnail_url": self.thumbnail_url,
        # ... additional fields
    }
```

---

## Dashboard JSON Structure

The final output consumed by the frontend:

```json
{
  "export_id": "uuid-v4",
  "books": [
    {
      "goodreads_id": "12345",
      "title": "The Hobbit",
      "author": "J.R.R. Tolkien",
      "isbn": "0547928227",
      "isbn13": "9780547928227",
      "date_read": "2023-12-01",
      "reading_year": 2023,
      "reading_month_year": "2023-12",
      "my_rating": 5,
      "average_rating": 4.28,
      "is_rated": true,
      "num_pages": 310,
      "publisher": "Mariner Books",
      "binding": "Paperback",
      "publication_year": 1937,
      "page_category": "Medium (200-350)",
      "reading_status": "read",
      "bookshelves": ["fantasy", "favorites"],
      "genres": ["Fantasy", "Fiction", "Classics", "Adventure"],
      "thumbnail_url": "https://books.google.com/...",
      "small_thumbnail_url": "https://books.google.com/...",
      "my_review": "A wonderful adventure...",
      "private_notes": null,
      "has_spoilers": false,
      "has_review": true,
      "genre_enriched": true,
      "was_reread": false,
      "original_read_count": 1
    }
  ],
  "summary": {
    "total_books": 1247,
    "read_books": 564,
    "rated_books": 520,
    "genre_enriched_books": 500,
    "genre_enrichment_rate": 88.7,
    "unique_authors": 380,
    "unique_genres": 45,
    "total_pages": 150000,
    "reading_date_range": {
      "earliest": "2010-01-15",
      "latest": "2024-12-20"
    },
    "reading_years": [2010, 2011, 2023, 2024],
    "average_rating": 3.8,
    "most_common_genres": [
      {"genre": "Fiction", "count": 200, "percentage": 15.5}
    ]
  },
  "metadata": {
    "export_id": "uuid-v4",
    "export_timestamp": "2024-01-15T10:25:33Z",
    "exporter_version": "1.0.0",
    "data_schema_version": "1.0.0",
    "export_source": "goodreads_csv_with_genre_enrichment",
    "processing_notes": ["..."],
    "validation": {"...": "..."}
  }
}
```

### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `export_id` | `string` | UUID identifying this export |
| `books` | `array` | Array of book objects (from `to_dashboard_dict()`) |
| `summary` | `object` | Aggregate statistics (total books, read count, genre stats, etc.) |
| `metadata` | `object` | Export metadata (timestamp, version, validation) |

---

## Data Flow

```
Goodreads CSV
     |
     v
[AnalyticsCSVProcessor]
     |
     v
List[BookAnalytics]  (initial, without genres)
     |
     v
[Convert to BookInfo for API lookups]
     |
     v
[AsyncGenreEnricher]
     |
     v
List[EnrichedBook]  (with API responses)
     |
     v
[Merge back to BookAnalytics]
     |
     v
List[BookAnalytics]  (complete, with genres)
     |
     v
[create_dashboard_json()]
     |
     v
Dashboard JSON file
```

---

## ReadingSession (Auxiliary)

**Purpose:** Represents a single reading session for analytics.

**Source:** `genres/models/analytics.py:161-179`

```python
@dataclass
class ReadingSession:
    book: BookAnalytics
    session_date: date
    pages_read: Optional[int] = None
    rating: Optional[int] = None

    @property
    def year(self) -> int:
        return self.session_date.year

    @property
    def month_year(self) -> tuple:
        return (self.session_date.year, self.session_date.month)
```

Each `BookAnalytics` generates exactly one `ReadingSession` if read, avoiding re-read skewing in time-series analytics.
