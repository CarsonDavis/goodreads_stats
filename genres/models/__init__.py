# genres/models/__init__.py
"""
Data models for the book genre enrichment pipeline.
"""

from .book import BookInfo, EnrichedBook
from .analytics import BookAnalytics, ReadingSession

__all__ = [
    "BookInfo",
    "EnrichedBook", 
    "BookAnalytics",
    "ReadingSession"
]