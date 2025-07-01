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
    Lambda handler that either loads books from S3 or processes a single book.
    
    For loading books:
    {
        "action": "load_books",
        "bucket": "bucket-name",
        "books_s3_key": "path/to/books.json"
    }
    
    For processing a single book:
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
        logger.info(f"BookProcessor invoked: {json.dumps(event, default=str)}")
        
        # Check if this is a load_books action
        if event.get('action') == 'load_books':
            return load_books_from_s3(event)
        else:
            # Process single book
            book_data = event.get('book', {})
            if not book_data:
                raise ValueError("No book data provided in event")
            
            result = asyncio.run(enrich_single_book(book_data))
            logger.info(f"Successfully processed book: {book_data.get('title', 'Unknown')}")
            return result
        
    except Exception as e:
        logger.error(f"BookProcessor failed: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'final_genres': [],
                'genre_enrichment_success': False
            }
        }


def load_books_from_s3(event):
    """Load books from S3 and return them for the Map state."""
    import boto3
    
    s3_client = boto3.client('s3')
    bucket = event['bucket']
    books_s3_key = event['books_s3_key']
    
    logger.info(f"Loading books from s3://{bucket}/{books_s3_key}")
    
    # Download books data
    obj = s3_client.get_object(Bucket=bucket, Key=books_s3_key)
    books_data = json.loads(obj['Body'].read().decode('utf-8'))
    
    logger.info(f"Loaded {len(books_data)} books from S3")
    
    # Return books data with other Step Function context
    return {
        'books': books_data,
        'processing_uuid': event.get('processing_uuid'),
        'bucket': bucket,
        'original_books_s3_key': event.get('original_books_s3_key')
    }