# System-Wide Logging Strategy for Goodreads Stats Pipeline

## Overview

This document outlines a comprehensive logging strategy to provide complete visibility into the book enrichment pipeline, enabling easy debugging and monitoring of individual book processing jobs.

## Current Architecture (SQS-Based)

```
Upload → Orchestrator → SQS Queue → BookProcessor (per book) → S3 Results → Aggregator
```

## Core Logging Principles

### 1. Correlation ID Strategy
- **Processing UUID**: Each CSV upload gets a unique processing UUID
- **Book Correlation ID**: Each book gets a unique ID within the processing session
- **Format**: `{processing_uuid}-{book_index}` (e.g., `abc123-001`, `abc123-002`)

### 2. Structured Logging Format
All logs should use structured JSON format for easy parsing and searching:

```json
{
  "timestamp": "2025-07-01T15:30:00.000Z",
  "level": "INFO",
  "processing_uuid": "abc123-def456",
  "book_correlation_id": "abc123-def456-001",
  "component": "book_processor",
  "operation": "google_books_api",
  "message": "Successfully retrieved book data",
  "metadata": {
    "title": "Book Title",
    "isbn13": "9780123456789",
    "api_response_size": 2048,
    "genres_found": 3,
    "thumbnail_url": "https://...",
    "execution_time_ms": 1250
  }
}
```

### 3. Log Level Strategy
- **ERROR**: Critical failures that prevent processing
- **WARN**: Non-critical issues that might affect quality
- **INFO**: Key milestones and successful operations
- **DEBUG**: Detailed API responses and internal state (dev/staging only)

## Component-Specific Logging Requirements

### Upload Handler
```python
# Log upload start
log_info("upload_started", {
    "file_size": len(csv_content),
    "estimated_books": book_count,
    "processing_uuid": processing_uuid
})

# Log validation results
log_info("csv_validation_complete", {
    "total_rows": total_rows,
    "valid_books": valid_count,
    "skipped_rows": skipped_count,
    "validation_errors": error_list
})
```

### Orchestrator
```python
# Log processing initiation
log_info("processing_initiated", {
    "total_books": len(books),
    "queue_url": queue_url,
    "batch_size": batch_size
})

# Log SQS message sending
for book in books:
    log_info("book_queued", {
        "book_correlation_id": f"{processing_uuid}-{book_index:03d}",
        "title": book.title,
        "isbn13": book.isbn13,
        "sqs_message_id": message_id
    })

# Log completion trigger
log_info("aggregation_triggered", {
    "books_processed": total_books,
    "aggregator_invocation_id": invocation_id
})
```

### BookProcessor (Most Critical)
```python
# Log processing start
log_info("book_processing_started", {
    "book_correlation_id": book_correlation_id,
    "title": book_data.get('title'),
    "isbn13": book_data.get('isbn13'),
    "enrichment_strategy": "async_api_calls"
})

# Log API call attempts and results
log_info("google_books_api_call", {
    "query_type": "isbn" | "title_author",
    "query_value": query,
    "response_status": 200,
    "items_returned": len(items),
    "execution_time_ms": elapsed_ms
})

log_info("google_books_processing", {
    "genres_extracted": len(genres),
    "thumbnail_url": thumbnail_url,
    "small_thumbnail_url": small_thumbnail_url,
    "categories": raw_categories
})

log_info("openlibrary_api_call", {
    "api_type": "isbn_lookup" | "search",
    "query": query,
    "response_status": 200,
    "edition_found": bool(edition_data),
    "work_found": bool(work_data),
    "execution_time_ms": elapsed_ms
})

log_info("openlibrary_processing", {
    "subjects_extracted": len(subjects),
    "edition_subjects": len(edition_subjects),
    "work_subjects": len(work_subjects)
})

# Log final enrichment results
log_info("book_enrichment_complete", {
    "book_correlation_id": book_correlation_id,
    "enrichment_success": success,
    "final_genres": final_genres,
    "genre_count": len(final_genres),
    "thumbnail_url": thumbnail_url,
    "small_thumbnail_url": small_thumbnail_url,
    "google_books_success": google_success,
    "openlibrary_success": ol_success,
    "total_execution_time_ms": total_elapsed,
    "s3_result_key": result_s3_key
})

# Log errors with full context
log_error("book_processing_failed", {
    "book_correlation_id": book_correlation_id,
    "error_type": type(e).__name__,
    "error_message": str(e),
    "stack_trace": traceback.format_exc(),
    "book_data": book_data,
    "stage": "api_call" | "processing" | "s3_upload"
})
```

### Aggregator
```python
# Log aggregation start
log_info("aggregation_started", {
    "expected_books": total_books,
    "s3_results_prefix": f"processing/{processing_uuid}/results/",
    "timeout_minutes": 10
})

# Log book result collection
log_info("book_results_collected", {
    "successful_enrichments": success_count,
    "failed_enrichments": failed_count,
    "missing_results": missing_count,
    "books_with_thumbnails": thumbnail_count,
    "average_genres_per_book": avg_genres
})

# Log final dashboard creation
log_info("dashboard_json_created", {
    "final_book_count": len(books),
    "output_s3_key": output_key,
    "file_size_bytes": file_size,
    "enrichment_success_rate": success_rate,
    "thumbnail_success_rate": thumbnail_rate
})
```

## CloudWatch Log Group Strategy

