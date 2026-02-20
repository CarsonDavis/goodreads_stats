# Event-Driven Aggregator Plan

## Current Problem
- Aggregator runs on 1-minute cron schedule
- Average 30-second wait time even when all books are processed
- Unnecessary Lambda invocations when no work is ready
- Total processing time: ~78 seconds (target: 5-10 seconds)

## Proposed Event-Driven Architecture

### Option 1: S3 Event Trigger (Recommended)
**Flow:**
1. BookProcessor stores enriched result → S3 PutObject event
2. S3 event triggers Aggregator Lambda
3. Aggregator checks completion count, processes if ready

**Implementation:**
- Add S3 event notification on `processing/{uuid}/enriched/` prefix
- Aggregator maintains atomic counter in DynamoDB or S3
- Only aggregates when counter = expected book count

**Pros:**
- AWS-native pattern
- Zero polling overhead
- Immediate response to completion

**Cons:**
- Need completion counting logic
- Potential for duplicate triggers

### Option 2: SQS Completion Queue
**Flow:**
1. BookProcessor sends completion message to SQS "completion queue"
2. Aggregator triggered by SQS events (batch size = expected book count)
3. When batch is full, trigger aggregation

**Pros:**
- Built-in batching
- Guaranteed delivery
- Simple completion detection

**Cons:**
- Additional SQS queue
- Fixed batch size challenges

### Option 3: Direct Lambda Invocation with Coordination
**Flow:**
1. BookProcessor updates completion counter in DynamoDB
2. Last BookProcessor to complete triggers Aggregator directly
3. Aggregator processes immediately when all books done

**Pros:**
- Immediate processing
- No intermediate queues

**Cons:**
- Race conditions with counters
- More complex coordination logic

## Benefits
- **Performance**: 0-5 second processing time (eliminates ~30s wait)
- **Cost**: ~90% reduction in aggregator invocations 
- **Scalability**: Works for any number of books
- **Reliability**: Only processes when work is actually ready

## Implementation Steps
1. Add S3 event notification to CDK infrastructure
2. Modify aggregator to handle S3 events vs cron triggers
3. Add completion tracking logic (DynamoDB counter)
4. Remove CloudWatch Events schedule
5. Test with sample processing job
6. Monitor and optimize

## Recommended Approach: Option 1 (S3 Events)

### Technical Implementation
```python
# CDK: Add S3 event notification
s3_bucket.add_event_notification(
    s3.EventType.OBJECT_CREATED,
    s3n.LambdaDestination(aggregator_lambda),
    s3.NotificationKeyFilter(prefix="processing/", suffix=".json")
)

# Aggregator: Handle S3 events
def lambda_handler(event, context):
    if 'Records' in event and event['Records'][0]['eventSource'] == 'aws:s3':
        # S3 event - check if job is complete
        return handle_s3_completion_event(event)
    else:
        # Legacy cron trigger (keep during transition)
        return check_and_process_ready_jobs()
```

### Completion Tracking
- Use DynamoDB table: `processing_status`
- Key: `processing_uuid`
- Attributes: `total_books`, `completed_books`, `status`
- Atomic increment on each BookProcessor completion

This approach will reduce total processing time from ~78 seconds to ~5-10 seconds by eliminating the cron schedule delay.