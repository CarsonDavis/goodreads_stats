# genres/processors/__init__.py
"""
Data processor modules for the Book Data Enrichment Pipeline.
"""

from .google_processor import process_google_response
from .open_library_processor import process_open_library_response

__all__ = ["process_google_response", "process_open_library_response"]