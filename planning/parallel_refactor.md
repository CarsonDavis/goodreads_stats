# Parallel Processing Refactor Plan

## Overview

Refactor the Goodreads Stats application from a complex event-driven SQS architecture to a simplified parallel processing system with chunked execution. This reduces complexity from 5 Lambda functions to 2 while maintaining high performance and scalability.

## Current Architecture Problems

- **Over-engineered**: 5 Lambda functions for a fundamentally simple task
- **Timer-based aggregation**: 1-minute CloudWatch timer adds unnecessary latency
- **Complex coordination**: SQS + status tracking + aggregation detection
- **Unpredictable timing**: 50-110 second processing time due to timer delays

## New Architecture

### Simplified Flow
```
CSV Upload → Upload Handler → Orchestrator → [BookProcessor × 350] → Final JSON
```

### Core Components
1. **Upload Handler**: Validate CSV and trigger orchestrator
2. **Orchestrator**: Chunk books and coordinate parallel processing
3. **BookProcessor**: Process individual books (unchanged logic)

## Key Design Decisions

### Concurrency Configuration
- **Reserved Concurrency**: 350 for BookProcessor
- **Account Buffer**: 50 executions remaining for other functions
- **Chunk Size**: 350 books per chunk (matches reserved concurrency)

### Processing Strategy
- **Chunked Parallel Processing**: Process 350 books simultaneously per chunk
- **Sequential Chunks**: Process chunks one after another
- **Synchronous Coordination**: Orchestrator waits for all results
- **Graceful Failure Handling**: Individual book failures don't stop job completion

## Technical Implementation

### 1. Upload Handler Lambda

**Configuration:**
- Timeout: 2 minutes
- Memory: 512MB
- Trigger: API Gateway POST `/api/upload`

**Changes:**
- Invoke orchestrator synchronously (not async)
- Wait for complete results
- Return final job status immediately

```python
def upload_handler(event, context):
    # Validate and store CSV
    csv_data = parse_multipart_csv(event['body'])
    job_id = str(uuid.uuid4())
    csv_key = f"uploads/{job_id}/raw.csv"
    
    s3.put_object(Bucket=DATA_BUCKET, Key=csv_key, Body=csv_data)
    
    # Invoke orchestrator synchronously
    orchestrator_response = lambda_client.invoke(
        FunctionName='Orchestrator',
        InvocationType='RequestResponse',  # Wait for completion
        Payload=json.dumps({'csv_key': csv_key, 'job_id': job_id})
    )
    
    result = json.loads(orchestrator_response['Payload'].read())
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'job_id': result['job_id'],
            'status': 'complete',
            'processing_time': result['processing_time_seconds'],
            'books_processed': result['total_books'],
            'successful_enrichments': result['successful_books'],
            'failed_enrichments': result['failed_books'],
            'success_rate': result['success_rate']
        })
    }
```

### 2. Orchestrator Lambda

**Configuration:**
- Timeout: 15 minutes
- Memory: 3008MB (maximum)
- Trigger: Direct invocation from Upload Handler

**Logic:**
- Parse CSV into BookAnalytics objects
- Split into chunks of 350 books
- Process each chunk simultaneously
- Combine all results into final JSON

