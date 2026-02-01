# genres/sources/__init__.py
"""
External source integrations for book data.

Includes:
- Goodreads web scraping (primary genre source)
- Google Books API (fallback + thumbnails)
- Open Library API (fallback)
"""

from .google import process_google_response
from .openlibrary import process_open_library_response
from .goodreads import fetch_goodreads_genres, parse_goodreads_genres

__all__ = [
    "process_google_response",
    "process_open_library_response",
    "fetch_goodreads_genres",
    "parse_goodreads_genres",
]