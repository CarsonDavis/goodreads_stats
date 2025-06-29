"""
Enhanced data models for dashboard analytics and time-series analysis.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import date


@dataclass
class BookAnalytics:
    """
    Comprehensive book model for dashboard analytics and time-series analysis.

    Designed to capture all relevant CSV data while treating re-reads as single entries
    using the latest read date to avoid skewing time-series statistics.
    """

    # Core identification
    goodreads_id: str
    title: str
    author: str
    author_lf: Optional[str] = None  # "Last, First" format
    additional_authors: Optional[str] = None

    # ISBN data
    isbn: Optional[str] = None
    isbn13: Optional[str] = None

    # Rating data (key for analytics)
    my_rating: Optional[int] = None  # 0-5 stars, 0 = unrated
    average_rating: Optional[float] = None

    # Publication info
    publisher: Optional[str] = None
    binding: Optional[str] = None  # Kindle, Hardcover, Paperback, etc.
    num_pages: Optional[int] = None
    year_published: Optional[int] = None
    original_publication_year: Optional[int] = None

    # Reading timeline (critical for dashboard)
    date_read: Optional[date] = None  # Latest read date only
    date_added: Optional[date] = None  # When added to library
    reading_status: Optional[str] = None  # read, to-read, currently-reading, dnf

    # Organization
    bookshelves: List[str] = field(default_factory=list)
    bookshelves_with_positions: Optional[str] = None

    # User content
    my_review: Optional[str] = None
    private_notes: Optional[str] = None
    has_spoilers: bool = False

    # Metadata (ignoring for analytics to avoid skew)
    read_count_original: int = 1  # Store original but treat as 1 for analytics
    owned_copies: int = 0

    # Enriched genre data (from our pipeline)
    final_genres: List[str] = field(default_factory=list)
    genre_enrichment_success: bool = False
    
    # Image/thumbnail data
    thumbnail_url: Optional[str] = None
    small_thumbnail_url: Optional[str] = None

    @property
    def read_count_for_analytics(self) -> int:
        """Always returns 1 to avoid skewing time-series analytics"""
        return 1

    @property
    def is_read(self) -> bool:
        """True if book has been read"""
        return self.reading_status == "read" and self.date_read is not None

    @property
    def is_rated(self) -> bool:
        """True if user provided a rating"""
        return self.my_rating is not None and self.my_rating > 0

    @property
    def reading_year(self) -> Optional[int]:
        """Year the book was read (for time-series grouping)"""
        return self.date_read.year if self.date_read else None

    @property
    def reading_month_year(self) -> Optional[tuple]:
        """(year, month) tuple for monthly time-series"""
        return (self.date_read.year, self.date_read.month) if self.date_read else None

    @property
    def page_category(self) -> Optional[str]:
        """Categorize by length for analysis"""
        if not self.num_pages:
            return None

        if self.num_pages < 200:
            return "Short (<200)"
        elif self.num_pages < 350:
            return "Medium (200-350)"
        elif self.num_pages < 500:
            return "Long (350-500)"
        else:
            return "Very Long (500+)"

    def to_dashboard_dict(self) -> Dict:
        """
        Convert to dictionary optimized for dashboard consumption.
        Only includes fields relevant for analytics.
        """
        return {
            # Identifiers
            "goodreads_id": self.goodreads_id,
            "title": self.title,
            "author": self.author,
            "isbn": self.isbn,
            "isbn13": self.isbn13,
            # Analytics key fields
            "date_read": self.date_read.isoformat() if self.date_read else None,
            "reading_year": self.reading_year,
            "reading_month_year": (
                f"{self.reading_month_year[0]}-{self.reading_month_year[1]:02d}"
                if self.reading_month_year
                else None
            ),
            # Rating data
            "my_rating": self.my_rating,
            "average_rating": (
                float(self.average_rating) if self.average_rating else None
            ),
            "is_rated": self.is_rated,
            # Book metadata
            "num_pages": self.num_pages,
            "publisher": self.publisher,
            "binding": self.binding,
            "publication_year": self.original_publication_year,
            "page_category": self.page_category,
            # Organization
            "reading_status": self.reading_status,
            "bookshelves": self.bookshelves,
            "genres": self.final_genres,
            # Images
            "thumbnail_url": self.thumbnail_url,
            "small_thumbnail_url": self.small_thumbnail_url,
            # Flags
            "has_review": bool(self.my_review and self.my_review.strip()),
            "genre_enriched": self.genre_enrichment_success,
            # Metadata (noting but not using for analytics)
            "was_reread": self.read_count_original > 1,
            "original_read_count": self.read_count_original,
        }


@dataclass
class ReadingSession:
    """
    Represents a single reading session for analytics.
    Each BookAnalytics generates exactly one ReadingSession if read.
    """

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
