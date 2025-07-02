import json
import logging
import os
import uuid
import boto3
import time
from datetime import datetime
from typing import Dict, Any

# Configure structured logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

def log_structured(level: str, message: str, correlation_id: str = None, **kwargs):
    """Structured logging with correlation ID and metadata"""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "level": level,
        "message": message,
        "service": "upload_handler",
        "environment": os.environ.get('ENVIRONMENT', 'unknown')
    }
    
    if correlation_id:
        log_entry["correlation_id"] = correlation_id
    
    # Add any additional fields
    log_entry.update(kwargs)
    
    if level == "ERROR":
        logger.error(json.dumps(log_entry))
    elif level == "WARNING":
        logger.warning(json.dumps(log_entry))
    elif level == "DEBUG":
        logger.debug(json.dumps(log_entry))
    else:
        logger.info(json.dumps(log_entry))

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
    # Extract correlation ID from headers or generate new one
    correlation_id = event.get('headers', {}).get('X-Correlation-ID') or str(uuid.uuid4())
    start_time = time.time()
    
    # Log full event structure for debugging (sanitized)
    debug_event = {
        'httpMethod': event.get('httpMethod'),
        'path': event.get('path'),
        'queryStringParameters': event.get('queryStringParameters'),
        'headers': event.get('headers', {}),
        'isBase64Encoded': event.get('isBase64Encoded'),
        'body_length': len(event.get('body', '')),
        'body_preview': event.get('body', '')[:100] if event.get('body') else None,
        'requestContext': {
            'requestId': event.get('requestContext', {}).get('requestId'),
            'identity': event.get('requestContext', {}).get('identity', {})
        }
    }
    
    log_structured("INFO", "Upload handler invoked", correlation_id,
                  request_id=context.aws_request_id,
                  function_name=context.function_name,
                  debug_event=debug_event)
    
    try:
        # Parse the API Gateway event
        if 'body' not in event:
            log_structured("ERROR", "No file data provided in request body", correlation_id)
            return error_response(400, "No file data provided")
        
        # For API Gateway, body is base64 encoded
        import base64
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(event['body'])
        else:
            body = event['body'].encode() if isinstance(event['body'], str) else event['body']
        
        # Parse multipart form data - check all possible header cases
        headers = event.get('headers', {})
        content_type = (headers.get('content-type', '') or 
                       headers.get('Content-Type', '') or 
                       headers.get('CONTENT-TYPE', ''))
        
        log_structured("DEBUG", "Parsing multipart form data", correlation_id, 
                      content_type=content_type[:100],  # Truncate for logging
                      all_headers=list(headers.keys())[:10])  # Show available headers
        
        if 'multipart/form-data' not in content_type:
            log_structured("ERROR", "Invalid content type", correlation_id, content_type=content_type)
            return error_response(400, "Content-Type must be multipart/form-data")
        
        # Extract boundary
        boundary = None
        for part in content_type.split(';'):
            if 'boundary=' in part:
                boundary = part.split('boundary=')[1].strip()
                break
        
        if not boundary:
            log_structured("ERROR", "No boundary found in Content-Type", correlation_id,
                          content_type_full=content_type,
                          content_type_parts=[p.strip() for p in content_type.split(';')])
            return error_response(400, "No boundary found in Content-Type")
        
        # Parse multipart data (simplified parser)
        log_structured("DEBUG", "Parsing multipart CSV data", correlation_id, 
                      boundary=boundary[:20],
                      body_type=type(body).__name__,
                      body_size=len(body),
                      body_starts_with=body[:50] if len(body) > 50 else body)
        
        csv_data = parse_multipart_csv(body, boundary)
        if not csv_data:
            log_structured("ERROR", "No CSV file found in upload", correlation_id,
                          multipart_parts_found=len(body.split(f"--{boundary}".encode())) - 1 if isinstance(body, bytes) else 0)
            return error_response(400, "No CSV file found in upload")
        
        # Validate file size
        file_size_mb = len(csv_data) / 1024 / 1024
        log_structured("INFO", "CSV file parsed successfully", correlation_id, 
                      file_size_bytes=len(csv_data), file_size_mb=round(file_size_mb, 2))
        
        if len(csv_data) > MAX_FILE_SIZE:
            log_structured("ERROR", "File too large", correlation_id, 
                          file_size_mb=file_size_mb, max_size_mb=MAX_FILE_SIZE / 1024 / 1024)
            return error_response(400, f"File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB")
        
        # Validate CSV format (basic check)
        if not is_valid_csv(csv_data):
            log_structured("ERROR", "Invalid CSV format", correlation_id)
            return error_response(400, "Invalid CSV format or not a Goodreads export")
        
        # Generate job ID for this processing job
        job_id = str(uuid.uuid4())
        log_structured("INFO", "Generated job ID", correlation_id, job_id=job_id)
        
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
            'job_id': job_id,
            'correlation_id': correlation_id  # Pass correlation ID to orchestrator
        }
        
        log_structured("INFO", "Invoking orchestrator synchronously", correlation_id,
                      job_id=job_id, orchestrator_function=orchestrator_name)
        
        try:
            orchestrator_start_time = time.time()
            
            # Synchronous invocation - wait for completion
            orchestrator_response = lambda_client.invoke(
                FunctionName=orchestrator_name,
                InvocationType='RequestResponse',  # Wait for completion
                Payload=json.dumps(orchestrator_payload)
            )
            
            orchestrator_duration = time.time() - orchestrator_start_time
            
            # Parse orchestrator response
            response_payload = orchestrator_response['Payload'].read()
            result = json.loads(response_payload)
            
            log_structured("INFO", "Orchestrator completed", correlation_id,
                          job_id=job_id, 
                          orchestrator_duration_seconds=round(orchestrator_duration, 2),
                          orchestrator_status_code=result.get('statusCode'),
                          total_books=result.get('total_books'),
                          successful_books=result.get('successful_books'),
                          processing_time_seconds=result.get('processing_time_seconds'))
            
            # Check for orchestrator errors
            if result.get('statusCode') == 500:
                log_structured("ERROR", "Orchestrator failed", correlation_id,
                              job_id=job_id, error_message=result.get('error_message'))
                raise Exception(f"Orchestrator failed: {result.get('error_message', 'Unknown error')}")
            
            total_duration = time.time() - start_time
            
            # Return success response with complete processing results
            response_body = {
                'job_id': result['job_id'],
                'status': 'complete',
                'processing_time': result['processing_time_seconds'],
                'books_processed': result['total_books'],
                'successful_enrichments': result['successful_books'],
                'failed_enrichments': result['failed_books'],
                'success_rate': result['success_rate'],
                'chunks_processed': result['chunks_processed'],
                'correlation_id': correlation_id
            }
            
            log_structured("INFO", "Upload completed successfully", correlation_id,
                          job_id=job_id,
                          total_duration_seconds=round(total_duration, 2),
                          **{k: v for k, v in response_body.items() if k != 'correlation_id'})
            
            return {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*',
                    'Access-Control-Allow-Headers': 'Content-Type, X-Correlation-ID',
                    'Access-Control-Allow-Methods': 'POST, OPTIONS',
                    'X-Correlation-ID': correlation_id
                },
                'body': json.dumps(response_body)
            }
            
        except Exception as e:
            log_structured("ERROR", "Failed to process with orchestrator", correlation_id,
                          job_id=job_id, error=str(e), error_type=type(e).__name__)
            # Clean up uploaded files on failure
            try:
                s3_client.delete_object(Bucket=DATA_BUCKET, Key=csv_key)
                s3_client.delete_object(Bucket=DATA_BUCKET, Key=metadata_key)
                log_structured("INFO", "Cleaned up uploaded files after failure", correlation_id, job_id=job_id)
            except Exception as cleanup_error:
                log_structured("WARNING", "Failed to clean up files", correlation_id, 
                              job_id=job_id, cleanup_error=str(cleanup_error))
            return error_response(500, "Processing failed", correlation_id)
        
    except Exception as e:
        total_duration = time.time() - start_time
        log_structured("ERROR", "Upload handler error", correlation_id,
                      error=str(e), error_type=type(e).__name__, 
                      total_duration_seconds=round(total_duration, 2))
        return error_response(500, "Internal server error", correlation_id)


