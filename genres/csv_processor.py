"""
CSV Processor - Handles loading and cleaning Goodreads CSV exports.
Separate from enrichment logic for clean separation of concerns.
"""

import pandas as pd
import re
import logging
from typing import List, Optional

from .models import BookInfo


class CSVProcessor:
    """
    Handles loading and processing Goodreads CSV exports into BookInfo objects.
    
    This class is responsible only for CSV handling and data cleaning,
    with no knowledge of enrichment or API operations.
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def load_books(self, csv_path: str, sample_size: Optional[int] = None) -> List[BookInfo]:
        """
        Load books from Goodreads CSV export.
        
        Args:
            csv_path: Path to Goodreads CSV export file
            sample_size: Optional limit on number of books to load
            
        Returns:
            List of BookInfo objects ready for enrichment
        """
        self.logger.info(f"Loading books from {csv_path}")
        
        df = pd.read_csv(csv_path)
        
        if sample_size:
            df = df.sample(n=min(sample_size, len(df)), random_state=42).reset_index(drop=True)
            self.logger.info(f"Sampling {len(df)} books from {len(pd.read_csv(csv_path))} total")
        
        books = []
        for _, row in df.iterrows():
            book = self._row_to_book_info(row)
            if book:
                books.append(book)
        
        self.logger.info(f"Loaded {len(books)} valid books for processing")
        return books
    
    def _row_to_book_info(self, row: pd.Series) -> Optional[BookInfo]:
        """
        Convert a CSV row to a BookInfo object.
        
        Args:
            row: Pandas Series representing a CSV row
            
        Returns:
            BookInfo object or None if row is invalid
        """
        try:
            # Clean ISBNs
            isbn13 = self._clean_isbn(row.get("ISBN13", ""))
            isbn = self._clean_isbn(row.get("ISBN", ""))
            
            # Create BookInfo
            book = BookInfo(
                title=str(row["Title"]),
                author=str(row["Author"]),
                isbn13=isbn13 if isbn13 else None,
                isbn=isbn if isbn else None,
                goodreads_id=str(row["Book Id"])
            )
            
            return book
            
        except Exception as e:
            self.logger.warning(f"Failed to process row: {e}")
            return None
    
    def _clean_isbn(self, isbn_str: str) -> str:
        """
        Clean ISBN from Excel formatting and validate.
        
        Args:
            isbn_str: Raw ISBN string from CSV
            
        Returns:
            Cleaned ISBN string or empty string if invalid
        """
        if not isbn_str or pd.isna(isbn_str):
            return ""
        
        # Remove Excel formula formatting (e.g., ="1234567890")
        clean_isbn = re.sub(r'^="?([0-9X]+)"?$', r"\1", str(isbn_str))
        
        # Remove any non-alphanumeric characters except X
        clean_isbn = re.sub(r"[^0-9X]", "", clean_isbn.upper())
        
        # Validate length (ISBN-10 or ISBN-13)
        if len(clean_isbn) in [10, 13]:
            return clean_isbn
        
        return ""