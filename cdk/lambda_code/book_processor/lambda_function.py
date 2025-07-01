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
            
            # Return enriched data in expected format
            return {
                'statusCode': 200,
                'body': {
                    'isbn': enriched_book.input_info.isbn,
                    'title': enriched_book.input_info.title,
                    'author': enriched_book.input_info.author,
                    'final_genres': enriched_book.final_genres,
                    'thumbnail_url': enriched_book.thumbnail_url,
                    'genre_sources': getattr(enriched_book, 'genre_sources', []),
                    'enrichment_logs': enriched_book.processing_log,
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
    Lambda handler that processes books from SQS events.
    
    SQS event format:
    {
        "Records": [
            {
                "body": "{\"book\": {...}, \"processing_uuid\": \"...\", ...}"
            }
        ]
    }
    """
    try:
        logger.info(f"BookProcessor invoked with {len(event.get('Records', []))} records")
        
        # Handle SQS event
        if 'Records' in event:
            results = []
            for record in event['Records']:
                try:
                    # Parse SQS message body
                    message_body = json.loads(record['body'])
                    book_data = message_body.get('book', {})
                    processing_uuid = message_body.get('processing_uuid')
                    
                    if not book_data:
                        raise ValueError("No book data in SQS message")
                    
                    logger.info(f"Processing book: {book_data.get('title', 'Unknown')} for UUID: {processing_uuid}")
                    
                    # Process the book
                    result = asyncio.run(enrich_single_book(book_data))
                    
                    # Store enriched result in S3 for aggregator (both success and failure)
                    if processing_uuid:
                        store_enriched_result(processing_uuid, book_data, result, message_body)
                    
                    results.append(result)
                    logger.info(f"Successfully processed book: {book_data.get('title', 'Unknown')}")
                    
                except Exception as e:
                    logger.error(f"Error processing SQS record: {e}", exc_info=True)
                    # Don't fail the entire batch, just log the error
                    results.append({
                        'statusCode': 500,
                        'body': {
                            'error': str(e),
                            'final_genres': [],
                            'genre_enrichment_success': False
                        }
                    })
            
            return {
                'statusCode': 200,
                'processedRecords': len(results),
                'results': results
            }
        
        # Fallback for direct invocation (backward compatibility)
        else:
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


def store_enriched_result(processing_uuid: str, book_data: Dict, result: Dict, message_body: Dict):
    """Store enriched result in S3 for aggregator to collect"""
    import boto3
    import os
    
    s3_client = boto3.client('s3')
    data_bucket = os.environ.get('DATA_BUCKET')
    
    if not data_bucket:
        logger.warning("DATA_BUCKET not set, skipping result storage")
        return
    
    try:
        # Create a unique key for this enriched result
        book_title = book_data.get('title', 'unknown').replace('/', '_').replace('\\', '_')
        book_isbn = book_data.get('isbn', book_data.get('isbn13', 'no-isbn'))
        result_key = f"processing/{processing_uuid}/enriched/{book_isbn}_{book_title[:50]}.json"
        
        # Store the enriched result
        enriched_data = {
            'original_book': book_data,
            'enriched_result': result,
            'processing_uuid': processing_uuid,
            'timestamp': str(int(__import__('time').time()))
        }
        
        s3_client.put_object(
            Bucket=data_bucket,
            Key=result_key,
            Body=json.dumps(enriched_data),
            ContentType='application/json'
        )
        
        logger.info(f"Stored enriched result: {result_key}")
        
    except Exception as e:
        logger.error(f"Failed to store enriched result: {e}")
        # Don't fail the processing, just log the error