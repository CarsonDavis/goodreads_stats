# api/enriched_models.py
"""
Central data models for the Book Data Enrichment Pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from ..api.models import BookInfo


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
            "openlib_success": (
                self.openlib_edition_response is not None
                or self.openlib_work_response is not None
            ),
            "google_genres_count": len(self.processed_google_genres),
            "openlib_genres_count": len(self.processed_openlib_genres),
            "final_genres_count": len(self.final_genres),
            "final_genres": self.final_genres,
            "processing_log": self.processing_log,
        }
