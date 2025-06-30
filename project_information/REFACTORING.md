# Refactoring Plan: Monolithic Orchestrator to Step Functions Architecture

## Current Architecture

### Data Flow
1. **Upload Handler** (`upload_handler/lambda_function.py`) receives CSV upload
2. **Orchestrator** (`orchestrator/lambda_function.py`) processes entire CSV sequentially:
   - Uses `AnalyticsCSVProcessor` to parse CSV into `BookAnalytics` objects
   - Converts to `BookInfo` objects for enrichment
   - Uses `EnvironmentAwareBookPipeline` with `AsyncGenreEnricher` (15 concurrent)
   - Processes all books in single Lambda execution
   - Uses `create_dashboard_json` to generate final output
3. **Status Checker** (`status_checker/lambda_function.py`) handles status/data retrieval

### Key Components
- **Data Models**: `BookAnalytics` (67 fields), `BookInfo` (lightweight), `EnrichedBook` (progressive enrichment)
- **Pipeline**: `AnalyticsCSVProcessor`, `EnvironmentAwareBookPipeline`, `FinalJSONExporter`
- **Infrastructure**: CDK stack with Lambda layer, S3 bucket, API Gateway

### Current Limitations
- Single Lambda processes entire library (timeout risk at 15 minutes)
- Sequential bottleneck despite async processing
- Memory/CPU constrained to single function

---

## Proposed Architecture

### Data Flow
1. **Upload Handler** (unchanged)
2. **Orchestrator** (refactored):
   - Parse CSV using existing `AnalyticsCSVProcessor`
   - Start Step Function execution with book array
3. **Step Function State Machine**:
   - **Map State**: Fan out to N parallel `BookProcessor` Lambdas
   - **Aggregator**: Fan in results and create final JSON
4. **Status Checker** (unchanged)

### New Components

**BookProcessor Lambda** (`lambda_code/book_processor/`):
- Processes single book using existing `AsyncGenreEnricher`
- Input: Single `BookInfo` object
- Output: `EnrichedBook` data (genres, thumbnails, logs)
- 30-second timeout, 256MB memory

**Aggregator Lambda** (`lambda_code/aggregator/`):
- Merges enriched data back into `BookAnalytics` objects
- Uses existing `create_dashboard_json` for final output
- Updates S3 status to 'complete'
- 5-minute timeout, 512MB memory

**Step Function State Machine**:
- Map state with 1000 max concurrency
- Chains Map → Aggregator
- 30-minute total timeout

---

## Implementation Details

### CDK Updates (`api_stack.py`)
```python
# Add Step Functions imports
from aws_cdk import aws_stepfunctions as sfn, aws_stepfunctions_tasks as tasks

# New Lambda functions
self.book_processor = _lambda.Function(...)
self.aggregator = _lambda.Function(...)

# Step Function definition
book_processor_task = tasks.LambdaInvoke(self, "ProcessBook", lambda_function=self.book_processor)
map_state = sfn.Map(self, "ProcessAllBooks", max_concurrency=1000).iterator(book_processor_task)
aggregator_task = tasks.LambdaInvoke(self, "AggregateResults", lambda_function=self.aggregator)
definition = map_state.next(aggregator_task)

self.state_machine = sfn.StateMachine(self, "BookProcessingStateMachine", definition=definition)
```

### Orchestrator Changes
Replace enrichment loop with:
```python
# Prepare Step Function input
step_function_input = {
    "processing_uuid": processing_uuid,
    "books": [{"book": book_info.__dict__} for book_info in book_infos],
    "original_books": [book.to_dashboard_dict() for book in books]
}

# Start Step Function
stepfunctions_client.start_execution(
    stateMachineArn=os.environ['STATE_MACHINE_ARN'],
    input=json.dumps(step_function_input)
)
```

### BookProcessor Implementation
```python
# Use existing enricher for single book
async with AsyncGenreEnricher(max_concurrent=1) as enricher:
    enriched_book = await enricher.enrich_book_async(book_info)
    return enriched_book.to_dict()
```

### Aggregator Implementation
```python
# Merge enriched data back into BookAnalytics
for original_book, enriched_result in zip(original_books, enriched_results):
    book = BookAnalytics(**original_book)
    if enriched_result['statusCode'] == 200:
        book.final_genres = enriched_result['body']['final_genres']
        book.genre_enrichment_success = len(book.final_genres) > 0

# Use existing exporter
create_dashboard_json(enhanced_books, output_path)
```

---

## Additional Considerations

### Dependencies
- Add to `cdk/requirements.txt`: `aws-cdk.aws-stepfunctions`, `aws-cdk.aws_stepfunctions_tasks`
- BookProcessor needs: `boto3`, `aiohttp`
- Aggregator needs: `boto3`

### IAM Permissions
- Orchestrator: `states:StartExecution` on Step Function
- Step Function: `lambda:InvokeFunction` on BookProcessor and Aggregator
- Aggregator: `s3:PutObject` on data bucket

### Error Handling
- Individual book failures don't affect batch
- Step Function has built-in retry/error handling
- Dead letter queues for persistent failures

### Rate Limiting
- Google Books: 1000 requests/day, 100/100 seconds
- Open Library: No official limits (recommend 1 req/second)
- Built into existing `AsyncGenreEnricher`

### Performance Impact
- 1000 books: 6+ minutes → ~60 seconds
- No timeout risk regardless of library size
- Cost reduction: ~50-75% due to smaller Lambda instances

### Backwards Compatibility
- Upload Handler unchanged
- Status Checker unchanged
- API Gateway unchanged
- Dashboard application unchanged
- S3 bucket structure preserved