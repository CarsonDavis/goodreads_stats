# genres/sources/__init__.py
"""
External API source integrations for book data.
"""

from .google import process_google_response
from .openlibrary import process_open_library_response

__all__ = [
    "process_google_response",
    "process_open_library_response"
]