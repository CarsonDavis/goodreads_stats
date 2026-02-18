# Lambda Functions

This document describes the AWS Lambda functions that power the cloud production environment. All functions are defined in `cdk/lambda_code/`.

## Overview

| Function | Trigger | Purpose |
|----------|---------|---------|
| [Upload Handler](#upload-handler) | API Gateway POST | Receives CSV, saves to S3, triggers orchestrator |
| [Orchestrator](#orchestrator) | Lambda invoke (async) | Parses CSV, sends books to SQS |
| [Book Processor](#book-processor) | SQS | Enriches single book via external APIs |
| [Aggregator](#aggregator) | CloudWatch Events | Combines results, generates dashboard JSON |
| [Status Checker](#status-checker) | API Gateway GET/DELETE | Returns status, retrieves/deletes data |

## Processing Flow

```
                    ┌─────────────────┐
                    │  API Gateway    │
                    │  POST /upload   │
                    └────────┬────────┘
                             │
                             v
┌─────────────────────────────────────────────────────────────┐
│                    UPLOAD HANDLER                            │
│  1. Parse multipart form data                               │
│  2. Validate CSV format (Goodreads headers)                 │
│  3. Generate UUID                                           │
│  4. Save CSV to S3 (uploads/{uuid}/raw.csv)                 │
│  5. Initialize status (status/{uuid}.json)                  │
│  6. Invoke Orchestrator (async)                             │
│  7. Return UUID to client                                   │
└────────────────────────────┬────────────────────────────────┘
                             │ async invoke
                             v
┌─────────────────────────────────────────────────────────────┐
│                      ORCHESTRATOR                            │
│  1. Download CSV from S3                                    │
│  2. Parse with AnalyticsCSVProcessor                        │
│  3. Convert to BookInfo objects                             │
│  4. Store original books in S3 (processing/{uuid}/...)      │
│  5. Send books to SQS in batches of 10                      │
│  6. Update status                                           │
└────────────────────────────┬────────────────────────────────┘
                             │ SQS messages
                             v
┌─────────────────────────────────────────────────────────────┐
│                    BOOK PROCESSOR (x N)                      │
│  (One invocation per SQS message, runs in parallel)         │
│  1. Parse book data from SQS message                        │
│  2. Call AsyncGenreEnricher for single book                 │
│     - Google Books API                                      │
│     - Open Library API                                      │
│  3. Store enriched result in S3 (processing/{uuid}/...)     │
└────────────────────────────┬────────────────────────────────┘
                             │ S3 files
                             v
┌─────────────────────────────────────────────────────────────┐
│                      AGGREGATOR                              │
│  (Triggered periodically by CloudWatch Events)              │
│  1. Check for jobs where all books are enriched             │
│  2. Load original books from S3                             │
│  3. Load all enriched results from S3                       │
│  4. Merge into BookAnalytics objects                        │
│  5. Generate dashboard JSON                                 │
│  6. Save to S3 (data/{uuid}.json)                           │
│  7. Update status to 'complete'                             │
│  8. Clean up intermediate files                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Upload Handler

**Source:** `cdk/lambda_code/upload_handler/lambda_function.py`

**Trigger:** API Gateway `POST /api/upload`

### Purpose

Receives uploaded CSV files from the frontend, validates them, and initiates processing.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DATA_BUCKET` | S3 bucket for all data storage |
| `ENVIRONMENT` | Deployment environment (prod/dev) |
| `ORCHESTRATOR_FUNCTION_NAME` | Name of orchestrator Lambda |
| `LOG_LEVEL` | Logging verbosity (default: INFO) |

### Input Event

API Gateway event with multipart/form-data body (base64 encoded):

```json
{
  "body": "<base64-encoded-multipart-data>",
  "isBase64Encoded": true,
  "headers": {
    "content-type": "multipart/form-data; boundary=----WebKitFormBoundary..."
  }
}
```

### Processing Steps

1. **Parse multipart data** - Extract CSV file from form data
2. **Validate CSV** - Check for required Goodreads headers (Title, Author, My Rating, Date Read)
3. **Check file size** - Maximum 50MB
4. **Generate UUID** - Create unique identifier for this job
5. **Save to S3:**
   - `uploads/{uuid}/raw.csv` - Original CSV
   - `uploads/{uuid}/metadata.json` - Upload metadata
   - `status/{uuid}.json` - Initial processing status
6. **Trigger Orchestrator** - Invoke asynchronously with job details

### Output

```json
{
  "statusCode": 200,
  "body": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "message": "Upload successful, processing started"
  }
}
```

---

## Orchestrator

**Source:** `cdk/lambda_code/orchestrator/lambda_function.py`

**Trigger:** Lambda invoke (async) from Upload Handler

### Purpose

Parses the uploaded CSV and distributes book processing to SQS for parallel enrichment.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DATA_BUCKET` | S3 bucket for all data storage |
| `BOOK_QUEUE_URL` | SQS queue URL for book processing |
| `ENVIRONMENT` | Deployment environment |
| `LOG_LEVEL` | Logging verbosity |

### Input Event

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "bucket": "goodreads-stats-data-prod",
  "csv_key": "uploads/550e8400.../raw.csv"
}
```

### Processing Steps

1. **Download CSV** - Fetch from S3
2. **Parse with AnalyticsCSVProcessor** - Convert to BookAnalytics objects
3. **Convert to BookInfo** - Extract minimal fields for API lookups
4. **Store original books** - Save `processing/{uuid}/original_books.json`
5. **Send to SQS** - Batch messages (10 per batch) to book processing queue
6. **Update status** - Progress tracking

### SQS Message Format

```json
{
  "book": {
    "title": "The Hobbit",
    "author": "J.R.R. Tolkien",
    "isbn13": "9780547928227",
    "isbn": "0547928227",
    "goodreads_id": "12345"
  },
  "processing_uuid": "550e8400-...",
  "bucket": "goodreads-stats-data-prod",
  "original_books_s3_key": "processing/550e8400.../original_books.json"
}
```

---

## Book Processor

**Source:** `cdk/lambda_code/book_processor/lambda_function.py`

**Trigger:** SQS queue (books to process)

### Purpose

Enriches a single book with genre data from external APIs.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DATA_BUCKET` | S3 bucket for storing results |
| `LOG_LEVEL` | Logging verbosity |

### Input Event

SQS event with one or more messages:

```json
{
  "Records": [
    {
      "body": "{\"book\": {...}, \"processing_uuid\": \"...\", ...}"
    }
  ]
}
```

### Processing Steps

1. **Parse SQS message** - Extract book data and processing UUID
2. **Create BookInfo** - Initialize enrichment input
3. **Call AsyncGenreEnricher** - Query external APIs:
   - Google Books API (ISBN lookup, then title/author fallback)
   - Open Library API (edition lookup, then work lookup)
4. **Extract genres** - Process API responses
5. **Store result** - Save to `processing/{uuid}/enriched/{isbn}_{title}.json`

### Output Format

Stored in S3:

```json
{
  "original_book": {
    "title": "The Hobbit",
    "author": "J.R.R. Tolkien",
    "isbn13": "9780547928227"
  },
  "enriched_result": {
    "statusCode": 200,
    "body": {
      "isbn": "0547928227",
      "title": "The Hobbit",
      "author": "J.R.R. Tolkien",
      "final_genres": ["Fantasy", "Fiction", "Classics"],
      "thumbnail_url": "https://books.google.com/...",
      "genre_sources": ["google", "openlibrary"],
      "enrichment_logs": ["Found via Google Books ISBN lookup"],
      "genre_enrichment_success": true
    }
  },
  "processing_uuid": "550e8400-...",
  "timestamp": "1705315200"
}
```

---

## Aggregator

**Source:** `cdk/lambda_code/aggregator/lambda_function.py`

**Trigger:** CloudWatch Events (periodic) or direct invocation

### Purpose

Combines enriched book results and generates the final dashboard JSON.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `S3_BUCKET_NAME` | S3 bucket for all data |
| `LOG_LEVEL` | Logging verbosity |

### Processing Modes

#### Scheduled (CloudWatch Events)
Checks all processing jobs and aggregates any that are ready:

```json
{}  // Empty event triggers scan
```

#### Direct Invocation
Process a specific job:

```json
{
  "processing_uuid": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Processing Steps

1. **Check readiness** - Verify all books have enriched results
2. **Load original books** - Fetch from `processing/{uuid}/original_books.json`
3. **Load enriched results** - Fetch all files from `processing/{uuid}/enriched/`
4. **Merge data** - Combine into BookAnalytics objects
5. **Generate dashboard JSON** - Using `create_dashboard_json()`
6. **Save to S3** - Store at `data/{uuid}.json`
7. **Update status** - Mark as 'complete'
8. **Clean up** - Delete intermediate files

### Readiness Check

A job is ready for aggregation when:
- Status is 'processing' (not 'complete' or 'error')
- `original_books.json` exists
- Enriched file count >= total_books count

---

## Status Checker

**Source:** `cdk/lambda_code/status_checker/lambda_function.py`

**Trigger:** API Gateway `GET /api/status/{uuid}`, `GET /api/data/{uuid}`, `DELETE /api/data/{uuid}`

### Purpose

Handles status checking, data retrieval, and data deletion.

### Environment Variables

| Variable | Description |
|----------|-------------|
| `DATA_BUCKET` | S3 bucket for all data |
| `ENVIRONMENT` | Deployment environment |
| `LOG_LEVEL` | Logging verbosity |

### Routes

| Method | Path | Handler |
|--------|------|---------|
| GET | `/api/status/{uuid}` | `get_processing_status()` |
| GET | `/api/data/{uuid}` | `get_dashboard_data()` |
| DELETE | `/api/data/{uuid}` | `delete_user_data()` |

### Input Event

API Gateway event:

```json
{
  "path": "/api/status/550e8400-...",
  "httpMethod": "GET",
  "pathParameters": {
    "uuid": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

### Status Response

```json
{
  "uuid": "550e8400-...",
  "status": "processing",
  "progress": {
    "total_books": 1247,
    "processed_books": 856,
    "percent_complete": 68.7
  },
  "message": "Genre enrichment in progress",
  "estimated_completion": 1705315800.5
}
```

### Data Response

Returns full dashboard JSON (see [Data Models](data-models.md#dashboard-json-structure)).

### Delete Response

```json
{
  "message": "Data deleted successfully",
  "deleted_files": ["dashboard.json", "status.json", "raw.csv"]
}
```

---

## Shared Dependencies

All Lambda functions use a shared Lambda Layer containing:

- `genres/` Python package
- `boto3` (AWS SDK)
- `pandas` (CSV processing)
- `aiohttp` (async HTTP)

The layer is built and deployed via CDK.

---

## Error Handling

All functions follow this pattern:

1. **Try/catch at handler level** - Catch all exceptions
2. **Update status on error** - Set status to 'error' with message
3. **Log errors** - Detailed logging with `exc_info=True`
4. **Return error response** - Appropriate HTTP status code

Example:

```python
try:
    # Processing logic
except Exception as e:
    logger.error(f"Error: {e}", exc_info=True)
    update_status(uuid, 'error', error_message=str(e))
    return {
        'statusCode': 500,
        'body': json.dumps({'error': str(e)})
    }
```

---

## Monitoring

### CloudWatch Log Groups

| Function | Log Group |
|----------|-----------|
| Upload Handler | `/aws/lambda/GoodreadsStats-{env}-Api-UploadHandler...` |
| Orchestrator | `/aws/lambda/GoodreadsStats-{env}-Api-Orchestrator...` |
| Book Processor | `/aws/lambda/GoodreadsStats-{env}-Api-BookProcessor...` |
| Aggregator | `/aws/lambda/GoodreadsStats-{env}-Api-Aggregator...` |
| Status Checker | `/aws/lambda/GoodreadsStats-{env}-Api-StatusChecker...` |

### Viewing Logs

```bash
# Tail recent logs
aws logs tail /aws/lambda/GoodreadsStats-Prod-Api-UploadHandler... --since 1h

# Filter for errors
aws logs filter-log-events \
  --log-group-name '/aws/lambda/GoodreadsStats-Prod-Api-Orchestrator...' \
  --filter-pattern "ERROR"
```

---

## Timeout Configuration

| Function | Timeout | Memory |
|----------|---------|--------|
| Upload Handler | 30s | 256 MB |
| Orchestrator | 300s (5 min) | 512 MB |
| Book Processor | 60s | 512 MB |
| Aggregator | 300s (5 min) | 1024 MB |
| Status Checker | 30s | 256 MB |
