# api_testing/models.py
"""
Data models and structures for book API testing.
"""

from dataclasses import dataclass
from typing import List, Dict, Optional


@dataclass
class BookInfo:
    """Standardized book information structure"""
    title: str
    author: str
    isbn13: Optional[str] = None
    isbn: Optional[str] = None
    goodreads_id: Optional[str] = None


@dataclass
class APIResponse:
    """Standardized API response structure"""
    api_name: str
    book_info: BookInfo
    success: bool
    response_time: float
    genres: List[str]
    error_message: Optional[str] = None
    raw_response: Optional[Dict] = None