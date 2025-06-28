"""
Book Feeder - Orchestrates feeding books through the enrichment pipeline.
Handles batch processing and will support async/parallel processing in the future.
"""

import logging
from typing import List, Optional

from .models import BookInfo, EnrichedBook
from .genre_enricher import GenreEnricher


class BookFeeder:
    """
    Orchestrates feeding books through the enrichment pipeline.
    
    This class handles batch processing and coordination between
    CSV loading and genre enrichment, keeping those concerns separate.
    
    Future: Will support async/parallel processing for performance.
    """
    
    def __init__(self, enricher: GenreEnricher):
        self.enricher = enricher
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_books(self, books: List[BookInfo], max_books: Optional[int] = None) -> List[EnrichedBook]:
        """
        Process a list of books through the enrichment pipeline.
        
        Args:
            books: List of BookInfo objects to enrich
            max_books: Optional limit on number of books to process
            
        Returns:
            List of EnrichedBook objects with genre data
        """
        books_to_process = books[:max_books] if max_books else books
        
        self.logger.info(f"Starting batch processing of {len(books_to_process)} books")
        
        enriched_books = []
        
        for i, book in enumerate(books_to_process, 1):
            self.logger.info(f"Processing book {i}/{len(books_to_process)}: {book.title}")
            
            try:
                enriched_book = self.enricher.enrich_book(book)
                enriched_books.append(enriched_book)
                
            except Exception as e:
                self.logger.error(f"Failed to enrich book '{book.title}': {e}")
                # Create a minimal EnrichedBook with error info
                error_book = EnrichedBook(input_info=book)
                error_book.add_log(f"Enrichment failed: {str(e)}")
                enriched_books.append(error_book)
        
        self.logger.info(f"Batch processing complete: {len(enriched_books)} books processed")
        return enriched_books
    
    # Future: async processing methods
    # async def process_books_async(self, books: List[BookInfo]) -> List[EnrichedBook]:
    #     """Process books asynchronously for better performance."""
    #     pass
    #
    # async def process_book_parallel_apis(self, book: BookInfo) -> EnrichedBook:
    #     """Process a single book with parallel Google/OpenLibrary calls."""
    #     pass