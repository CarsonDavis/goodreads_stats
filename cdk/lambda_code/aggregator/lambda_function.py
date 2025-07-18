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


def merge_enriched_data(original_books: List[Dict], enriched_results_map: Dict[str, Dict]) -> List[BookAnalytics]:
    """
    Merge enriched data back into BookAnalytics objects.
    
    Args:
        original_books: List of original book dictionaries
        enriched_results_map: Map of book_key -> enrichment results
        
    Returns:
        List of enhanced BookAnalytics objects
    """
    enhanced_books = []
    
    for original_book in original_books:
        try:
            # Find the enriched result for this book
            book_key = original_book.get('goodreads_id')
            if not book_key:
                book_key = f"{original_book.get('title', '')}-{original_book.get('author', '')}"
            
            enriched_result = enriched_results_map.get(book_key)
            if not enriched_result:
                logger.warning(f"No enriched result found for book: {original_book.get('title', 'Unknown')}")
                enriched_result = {'statusCode': 500, 'body': {'error': 'No enriched result found'}}
            
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
    
    This function is triggered periodically by CloudWatch Events and checks
    for processing jobs that are ready for aggregation.
    """
    import time
    
    try:
        logger.info("Aggregator triggered - checking for ready processing jobs")
        
        # Check if this is a direct invocation with specific processing_uuid
        if event.get('processing_uuid'):
            return process_specific_job(event)
        
        # This is a scheduled trigger - check for ready jobs
        return check_and_process_ready_jobs()
        
    except Exception as e:
        logger.error(f"Aggregator error: {str(e)}")
        return {
            'statusCode': 500,
            'body': {
                'error': str(e),
                'message': 'Aggregator failed'
            }
        }


def check_and_process_ready_jobs():
    """Check for processing jobs that are ready for aggregation"""
    try:
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        # List all processing directories
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix="processing/",
            Delimiter="/"
        )
        
        if 'CommonPrefixes' not in response:
            logger.info("No processing jobs found")
            return {'statusCode': 200, 'message': 'No processing jobs found'}
        
        processed_jobs = 0
        for prefix in response['CommonPrefixes']:
            processing_uuid = prefix['Prefix'].split('/')[-2]  # Extract UUID from path
            
            # Check if this job is ready for aggregation
            if is_job_ready_for_aggregation(processing_uuid):
                logger.info(f"Processing ready job: {processing_uuid}")
                result = process_job_aggregation(processing_uuid)
                if result.get('statusCode') == 200:
                    processed_jobs += 1
        
        logger.info(f"Processed {processed_jobs} ready jobs")
        return {
            'statusCode': 200,
            'processed_jobs': processed_jobs,
            'message': f'Processed {processed_jobs} ready jobs'
        }
        
    except Exception as e:
        logger.error(f"Error checking ready jobs: {e}")
        return {
            'statusCode': 500,
            'error': str(e)
        }


def is_job_ready_for_aggregation(processing_uuid: str) -> bool:
    """Check if a processing job is ready for aggregation"""
    try:
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        # Check if status shows processing is complete
        status_key = f"status/{processing_uuid}.json"
        try:
            obj = s3_client.get_object(Bucket=bucket_name, Key=status_key)
            status = json.loads(obj['Body'].read().decode('utf-8'))
            
            # If already complete or error, skip
            if status.get('status') in ['complete', 'error']:
                return False
                
            # If not in processing status, skip
            if status.get('status') != 'processing':
                return False
                
        except:
            # No status file, skip
            return False
        
        # Check if original books file exists
        original_books_key = f"processing/{processing_uuid}/original_books.json"
        try:
            s3_client.head_object(Bucket=bucket_name, Key=original_books_key)
        except:
            return False
        
        # Check if enriched results directory exists and has files
        enriched_prefix = f"processing/{processing_uuid}/enriched/"
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=enriched_prefix
        )
        
        enriched_count = response.get('KeyCount', 0)
        expected_count = status.get('progress', {}).get('total_books', 0)
        
        logger.info(f"Job {processing_uuid}: {enriched_count}/{expected_count} enriched")
        
        # Ready if we have enriched results for all books
        return enriched_count >= expected_count and expected_count > 0
        
    except Exception as e:
        logger.error(f"Error checking job readiness for {processing_uuid}: {e}")
        return False


def process_job_aggregation(processing_uuid: str):
    """Process aggregation for a specific job"""
    try:
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        # Load original books
        original_books_key = f"processing/{processing_uuid}/original_books.json"
        obj = s3_client.get_object(Bucket=bucket_name, Key=original_books_key)
        original_books = json.loads(obj['Body'].read().decode('utf-8'))
        
        # Load all enriched results and create a lookup map
        enriched_prefix = f"processing/{processing_uuid}/enriched/"
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=enriched_prefix
        )
        
        enriched_results_map = {}
        for obj_info in response.get('Contents', []):
            obj = s3_client.get_object(Bucket=bucket_name, Key=obj_info['Key'])
            enriched_data = json.loads(obj['Body'].read().decode('utf-8'))
            
            # Use goodreads_id as key, fallback to title+author
            original_book = enriched_data['original_book']
            book_key = original_book.get('goodreads_id')
            if not book_key:
                book_key = f"{original_book.get('title', '')}-{original_book.get('author', '')}"
            
            enriched_results_map[book_key] = enriched_data['enriched_result']
        
        if len(enriched_results_map) != len(original_books):
            raise ValueError(f"Mismatch: {len(original_books)} original books vs {len(enriched_results_map)} enriched results")
        
        logger.info(f"Processing {len(original_books)} books for UUID: {processing_uuid}")
        
        # Merge enriched data back into BookAnalytics objects
        enhanced_books = merge_enriched_data(original_books, enriched_results_map)
        
        if not enhanced_books:
            raise ValueError("No enhanced books created")
        
        # Generate dashboard JSON using existing exporter
        import tempfile
        
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
        
        # Clean up processing files
        cleanup_processing_files(processing_uuid)
        
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
        logger.error(f"Aggregation error for {processing_uuid}: {str(e)}")
        
        # Update status to error
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


def process_specific_job(event):
    """Process aggregation for a specific job (backward compatibility)"""
    processing_uuid = event.get('processing_uuid')
    if not processing_uuid:
        raise ValueError("No processing_uuid provided")
    
    return process_job_aggregation(processing_uuid)


def cleanup_processing_files(processing_uuid: str):
    """Clean up intermediate processing files"""
    try:
        bucket_name = os.environ['S3_BUCKET_NAME']
        
        # Delete enriched results directory
        enriched_prefix = f"processing/{processing_uuid}/enriched/"
        response = s3_client.list_objects_v2(
            Bucket=bucket_name,
            Prefix=enriched_prefix
        )
        
        if 'Contents' in response:
            delete_keys = [{'Key': obj['Key']} for obj in response['Contents']]
            s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': delete_keys}
            )
            logger.info(f"Cleaned up {len(delete_keys)} enriched files")
        
        # Delete original books file
        original_books_key = f"processing/{processing_uuid}/original_books.json"
        try:
            s3_client.delete_object(Bucket=bucket_name, Key=original_books_key)
            logger.info(f"Cleaned up original books file")
        except:
            pass
            
    except Exception as e:
        logger.error(f"Error cleaning up processing files: {e}")
        # Don't fail the aggregation due to cleanup errors