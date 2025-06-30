import json
import logging
import os
import asyncio
import boto3
from datetime import datetime
from typing import List, Dict, Any
import sys

# Add the shared layer to Python path
sys.path.append('/opt')

# Import our existing pipeline components
from genres.pipeline.csv_loader import AnalyticsCSVProcessor
from genres.pipeline.enricher import EnvironmentAwareBookPipeline
from genres.pipeline.exporter import create_dashboard_json
from genres.models.book_analytics import BookInfo

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')

# Configuration
DATA_BUCKET = os.environ['DATA_BUCKET']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')
MAX_CONCURRENT = int(os.environ.get('MAX_CONCURRENT', '10'))
API_TIMEOUT = int(os.environ.get('API_TIMEOUT', '30'))

def lambda_handler(event, context):
    """
    Main orchestrator function that processes uploaded CSV files.
    
    Expected event:
    {
        "uuid": "processing-uuid",
        "bucket": "s3-bucket-name", 
        "csv_key": "uploads/uuid/raw.csv"
    }
    """
    try:
        logger.info(f"Orchestrator invoked: {json.dumps(event, default=str)}")
        
        # Extract parameters
        processing_uuid = event['uuid']
        bucket = event['bucket']
        csv_key = event['csv_key']
        
        # Run the processing pipeline
        asyncio.run(process_csv_pipeline(processing_uuid, bucket, csv_key))
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'uuid': processing_uuid,
                'status': 'completed'
            })
        }
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
        
        # Try to update status to error
        try:
            processing_uuid = event.get('uuid')
            if processing_uuid:
                update_status(processing_uuid, 'error', error_message=str(e))
        except:
            pass
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }


async def process_csv_pipeline(processing_uuid: str, bucket: str, csv_key: str):
    """
    Main processing pipeline using our existing code.
    """
    logger.info(f"Starting processing pipeline for {processing_uuid}")
    
    try:
        # Step 1: Download CSV from S3
        logger.info(f"Downloading CSV from s3://{bucket}/{csv_key}")
        csv_obj = s3_client.get_object(Bucket=bucket, Key=csv_key)
        csv_content = csv_obj['Body'].read().decode('utf-8')
        
        # Save to temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            f.write(csv_content)
            csv_path = f.name
        
        # Step 2: Load books from CSV
        logger.info("Loading books from CSV")
        csv_processor = AnalyticsCSVProcessor()
        books = csv_processor.load_books_for_analytics(
            csv_path,
            include_unread=False,
            sample_size=None
        )
        
        # Clean up temp file
        os.unlink(csv_path)
        
        # Update status with total count
        update_status(processing_uuid, 'processing', {
            'total_books': len(books),
            'processed_books': 0,
            'percent_complete': 10
        }, "Loading books from CSV completed")
        
        # Step 3: Convert to BookInfo for enrichment
        logger.info(f"Converting {len(books)} books for enrichment")
        book_infos = []
        for book in books:
            book_info = BookInfo(
                title=book.title,
                author=book.author,
                isbn13=book.isbn13,
                isbn=book.isbn,
                goodreads_id=book.goodreads_id
            )
            book_infos.append(book_info)
        
        # Update status
        update_status(processing_uuid, 'processing', {
            'total_books': len(book_infos),
            'processed_books': 0,
            'percent_complete': 20
        }, "Starting genre enrichment")
        
        # Step 4: Genre enrichment with progress updates
        logger.info(f"Starting genre enrichment for {len(book_infos)} books")
        
        # Create pipeline optimized for Lambda execution
        pipeline = EnvironmentAwareBookPipeline(
            max_local_concurrent=MAX_CONCURRENT,
            api_timeout=API_TIMEOUT
        )
        
        # Process with progress callback
        enriched_data = await pipeline.process_books_smart(
            book_infos,
            progress_callback=lambda processed, total: update_progress(
                processing_uuid, processed, total, 20, 70
            )
        )
        
        # Update status
        update_status(processing_uuid, 'processing', {
            'total_books': len(book_infos),
            'processed_books': len(enriched_data),
            'percent_complete': 80
        }, "Merging enriched data")
        
        # Step 5: Merge enriched data back
        logger.info("Merging enriched data back to analytics objects")
        enhanced_books = []
        for original_book, enriched_item in zip(books, enriched_data):
            # Transfer enriched data back
            original_book.final_genres = enriched_item.final_genres
            original_book.genre_enrichment_success = len(enriched_item.final_genres) > 0
            original_book.thumbnail_url = enriched_item.thumbnail_url
            original_book.small_thumbnail_url = enriched_item.small_thumbnail_url
            enhanced_books.append(original_book)
        
        # Update status
        update_status(processing_uuid, 'processing', {
            'total_books': len(book_infos),
            'processed_books': len(enhanced_books),
            'percent_complete': 90
        }, "Generating dashboard JSON")
        
        # Step 6: Create dashboard JSON and upload to S3
        logger.info("Creating dashboard JSON")
        
        # Create temporary file and use existing function
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_json_path = f.name
        
        # Use existing create_dashboard_json function
        json_path = create_dashboard_json(enhanced_books, output_path=temp_json_path)
        
        # Read the generated JSON
        with open(json_path, 'r') as f:
            dashboard_data = json.load(f)
        
        # Clean up temp file
        os.unlink(json_path)
        
        # Upload to S3
        data_key = f"data/{processing_uuid}.json"
        s3_client.put_object(
            Bucket=DATA_BUCKET,
            Key=data_key,
            Body=json.dumps(dashboard_data, indent=2),
            ContentType='application/json',
            CacheControl='public, max-age=31536000'  # 1 year cache
        )
        
        # Step 7: Mark as complete
        final_status = {
            'uuid': processing_uuid,
            'status': 'complete', 
            'upload_time': get_upload_time(processing_uuid),
            'completion_time': datetime.now().isoformat(),
            'progress': {
                'total_books': len(book_infos),
                'processed_books': len(enhanced_books),
                'percent_complete': 100
            },
            'message': 'Processing complete',
            'data_url': f"https://{DATA_BUCKET}.s3.amazonaws.com/{data_key}",
            'enrichment_stats': calculate_enrichment_stats(enhanced_books)
        }
        
        status_key = f"status/{processing_uuid}.json"
        s3_client.put_object(
            Bucket=DATA_BUCKET,
            Key=status_key,
            Body=json.dumps(final_status),
            ContentType='application/json'
        )
        
        logger.info(f"Processing complete for {processing_uuid}")
        
        # Clean up uploaded CSV
        try:
            s3_client.delete_object(Bucket=DATA_BUCKET, Key=csv_key)
            logger.info(f"Cleaned up uploaded CSV: {csv_key}")
        except Exception as e:
            logger.warning(f"Failed to clean up CSV: {e}")
        
    except Exception as e:
        logger.error(f"Processing failed for {processing_uuid}: {e}", exc_info=True)
        update_status(processing_uuid, 'error', error_message=str(e))
        raise


