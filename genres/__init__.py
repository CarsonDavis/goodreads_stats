# genres/__init__.py
"""
Book genre enrichment pipeline.

Primary interfaces:
- AsyncGenreEnricher: Async enricher with concurrent API lookups
- AnalyticsCSVProcessor: Load comprehensive book data for dashboard analytics
- BookAnalytics: Enhanced book model for time-series analysis
"""

# Data models
from .models import BookInfo, EnrichedBook, BookAnalytics, ReadingSession

# Core pipeline components
from .pipeline import (
    AnalyticsCSVProcessor,
    AsyncGenreEnricher,
    FinalJSONExporter,
    create_dashboard_json
)

# Supporting components
from .sources import process_google_response, process_open_library_response
from .utils import merge_and_normalize

__all__ = [
    # Core data models
    "BookInfo",
    "EnrichedBook",
    "BookAnalytics",
    "ReadingSession",

    # Main pipeline interface
    "AsyncGenreEnricher",
    "AnalyticsCSVProcessor",
    "FinalJSONExporter",
    "create_dashboard_json",

    # Low-level components
    "process_google_response",
    "process_open_library_response",
    "merge_and_normalize"
]
