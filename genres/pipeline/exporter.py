"""
Final JSON exporter for dashboard consumption.

Workflow: CSV -> Genre Enrichment -> BookAnalytics -> Final JSON
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from ..models.analytics import BookAnalytics


class FinalJSONExporter:
    """
    Exports a collection of BookAnalytics objects (with enriched genres) to final JSON.
    
    The resulting JSON is optimized for dashboard consumption and includes:
    - All analytics data from BookAnalytics
    - Enriched genre information from the pipeline
    - Metadata about the export process
    - Validation statistics
    """
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def export_books_to_json(
        self, 
        books: List[BookAnalytics], 
        output_path: Optional[str] = None,
        include_metadata: bool = True
    ) -> Dict[str, Any]:
        """
        Export enriched books to final JSON for dashboard consumption.
        
        Args:
            books: List of BookAnalytics objects with enriched genres
            output_path: Path where to save the JSON file (if None, generates UUID filename)
            include_metadata: Whether to include export metadata
            
        Returns:
            Dictionary containing the exported data structure with 'export_path' added
        """
        # Generate export UUID for tracking and filename
        export_uuid = str(uuid.uuid4())
        
        # Generate UUID filename if no path provided
        if output_path is None:
            output_path = f"dashboard_data/{export_uuid}.json"
        
        self.logger.info(f"Exporting {len(books)} books to {output_path}")
        
        # Convert books to dashboard format
        dashboard_books = []
        for book in books:
            dashboard_data = book.to_dashboard_dict()
            dashboard_books.append(dashboard_data)
        
        # Create the final data structure
        export_data = {
            "export_id": export_uuid,
            "books": dashboard_books,
            "summary": self._generate_summary_stats(books),
        }
        
        if include_metadata:
            export_data["metadata"] = self._generate_metadata(books, export_uuid)
        
        # Ensure output directory exists
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to JSON file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"Successfully exported to {output_path}")
        self.logger.info(f"Export ID: {export_uuid}")
        self.logger.info(f"Export summary: {export_data['summary']['total_books']} books, "
                        f"{export_data['summary']['read_books']} read, "
                        f"{export_data['summary']['genre_enriched_books']} with genres")
        
        # Add export path to returned data
        export_data["export_path"] = str(output_path)
        return export_data
    
    def _generate_summary_stats(self, books: List[BookAnalytics]) -> Dict[str, Any]:
        """Generate summary statistics for the exported data"""
        read_books = [book for book in books if book.is_read]
        rated_books = [book for book in books if book.is_rated]
        genre_enriched = [book for book in books if book.genre_enrichment_success]
        
        # Time range analysis
        read_dates = [book.date_read for book in read_books if book.date_read]
        min_date = min(read_dates) if read_dates else None
        max_date = max(read_dates) if read_dates else None
        
        # Genre statistics
        all_genres = []
        for book in books:
            all_genres.extend(book.final_genres)
        
        unique_genres = list(set(all_genres))
        
        return {
            "total_books": len(books),
            "read_books": len(read_books),
            "rated_books": len(rated_books),
            "genre_enriched_books": len(genre_enriched),
            "genre_enrichment_rate": len(genre_enriched) / len(books) * 100 if books else 0,
            "unique_authors": len(set(book.author for book in books)),
            "unique_genres": len(unique_genres),
            "total_pages": sum(book.num_pages for book in read_books if book.num_pages),
            "reading_date_range": {
                "earliest": min_date.isoformat() if min_date else None,
                "latest": max_date.isoformat() if max_date else None
            },
            "reading_years": sorted(list(set(book.reading_year for book in read_books if book.reading_year))),
            "average_rating": sum(book.my_rating for book in rated_books) / len(rated_books) if rated_books else None,
            "most_common_genres": self._get_top_genres(all_genres, top_n=10)
        }
    
    def _get_top_genres(self, all_genres: List[str], top_n: int = 10) -> List[Dict[str, Any]]:
        """Get the most common genres with counts"""
        from collections import Counter
        
        genre_counts = Counter(all_genres)
        top_genres = []
        
        for genre, count in genre_counts.most_common(top_n):
            top_genres.append({
                "genre": genre,
                "count": count,
                "percentage": count / len(all_genres) * 100 if all_genres else 0
            })
        
        return top_genres
    
    def _generate_metadata(self, books: List[BookAnalytics], export_id: str) -> Dict[str, Any]:
        """Generate metadata about the export process"""
        return {
            "export_id": export_id,
            "export_timestamp": datetime.now().isoformat(),
            "exporter_version": "1.0.0",
            "data_schema_version": "1.0.0",
            "export_source": "goodreads_csv_with_genre_enrichment",
            "processing_notes": [
                "Re-reads treated as single entries using latest read date",
                "Genres enriched via Google Books and Open Library APIs",
                "Unrated books (rating=0) treated as None for analytics"
            ],
            "validation": {
                "books_with_missing_dates": sum(1 for book in books if book.is_read and not book.date_read),
                "books_with_missing_pages": sum(1 for book in books if book.is_read and not book.num_pages),
                "re_read_books_original_count": sum(1 for book in books if book.read_count_original > 1),
                "genre_sources_success": {
                    "google_books": sum(1 for book in books if "Google Books" in str(book.final_genres)),
                    "open_library": sum(1 for book in books if "Open Library" in str(book.final_genres)),
                    "both_sources": sum(1 for book in books if book.genre_enrichment_success),
                    "no_genres": sum(1 for book in books if not book.final_genres)
                }
            }
        }
    
    def validate_export(self, export_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate the exported data structure for dashboard compatibility.
        
        Args:
            export_data: The exported data dictionary
            
        Returns:
            Validation report with any issues found
        """
        issues = []
        warnings = []
        
        # Check required top-level keys
        required_keys = ["books", "summary"]
        for key in required_keys:
            if key not in export_data:
                issues.append(f"Missing required key: {key}")
        
        # Validate books array
        if "books" in export_data:
            books = export_data["books"]
            
            if not isinstance(books, list):
                issues.append("'books' should be an array")
            else:
                # Check a sample of books for required fields
                required_book_fields = ["goodreads_id", "title", "author", "reading_status"]
                
                for i, book in enumerate(books[:5]):  # Check first 5 books
                    for field in required_book_fields:
                        if field not in book:
                            issues.append(f"Book {i} missing required field: {field}")
                
                # Check for data consistency
                read_books = [book for book in books if book.get("reading_status") == "read"]
                books_with_dates = [book for book in books if book.get("date_read")]
                
                if len(read_books) > len(books_with_dates):
                    warnings.append(f"{len(read_books) - len(books_with_dates)} read books missing read dates")
        
        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "warnings": warnings,
            "book_count": len(export_data.get("books", [])),
            "summary_stats": export_data.get("summary", {})
        }


def create_dashboard_json(
    books: List[BookAnalytics], 
    output_path: Optional[str] = None
) -> str:
    """
    Convenience function to create final dashboard JSON.
    
    Args:
        books: List of BookAnalytics objects with enriched genres
        output_path: Where to save the JSON file (if None, generates UUID filename)
        
    Returns:
        Path to the created JSON file
    """
    exporter = FinalJSONExporter()
    export_data = exporter.export_books_to_json(books, output_path)
    
    # Validate the export
    validation = exporter.validate_export(export_data)
    
    if not validation["is_valid"]:
        raise ValueError(f"Export validation failed: {validation['issues']}")
    
    if validation["warnings"]:
        logger = logging.getLogger(__name__)
        for warning in validation["warnings"]:
            logger.warning(warning)
    
    return export_data["export_path"]