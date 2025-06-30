import json
import logging
import os
import boto3
from datetime import datetime
from typing import List, Dict, Any
import sys

# Add the shared layer to Python path
sys.path.append('/opt')

# Import our existing pipeline components
from genres.pipeline.csv_loader import AnalyticsCSVProcessor
from genres.models.book_analytics import BookInfo

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
stepfunctions_client = boto3.client('stepfunctions')

# Configuration
DATA_BUCKET = os.environ['DATA_BUCKET']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')
STATE_MACHINE_ARN = os.environ['STATE_MACHINE_ARN']

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
        process_csv_pipeline(processing_uuid, bucket, csv_key)
        
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


def process_csv_pipeline(processing_uuid: str, bucket: str, csv_key: str):
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
        
        # Step 4: Prepare Step Function input
        logger.info(f"Starting Step Function for {len(book_infos)} books")
        
        # Prepare Step Function input
        step_function_input = {
            "processing_uuid": processing_uuid,
            "books": [{"book": {
                "title": book_info.title,
                "author": book_info.author,
                "isbn13": book_info.isbn13,
                "isbn": book_info.isbn,
                "goodreads_id": book_info.goodreads_id
            }} for book_info in book_infos],
            "original_books": [book.to_dashboard_dict() for book in books]
        }
        
        # Update status
        update_status(processing_uuid, 'processing', {
            'total_books': len(book_infos),
            'processed_books': 0,
            'percent_complete': 30
        }, "Starting Step Function execution")
        
        # Start Step Function execution
        logger.info(f"Starting Step Function execution for {processing_uuid}")
        execution_name = f"processing-{processing_uuid}-{int(datetime.now().timestamp())}"
        
        response = stepfunctions_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(step_function_input)
        )
        
        logger.info(f"Step Function execution started: {response['executionArn']}")
        
        # Update status with execution info
        update_status(processing_uuid, 'processing', {
            'total_books': len(book_infos),
            'processed_books': 0,
            'percent_complete': 40
        }, "Step Function execution started - enriching books in parallel")
        
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




def get_upload_time(processing_uuid: str) -> str:
    """Get upload time from metadata"""
    try:
        metadata_key = f"uploads/{processing_uuid}/metadata.json"
        obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=metadata_key)
        metadata = json.loads(obj['Body'].read().decode('utf-8'))
        return metadata.get('upload_time', datetime.now().isoformat())
    except:
        return datetime.now().isoformat()