### Current Log Groups (Keep)
- `/aws/lambda/GoodreadsStats-Prod-Api-UploadHandler*`
- `/aws/lambda/GoodreadsStats-Prod-Api-Orchestrator*`
- `/aws/lambda/GoodreadsStats-Prod-Api-BookProcessor*`
- `/aws/lambda/GoodreadsStats-Prod-Api-Aggregator*`
- `/aws/lambda/GoodreadsStats-Prod-Api-StatusChecker*`

### Additional Monitoring
- **SQS Dead Letter Queue Monitoring**: CloudWatch alarms for DLQ message counts
- **Processing Duration Tracking**: Custom metrics for end-to-end processing time
- **Success Rate Metrics**: Custom metrics for enrichment success rates

## Query Examples for Debugging

### Find All Logs for a Processing Session
```bash
# CloudWatch Insights query
fields @timestamp, component, operation, message, metadata
| filter processing_uuid = "abc123-def456"
| sort @timestamp asc
```

### Find Specific Book Processing
```bash
# For a specific book
fields @timestamp, operation, message, metadata
| filter book_correlation_id = "abc123-def456-001"
| sort @timestamp asc
```

### Find API Failures
```bash
# Find Google Books API failures
fields @timestamp, book_correlation_id, message, metadata.error_message
| filter operation = "google_books_api" and level = "ERROR"
| sort @timestamp desc
```

### Enrichment Success Analysis
```bash
# Success rate by book
fields book_correlation_id, metadata.enrichment_success, metadata.final_genres, metadata.thumbnail_url
| filter operation = "book_enrichment_complete"
| stats count() by metadata.enrichment_success
```

## Implementation Plan

### Phase 1: Core Correlation ID System
1. Add `processing_uuid` and `book_correlation_id` to all Lambda environments
2. Update BookProcessor to generate and use correlation IDs
3. Ensure all log statements include correlation context

### Phase 2: Structured Logging Library
1. Create shared logging utility in Lambda layer
2. Implement structured logging format
3. Add execution time tracking

### Phase 3: Enhanced Monitoring
1. Add custom CloudWatch metrics
2. Create CloudWatch dashboards
3. Set up alerting for high failure rates

### Phase 4: Advanced Analytics
1. Enable CloudWatch Insights on all log groups
2. Create saved queries for common debugging scenarios
3. Add log retention policies based on environment

## Code Implementation Example

### Shared Logging Utility (`lambda_layer/python/logging_utils.py`)
```python
import json
import logging
import time
from datetime import datetime
from typing import Dict, Any, Optional

class StructuredLogger:
    def __init__(self, component: str, processing_uuid: str = None, book_correlation_id: str = None):
        self.component = component
        self.processing_uuid = processing_uuid
        self.book_correlation_id = book_correlation_id
        self.logger = logging.getLogger(component)
        
    def _log(self, level: str, operation: str, message: str, metadata: Dict[str, Any] = None):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "component": self.component,
            "operation": operation,
            "message": message
        }
        
        if self.processing_uuid:
            log_entry["processing_uuid"] = self.processing_uuid
        if self.book_correlation_id:
            log_entry["book_correlation_id"] = self.book_correlation_id
        if metadata:
            log_entry["metadata"] = metadata
            
        self.logger.info(json.dumps(log_entry))
    
    def info(self, operation: str, message: str, metadata: Dict[str, Any] = None):
        self._log("INFO", operation, message, metadata)
    
    def error(self, operation: str, message: str, metadata: Dict[str, Any] = None):
        self._log("ERROR", operation, message, metadata)
    
    def warn(self, operation: str, message: str, metadata: Dict[str, Any] = None):
        self._log("WARN", operation, message, metadata)

class TimedOperation:
    def __init__(self, logger: StructuredLogger, operation: str):
        self.logger = logger
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_ms = int((time.time() - self.start_time) * 1000)
        if exc_type:
            self.logger.error(self.operation, f"Operation failed: {exc_val}", {
                "execution_time_ms": elapsed_ms,
                "error_type": exc_type.__name__
            })
        else:
            self.logger.info(self.operation, "Operation completed successfully", {
                "execution_time_ms": elapsed_ms
            })
```

### Usage in BookProcessor
```python
from logging_utils import StructuredLogger, TimedOperation

def lambda_handler(event, context):
    # Extract correlation info from SQS message
    processing_uuid = event['Records'][0]['messageAttributes']['processing_uuid']['stringValue']
    book_correlation_id = event['Records'][0]['messageAttributes']['book_correlation_id']['stringValue']
    
    logger = StructuredLogger("book_processor", processing_uuid, book_correlation_id)
    
    logger.info("book_processing_started", "Starting enrichment for book", {
        "title": book_data.get('title'),
        "isbn13": book_data.get('isbn13')
    })
    
    with TimedOperation(logger, "google_books_api"):
        # Google Books API call
        response = fetch_google_books(book_info)
    
    logger.info("book_enrichment_complete", "Book enrichment finished", {
        "enrichment_success": bool(final_genres),
        "genre_count": len(final_genres),
        "thumbnail_url": thumbnail_url
    })
```

## Benefits

1. **Complete Traceability**: Follow a single book through the entire pipeline
2. **Easy Debugging**: Quickly identify where failures occur
3. **Performance Monitoring**: Track API response times and bottlenecks
4. **Quality Metrics**: Monitor enrichment success rates and data quality
5. **Operational Insights**: Understand system behavior and optimize accordingly

## Monitoring Dashboards

Create CloudWatch dashboards showing:
- Processing volume over time
- Success/failure rates by component
- Average processing time per book
- API response time trends
- Queue depth and processing lag
- Error categorization and trends

This logging strategy will provide complete visibility into the book enrichment pipeline, making debugging and optimization much easier.