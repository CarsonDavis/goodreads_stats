# Book Data Enrichment Pipeline

A modular system that enriches Goodreads export data with genre information from Google Books and Open Library APIs.

## Clean Architecture

The pipeline has three main components with clear separation of concerns:

- **`GenreEnricher`** - Core single-book enrichment (primary interface)
- **`CSVProcessor`** - Handles CSV loading and data cleaning
- **`BookFeeder`** - Orchestrates batch processing (ready for async/parallel)

## Quick Start

### Single Book Enrichment
```python
from genres import GenreEnricher, BookInfo

# Create a book
book = BookInfo(
    title="The Great Gatsby",
    author="F. Scott Fitzgerald", 
    isbn13="9780743273565"
)

# Enrich it
enricher = GenreEnricher(rate_limit=1.0)
enriched_book = enricher.enrich_book(book)

print(f"Final genres: {enriched_book.final_genres}")
```

### CSV Batch Processing
```python
from genres import GenreEnricher, CSVProcessor, BookFeeder

# Load books from CSV
csv_processor = CSVProcessor()
books = csv_processor.load_books("goodreads_export.csv", sample_size=10)

# Process them
enricher = GenreEnricher(rate_limit=1.0)
feeder = BookFeeder(enricher)
enriched_books = feeder.process_books(books)
```

## Features

- **Resilient API calls** with rate limiting, retries, and exponential backoff
- **Dual data sources** combining Google Books and Open Library for maximum coverage
- **Smart query strategies** using ISBN first, then falling back to title+author
- **Genre normalization** and deduplication across sources
- **Comprehensive reporting** with detailed analysis and overlap statistics
- **Modular architecture** for easy extension to additional data sources

## Key Components

- **`BookDataOrchestrator`** - Main pipeline coordinator
- **`APICaller`** - Handles all HTTP requests with resilience features
- **Fetchers** - API-specific data retrieval (`google_fetcher`, `open_library_fetcher`)
- **Processors** - Extract and clean data from API responses
- **`GenreMerger`** - Combines and normalizes genre data
- **`EnrichedBook`** - Central data model tracking enrichment progress

## Configuration

Adjust rate limiting for API calls:
```python
enricher = GenreEnricher(rate_limit=0.5)  # 0.5 seconds between requests
```

Process a subset of books:
```python
books = csv_processor.load_books(csv_path, sample_size=50)
enriched_books = feeder.process_books(books, max_books=25)
```

## Output

The pipeline generates:
- **CSV file** with enriched book data and final genre lists
- **JSON report** with pipeline performance statistics
- **Console displays** showing coverage, overlap analysis, and top genres

## Architecture Benefits

- **Single Responsibility**: Each component has one clear purpose
- **Easy Testing**: Components can be tested independently  
- **Async Ready**: Architecture supports future parallel processing
- **Extensible**: Easy to add new data sources or processing steps

```python
# Future: Parallel API calls for better performance
# enriched_book = await enricher.enrich_book_async(book)
```

Perfect for book lovers wanting to analyze and categorize their reading habits with reliable, comprehensive genre data.