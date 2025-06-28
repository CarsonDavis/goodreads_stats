"""
Core Genre Enricher - Single book enrichment logic.
Handles a single BookInfo -> EnrichedBook transformation.
"""

import logging
from typing import Optional

from .models import BookInfo, EnrichedBook
from .api_caller import APICaller
from .fetchers import fetch_google_data, fetch_open_library_data
from .processors import process_google_response, process_open_library_response
from .genre_merger import merge_and_normalize


class GenreEnricher:
    """
    Core enrichment engine that takes a single BookInfo and returns an EnrichedBook.
    
    This class focuses solely on the enrichment logic for individual books,
    with no knowledge of CSV processing or batch operations.
    """
    
    def __init__(self, rate_limit: float = 1.0):
        self.api_caller = APICaller(rate_limit=rate_limit)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def enrich_book(self, book: BookInfo) -> EnrichedBook:
        """
        Main enrichment method for a single book.
        
        Args:
            book: BookInfo to enrich
            
        Returns:
            EnrichedBook with all available data populated
        """
        self.logger.info(f"Enriching: {book.title} by {book.author}")
        
        # Initialize enriched book
        enriched_book = EnrichedBook(input_info=book)
        enriched_book.add_log("Starting enrichment pipeline")
        
        # Step 1: Fetch raw data from APIs
        self._fetch_data(enriched_book)
        
        # Step 2: Process raw data into genres
        self._process_data(enriched_book)
        
        # Step 3: Merge and normalize final genres
        self._merge_and_finalize(enriched_book)
        
        self.logger.info(
            f"Enrichment complete: Google={len(enriched_book.processed_google_genres)}, "
            f"OpenLib={len(enriched_book.processed_openlib_genres)}, "
            f"Final={len(enriched_book.final_genres)}"
        )
        
        return enriched_book
    
    def _fetch_data(self, enriched_book: EnrichedBook) -> None:
        """Fetch raw data from both APIs"""
        book = enriched_book.input_info
        
        # Fetch Google Books data
        try:
            google_data = fetch_google_data(book, self.api_caller)
            if google_data:
                enriched_book.google_response = google_data
                enriched_book.add_log("Google Books: Success")
            else:
                enriched_book.add_log("Google Books: No data found")
        except Exception as e:
            enriched_book.add_log(f"Google Books: Error - {str(e)}")
        
        # Fetch Open Library data
        try:
            edition_data, work_data = fetch_open_library_data(book, self.api_caller)
            if edition_data:
                enriched_book.openlib_edition_response = edition_data
                enriched_book.add_log("Open Library Edition: Success")
            if work_data:
                enriched_book.openlib_work_response = work_data
                enriched_book.add_log("Open Library Work: Success")
            if not edition_data and not work_data:
                enriched_book.add_log("Open Library: No data found")
        except Exception as e:
            enriched_book.add_log(f"Open Library: Error - {str(e)}")
    
    def _process_data(self, enriched_book: EnrichedBook) -> None:
        """Process raw API responses into genre lists"""
        
        # Process Google Books data
        if enriched_book.google_response:
            try:
                google_genres = process_google_response(enriched_book.google_response)
                enriched_book.processed_google_genres = google_genres
                enriched_book.add_log(f"Google Books: Extracted {len(google_genres)} genres")
            except Exception as e:
                enriched_book.add_log(f"Google Books processing error: {str(e)}")
        
        # Process Open Library data
        if enriched_book.openlib_edition_response or enriched_book.openlib_work_response:
            try:
                openlib_genres = process_open_library_response(
                    enriched_book.openlib_edition_response,
                    enriched_book.openlib_work_response
                )
                enriched_book.processed_openlib_genres = openlib_genres
                enriched_book.add_log(f"Open Library: Extracted {len(openlib_genres)} subjects")
            except Exception as e:
                enriched_book.add_log(f"Open Library processing error: {str(e)}")
    
    def _merge_and_finalize(self, enriched_book: EnrichedBook) -> None:
        """Merge and normalize final genre list"""
        try:
            final_genres = merge_and_normalize(
                enriched_book.processed_google_genres,
                enriched_book.processed_openlib_genres
            )
            enriched_book.final_genres = final_genres
            enriched_book.add_log(f"Final: {len(final_genres)} merged and normalized genres")
        except Exception as e:
            enriched_book.add_log(f"Genre merging error: {str(e)}")