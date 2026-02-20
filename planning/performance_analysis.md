# Step Functions Performance Analysis: Concurrency Bottleneck Investigation

## Executive Summary

A Step Functions workflow designed to process 565 books in parallel is taking 63 seconds instead of the expected 3-5 seconds. Investigation reveals that AWS Step Functions is throttling concurrent executions to only 24 Lambda instances, despite being configured for 1000 max concurrency.

## Current Performance Breakdown

### Expected vs Actual Timing
- **Expected**: 3-5 seconds total
  - Orchestrator: 1s
  - Map State (parallel): 3s (with cold starts)
  - Aggregator: 1s

- **Actual**: 63 seconds total
  - Orchestrator: 1.17s ✅
  - Map State (parallel): 61s ❌ **BOTTLENECK**
  - Aggregator: 0.59s ✅

### Component Analysis
1. **Orchestrator**: 1.17 seconds (CSV parsing, S3 upload, Step Function trigger)
2. **Map State**: 61 seconds processing 565 books
3. **Aggregator**: 0.59 seconds (data merge, JSON creation, S3 upload)

## Root Cause Analysis

### Concurrency Throttling Discovery
- **Configured**: `max_concurrency=1000` in Step Functions Map state
- **AWS Account Limit**: 400 concurrent Lambda executions
- **Measured Reality**: Only 24 concurrent executions peak

### The Math That Doesn't Add Up
```
Expected: 565 books ÷ 400 concurrent = 2 waves × 3 seconds = 6 seconds
Actual: 565 books ÷ 24 concurrent = 24 waves × 3 seconds = 60+ seconds
```

### Execution Pattern Analysis
Timestamps show Lambda executions spread across 59 seconds (05:15:02 to 05:16:02), indicating sequential waves rather than true parallelization.

## AWS Queries to Confirm Bottleneck

### 1. Check Lambda Concurrency Metrics
```bash
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name ConcurrentExecutions \
  --dimensions Name=FunctionName,Value=<FUNCTION_NAME> \
  --start-time "2025-07-01T05:14:00Z" \
  --end-time "2025-07-01T05:17:00Z" \
  --period 60 \
  --statistics Maximum \
  --profile personal
```

**Expected Result**: Should show peak concurrency around 24, not 400+

### 2. Verify Account Limits
```bash
aws lambda get-account-settings --profile personal
```

**Check**: `ConcurrentExecutions` should be 400 (not the bottleneck)

### 3. Check Reserved Concurrency
```bash
aws lambda get-function \
  --function-name <FUNCTION_NAME> \
  --profile personal \
  --query "Configuration.ReservedConcurrencyExecutions"
```

**Expected Result**: `null` (no reserved limits)

### 4. Analyze Execution Timing Pattern
```bash
aws logs filter-log-events \
  --log-group-name <LOG_GROUP> \
  --start-time <START_TIMESTAMP> \
  --end-time <END_TIMESTAMP> \
  --profile personal \
  --query "events[?contains(message, 'REPORT RequestId')].timestamp" \
  --output text
```

**Expected Pattern**: Timestamps spread across 60 seconds instead of clustered in 3-6 seconds

## Conclusion

The bottleneck is **Step Functions' internal concurrency throttling**, not Lambda account limits. Despite configuring `max_concurrency=1000`, Step Functions is only allowing ~24 concurrent Map state executions.

This represents a **96% reduction** in expected parallelism (24 vs 1000 configured) and explains the 10x performance degradation.

## Recommended Solutions

1. **Contact AWS Support**: Request Step Functions concurrency limit increase
2. **Batch Processing**: Process 10-20 books per Lambda (reduce to ~30-60 total Lambdas)
3. **Provisioned Concurrency**: Eliminate cold start delays
4. **Alternative Architecture**: Consider SQS + Lambda for true parallelization

The batch processing approach would likely provide the best immediate improvement while staying within current AWS service limits.
