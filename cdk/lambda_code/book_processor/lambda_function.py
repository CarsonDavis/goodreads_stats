import json
import asyncio
import logging
from typing import Dict, Any

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import existing enrichment functionality
import sys
sys.path.append('/opt/python')
from genres.models.book import BookInfo
from genres.pipeline.enricher import AsyncGenreEnricher


def lambda_handler(event, context):
    """
    Lambda handler that processes individual books and returns enriched data directly.
    
    Expected event format (direct invocation):
    {
        "book": {
            "title": "Book Title",
            "author": "Author Name", 
            "isbn13": "9781234567890",
            "isbn": "1234567890",
            "goodreads_id": "12345"
        }
    }
    """
    try:
        logger.info(f"BookProcessor invoked for book enrichment")
        
        # Extract book data from direct invocation
        book_data = event.get('book', {})
        if not book_data:
            raise ValueError("No book data provided in event")
        
        logger.info(f"Processing book: {book_data.get('title', 'Unknown')} by {book_data.get('author', 'Unknown')}")
        
        # Process the book
        result = asyncio.run(enrich_single_book(book_data))
        logger.info(f"Successfully processed book: {book_data.get('title', 'Unknown')}")
        return result
        
    except Exception as e:
        logger.error(f"BookProcessor failed: {e}", exc_info=True)
        return create_failed_result(event.get('book', {}), str(e))


async def enrich_single_book(book_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich a single book using the existing AsyncGenreEnricher.
    
    Args:
        book_data: Dictionary containing book information
        
    Returns:
        Dictionary containing enriched book data in standardized format
    """
    try:
        # Create BookInfo object from input data - filter to only expected fields
        book_info_fields = {
            'title': book_data.get('title'),
            'author': book_data.get('author'), 
            'isbn13': book_data.get('isbn13'),
            'isbn': book_data.get('isbn'),
            'goodreads_id': book_data.get('goodreads_id')
        }
        book_info = BookInfo(**book_info_fields)
        
        # Use existing enricher with concurrency=1 for single book
        async with AsyncGenreEnricher(max_concurrent=1) as enricher:
            enriched_book = await enricher.enrich_book_async(book_info)
            
            # Return enriched data in standardized format for orchestrator
            return {
                'book_id': enriched_book.input_info.goodreads_id or f"{enriched_book.input_info.title}-{enriched_book.input_info.author}",
                'title': enriched_book.input_info.title,
                'author': enriched_book.input_info.author,
                'success': True,
                'final_genres': enriched_book.final_genres,
                'thumbnail_url': enriched_book.thumbnail_url,
                'genre_enrichment_success': len(enriched_book.final_genres) > 0,
                'error_message': None,
                'processing_logs': enriched_book.processing_log
            }
            
    except asyncio.TimeoutError:
        logger.warning(f"Timeout enriching book {book_data.get('title', 'Unknown')}")
        return create_failed_result(book_data, "API timeout during enrichment")
    except Exception as e:
        logger.error(f"Error enriching book {book_data.get('title', 'Unknown')}: {str(e)}")
        return create_failed_result(book_data, f"Enrichment failed: {str(e)}")


def create_failed_result(book_data: Dict[str, Any], error_message: str) -> Dict[str, Any]:
    """
    Create a standardized failed result.
    
    Args:
        book_data: Original book data
        error_message: Error message
        
    Returns:
        Standardized failed result dictionary
    """
    return {
        'book_id': book_data.get('goodreads_id') or f"{book_data.get('title', '')}-{book_data.get('author', '')}",
        'title': book_data.get('title', ''),
        'author': book_data.get('author', ''),
        'success': False,
        'final_genres': [],
        'thumbnail_url': None,
        'genre_enrichment_success': False,
        'error_message': error_message,
        'processing_logs': [f"Processing failed: {error_message}"]
    }