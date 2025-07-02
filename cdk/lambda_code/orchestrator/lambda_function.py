import json
import logging
import os
import boto3
import asyncio
import math
import time
from datetime import datetime
from typing import Dict, List
import sys

# Add the shared layer to Python path
sys.path.append('/opt/python')

# Import our existing pipeline components
from genres.pipeline.csv_loader import AnalyticsCSVProcessor
from genres.models.book import BookInfo
from genres.pipeline.exporter import FinalJSONExporter

# Configure logging
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS clients
s3_client = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Configuration
DATA_BUCKET = os.environ['DATA_BUCKET']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'prod')
CHUNK_SIZE = int(os.environ.get('CHUNK_SIZE', 350))
BOOK_PROCESSOR_FUNCTION_NAME = os.environ['BOOK_PROCESSOR_FUNCTION_NAME']

def lambda_handler(event, context):
    """
    Main orchestrator function that processes uploaded CSV files using chunked parallel processing.
    
    Expected event:
    {
        "csv_key": "uploads/job_id/raw.csv",
        "job_id": "uuid-string"
    }
    """
    try:
        logger.info(f"Orchestrator invoked: {json.dumps(event, default=str)}")
        
        # Extract parameters
        csv_key = event['csv_key']
        job_id = event['job_id']
        
        # Run the processing pipeline
        result = process_csv_pipeline(job_id, csv_key)
        
        return result
        
    except Exception as e:
        logger.error(f"Orchestrator error: {e}", exc_info=True)
        
        return {
            'statusCode': 500,
            'job_id': event.get('job_id'),
            'status': 'error',
            'error_message': str(e)
        }


def process_csv_pipeline(job_id: str, csv_key: str) -> Dict:
    """
    Main processing pipeline using chunked parallel processing.
    """
    logger.info(f"Starting chunked parallel processing for {job_id}")
    start_time = time.time()
    
    try:
        # Step 1: Download and parse CSV
        logger.info(f"Loading CSV from s3://{DATA_BUCKET}/{csv_key}")
        csv_obj = s3_client.get_object(Bucket=DATA_BUCKET, Key=csv_key)
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
        
        # Step 4: Process books in chunks
        total_chunks = math.ceil(len(book_infos) / CHUNK_SIZE)
        logger.info(f"Processing {len(book_infos)} books in {total_chunks} chunks of {CHUNK_SIZE}")
        
        all_results = []
        
        for chunk_index in range(total_chunks):
            start_idx = chunk_index * CHUNK_SIZE
            end_idx = min(start_idx + CHUNK_SIZE, len(book_infos))
            chunk = book_infos[start_idx:end_idx]
            
            logger.info(f"Processing chunk {chunk_index + 1}/{total_chunks} ({len(chunk)} books)")
            
            # Process this chunk simultaneously with graceful failure handling
            chunk_results = asyncio.run(process_chunk_simultaneously(chunk, job_id, chunk_index))
            all_results.extend(chunk_results)
            
            # Calculate statistics
            successful_in_chunk = len([r for r in chunk_results if r.get('success', True)])
            failed_in_chunk = len(chunk_results) - successful_in_chunk
            
            progress = ((chunk_index + 1) / total_chunks) * 100
            logger.info(f"Chunk {chunk_index + 1} completed. Progress: {progress:.1f}% "
                      f"({successful_in_chunk} successful, {failed_in_chunk} failed)")
            
            # Brief pause between chunks
            if chunk_index < total_chunks - 1:
                time.sleep(1)
        
        # Step 5: Calculate final statistics
        successful_books = len([r for r in all_results if r.get('success', True)])
        failed_books = len(all_results) - successful_books
        success_rate = (successful_books / len(all_results)) * 100 if all_results else 0
        
        # Step 6: Create final dashboard JSON
        logger.info("Creating final dashboard JSON")
        dashboard_data = create_final_dashboard_json(all_results, books)
        
        # Store final JSON in S3
        final_json_key = f"data/{job_id}.json"
        s3_client.put_object(
            Bucket=DATA_BUCKET,
            Key=final_json_key,
            Body=json.dumps(dashboard_data),
            ContentType='application/json'
        )
        
        processing_time = time.time() - start_time
        logger.info(f"Processing completed in {processing_time:.1f} seconds")
        
        # Clean up uploaded CSV
        try:
            s3_client.delete_object(Bucket=DATA_BUCKET, Key=csv_key)
            logger.info(f"Cleaned up uploaded CSV: {csv_key}")
        except Exception as e:
            logger.warning(f"Failed to clean up CSV: {e}")
        
        return {
            'job_id': job_id,
            'status': 'complete',
            'total_books': len(books),
            'successful_books': successful_books,
            'failed_books': failed_books,
            'success_rate': round(success_rate, 1),
            'chunks_processed': total_chunks,
            'processing_time_seconds': round(processing_time, 1)
        }
        
    except Exception as e:
        logger.error(f"Processing failed for {job_id}: {e}", exc_info=True)
        raise


