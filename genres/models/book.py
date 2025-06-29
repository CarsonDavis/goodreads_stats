# genres/models/book.py
"""
Data models for the book genre enrichment pipeline.
"""

from dataclasses import dataclass, field
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
class EnrichedBook:
    """
    Central data model that gets progressively enriched through the pipeline.
    """
    input_info: BookInfo
    
    # Raw API responses
    google_response: Optional[Dict] = None
    openlib_edition_response: Optional[Dict] = None
    openlib_work_response: Optional[Dict] = None
    
    # Processed genre data
    processed_google_genres: List[str] = field(default_factory=list)
    processed_openlib_genres: List[str] = field(default_factory=list)
    final_genres: List[str] = field(default_factory=list)
    
    # Image/thumbnail data
    thumbnail_url: Optional[str] = None
    small_thumbnail_url: Optional[str] = None
    
    # Processing metadata
    processing_log: List[str] = field(default_factory=list)
    
    def add_log(self, message: str) -> None:
        """Add a message to the processing log"""
        self.processing_log.append(message)
    
    def get_success_status(self) -> bool:
        """Return True if we got any genre data from any source"""
        return len(self.final_genres) > 0
    
    def get_summary(self) -> Dict:
        """Get a summary dict for reporting"""
        return {
            "title": self.input_info.title,
            "author": self.input_info.author,
            "isbn13": self.input_info.isbn13,
            "google_success": self.google_response is not None,
            "openlib_success": (self.openlib_edition_response is not None or 
                              self.openlib_work_response is not None),
            "google_genres_count": len(self.processed_google_genres),
            "openlib_genres_count": len(self.processed_openlib_genres),
            "final_genres_count": len(self.final_genres),
            "final_genres": self.final_genres,
            "thumbnail_url": self.thumbnail_url,
            "small_thumbnail_url": self.small_thumbnail_url,
            "processing_log": self.processing_log
        }