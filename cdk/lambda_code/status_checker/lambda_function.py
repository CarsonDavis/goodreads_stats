import json
import logging
import os
import boto3
from datetime import datetime
from typing import Dict, Any

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')

# Configuration
DATA_BUCKET = os.environ['DATA_BUCKET']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')

def lambda_handler(event, context):
    """
    Handle status checking, data retrieval, and data deletion.
    
    Routes:
    - GET /api/status/{uuid} -> get_processing_status
    - GET /api/data/{uuid} -> get_dashboard_data  
    - DELETE /api/data/{uuid} -> delete_user_data
    """
    try:
        logger.info(f"Status checker invoked: {json.dumps(event, default=str)}")
        
        # Extract path and method from API Gateway event
        path = event.get('path', '')
        method = event.get('httpMethod', 'GET')
        path_params = event.get('pathParameters', {})
        
        if not path_params or 'uuid' not in path_params:
            return error_response(400, "UUID parameter required")
        
        uuid = path_params['uuid']
        
        # Route based on path and method
        if '/status/' in path and method == 'GET':
            return get_processing_status(uuid)
        elif '/data/' in path and method == 'GET':
            return get_dashboard_data(uuid)
        elif '/data/' in path and method == 'DELETE':
            return delete_user_data(uuid)
        else:
            return error_response(404, "Endpoint not found")
            
    except Exception as e:
        logger.error(f"Status checker error: {e}", exc_info=True)
        return error_response(500, "Internal server error")


def get_processing_status(uuid: str) -> Dict[str, Any]:
    """
    Get processing status for a given UUID.
    """
    try:
        status_key = f"status/{uuid}.json"
        
        # Get status from S3
        try:
            obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=status_key)
            status_data = json.loads(obj['Body'].read().decode('utf-8'))
        except s3_client.exceptions.NoSuchKey:
            return error_response(404, "UUID not found")
        
        # Add estimated completion time for processing jobs
        if status_data.get('status') == 'processing':
            progress = status_data.get('progress', {})
            if progress.get('processed_books', 0) > 0:
                # Simple estimation based on current progress
                total_books = progress.get('total_books', 1)
                processed_books = progress.get('processed_books', 0)
                
                if processed_books > 0:
                    # Estimate ~0.5 seconds per book remaining
                    remaining_books = total_books - processed_books
                    estimated_remaining_seconds = remaining_books * 0.5
                    
                    current_time = datetime.now()
                    estimated_completion = current_time.timestamp() + estimated_remaining_seconds
                    status_data['estimated_completion'] = estimated_completion
        
        return success_response(status_data)
        
    except Exception as e:
        logger.error(f"Failed to get status for {uuid}: {e}")
        return error_response(500, "Failed to get processing status")


def get_dashboard_data(uuid: str) -> Dict[str, Any]:
    """
    Get dashboard JSON data for a given UUID.
    """
    try:
        data_key = f"data/{uuid}.json"
        
        # Check if data exists
        try:
            obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=data_key)
            dashboard_data = json.loads(obj['Body'].read().decode('utf-8'))
            return success_response(dashboard_data)
            
        except s3_client.exceptions.NoSuchKey:
            # Check if it's still processing
            status_key = f"status/{uuid}.json"
            try:
                status_obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=status_key)
                status_data = json.loads(status_obj['Body'].read().decode('utf-8'))
                
                status = status_data.get('status')
                if status == 'processing':
                    return error_response(202, "Still processing", extra_data={
                        'status': 'processing',
                        'progress': status_data.get('progress', {})
                    })
                elif status == 'error':
                    error_msg = status_data.get('error_message', 'Processing failed')
                    return error_response(500, f"Processing failed: {error_msg}")
                    
            except s3_client.exceptions.NoSuchKey:
                pass
            
            return error_response(404, "Data not found")
            
    except Exception as e:
        logger.error(f"Failed to get data for {uuid}: {e}")
        return error_response(500, "Failed to load dashboard data")


def delete_user_data(uuid: str) -> Dict[str, Any]:
    """
    Delete all data associated with a given UUID.
    """
    try:
        deleted_files = []
        
        # Delete dashboard data
        data_key = f"data/{uuid}.json"
        try:
            s3_client.delete_object(Bucket=DATA_BUCKET, Key=data_key)
            deleted_files.append("dashboard.json")
        except s3_client.exceptions.NoSuchKey:
            pass
        
        # Delete status
        status_key = f"status/{uuid}.json"
        try:
            s3_client.delete_object(Bucket=DATA_BUCKET, Key=status_key)
            deleted_files.append("status.json")
        except s3_client.exceptions.NoSuchKey:
            pass
        
        # Delete any remaining upload files
        upload_prefix = f"uploads/{uuid}/"
        try:
            # List objects with prefix
            response = s3_client.list_objects_v2(
                Bucket=DATA_BUCKET,
                Prefix=upload_prefix
            )
            
            if 'Contents' in response:
                # Delete all objects with this prefix
                delete_objects = [{'Key': obj['Key']} for obj in response['Contents']]
                s3_client.delete_objects(
                    Bucket=DATA_BUCKET,
                    Delete={'Objects': delete_objects}
                )
                deleted_files.append("raw.csv")
                deleted_files.append("metadata.json")
        except Exception as e:
            logger.warning(f"Failed to clean up upload files: {e}")
        
        if not deleted_files:
            return error_response(404, "No data found to delete")
        
        return success_response({
            'message': 'Data deleted successfully',
            'deleted_files': deleted_files
        })
        
    except Exception as e:
        logger.error(f"Failed to delete data for {uuid}: {e}")
        return error_response(500, "Failed to delete data")


def success_response(data: Any) -> Dict[str, Any]:
    """Generate success response for API Gateway"""
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET, DELETE, OPTIONS'
        },
        'body': json.dumps(data, default=str)
    }


def error_response(status_code: int, message: str, extra_data: Dict = None) -> Dict[str, Any]:
    """Generate error response for API Gateway"""
    response_data = {'error': message}
    if extra_data:
        response_data.update(extra_data)
    
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'GET, DELETE, OPTIONS'
        },
        'body': json.dumps(response_data)
    }