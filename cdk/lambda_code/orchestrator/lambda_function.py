import json
import logging
import os
import boto3
from datetime import datetime
from typing import Dict
import sys

# Add the shared layer to Python path
sys.path.append('/opt/python')

# Import our existing pipeline components
from genres.pipeline.csv_loader import AnalyticsCSVProcessor
from genres.models.book import BookInfo

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
sqs_client = boto3.client('sqs')

# Configuration
DATA_BUCKET = os.environ['DATA_BUCKET']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')
BOOK_QUEUE_URL = os.environ['BOOK_QUEUE_URL']

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
        
        # Step 4: Store original book data in S3 and send SQS messages
        logger.info(f"Storing original books in S3 and sending {len(book_infos)} messages to SQS")
        
        # Store original book data in S3 for aggregator
        original_books_s3_key = f"processing/{processing_uuid}/original_books.json"
        original_books_data = [book.to_dashboard_dict() for book in books]
        
        s3_client.put_object(
            Bucket=DATA_BUCKET,
            Key=original_books_s3_key,
            Body=json.dumps(original_books_data),
            ContentType='application/json'
        )
        
        # Update status
        update_status(processing_uuid, 'processing', {
            'total_books': len(book_infos),
            'processed_books': 0,
            'percent_complete': 30
        }, "Sending books to SQS queue for parallel processing")
        
        # Send individual SQS messages for each book
        logger.info(f"Sending {len(book_infos)} messages to SQS queue")
        
        messages_sent = 0
        batch_size = 10  # SQS batch send limit
        
        for i in range(0, len(book_infos), batch_size):
            batch = book_infos[i:i + batch_size]
            entries = []
            
            for j, book_info in enumerate(batch):
                message_body = {
                    'book': book_info.__dict__,
                    'processing_uuid': processing_uuid,
                    'bucket': DATA_BUCKET,
                    'original_books_s3_key': original_books_s3_key
                }
                
                entries.append({
                    'Id': str(i + j),
                    'MessageBody': json.dumps(message_body)
                })
            
            # Send batch
            response = sqs_client.send_message_batch(
                QueueUrl=BOOK_QUEUE_URL,
                Entries=entries
            )
            
            messages_sent += len(entries)
            
            # Check for failures
            if 'Failed' in response and response['Failed']:
                logger.error(f"Failed to send {len(response['Failed'])} messages: {response['Failed']}")
                raise Exception(f"Failed to send {len(response['Failed'])} SQS messages")
        
        logger.info(f"Successfully sent {messages_sent} messages to SQS")
        
        # Update status - processing will now happen asynchronously via SQS
        update_status(processing_uuid, 'processing', {
            'total_books': len(book_infos),
            'processed_books': 0,
            'percent_complete': 40
        }, f"Sent {messages_sent} books to processing queue - enrichment in progress")
        
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