```python
def orchestrator(event, context):
    csv_key = event['csv_key']
    job_id = event['job_id']
    chunk_size = int(os.environ.get('CHUNK_SIZE', 350))
    
    # Parse CSV
    books = load_and_parse_csv(csv_key)
    total_chunks = math.ceil(len(books) / chunk_size)
    
    print(f"Processing {len(books)} books in {total_chunks} chunks of {chunk_size}")
    
    # Process all chunks sequentially
    all_results = []
    start_time = time.time()
    
    for chunk_index, chunk in enumerate(chunks(books, chunk_size)):
        print(f"Processing chunk {chunk_index + 1}/{total_chunks} ({len(chunk)} books)")
        
        # Process this chunk simultaneously with graceful failure handling
        chunk_results = await process_chunk_simultaneously(chunk, job_id, chunk_index)
        all_results.extend(chunk_results)
        
        # Calculate statistics
        successful_in_chunk = len([r for r in chunk_results if r.get('success', True)])
        failed_in_chunk = len(chunk_results) - successful_in_chunk
        
        progress = ((chunk_index + 1) / total_chunks) * 100
        print(f"Chunk {chunk_index + 1} completed. Progress: {progress:.1f}% "
              f"({successful_in_chunk} successful, {failed_in_chunk} failed)")
        
        # Brief pause between chunks
        if chunk_index < total_chunks - 1:
            await asyncio.sleep(1)
    
    # Calculate final statistics
    successful_books = len([r for r in all_results if r.get('success', True)])
    failed_books = len(all_results) - successful_books
    success_rate = (successful_books / len(all_results)) * 100 if all_results else 0
    
    # Create final dashboard JSON with failed books included
    dashboard_data = create_final_dashboard_json(all_results)
    s3.put_object(Bucket=DATA_BUCKET, Key=f"data/{job_id}.json", Body=json.dumps(dashboard_data))
    
    return {
        'job_id': job_id,
        'status': 'complete',
        'total_books': len(books),
        'successful_books': successful_books,
        'failed_books': failed_books,
        'success_rate': round(success_rate, 1),
        'chunks_processed': total_chunks,
        'processing_time_seconds': round(time.time() - start_time, 1)
    }

async def process_chunk_simultaneously(chunk, job_id, chunk_index):
    """Process chunk with graceful failure handling"""
    tasks = []
    for book_index, book in enumerate(chunk):
        task = invoke_book_processor_with_fallback(book, job_id, (chunk_index * 350) + book_index)
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
                'book_id': book.get('goodreads_id', f"{book['title']}-{book['author']}"),
                'title': book['title'],
                'author': book['author'],
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

async def invoke_book_processor_with_fallback(book, job_id, book_index):
    """Invoke book processor with timeout and retry logic"""
    try:
        response = await lambda_client.invoke(
            FunctionName='BookProcessor',
            InvocationType='RequestResponse',
            Payload=json.dumps({'book': book})
        )
        
        result = json.loads(response['Payload'].read())
        
        # Check for Lambda-level errors
        if 'errorMessage' in result:
            raise Exception(f"Lambda error: {result['errorMessage']}")
            
        return result
        
    except Exception as e:
        # Return a failed result rather than raising
        return {
            'book_id': book.get('goodreads_id', f"{book['title']}-{book['author']}"),
            'title': book['title'],
            'author': book['author'],
            'success': False,
            'final_genres': [],
            'thumbnail_url': None,
            'genre_enrichment_success': False,
            'error_message': f"Invocation failed: {str(e)}",
            'processing_logs': [f"Lambda invocation error: {str(e)}"]
        }
```

### 3. BookProcessor Lambda

**Configuration:**
- Timeout: 5 minutes
- Memory: 512MB
- Reserved Concurrency: 350
- Trigger: Direct invocation from Orchestrator

**Changes:**
- Remove SQS event handling
- Remove S3 result storage
- Return enriched data directly

