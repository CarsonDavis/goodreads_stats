# Goodreads Stats Application - Complete Data Flow Documentation

## Overview

This document provides a comprehensive analysis of how data flows through the Goodreads Stats application, from CSV upload through processing to final dashboard display. The system is built on AWS using a serverless architecture with sophisticated genre enrichment capabilities.

## High-Level Architecture

The application consists of **three main architectural layers**:

1. **Infrastructure Layer** (AWS CDK) - Serverless AWS resources
2. **Processing Layer** (genres module) - Genre enrichment and analytics pipeline
3. **Frontend Layer** (React dashboard) - User interface and data visualization

## Detailed Data Flow

### Phase 1: Initial Upload and Validation

**Trigger**: User uploads CSV file through the web interface

**URL Endpoints**:
- **Production**: `https://goodreads-stats.codebycarson.com/api/upload`
- **Development**: `https://dev.goodreads-stats.codebycarson.com/api/upload`

**Flow**:
1. **User Action**: CSV file upload via web form (multipart/form-data)
2. **CloudFront**: Request routed through CDN
3. **API Gateway**: Forwards to Upload Handler Lambda
4. **Upload Handler Lambda** (`cdk/lambda_code/upload_handler/lambda_function.py:48`):
   - **Multipart Parsing**: Extracts CSV from form data
   - **Validation**: Checks for required Goodreads headers (title, author, my rating, date read)
   - **Size Check**: Enforces 50MB maximum file size
   - **Storage**: Saves CSV to S3 at `uploads/{job_id}/raw.csv`
   - **Metadata**: Creates `uploads/{job_id}/metadata.json`
   - **Synchronous Processing**: Invokes Orchestrator and waits for completion

**Key Files**:
- Storage: `cdk/stacks/storage_stack.py` - S3 bucket configuration
- Upload Handler: `cdk/lambda_code/upload_handler/lambda_function.py`

### Phase 2: CSV Processing and Book Extraction

**Trigger**: Upload Handler invokes Orchestrator Lambda synchronously

**Flow**:
1. **Orchestrator Lambda** (`cdk/lambda_code/orchestrator/lambda_function.py:59`):
   - **CSV Download**: Retrieves file from S3
   - **CSV Parsing**: Uses `AnalyticsCSVProcessor` from genres module
   - **Book Loading**: Converts to `BookAnalytics` objects
   - **Book Conversion**: Creates `BookInfo` objects for enrichment
   - **Chunked Processing**: Divides books into chunks of 350 books each

**Key Integration Points**:
- **AnalyticsCSVProcessor** (`genres/pipeline/csv_loader.py`): Parses Goodreads CSV format
- **BookAnalytics** (`genres/models/analytics.py`): Comprehensive book data model
- **BookInfo** (`genres/models/book.py`): Simplified model for enrichment

### Phase 3: Parallel Genre Enrichment

**Trigger**: Orchestrator processes each chunk of books in parallel

**Architecture**: **Adaptive Processing Strategy**
- **Local Environment**: Uses `AsyncGenreEnricher` with 15 concurrent threads (4-6 minutes)
- **AWS Lambda Environment**: Spawns 1 Lambda per book for massive parallelism (10-30 seconds)

**Flow**:
1. **Chunk Processing**: Each chunk of 350 books processed simultaneously
2. **Book Processor Lambda** (`cdk/lambda_code/book_processor/lambda_function.py:17`):
   - **Individual Book Processing**: One Lambda invocation per book
   - **AsyncGenreEnricher Integration**: Uses existing enrichment pipeline
   - **API Calls**: Concurrent calls to Google Books and Open Library APIs
   - **Genre Extraction**: Processes and normalizes genre data
   - **Thumbnail Extraction**: Gets book cover images

**Genre Enrichment Deep Dive**:

**API Sources** (`genres/sources/`):
- **Google Books API** (`genres/sources/google.py`):
  - Primary strategy: ISBN lookup
  - Fallback: Title + Author search
  - Extracts: `mainCategory`, `categories`, thumbnail URLs
- **Open Library API** (`genres/sources/openlibrary.py`):
  - Dual lookup: Edition API + Work API
  - Extracts: subjects from multiple response formats

**Processing Pipeline** (`genres/pipeline/enricher.py`):
- **AsyncGenreEnricher**: High-performance async enrichment
- **Concurrent API Calls**: Google Books and Open Library called simultaneously
- **Rate Limiting**: Configurable delays and semaphore controls
- **Error Handling**: Graceful degradation with comprehensive logging

**Data Processing** (`genres/utils/genre_merger.py`):
- **Genre Normalization**: Case-insensitive deduplication
- **Noise Removal**: Filters out date-like entries and short strings
- **Capitalization**: Preserves better title case formatting

### Phase 4: Result Aggregation and Dashboard Generation

**Trigger**: All book processing chunks complete

**Flow**:
1. **Result Aggregation**: Orchestrator collects all enriched book results
2. **Dashboard JSON Creation** (`cdk/lambda_code/orchestrator/lambda_function.py:380`):
   - **Data Merging**: Combines original CSV data with enriched results
   - **Analytics Preparation**: Creates dashboard-optimized structure
   - **Metadata Generation**: Adds processing statistics and timestamps
3. **S3 Storage**: Final JSON saved to `data/{job_id}.json`
4. **Cleanup**: Original CSV file deleted from uploads folder

**Key Integration Points**:
- **BookAnalytics.to_dashboard_dict()**: Converts analytics data for dashboard
- **FinalJSONExporter** (`genres/pipeline/exporter.py`): Dashboard optimization

