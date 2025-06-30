import json
import boto3
import os
import logging
from typing import List, Dict, Any

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Import existing analytics and export functionality
import sys
sys.path.append('/opt/python')
from genres.analytics.book_analytics import BookAnalytics
from genres.export.dashboard_json_exporter import create_dashboard_json

# Initialize S3 client
s3_client = boto3.client('s3')


def merge_enriched_data(original_books: List[Dict], enriched_results: List[Dict]) -> List[BookAnalytics]:
    """
    Merge enriched data back into BookAnalytics objects.
    
    Args:
        original_books: List of original book dictionaries
        enriched_results: List of enrichment results from BookProcessor
        
    Returns:
        List of enhanced BookAnalytics objects
    """
    enhanced_books = []
    
    for original_book, enriched_result in zip(original_books, enriched_results):
        try:
            # Create BookAnalytics object from original data
            book = BookAnalytics(**original_book)
            
            # Apply enrichment if successful
            if enriched_result.get('statusCode') == 200:
                enriched_body = enriched_result.get('body', {})
                
                # Update with enriched data
                book.final_genres = enriched_body.get('final_genres', [])
                book.genre_enrichment_success = enriched_body.get('genre_enrichment_success', False)
                book.thumbnail_url = enriched_body.get('thumbnail_url')
                book.genre_sources = enriched_body.get('genre_sources', [])
                book.enrichment_logs = enriched_body.get('enrichment_logs', [])
                
                logger.info(f"Successfully merged enrichment for: {book.title}")
            else:
                # Handle failed enrichment
                book.final_genres = []
                book.genre_enrichment_success = False
                book.enrichment_logs = [f"Enrichment failed: {enriched_result.get('body', {}).get('error', 'Unknown error')}"]
                
                logger.warning(f"Enrichment failed for: {book.title}")
            
            enhanced_books.append(book)
            
        except Exception as e:
            logger.error(f"Error merging data for book {original_book.get('title', 'Unknown')}: {str(e)}")
            # Create a basic BookAnalytics object with error info
            try:
                book = BookAnalytics(**original_book)
                book.final_genres = []
                book.genre_enrichment_success = False
                book.enrichment_logs = [f"Merge error: {str(e)}"]
                enhanced_books.append(book)
            except Exception as inner_e:
                logger.error(f"Failed to create BookAnalytics object: {str(inner_e)}")
                continue
    
    return enhanced_books


def update_processing_status(processing_uuid: str, status: str, progress: int = 100, message: str = ""):
    """
    Update processing status in S3.
    
    Args:
        processing_uuid: Unique identifier for the processing job
        status: Status to set ('complete', 'error', etc.)
        progress: Progress percentage (default 100)
        message: Additional status message
    """
    try:
        bucket_name = os.environ['S3_BUCKET_NAME']
        status_key = f"status/{processing_uuid}.json"
        
        status_data = {
            'status': status,
            'progress': progress,
            'message': message,
            'timestamp': str(int(time.time()))
        }
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=status_key,
            Body=json.dumps(status_data),
            ContentType='application/json'
        )
        
        logger.info(f"Updated status for {processing_uuid}: {status}")
        
    except Exception as e:
        logger.error(f"Failed to update status: {str(e)}")


def lambda_handler(event, context):
    """
    Lambda handler for aggregating enriched book results.
    
    Expected event format:
    {
        "processing_uuid": "...",
        "original_books": [...],
        "enriched_results": [...]
    }
    """
    import time
    
    try:
        logger.info("Starting result aggregation")
        
        # Extract data from event
        processing_uuid = event.get('processing_uuid')
        original_books = event.get('original_books', [])
        
        # Handle Step Functions Map state output format
        enriched_results = event.get('enriched_results', [])
        if isinstance(enriched_results, list) and len(enriched_results) > 0:
            # If results are nested (from Step Functions), flatten them
            if isinstance(enriched_results[0], list):
                enriched_results = [item for sublist in enriched_results for item in sublist]
        
        if not processing_uuid:
            raise ValueError("No processing_uuid provided")
        
        if not original_books:
            raise ValueError("No original_books provided")
        
        if not enriched_results:
            raise ValueError("No enriched_results provided")
        
        logger.info(f"Processing {len(original_books)} books for UUID: {processing_uuid}")
        
        # Merge enriched data back into BookAnalytics objects
        enhanced_books = merge_enriched_data(original_books, enriched_results)
        
        if not enhanced_books:
            raise ValueError("No enhanced books created")
        
        # Generate dashboard JSON using existing exporter
        bucket_name = os.environ['S3_BUCKET_NAME']
        output_path = f"s3://{bucket_name}/data/{processing_uuid}/"
        
        logger.info(f"Creating dashboard JSON at: {output_path}")
        create_dashboard_json(enhanced_books, output_path)
        
        # Update status to complete
        update_processing_status(
            processing_uuid, 
            'complete', 
            100, 
            f"Successfully processed {len(enhanced_books)} books"
        )
        
        logger.info(f"Successfully completed aggregation for {processing_uuid}")
        
        return {
            'statusCode': 200,
            'body': {
                'processing_uuid': processing_uuid,
                'books_processed': len(enhanced_books),
                'successful_enrichments': sum(1 for book in enhanced_books if book.genre_enrichment_success),
                'message': 'Aggregation completed successfully'
            }
        }
        
    except Exception as e:
        logger.error(f"Aggregation error: {str(e)}")
        
        # Update status to error if we have a processing_uuid
        if 'processing_uuid' in locals():
            update_processing_status(
                processing_uuid, 
                'error', 
                0, 
                f"Aggregation failed: {str(e)}"
            )
        
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message': 'Aggregation failed'
            }
        }