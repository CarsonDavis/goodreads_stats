"""
Analytics-focused CSV processor for creating BookAnalytics objects.
Parses all Goodreads CSV fields for comprehensive dashboard analytics.
"""

import pandas as pd
import re
import logging
from typing import List, Optional
from datetime import datetime, date

from ..models.analytics import BookAnalytics


class AnalyticsCSVProcessor:
    """
    Processes Goodreads CSV exports into BookAnalytics objects for dashboard analytics.
    
    Key features:
    - Parses all relevant CSV fields
    - Treats re-reads as single entries (uses latest read date)
    - Handles date parsing and data cleaning
    - Optimized for time-series analysis
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def load_books_for_analytics(
        self, 
        csv_path: str, 
        include_unread: bool = False,
        sample_size: Optional[int] = None
    ) -> List[BookAnalytics]:
        """
        Load books from Goodreads CSV for analytics purposes.
        
        Args:
            csv_path: Path to Goodreads CSV export
            include_unread: If True, include to-read and currently-reading books
            sample_size: Optional limit on number of books to load
            
        Returns:
            List of BookAnalytics objects ready for dashboard analysis
        """
        self.logger.info(f"Loading books for analytics from {csv_path}")
        
        df = pd.read_csv(csv_path)
        
        if sample_size:
            df = df.sample(n=min(sample_size, len(df)), random_state=42).reset_index(drop=True)
            self.logger.info(f"Sampling {len(df)} books from {len(pd.read_csv(csv_path))} total")
        
        books = []
        for _, row in df.iterrows():
            book = self._row_to_book_analytics(row)
            if book:
                # Filter based on reading status
                if include_unread or book.is_read:
                    books.append(book)
        
        read_books = sum(1 for book in books if book.is_read)
        self.logger.info(f"Loaded {len(books)} books for analytics ({read_books} read)")
        
        return books
    
    def _row_to_book_analytics(self, row: pd.Series) -> Optional[BookAnalytics]:
        """
        Convert a CSV row to a BookAnalytics object.
        
        Args:
            row: Pandas Series representing a CSV row
            
        Returns:
            BookAnalytics object or None if row is invalid
        """
        try:
            # Parse bookshelves
            bookshelves = self._parse_bookshelves(row.get("Bookshelves", ""))
            
            book = BookAnalytics(
                # Core identification
                goodreads_id=str(row["Book Id"]),
                title=str(row["Title"]),
                author=str(row["Author"]),
                author_lf=self._safe_str(row.get("Author l-f")),
                additional_authors=self._safe_str(row.get("Additional Authors")),
                
                # ISBN data
                isbn=self._clean_isbn(row.get("ISBN", "")),
                isbn13=self._clean_isbn(row.get("ISBN13", "")),
                
                # Rating data
                my_rating=self._safe_int(row.get("My Rating")),
                average_rating=self._safe_float(row.get("Average Rating")),
                
                # Publication info
                publisher=self._safe_str(row.get("Publisher")),
                binding=self._safe_str(row.get("Binding")),
                num_pages=self._safe_int(row.get("Number of Pages")),
                year_published=self._safe_int(row.get("Year Published")),
                original_publication_year=self._safe_int(row.get("Original Publication Year")),
                
                # Reading timeline - KEY FOR ANALYTICS
                date_read=self._parse_date(row.get("Date Read")),
                date_added=self._parse_date(row.get("Date Added")),
                reading_status=self._safe_str(row.get("Exclusive Shelf")),
                
                # Organization
                bookshelves=bookshelves,
                bookshelves_with_positions=self._safe_str(row.get("Bookshelves with positions")),
                
                # User content
                my_review=self._safe_str(row.get("My Review")),
                private_notes=self._safe_str(row.get("Private Notes")),
                has_spoilers=self._parse_boolean(row.get("Spoiler", "")),
                
                # Metadata (store but ignore for analytics)
                read_count_original=max(1, self._safe_int(row.get("Read Count", 1)) or 1),
                owned_copies=self._safe_int(row.get("Owned Copies", 0)) or 0
            )
            
            return book
            
        except Exception as e:
            self.logger.warning(f"Failed to process row: {e}")
            return None
    
    def _parse_date(self, date_str: str) -> Optional[date]:
        """Parse date string to date object"""
        if not date_str or pd.isna(date_str) or date_str.strip() == "":
            return None
        
        # Handle common Goodreads date formats
        date_formats = [
            "%Y/%m/%d",     # 2024/11/28
            "%Y-%m-%d",     # 2024-11-28
            "%m/%d/%Y",     # 11/28/2024
            "%Y/%m",        # 2024/11 (assume first of month)
            "%Y"            # 2024 (assume January 1st)
        ]
        
        date_str = str(date_str).strip()
        
        for fmt in date_formats:
            try:
                parsed = datetime.strptime(date_str, fmt)
                return parsed.date()
            except ValueError:
                continue
        
        self.logger.warning(f"Could not parse date: {date_str}")
        return None
    
    def _parse_bookshelves(self, shelves_str: str) -> List[str]:
        """Parse comma-separated bookshelves"""
        if not shelves_str or pd.isna(shelves_str):
            return []
        
        shelves = [shelf.strip() for shelf in str(shelves_str).split(',')]
        return [shelf for shelf in shelves if shelf]
    
    def _clean_isbn(self, isbn_str: str) -> Optional[str]:
        """Clean ISBN from Excel formatting"""
        if not isbn_str or pd.isna(isbn_str):
            return None
        
        # Remove Excel formula formatting (e.g., ="1234567890")
        clean_isbn = re.sub(r'^="?([0-9X]+)"?$', r"\1", str(isbn_str))
        
        # Remove any non-alphanumeric characters except X
        clean_isbn = re.sub(r"[^0-9X]", "", clean_isbn.upper())
        
        # Validate length (ISBN-10 or ISBN-13)
        if len(clean_isbn) in [10, 13]:
            return clean_isbn
        
        return None
    
    def _safe_str(self, value) -> Optional[str]:
        """Safely convert to string, handling NaN"""
        if pd.isna(value) or value == "":
            return None
        return str(value).strip()
    
    def _safe_int(self, value) -> Optional[int]:
        """Safely convert to int, handling NaN and invalid values"""
        if pd.isna(value) or value == "" or value == 0:
            return None
        try:
            return int(float(value))  # Handle "3.0" -> 3
        except (ValueError, TypeError):
            return None
    
    def _safe_float(self, value) -> Optional[float]:
        """Safely convert to float, handling NaN"""
        if pd.isna(value) or value == "":
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def _parse_boolean(self, value) -> bool:
        """Safely parse boolean values from CSV"""
        if pd.isna(value) or value == "" or value is None:
            return False
        
        str_value = str(value).lower().strip()
        return str_value in ["true", "yes", "1", "y"]
    
    def export_analytics_summary(self, books: List[BookAnalytics]) -> dict:
        """
        Generate a summary report for analytics validation.
        
        Args:
            books: List of BookAnalytics objects
            
        Returns:
            Dictionary with summary statistics
        """
        read_books = [book for book in books if book.is_read]
        rated_books = [book for book in books if book.is_rated]
        
        return {
            "total_books": len(books),
            "read_books": len(read_books),
            "rated_books": len(rated_books),
            "books_with_dates": sum(1 for book in read_books if book.date_read),
            "books_with_pages": sum(1 for book in read_books if book.num_pages),
            "re_read_count": sum(1 for book in books if book.read_count_original > 1),
            "reading_years": sorted(list(set(book.reading_year for book in read_books if book.reading_year))),
            "avg_rating": sum(book.my_rating for book in rated_books) / len(rated_books) if rated_books else 0,
            "total_pages": sum(book.num_pages for book in read_books if book.num_pages),
            "unique_authors": len(set(book.author for book in books)),
            "unique_publishers": len(set(book.publisher for book in books if book.publisher))
        }