# genres/__init__.py
"""
Book genre enrichment pipeline with clean separation of concerns.

Primary interfaces:
- GenreEnricher: Core single-book enrichment
- CSVProcessor: Load books from Goodreads CSV
- BookFeeder: Orchestrate batch processing

Analytics interfaces:
- AnalyticsCSVProcessor: Load comprehensive book data for dashboard analytics
- BookAnalytics: Enhanced book model for time-series analysis
"""

from .models import BookInfo, EnrichedBook
from .genre_enricher import GenreEnricher
from .csv_processor import CSVProcessor
from .book_feeder import BookFeeder

# Analytics components
from .analytics_models import BookAnalytics, ReadingSession
from .analytics_csv_processor import AnalyticsCSVProcessor

# Legacy/internal components (available but not primary interface)
from .api_caller import APICaller
from .fetchers import fetch_google_data, fetch_open_library_data
from .processors import process_google_response, process_open_library_response
from .genre_merger import merge_and_normalize

__all__ = [
    # Primary interface
    "GenreEnricher",
    "CSVProcessor", 
    "BookFeeder",
    "BookInfo",
    "EnrichedBook",
    
    # Analytics interface
    "BookAnalytics",
    "ReadingSession",
    "AnalyticsCSVProcessor",
    
    # Internal components
    "APICaller",
    "fetch_google_data",
    "fetch_open_library_data",
    "process_google_response",
    "process_open_library_response",
    "merge_and_normalize"
]