def parse_multipart_csv(body: bytes, boundary: str) -> bytes:
    """
    Simple multipart parser to extract CSV data with enhanced debugging.
    """
    try:
        boundary_bytes = f"--{boundary}".encode()
        parts = body.split(boundary_bytes)
        
        logger.info(f"Multipart parsing: found {len(parts)} parts with boundary '{boundary}'")
        
        for i, part in enumerate(parts):
            logger.debug(f"Part {i}: length={len(part)}, starts_with={part[:100]}")
            
            if b'Content-Disposition: form-data' in part and b'filename=' in part:
                logger.info(f"Found file part {i} with Content-Disposition and filename")
                
                # Find the start of file data (after double CRLF)
                header_end = part.find(b'\r\n\r\n')
                if header_end == -1:
                    header_end = part.find(b'\n\n')
                    logger.debug(f"Using \\n\\n delimiter at position {header_end}")
                else:
                    logger.debug(f"Using \\r\\n\\r\\n delimiter at position {header_end}")
                
                if header_end != -1:
                    file_data = part[header_end + 4:]  # Skip the double CRLF
                    # Remove trailing boundary marker if present
                    if file_data.endswith(b'\r\n'):
                        file_data = file_data[:-2]
                    
                    logger.info(f"Extracted CSV data: {len(file_data)} bytes, starts_with={file_data[:50]}")
                    return file_data
        
        logger.error("No file part found in multipart data")
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


def error_response(status_code: int, message: str, correlation_id: str = None) -> Dict[str, Any]:
    """Generate error response for API Gateway"""
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Headers': 'Content-Type, X-Correlation-ID',
        'Access-Control-Allow-Methods': 'POST, OPTIONS'
    }
    
    if correlation_id:
        headers['X-Correlation-ID'] = correlation_id
    
    body = {'error': message}
    if correlation_id:
        body['correlation_id'] = correlation_id
    
    return {
        'statusCode': status_code,
        'headers': headers,
        'body': json.dumps(body)
    }