```python
def book_processor(event, context):
    book_data = event['book']
    book_id = book_data.get('goodreads_id', f"{book_data['title']}-{book_data['author']}")
    
    # Standardized result format
    result = {
        'book_id': book_id,
        'title': book_data['title'],
        'author': book_data['author'],
        'success': False,
        'final_genres': [],
        'thumbnail_url': None,
        'genre_enrichment_success': False,
        'error_message': None,
        'processing_logs': []
    }
    
    try:
        # Convert to BookInfo and enrich
        book_info = BookInfo(**book_data)
        
        async def enrich():
            try:
                async with AsyncGenreEnricher(max_concurrent=1) as enricher:
                    enriched_book = await enricher.enrich_book_async(book_info)
                    return enriched_book
            except asyncio.TimeoutError:
                raise Exception("API timeout during enrichment")
            except Exception as e:
                raise Exception(f"Enrichment failed: {str(e)}")
        
        enriched_result = asyncio.run(enrich())
        
        # Success case
        result.update({
            'success': True,
            'final_genres': enriched_result.final_genres,
            'thumbnail_url': enriched_result.thumbnail_url,
            'genre_enrichment_success': len(enriched_result.final_genres) > 0,
            'processing_logs': enriched_result.processing_log
        })
        
    except Exception as e:
        # Graceful failure - log error but don't fail the Lambda
        error_msg = str(e)
        result.update({
            'success': False,
            'error_message': error_msg,
            'processing_logs': [f"Processing failed: {error_msg}"],
            'final_genres': [],  # Empty genres for failed books
            'genre_enrichment_success': False
        })
        
        # Log for debugging but don't raise
        print(f"Book processing failed for {book_data['title']}: {error_msg}")
    
    return result
```

## CDK Infrastructure Changes

### Remove Components
- **SQS Queue**: No longer needed for coordination
- **Aggregator Lambda**: Logic moved to Orchestrator
- **Status Checker Lambda**: No status checking needed (synchronous)
- **CloudWatch Events**: No timer-based triggers

### Update Components

```python
class ApiStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, storage_stack, deployment_env: str, **kwargs):
        super().__init__(scope, construct_id, **kwargs)
        
        # Configuration
        BOOK_PROCESSOR_CONCURRENCY = 350
        CHUNK_SIZE = 350
        
        base_env = {
            "DATA_BUCKET": storage_stack.data_bucket.bucket_name,
            "ENVIRONMENT": deployment_env,
            "CHUNK_SIZE": str(CHUNK_SIZE)
        }
        
        # BookProcessor with reserved concurrency
        self.book_processor = _lambda.Function(
            self, "BookProcessor",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/book_processor"),
            timeout=Duration.seconds(300),
            memory_size=512,
            environment=base_env,
            layers=[lambda_layer],
            reserved_concurrent_executions=BOOK_PROCESSOR_CONCURRENCY
        )
        
        # Orchestrator
        self.orchestrator = _lambda.Function(
            self, "Orchestrator",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="lambda_function.lambda_handler",
            code=_lambda.Code.from_asset("lambda_code/orchestrator"),
            timeout=Duration.minutes(15),
            memory_size=3008,
            environment={
                **base_env,
                "BOOK_PROCESSOR_FUNCTION_NAME": self.book_processor.function_name
            },
            layers=[lambda_layer]
        )
        
        # Grant orchestrator permission to invoke book processor
        self.book_processor.grant_invoke(self.orchestrator)
```

## API Changes

### Before (Complex)
```
POST /upload → {"uuid": "...", "status": "processing"}
GET /status/{uuid} → {"status": "processing", "progress": "50%"}
GET /data/{uuid} → {dashboard_data}  # Only when complete
```

### After (Simple)
```
POST /upload → {
  "job_id": "...", 
  "status": "complete", 
  "processing_time": 85.2,
  "books_processed": 762,
  "successful_enrichments": 735,
  "failed_enrichments": 27,
  "success_rate": 96.5
}
GET /data/{job_id} → {dashboard_data}  # Always available
```

## Performance Characteristics

### Dataset Examples with 350 Chunk Size

| Books | Chunks | Processing Time | Concurrency Used |
|-------|--------|----------------|------------------|
| 150   | 1      | ~30 seconds    | 150/350         |
| 762   | 3      | ~90 seconds    | 350/350         |
| 1500  | 5      | ~150 seconds   | 350/350         |
| 3500  | 10     | ~300 seconds   | 350/350         |

### Concurrency Allocation
```
Total Account Limit: 400 concurrent executions

BookProcessor: 350 reserved (87.5%)
├── Processing chunks: Uses exactly 350
├── Guaranteed availability: ✅
└── No throttling: ✅

Other Functions: 50 available (12.5%)
├── Upload Handler: 1-2 executions
├── Orchestrator: 1 execution
├── Other apps: 40+ executions
└── Safety buffer: ✅
```

