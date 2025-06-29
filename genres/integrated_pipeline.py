"""
Integrated pipeline: CSV -> Genre Enrichment -> Analytics -> Final JSON

This module ties together all components for the complete workflow:
1. Load CSV data into BookAnalytics objects
2. Enrich genres using the existing pipeline
3. Export final JSON for dashboard consumption
"""

import logging
from typing import List, Optional

from .analytics_csv_processor import AnalyticsCSVProcessor
from .analytics_models import BookAnalytics
from .genre_enricher import GenreEnricher
from .models import BookInfo
from .final_json_exporter import FinalJSONExporter, create_dashboard_json


class IntegratedBookPipeline:
    """
    Complete pipeline that processes Goodreads CSV through genre enrichment 
    to final dashboard-ready JSON.
    
    Workflow:
    1. CSV -> BookAnalytics (comprehensive book data)
    2. BookAnalytics -> BookInfo (for genre enrichment)
    3. Genre enrichment -> Enhanced BookAnalytics
    4. Enhanced BookAnalytics -> Final JSON
    """
    
    def __init__(self, rate_limit: float = 1.0):
        self.csv_processor = AnalyticsCSVProcessor()
        self.genre_enricher = GenreEnricher(rate_limit=rate_limit)
        self.json_exporter = FinalJSONExporter()
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def process_csv_to_dashboard_json(
        self,
        csv_path: str,
        output_json_path: Optional[str] = None,
        sample_size: Optional[int] = None,
        include_unread: bool = False,
        enrich_genres: bool = True
    ) -> str:
        """
        Complete pipeline: CSV to dashboard JSON.
        
        Args:
            csv_path: Path to Goodreads CSV export
            output_json_path: Where to save final JSON (if None, generates UUID filename)
            sample_size: Optional limit on books to process
            include_unread: Whether to include to-read books
            enrich_genres: Whether to run genre enrichment (can be False for testing)
            
        Returns:
            Path to created JSON file
        """
        self.logger.info("🚀 Starting integrated book processing pipeline")
        
        # Step 1: Load CSV into BookAnalytics objects
        self.logger.info("📊 Step 1: Loading books from CSV")
        books = self.csv_processor.load_books_for_analytics(
            csv_path, 
            include_unread=include_unread,
            sample_size=sample_size
        )
        
        if not books:
            raise ValueError("No books loaded from CSV. Check file path and filters.")
        
        # Step 2: Enrich genres (optional)
        if enrich_genres:
            self.logger.info("🔍 Step 2: Enriching genres via APIs")
            enriched_books = self._enrich_book_genres(books)
        else:
            self.logger.info("⏭️  Step 2: Skipping genre enrichment")
            enriched_books = books
        
        # Step 3: Export to final JSON
        self.logger.info("💾 Step 3: Exporting to dashboard JSON")
        json_path = create_dashboard_json(enriched_books, output_json_path)
        
        self.logger.info(f"✅ Pipeline complete! Dashboard JSON saved to: {json_path}")
        return json_path
    
    def _enrich_book_genres(self, books: List[BookAnalytics]) -> List[BookAnalytics]:
        """
        Enrich genres for BookAnalytics objects using the existing genre pipeline.
        
        Args:
            books: List of BookAnalytics objects
            
        Returns:
            List of BookAnalytics objects with enriched genres
        """
        enriched_books = []
        
        for i, book in enumerate(books, 1):
            self.logger.info(f"Enriching genres {i}/{len(books)}: {book.title}")
            
            try:
                # Convert BookAnalytics -> BookInfo for genre enrichment
                book_info = self._book_analytics_to_book_info(book)
                
                # Enrich genres using existing pipeline
                enriched_book_data = self.genre_enricher.enrich_book(book_info)
                
                # Transfer enriched genres back to BookAnalytics
                enhanced_book = self._transfer_enriched_genres(book, enriched_book_data)
                enriched_books.append(enhanced_book)
                
            except Exception as e:
                self.logger.error(f"Failed to enrich genres for '{book.title}': {e}")
                # Keep original book without enrichment
                enriched_books.append(book)
        
        # Log enrichment summary
        successful_enrichments = sum(1 for book in enriched_books if book.genre_enrichment_success)
        self.logger.info(f"Genre enrichment complete: {successful_enrichments}/{len(books)} books enriched")
        
        return enriched_books
    
    def _book_analytics_to_book_info(self, book: BookAnalytics) -> BookInfo:
        """Convert BookAnalytics to BookInfo for genre enrichment"""
        return BookInfo(
            title=book.title,
            author=book.author,
            isbn13=book.isbn13,
            isbn=book.isbn,
            goodreads_id=book.goodreads_id
        )
    
    def _transfer_enriched_genres(self, original_book: BookAnalytics, enriched_data) -> BookAnalytics:
        """
        Transfer enriched genre data from EnrichedBook back to BookAnalytics.
        
        Args:
            original_book: Original BookAnalytics object
            enriched_data: EnrichedBook from genre enrichment pipeline
            
        Returns:
            BookAnalytics with enriched genre data
        """
        # Create a copy of the original book
        enhanced_book = BookAnalytics(
            # Copy all original fields
            goodreads_id=original_book.goodreads_id,
            title=original_book.title,
            author=original_book.author,
            author_lf=original_book.author_lf,
            additional_authors=original_book.additional_authors,
            isbn=original_book.isbn,
            isbn13=original_book.isbn13,
            my_rating=original_book.my_rating,
            average_rating=original_book.average_rating,
            publisher=original_book.publisher,
            binding=original_book.binding,
            num_pages=original_book.num_pages,
            year_published=original_book.year_published,
            original_publication_year=original_book.original_publication_year,
            date_read=original_book.date_read,
            date_added=original_book.date_added,
            reading_status=original_book.reading_status,
            bookshelves=original_book.bookshelves,
            bookshelves_with_positions=original_book.bookshelves_with_positions,
            my_review=original_book.my_review,
            private_notes=original_book.private_notes,
            has_spoilers=original_book.has_spoilers,
            read_count_original=original_book.read_count_original,
            owned_copies=original_book.owned_copies,
            
            # Add enriched genre data
            final_genres=enriched_data.final_genres,
            genre_enrichment_success=len(enriched_data.final_genres) > 0
        )
        
        return enhanced_book


def quick_pipeline(
    csv_path: str = "data/goodreads_library_export-2025.06.15.csv",
    output_path: Optional[str] = None,
    sample_size: int = 10,
    enrich_genres: bool = True
) -> str:
    """
    Quick convenience function for testing the complete pipeline.
    
    Args:
        csv_path: Path to Goodreads CSV
        output_path: Output JSON path (if None, generates UUID filename)
        sample_size: Number of books to process (small for testing)
        enrich_genres: Whether to run genre enrichment
        
    Returns:
        Path to created JSON file
    """
    pipeline = IntegratedBookPipeline(rate_limit=1.0)
    
    return pipeline.process_csv_to_dashboard_json(
        csv_path=csv_path,
        output_json_path=output_path,
        sample_size=sample_size,
        include_unread=False,  # Only read books for dashboard
        enrich_genres=enrich_genres
    )