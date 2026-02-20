# Architecture Refactor: Step Functions → SQS + Lambda Fan-Out

## Executive Summary

We're refactoring from a Step Functions Map state architecture to an SQS + Lambda fan-out pattern to solve a critical performance bottleneck. The current system processes 565 books in 63 seconds due to Step Functions concurrency throttling (24 concurrent executions vs configured 1000). The new architecture will achieve ~5-10 second processing times with 79% cost reduction.

## Current Architecture Problems

### Performance Issues
- **Expected**: 3-5 seconds total processing time
- **Actual**: 63 seconds (20x slower than expected)
- **Root Cause**: Step Functions throttling to 24 concurrent executions despite `max_concurrency=1000`

### Cost Analysis (per 565-book job)
- **Step Functions**: $0.61/job
- **Limited scalability**: Cannot exceed 24 concurrent executions
- **Orchestration overhead**: 60+ seconds of coordination vs 1.8s actual work per book

## New Architecture: SQS + Lambda Fan-Out

### Design Overview
```
Upload → Orchestrator → SQS Queue (565 messages) → Lambda Auto-Scale (up to 400) → Aggregator → S3
```

### Flow Details
1. **Upload Handler**: Receives CSV, generates UUID, stores in S3
2. **Orchestrator**: Parses CSV, creates 565 SQS messages (1 per book)
3. **SQS Queue**: Distributes messages to auto-scaling Lambda functions
4. **Book Processor Lambda**: Processes individual books (triggered by SQS)
5. **Aggregator**: Triggered after all processing, creates final dashboard JSON

### Performance Improvements
- **Processing Time**: 5-10 seconds (vs 63 seconds)
- **True Parallelism**: Up to 400 concurrent Lambda executions
- **No Artificial Limits**: SQS doesn't throttle like Step Functions
- **Cost Savings**: $0.13/job (79% reduction)

## Current Code Architecture Review

### 1. Upload Handler (`upload_handler/lambda_function.py`)
**Current Behavior**: ✅ No changes needed
- Handles multipart form CSV uploads
- Generates UUID and stores files in S3
- Triggers orchestrator asynchronously
- Status management via S3

### 2. Orchestrator (`orchestrator/lambda_function.py`)
**Current Behavior**: 
- Downloads CSV from S3 (lines 87-94)
- Processes with `AnalyticsCSVProcessor` (lines 98-103)
- Converts to `BookInfo` objects (lines 118-126)
- Stores book data in S3 (lines 136-158)
- **Triggers Step Functions** (lines 176-194) ← **NEEDS CHANGE**

**Required Changes**:
- Replace Step Functions trigger with SQS message publishing
- Send 565 individual messages to SQS queue
- Each message contains single book data + processing context

### 3. Book Processor (`book_processor/lambda_function.py`)
**Current Behavior**: ✅ Minimal changes needed
- Handles both "load_books" and single book processing
- Uses `AsyncGenreEnricher` for API calls (lines 39-40)
- Returns structured result format (lines 43-55)

**Required Changes**:
- Remove "load_books" action (handled by orchestrator)
- Add SQS event source trigger
- Modify input parsing for SQS message format

### 4. Aggregator (`aggregator/lambda_function.py`)
**Current Behavior**: 
- Receives Step Functions Map output (line 183)
- Merges enriched data with original books (line 200)
- Creates dashboard JSON and uploads to S3 (lines 216-228)
- Updates processing status (lines 234-239)

**Required Changes**:
- Replace Step Functions trigger with S3 event or scheduled check
- Modify to wait for all SQS processing completion
- Same aggregation logic, different trigger mechanism

### 5. CDK Stack (`stacks/api_stack.py`)
**Current Step Functions Architecture** (lines 130-184):
- Map state with `max_concurrency=1000` (line 132)
- LoadBooks → Map → Aggregator chain (line 160)
- Complex Step Functions role and permissions

**Required Changes**:
- Replace Step Functions with SQS Queue and Dead Letter Queue
- Add SQS event source to BookProcessor Lambda
- Modify orchestrator to publish to SQS instead of Step Functions
- Update IAM permissions for SQS operations

## Refactoring Implementation Plan

### Phase 1: Infrastructure Changes (1-2 hours)

#### 1.1 Update CDK Stack
```python
# Replace Step Functions with SQS
book_queue = sqs.Queue(
    self, "BookProcessingQueue",
    visibility_timeout=Duration.minutes(2),  # 2x Lambda timeout
    dead_letter_queue=sqs.DeadLetterQueue(
        max_receive_count=3,
        queue=dlq
    )
)

# Add SQS event source to BookProcessor
book_processor.add_event_source(
    SqsEventSource(book_queue, batch_size=1)
)
```

