#!/usr/bin/env python3
"""
AWS Lambda Worker Function

This is the worker Lambda that processes individual books.
Deploy this as a separate Lambda function.

Function name: goodreads-genre-worker
Runtime: Python 3.12
Memory: 512MB
Timeout: 60 seconds
"""

import json
import logging
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """
    Lambda function to enrich a single book with genre data.
    
    Input event:
    {
        "book": {
            "title": "Book Title",
            "author": "Author Name", 
            "isbn13": "9781234567890",
            "isbn": "1234567890",
            "goodreads_id": "12345"
        }
    }
    
    Returns:
    {
        "final_genres": ["genre1", "genre2"],
        "google_response": {...},
        "openlib_edition_response": {...},
        "openlib_work_response": {...},
        "processed_google_genres": [...],
        "processed_openlib_genres": [...],
        "processing_log": [...]
    }
    """
    
    try:
        # Extract book info from event
        book_data = event.get('book', {})
        
        logger.info(f"Processing book: {book_data.get('title', 'Unknown')}")
        
        # Import here to avoid cold start overhead for non-genre operations
        from genres.models import BookInfo
        from genres.genre_enricher import GenreEnricher
        
        # Create BookInfo object
        book = BookInfo(
            title=book_data.get('title', ''),
            author=book_data.get('author', ''),
            isbn13=book_data.get('isbn13'),
            isbn=book_data.get('isbn'),
            goodreads_id=book_data.get('goodreads_id')
        )
        
        # Enrich the book
        enricher = GenreEnricher(rate_limit=0.0)  # No rate limiting needed in Lambda
        enriched_book = enricher.enrich_book(book)
        
        # Return enriched data
        response = {
            'final_genres': enriched_book.final_genres,
            'google_response': enriched_book.google_response,
            'openlib_edition_response': enriched_book.openlib_edition_response,
            'openlib_work_response': enriched_book.openlib_work_response,
            'processed_google_genres': enriched_book.processed_google_genres,
            'processed_openlib_genres': enriched_book.processed_openlib_genres,
            'processing_log': enriched_book.processing_log
        }
        
        logger.info(f"Successfully enriched: {len(enriched_book.final_genres)} final genres")
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing book: {str(e)}")
        return {
            'errorMessage': str(e),
            'errorType': type(e).__name__
        }

# For local testing
if __name__ == "__main__":
    # Test the Lambda function locally
    test_event = {
        "book": {
            "title": "The Great Gatsby",
            "author": "F. Scott Fitzgerald",
            "isbn13": "9780743273565",
            "goodreads_id": "4671"
        }
    }
    
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))