## Benefits

### Complexity Reduction
- **5 Lambda functions → 2 Lambda functions**
- **No SQS queues or DLQs**
- **No status tracking files**
- **No CloudWatch timers**
- **No completion detection logic**

### Performance Improvements
- **Predictable timing**: No 0-60 second timer delays
- **Immediate results**: Synchronous processing with instant completion
- **Faster small datasets**: No overhead for coordination
- **Progress visibility**: Real-time chunk progress logging

### Operational Benefits
- **Simpler debugging**: Linear execution flow
- **Robust error handling**: Individual book failures don't stop job completion
- **Easier monitoring**: Fewer moving parts
- **Cost optimization**: Fewer Lambda invocations
- **Complete transparency**: Success/failure statistics for every job

## Migration Plan

### Phase 1: Infrastructure Updates
1. Update CDK stacks to remove SQS, Aggregator, Status Checker
2. Modify BookProcessor Lambda configuration
3. Update API Gateway routes (remove status endpoints)
4. Deploy infrastructure changes

### Phase 2: Code Changes
1. Rewrite Orchestrator Lambda with chunked processing
2. Simplify BookProcessor Lambda (remove SQS handling)
3. Update Upload Handler for synchronous orchestrator calls
4. Remove aggregation and status checking code

### Phase 3: Testing & Deployment
1. Test with small datasets (< 350 books)
2. Test with medium datasets (350-1000 books)
3. Test with large datasets (1000+ books)
4. Monitor concurrency usage and performance
5. Deploy to production

### Phase 4: Cleanup
1. Remove old Lambda function code
2. Clean up S3 status and processing directories
3. Update documentation
4. Remove unused IAM permissions

## Risk Mitigation

### Timeout Risks
- **Orchestrator timeout**: 15-minute limit handles datasets up to ~15,000 books
- **BookProcessor timeout**: 5-minute limit per book is generous
- **Large datasets**: Can be processed in multiple upload sessions if needed

### Memory Risks
- **Orchestrator memory**: 3GB handles datasets up to ~10,000 books
- **Result accumulation**: Process results incrementally to avoid memory buildup

### Concurrency Risks
- **Account limits**: 350 reserved concurrency leaves buffer for other functions
- **Rate limiting**: 1-second pause between chunks prevents API overload
- **Graceful failure handling**: Individual book failures don't stop chunk processing
- **API resilience**: Failed API calls result in books without genres, not job failures

## Success Metrics

### Performance Targets
- **Small datasets** (< 350 books): Complete in < 45 seconds
- **Medium datasets** (350-1000 books): Complete in < 120 seconds
- **Large datasets** (1000+ books): Complete predictably at ~30 seconds per 350-book chunk

### Quality Targets
- **Reliability**: > 99% job completion rate
- **Data quality**: > 95% book enrichment success rate
- **Error handling**: Failed books get placeholder entries, don't block job completion
- **Transparency**: Complete success/failure statistics provided for every job

## Critical Design Feature: Graceful Failure Handling

### Philosophy
Individual book processing failures are treated as **data quality issues**, not **system failures**. The job always succeeds and returns complete results, with clear statistics on what worked and what didn't.

### Implementation Benefits
1. **User Experience**: Users always get results, even if some books fail to enrich
2. **Debugging**: Clear error messages preserved for failed books
3. **System Reliability**: No cascade failures from individual book issues
4. **Operational Clarity**: Success rates provide immediate quality feedback

### Error Categories Handled
- **API timeouts**: Google Books/Open Library unresponsive
- **Lambda failures**: Individual BookProcessor crashes
- **Network issues**: Connectivity problems during enrichment
- **Data format issues**: Malformed book data or API responses
- **Rate limiting**: API quotas exceeded during processing

This refactor significantly simplifies the architecture while maintaining high performance, improving predictability, and providing robust error handling for users.