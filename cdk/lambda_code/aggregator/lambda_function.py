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
from genres.models.analytics import BookAnalytics
from genres.pipeline.exporter import create_dashboard_json

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
            # Filter out computed properties that aren't constructor parameters
            filtered_book_data = {k: v for k, v in original_book.items() 
                                if k not in ['reading_year', 'reading_month_year', 'is_rated', 
                                           'page_category', 'has_review', 'was_reread']}
            
            # Map field names to match BookAnalytics constructor
            field_mappings = {
                'genres': 'final_genres',
                'publication_year': 'original_publication_year', 
                'genre_enriched': 'genre_enrichment_success',
                'original_read_count': 'read_count_original'
            }
            
            for old_name, new_name in field_mappings.items():
                if old_name in filtered_book_data:
                    filtered_book_data[new_name] = filtered_book_data.pop(old_name)
            
            # Convert date strings to date objects
            from datetime import datetime
            if 'date_read' in filtered_book_data and filtered_book_data['date_read']:
                filtered_book_data['date_read'] = datetime.fromisoformat(filtered_book_data['date_read']).date()
            
            # Provide defaults for missing constructor fields not in dashboard dict
            filtered_book_data.setdefault('author_lf', None)
            filtered_book_data.setdefault('additional_authors', None)
            filtered_book_data.setdefault('year_published', None)
            filtered_book_data.setdefault('date_added', None)
            filtered_book_data.setdefault('bookshelves_with_positions', None)
            filtered_book_data.setdefault('owned_copies', 0)
            
            # Create BookAnalytics object from filtered data
            book = BookAnalytics(**filtered_book_data)
            
            # Apply enrichment if successful
            if enriched_result.get('statusCode') == 200:
                enriched_body = enriched_result.get('body', {})
                
                # Update with enriched data
                book.final_genres = enriched_body.get('final_genres', [])
                book.genre_enrichment_success = enriched_body.get('genre_enrichment_success', False)
                book.thumbnail_url = enriched_body.get('thumbnail_url')
                book.small_thumbnail_url = enriched_body.get('small_thumbnail_url')
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
        import time
        bucket_name = os.environ['S3_BUCKET_NAME']
        status_key = f"status/{processing_uuid}.json"
        
        # Get current status and update it
        try:
            obj = s3_client.get_object(Bucket=bucket_name, Key=status_key)
            current_status = json.loads(obj['Body'].read().decode('utf-8'))
        except:
            current_status = {}
        
        # Update with new values
        current_status.update({
            'status': status,
            'message': message,
            'last_updated': str(int(time.time())),
            'progress': {'percent_complete': progress}
        })
        
        s3_client.put_object(
            Bucket=bucket_name,
            Key=status_key,
            Body=json.dumps(current_status),
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
        "bucket": "bucket-name",
        "original_books_s3_key": "path/to/original_books.json",
        "enriched_results": [...]
    }
    """
    import time
    
    try:
        logger.info("Starting result aggregation")
        
        # Extract data from event
        processing_uuid = event.get('processing_uuid')
        bucket = event.get('bucket')
        original_books_s3_key = event.get('original_books_s3_key')
        
        # Load original books from S3
        if not bucket or not original_books_s3_key:
            raise ValueError("Missing bucket or original_books_s3_key")
            
        logger.info(f"Loading original books from s3://{bucket}/{original_books_s3_key}")
        obj = s3_client.get_object(Bucket=bucket, Key=original_books_s3_key)
        original_books = json.loads(obj['Body'].read().decode('utf-8'))
        
        # Handle Step Functions Map state output format
        # Step Functions Map state returns results as an array of task outputs
        enriched_results = event.get('enriched_results', [])
        
        # Map state output is already an array of individual Lambda results
        # No flattening needed - each item is a Lambda response
        
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
        import tempfile
        import os
        
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        # Create JSON locally first
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            local_json_path = f.name
        
        logger.info(f"Creating dashboard JSON locally at: {local_json_path}")
        json_file_path = create_dashboard_json(enhanced_books, local_json_path)
        
        # Upload to S3 (path must match what status_checker expects)
        s3_key = f"data/{processing_uuid}.json"
        logger.info(f"Uploading dashboard JSON to s3://{bucket_name}/{s3_key}")
        
        with open(json_file_path, 'rb') as f:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=f.read(),
                ContentType='application/json'
            )
        
        # Clean up local file
        os.unlink(json_file_path)
        
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