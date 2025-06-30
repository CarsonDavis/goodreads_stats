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
from genres.enrichment.book_pipeline import BookInfo
from genres.enrichment.async_genre_enricher import AsyncGenreEnricher


async def enrich_single_book(book_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enrich a single book using the existing AsyncGenreEnricher.
    
    Args:
        book_data: Dictionary containing book information
        
    Returns:
        Dictionary containing enriched book data
    """
    try:
        # Create BookInfo object from input data
        book_info = BookInfo(**book_data)
        
        # Use existing enricher with concurrency=1 for single book
        async with AsyncGenreEnricher(max_concurrent=1) as enricher:
            enriched_book = await enricher.enrich_book_async(book_info)
            
            # Return enriched data in expected format
            return {
                'statusCode': 200,
                'body': {
                    'isbn': enriched_book.isbn,
                    'title': enriched_book.title,
                    'author': enriched_book.author,
                    'final_genres': enriched_book.final_genres,
                    'thumbnail_url': enriched_book.thumbnail_url,
                    'genre_sources': enriched_book.genre_sources,
                    'enrichment_logs': enriched_book.enrichment_logs,
                    'genre_enrichment_success': len(enriched_book.final_genres) > 0
                }
            }
            
    except Exception as e:
        logger.error(f"Error enriching book {book_data.get('title', 'Unknown')}: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'isbn': book_data.get('isbn', ''),
                'title': book_data.get('title', ''),
                'author': book_data.get('author', ''),
                'final_genres': [],
                'thumbnail_url': None,
                'genre_sources': [],
                'enrichment_logs': [f"Enrichment failed: {str(e)}"],
                'genre_enrichment_success': False,
                'error': str(e)
            }
        }


def lambda_handler(event, context):
    """
    Lambda handler for processing a single book.
    
    Expected event format:
    {
        "book": {
            "isbn": "...",
            "title": "...",
            "author": "...",
            ...
        }
    }
    """
    try:
        logger.info(f"Processing book: {event.get('book', {}).get('title', 'Unknown')}")
        
        # Extract book data from event
        book_data = event.get('book', {})
        if not book_data:
            raise ValueError("No book data provided in event")
        
        # Run async enrichment
        result = asyncio.run(enrich_single_book(book_data))
        
        logger.info(f"Successfully processed book: {book_data.get('title', 'Unknown')}")
        return result
        
    except Exception as e:
        logger.error(f"Lambda handler error: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'final_genres': [],
                'genre_enrichment_success': False
            }
        }