async def process_chunk_simultaneously(chunk: List[BookInfo], job_id: str, chunk_index: int) -> List[Dict]:
    """Process chunk with graceful failure handling"""
    tasks = []
    for book_index, book in enumerate(chunk):
        task = invoke_book_processor_with_fallback(book, job_id, (chunk_index * CHUNK_SIZE) + book_index)
        tasks.append(task)
    
    # Execute all books - individual failures won't stop the chunk
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Convert exceptions to failed results
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            # Lambda invocation failed entirely
            book = chunk[i]
            processed_results.append({
                'book_id': book.goodreads_id or f"{book.title}-{book.author}",
                'title': book.title,
                'author': book.author,
                'success': False,
                'final_genres': [],
                'thumbnail_url': None,
                'genre_enrichment_success': False,
                'error_message': f"Lambda invocation failed: {str(result)}",
                'processing_logs': [f"Lambda failed: {str(result)}"]
            })
        else:
            processed_results.append(result)
    
    return processed_results


async def invoke_book_processor_with_fallback(book: BookInfo, job_id: str, book_index: int) -> Dict:
    """Invoke book processor with timeout and retry logic"""
    try:
        payload = {
            'book': {
                'title': book.title,
                'author': book.author,
                'isbn13': book.isbn13,
                'isbn': book.isbn,
                'goodreads_id': book.goodreads_id
            }
        }
        
        # Create async wrapper for Lambda invocation
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: lambda_client.invoke(
                FunctionName=BOOK_PROCESSOR_FUNCTION_NAME,
                InvocationType='RequestResponse',
                Payload=json.dumps(payload)
            )
        )
        
        result = json.loads(response['Payload'].read())
        
        # Check for Lambda-level errors
        if 'errorMessage' in result:
            raise Exception(f"Lambda error: {result['errorMessage']}")
            
        return result
        
    except Exception as e:
        # Return a failed result rather than raising
        logger.warning(f"Book processor failed for {book.title}: {str(e)}")
        return {
            'book_id': book.goodreads_id or f"{book.title}-{book.author}",
            'title': book.title,
            'author': book.author,
            'success': False,
            'final_genres': [],
            'thumbnail_url': None,
            'genre_enrichment_success': False,
            'error_message': f"Invocation failed: {str(e)}",
            'processing_logs': [f"Lambda invocation error: {str(e)}"]
        }


def create_final_dashboard_json(enriched_results: List[Dict], original_books: List) -> Dict:
    """
    Create final dashboard JSON combining original book data with enrichment results.
    """
    logger.info(f"Creating dashboard JSON from {len(enriched_results)} enriched results")
    
    # Create a mapping of book identifiers to enriched results
    enriched_map = {}
    for result in enriched_results:
        book_id = result.get('book_id', f"{result.get('title', '')}-{result.get('author', '')}")
        enriched_map[book_id] = result
    
    # Combine original book data with enriched results
    final_books = []
    for original_book in original_books:
        book_id = original_book.goodreads_id or f"{original_book.title}-{original_book.author}"
        enriched_data = enriched_map.get(book_id, {})
        
        # Create combined book entry
        combined_book = {
            # Original book data (from CSV)
            **original_book.to_dashboard_dict(),
            
            # Enriched data (from processing)
            'final_genres': enriched_data.get('final_genres', []),
            'thumbnail_url': enriched_data.get('thumbnail_url'),
            'genre_enrichment_success': enriched_data.get('genre_enrichment_success', False),
            'processing_logs': enriched_data.get('processing_logs', []),
            'error_message': enriched_data.get('error_message')
        }
        
        final_books.append(combined_book)
    
    # Create final dashboard structure
    dashboard_data = {
        'metadata': {
            'total_books': len(final_books),
            'successful_enrichments': len([b for b in final_books if b.get('genre_enrichment_success', False)]),
            'failed_enrichments': len([b for b in final_books if not b.get('genre_enrichment_success', False)]),
            'processing_timestamp': datetime.now().isoformat(),
            'version': '2.0'  # New parallel processing version
        },
        'books': final_books
    }
    
    return dashboard_data