#### 1.2 Update IAM Permissions
```python
# Grant orchestrator SQS permissions
book_queue.grant_send_messages(orchestrator_role)

# Grant BookProcessor SQS permissions (auto-added by event source)
```

#### 1.3 Remove Step Functions Components
- Delete `state_machine` definition
- Remove Step Functions IAM role
- Remove Step Functions environment variables

### Phase 2: Code Changes (2-3 hours)

#### 2.1 Modify Orchestrator
**File**: `orchestrator/lambda_function.py`

**Replace Step Functions trigger** (lines 176-194):
```python
# OLD: Step Functions trigger
response = stepfunctions_client.start_execution(...)

# NEW: SQS batch publish
sqs_client = boto3.client('sqs')
queue_url = os.environ['BOOK_QUEUE_URL']

# Send individual messages for each book
for book_info in book_infos:
    message_body = {
        'book': book_info.__dict__,
        'processing_uuid': processing_uuid,
        'bucket': DATA_BUCKET,
        'original_books_s3_key': original_books_s3_key
    }
    
    sqs_client.send_message(
        QueueUrl=queue_url,
        MessageBody=json.dumps(message_body)
    )
```

#### 2.2 Modify BookProcessor
**File**: `book_processor/lambda_function.py`

**Update event parsing** (lines 96-111):
```python
# OLD: Direct invocation or Step Functions
book_data = event.get('book', {})

# NEW: SQS message parsing
if 'Records' in event:
    # SQS event
    for record in event['Records']:
        message_body = json.loads(record['body'])
        book_data = message_body.get('book', {})
        processing_uuid = message_body.get('processing_uuid')
        # Process book...
```

**Remove load_books action** (lines 100-101):
```python
# DELETE: load_books functionality (moved to orchestrator)
if event.get('action') == 'load_books':
    return load_books_from_s3(event)
```

#### 2.3 Modify Aggregator Trigger
**Option A**: S3 Event Trigger (Recommended)
- Trigger aggregator when last book result is written
- Use S3 object count or completion marker

**Option B**: CloudWatch Events
- Scheduled check for completion
- More complex but more reliable

### Phase 3: Testing & Deployment (1 hour)

#### 3.1 Deploy Infrastructure
```bash
cd cdk
cdk diff
cdk deploy
```

#### 3.2 Update Environment Variables
```python
# Add to orchestrator
BOOK_QUEUE_URL = queue_url

# Remove from all functions
STATE_MACHINE_ARN = # DELETE
```

#### 3.3 Test End-to-End
1. Upload sample CSV (10-20 books)
2. Verify SQS message distribution
3. Check Lambda concurrency metrics
4. Validate final dashboard JSON

### Phase 4: Performance Validation

#### 4.1 Expected Metrics
- **Processing Time**: 5-10 seconds (vs 63 seconds)
- **Lambda Concurrency**: Up to 400 concurrent executions
- **Cost**: $0.13/job (vs $0.61/job)
- **Error Rate**: <1% with DLQ handling

#### 4.2 Monitoring
- CloudWatch Lambda concurrency metrics
- SQS message metrics (sent, received, deleted)
- Dead letter queue monitoring
- End-to-end processing time

## Risk Assessment

### Low Risk
- **Code Changes**: Minimal changes to core business logic
- **Rollback**: Can revert CDK changes quickly
- **Data Safety**: Same S3 storage patterns

### Medium Risk
- **Aggregator Timing**: Need new trigger mechanism
- **Error Handling**: Different retry patterns with SQS
- **Concurrency**: Higher Lambda concurrency usage

### Mitigation Strategies
- **Gradual Rollout**: Test with small datasets first
- **Monitoring**: Enhanced CloudWatch dashboards
- **Rollback Plan**: Keep Step Functions CDK code in version control

## Success Criteria

### Performance
- [ ] Processing time < 15 seconds for 565 books
- [ ] Lambda concurrency > 100 concurrent executions
- [ ] Error rate < 1%

### Cost
- [ ] Cost reduction > 50% per job
- [ ] Total cost < $0.20 per 565-book job

### Reliability
- [ ] End-to-end success rate > 99%
- [ ] Dead letter queue < 1% of messages
- [ ] No data loss or corruption

## Implementation Timeline

- **Day 1**: CDK infrastructure changes and deployment
- **Day 2**: Code refactoring and testing
- **Day 3**: Performance validation and monitoring setup
- **Day 4**: Production deployment and validation

## Post-Refactor Benefits

1. **Performance**: 10-15x faster processing times
2. **Cost**: 79% cost reduction per job
3. **Scalability**: True auto-scaling to Lambda account limits
4. **Simplicity**: Simpler architecture with fewer moving parts
5. **Reliability**: Built-in retry and dead letter queue handling

This refactor transforms a throttled, complex orchestration into a simple, fast, cost-effective fan-out pattern that better matches the parallelizable nature of the book enrichment workload.