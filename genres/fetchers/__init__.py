# genres/fetchers/__init__.py
"""
Data fetcher modules for the Book Data Enrichment Pipeline.
"""

from .google_fetcher import fetch_google_data
from .open_library_fetcher import fetch_open_library_data

__all__ = ["fetch_google_data", "fetch_open_library_data"]