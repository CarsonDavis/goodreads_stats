import json
import logging
import os
import uuid
import boto3
from datetime import datetime
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Configuration
DATA_BUCKET = os.environ['DATA_BUCKET']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

def lambda_handler(event, context):
    """
    Handle CSV file uploads and process them synchronously.
    
    Expects API Gateway event with multipart/form-data containing CSV file.
    Returns complete processing results including job statistics.
    """
    try:
        logger.info(f"Upload handler invoked: {json.dumps(event, default=str)}")
        
        # Parse the API Gateway event
        if 'body' not in event:
            return error_response(400, "No file data provided")
        
        # For API Gateway, body is base64 encoded
        import base64
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(event['body'])
        else:
            body = event['body'].encode() if isinstance(event['body'], str) else event['body']
        
        # Parse multipart form data
        content_type = event.get('headers', {}).get('content-type', '')
        if 'multipart/form-data' not in content_type:
            return error_response(400, "Content-Type must be multipart/form-data")
        
        # Extract boundary
        boundary = None
        for part in content_type.split(';'):
            if 'boundary=' in part:
                boundary = part.split('boundary=')[1].strip()
                break
        
        if not boundary:
            return error_response(400, "No boundary found in Content-Type")
        
        # Parse multipart data (simplified parser)
        csv_data = parse_multipart_csv(body, boundary)
        if not csv_data:
            return error_response(400, "No CSV file found in upload")
        
        # Validate file size
        if len(csv_data) > MAX_FILE_SIZE:
            return error_response(400, f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB")
        
        # Validate CSV format (basic check)
        if not is_valid_csv(csv_data):
            return error_response(400, "Invalid CSV format or not a Goodreads export")
        
        # Generate job ID for this processing job
        job_id = str(uuid.uuid4())
        logger.info(f"Generated job ID: {job_id}")
        
        # Save CSV to S3
        csv_key = f"uploads/{job_id}/raw.csv"
        s3_client.put_object(
            Bucket=DATA_BUCKET,
            Key=csv_key,
            Body=csv_data,
            ContentType='text/csv'
        )
        
        # Save metadata
        metadata = {
            'job_id': job_id,
            'upload_time': datetime.now().isoformat(),
            'file_size': len(csv_data),
            'environment': ENVIRONMENT
        }
        
        metadata_key = f"uploads/{job_id}/metadata.json"
        s3_client.put_object(
            Bucket=DATA_BUCKET,
            Key=metadata_key,
            Body=json.dumps(metadata),
            ContentType='application/json'
        )
        
        # Invoke orchestrator synchronously and wait for complete results
        orchestrator_name = os.environ.get('ORCHESTRATOR_FUNCTION_NAME', f"GoodreadsStats-{ENVIRONMENT.title()}-Api-Orchestrator")
        orchestrator_payload = {
            'csv_key': csv_key,
            'job_id': job_id
        }
        
        logger.info(f"Invoking orchestrator synchronously for {job_id}")
        
        try:
            # Synchronous invocation - wait for completion
            orchestrator_response = lambda_client.invoke(
                FunctionName=orchestrator_name,
                InvocationType='RequestResponse',  # Wait for completion
                Payload=json.dumps(orchestrator_payload)
            )
            
            # Parse orchestrator response
            response_payload = orchestrator_response['Payload'].read()
            result = json.loads(response_payload)
            
            logger.info(f"Orchestrator completed for {job_id}: {result}")
            
            # Check for orchestrator errors
            if result.get('statusCode') == 500:
                raise Exception(f"Orchestrator failed: {result.get('error_message', 'Unknown error')}")
            
            # Return success response with complete processing results
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS'
                },
                'body': json.dumps({
                    'job_id': result['job_id'],
                    'status': 'complete',
                    'processing_time': result['processing_time_seconds'],
                    'books_processed': result['total_books'],
                    'successful_enrichments': result['successful_books'],
                    'failed_enrichments': result['failed_books'],
                    'success_rate': result['success_rate'],
                    'chunks_processed': result['chunks_processed']
                })
            }
            
        except Exception as e:
            logger.error(f"Failed to process with orchestrator: {e}")
            # Clean up uploaded files on failure
            try:
                s3_client.delete_object(Bucket=DATA_BUCKET, Key=csv_key)
                s3_client.delete_object(Bucket=DATA_BUCKET, Key=metadata_key)
            except:
                pass
            return error_response(500, "Processing failed")
        
    except Exception as e:
        logger.error(f"Upload handler error: {e}", exc_info=True)
        return error_response(500, "Internal server error")


def parse_multipart_csv(body: bytes, boundary: str) -> bytes:
    """
    Simple multipart parser to extract CSV data.
    """
    try:
        boundary_bytes = f"--{boundary}".encode()
        parts = body.split(boundary_bytes)
        
        for part in parts:
            if b'Content-Disposition: form-data' in part and b'filename=' in part:
                # Find the start of file data (after double CRLF)
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    header_end = part.find(b'\n\n')
                
                if header_end != -1:
                    file_data = part[header_end + 4:]  # Skip the double CRLF
                    # Remove trailing boundary marker if present
                    if file_data.endswith(b'\r\n'):
                        file_data = file_data[:-2]
                    return file_data
        
        return None
        
    except Exception as e:
        logger.error(f"Failed to parse multipart data: {e}")
        return None


def is_valid_csv(csv_data: bytes) -> bool:
    """
    Basic validation to check if this looks like a Goodreads CSV export.
    """
    try:
        # Decode and check first few lines
        content = csv_data.decode('utf-8')
        lines = content.split('\n')
        
        if len(lines) < 2:
            return False
        
        # Check for common Goodreads CSV headers
        header = lines[0].lower()
        required_fields = ['title', 'author', 'my rating', 'date read']
        
        for field in required_fields:
            if field not in header:
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"CSV validation error: {e}")
        return False


def error_response(status_code: int, message: str) -> Dict[str, Any]:
    """Generate error response for API Gateway"""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        },
        'body': json.dumps({
            'error': message
        })
    }