def update_status(processing_uuid: str, status: str, progress: Dict = None, message: str = None, error_message: str = None):
    """Update processing status in S3"""
    try:
        status_key = f"status/{processing_uuid}.json"
        
        # Get current status
        try:
            current_obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=status_key)
            current_status = json.loads(current_obj['Body'].read().decode('utf-8'))
        except:
            current_status = {}
        
        # Update fields
        current_status.update({
            'status': status,
            'last_updated': datetime.now().isoformat()
        })
        
        if progress:
            current_status['progress'] = progress
        if message:
            current_status['message'] = message
        if error_message:
            current_status['error_message'] = error_message
        
        # Save back to S3
        s3_client.put_object(
            Bucket=DATA_BUCKET,
            Key=status_key,
            Body=json.dumps(current_status),
            ContentType='application/json'
        )
        
    except Exception as e:
        logger.error(f"Failed to update status: {e}")


def update_progress(processing_uuid: str, processed: int, total: int, min_percent: int, max_percent: int):
    """Update progress during enrichment"""
    if total > 0:
        progress_ratio = processed / total
        percent_complete = min_percent + (progress_ratio * (max_percent - min_percent))
        
        update_status(processing_uuid, 'processing', {
            'total_books': total,
            'processed_books': processed,
            'percent_complete': int(percent_complete)
        }, f"Processing books: {processed}/{total}")


def get_upload_time(processing_uuid: str) -> str:
    """Get upload time from metadata"""
    try:
        metadata_key = f"uploads/{processing_uuid}/metadata.json"
        obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=metadata_key)
        metadata = json.loads(obj['Body'].read().decode('utf-8'))
        return metadata.get('upload_time', datetime.now().isoformat())
    except:
        return datetime.now().isoformat()


def create_dashboard_json_data(books: List, export_id: str) -> Dict[str, Any]:
    """Create dashboard JSON data structure"""
    
    # Calculate enrichment statistics
    total_books = len(books)
    books_with_genres = sum(1 for book in books if book.final_genres)
    google_success = sum(1 for book in books if hasattr(book, 'google_success') and book.google_success)
    openlibrary_success = sum(1 for book in books if hasattr(book, 'openlibrary_success') and book.openlibrary_success)
    
    # Convert books to serializable format
    serialized_books = []
    for book in books:
        book_data = {
            'goodreads_id': book.goodreads_id,
            'title': book.title,
            'author': book.author,
            'my_rating': book.my_rating,
            'date_read': book.date_read.isoformat() if book.date_read else None,
            'reading_year': book.reading_year,
            'num_pages': book.num_pages,
            'genres': book.final_genres,
            'thumbnail_url': book.thumbnail_url,
            'small_thumbnail_url': book.small_thumbnail_url
        }
        serialized_books.append(book_data)
    
    return {
        'export_id': export_id,
        'export_timestamp': datetime.now().isoformat(),
        'total_books': total_books,
        'enrichment_stats': {
            'google_success_rate': google_success / total_books if total_books > 0 else 0,
            'openlibrary_success_rate': openlibrary_success / total_books if total_books > 0 else 0,
            'final_enrichment_rate': books_with_genres / total_books if total_books > 0 else 0
        },
        'books': serialized_books
    }


def calculate_enrichment_stats(books: List) -> Dict[str, float]:
    """Calculate enrichment statistics"""
    total_books = len(books)
    if total_books == 0:
        return {'final_enrichment_rate': 0}
    
    books_with_genres = sum(1 for book in books if book.final_genres)
    
    return {
        'final_enrichment_rate': books_with_genres / total_books
    }