### Phase 5: Dashboard Data Retrieval

**Trigger**: Frontend requests dashboard data

**Flow**:
1. **Frontend Request**: Dashboard loads with job_id
2. **CloudFront**: Caches static content, passes API calls through
3. **API Gateway**: Routes `/api/data/{job_id}` to Data Handler
4. **Data Handler Lambda**: Simple S3 proxy returning JSON
5. **Dashboard Rendering**: React frontend processes and displays data

## Environment Configuration

### Production Environment
- **Domain**: `goodreads-stats.codebycarson.com`
- **Bucket**: `goodreads-stats`
- **Features**: CloudFront OAI, longer log retention, SSL termination
- **Processing**: AWS Lambda swarm for ultra-fast processing

### Development Environment  
- **Domain**: `dev.goodreads-stats.codebycarson.com`
- **Bucket**: `goodreads-stats-dev`
- **Features**: Direct S3 access, shorter log retention
- **Processing**: Same Lambda architecture as production

## Storage Structure

### S3 Bucket Organization
```
goodreads-stats/
├── uploads/{job_id}/           # Temporary upload storage
│   ├── raw.csv                 # Original CSV (deleted after processing)
│   └── metadata.json           # Upload metadata
├── data/                       # Final dashboard data
│   └── {job_id}.json          # Dashboard JSON (permanent)
└── status/                     # Processing status (legacy)
    └── {job_id}.json          # Status tracking
```

### Lifecycle Policies
- **uploads/**: Auto-delete after 7 days
- **data/**: Move to IA storage after 90 days
- **Dashboard data**: Permanent retention for analytics

## Performance Characteristics

### Processing Performance
- **Local Processing**: 4-6 minutes with AsyncGenreEnricher (15 threads)
- **AWS Lambda Processing**: 10-30 seconds with parallel Lambda swarm
- **Cost**: Approximately $0.05-0.10 per processing job in AWS
- **Concurrency**: 350 simultaneous book processors with reserved capacity

### Scalability Features
- **Chunked Processing**: Handles large CSV files (tested up to 50MB)
- **Graceful Failure**: Individual book failures don't stop overall processing
- **Rate Limiting**: Configurable API throttling
- **Concurrent Limits**: Semaphore controls prevent API overload

## Error Handling and Monitoring

### Comprehensive Logging
- **Correlation IDs**: Track requests across all Lambda functions
- **Structured Logging**: JSON format with metadata
- **CloudWatch Integration**: Centralized log aggregation
- **Processing Logs**: Stored in EnrichedBook objects for debugging

### Failure Modes
- **API Timeouts**: Graceful fallback with partial results
- **Lambda Failures**: Individual book failures isolated
- **CSV Validation**: Early detection of invalid formats
- **Storage Failures**: Automatic cleanup on processing errors

## API Rate Limiting and External Dependencies

### Google Books API
- **Rate Limits**: Configurable delays between requests
- **Query Strategy**: ISBN primary, title+author fallback
- **Response Processing**: Handles various response formats

### Open Library API
- **Dual Lookups**: Edition and Work APIs for comprehensive data
- **Error Handling**: Robust parsing of nested JSON structures
- **Caching**: Implicit through Lambda execution model

## Security Features

### Access Control
- **IAM Roles**: Least privilege for each Lambda function
- **S3 Policies**: Bucket-level access controls
- **CORS**: Properly configured for frontend domains
- **SSL/TLS**: End-to-end HTTPS with ACM certificates

### Data Protection
- **Input Validation**: CSV format and size validation
- **Origin Access Identity**: Secure CloudFront to S3 access
- **No Sensitive Data**: CSV contains only public book information
- **Automatic Cleanup**: Temporary data automatically deleted

## Integration Points

### CDK Infrastructure ↔ Genres Module
- **Lambda Layer**: Shared dependencies including genres module
- **Environment Variables**: Configuration passed to Lambda functions
- **S3 Integration**: Direct file access from processing pipeline
- **Error Propagation**: Structured error handling across layers

### Key Integration Files
- **Orchestrator**: `cdk/lambda_code/orchestrator/lambda_function.py:14-18` (imports genres)
- **Book Processor**: `cdk/lambda_code/book_processor/lambda_function.py:12-14` (imports genres)
- **CDK Deployment**: `cdk/stacks/api_stack.py` (Lambda layer creation)

## Monitoring and Observability

### CloudWatch Metrics
- **Lambda Performance**: Duration, memory usage, error rates
- **API Gateway**: Request counts, latency, error rates
- **S3 Operations**: Upload/download metrics

### X-Ray Tracing
- **Request Tracing**: End-to-end request tracking
- **Performance Analysis**: Lambda cold starts and execution time
- **Error Analysis**: Detailed error context and stack traces

## Summary

The Goodreads Stats application implements a sophisticated, scalable data processing pipeline that:

1. **Efficiently handles large CSV uploads** with validation and error handling
2. **Processes books in parallel** using AWS Lambda for massive scalability  
3. **Enriches book data** through multiple API sources with intelligent fallbacks
4. **Adapts processing strategy** automatically based on execution environment
5. **Provides comprehensive monitoring** with structured logging and correlation tracking
6. **Maintains data security** through proper access controls and cleanup procedures

The system processes typical Goodreads exports (500-2000 books) in under 30 seconds in AWS while maintaining high reliability and comprehensive error handling. The modular architecture allows for easy extension with additional data sources or processing capabilities.