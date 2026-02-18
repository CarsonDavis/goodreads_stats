# Architecture

This document describes the system architecture of Goodreads Stats, including both local development and cloud production modes.

## Overview

Goodreads Stats is a data processing pipeline that transforms Goodreads CSV exports into enriched JSON datasets for interactive dashboards. The system supports two execution modes with shared core logic.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GOODREADS STATS SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EXECUTION MODE 1: Local Development                           │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐│
│  │   CSV Upload    │───>│  FastAPI Server  │───>│   Static    ││
│  │   (Frontend)    │    │  (local_server)  │    │  Dashboard  ││
│  └─────────────────┘    └──────────────────┘    └─────────────┘│
│           │                       │                       │    │
│           │                       v                       │    │
│           │              ┌─────────────────┐              │    │
│           └─────────────>│ Local JSON Files│<─────────────┘    │
│                          │ (dashboard_data)│                   │
│                          └─────────────────┘                   │
│                                                                 │
│  EXECUTION MODE 2: Cloud Production (AWS)                      │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐│
│  │   CSV Upload    │───>│  Lambda Pipeline │───>│   Static    ││
│  │   (Frontend)    │    │  (AWS Serverless)│    │  Dashboard  ││
│  └─────────────────┘    └──────────────────┘    └─────────────┘│
│           │                       │                       │    │
│           │                       v                       │    │
│           │              ┌─────────────────┐              │    │
│           └─────────────>│   S3 JSON Files │<─────────────┘    │
│                          │  (Cloud Storage)│                   │
│                          └─────────────────┘                   │
└─────────────────────────────────────────────────────────────────┘
```

## Architecture Comparison

| Component | Local Docker | Cloud Production |
|-----------|--------------|------------------|
| **Frontend** | nginx:8000 | S3 + CloudFront |
| **Processing** | FastAPI:8001 | Lambda functions |
| **Data Storage** | Local `dashboard_data/` | S3 bucket |
| **APIs** | Local REST endpoints | API Gateway + Lambda |
| **Queue** | In-memory | SQS |

## Data Flow

### Local Development

```
1. User uploads CSV via frontend (localhost:8000)
                    │
                    v
2. FastAPI receives file (localhost:8001/upload)
                    │
                    v
3. AnalyticsCSVProcessor parses CSV
                    │
                    v
4. Books converted to BookInfo objects
                    │
                    v
5. EnvironmentAwareBookPipeline enriches books
   ├── Goodreads scraping (primary)
   └── Google Books + Open Library APIs (fallback)
                    │
                    v
6. Results merged back to BookAnalytics
                    │
                    v
7. Dashboard JSON created in dashboard_data/
                    │
                    v
8. Frontend polls status, then loads JSON
```

### Cloud Production

```
1. User uploads CSV via frontend (goodreads-stats.codebycarson.com)
                    │
                    v
2. API Gateway triggers UploadHandler Lambda
                    │
                    v
3. CSV saved to S3, Orchestrator Lambda invoked
                    │
                    v
4. Orchestrator parses CSV, sends books to SQS
                    │
                    v
5. BookProcessor Lambda enriches each book (parallel)
   ├── Goodreads scraping (primary)
   └── Google Books + Open Library APIs (fallback)
                    │
                    v
6. Enriched results stored in S3
                    │
                    v
7. Aggregator Lambda combines results
                    │
                    v
8. Dashboard JSON saved to S3 (data/{uuid}.json)
                    │
                    v
9. Frontend polls StatusChecker, then loads JSON
```

## Core Components

### Pipeline Components (Shared)

Located in `genres/` directory, used by both local and cloud modes:

#### CSV Processing (`genres/pipeline/csv_loader.py`)
- **Class:** `AnalyticsCSVProcessor`
- **Input:** Goodreads CSV export
- **Processing:**
  - Parses all CSV fields using pandas
  - Handles re-reads (uses latest read date)
  - Data cleaning and validation
  - Creates `BookAnalytics` objects
- **Output:** List of analytics-ready book objects

#### Genre Enrichment (`genres/pipeline/enricher.py`)
- **Classes:**
  - `AsyncGenreEnricher` - Core async enricher with rate limiting and concurrency control
  - `AdaptiveGenreEnricher` - Environment-adaptive wrapper (local async vs Lambda swarm)
  - `EnvironmentAwareBookPipeline` - Top-level interface used by `local_server.py` and Lambda
- **Genre Source Strategy:**
  - **Goodreads scraping:** Primary source — best quality, community-curated genres
  - **Google Books + Open Library APIs:** Parallel fallback when scraping fails
- **Features:**
  - Default 10 concurrent tasks (local server uses 15)
  - Rate limiting with configurable delay (default 0.1s, local uses 0.05s)
  - Exponential backoff for failures

#### Dashboard Export (`genres/pipeline/exporter.py`)
- **Function:** `create_dashboard_json()`
- **Input:** List of `BookAnalytics` objects
- **Output:** JSON file with enrichment statistics and book data

### Local Server (`local_server.py`)

FastAPI application providing REST endpoints for local development:

```python
app = FastAPI(
    title="Goodreads Stats Local API",
    version="1.0.0"
)

# Endpoints
POST /upload          # Upload CSV, start processing
GET  /status/{uuid}   # Check processing status
GET  /data/{uuid}     # Retrieve dashboard JSON
DELETE /data/{uuid}   # Delete user data
GET  /health          # Health check
```

### AWS Lambda Functions

Located in `cdk/lambda_code/`:

| Function | Trigger | Purpose |
|----------|---------|---------|
| `upload_handler` | API Gateway POST | Receives CSV, saves to S3, triggers orchestrator |
| `orchestrator` | Lambda invoke | Parses CSV, sends books to SQS |
| `book_processor` | SQS | Enriches single book via external APIs |
| `aggregator` | CloudWatch Events | Combines results, generates dashboard JSON |
| `status_checker` | API Gateway GET | Returns processing status |

## Frontend Architecture

### File Structure

```
dashboard/
├── index.html          # Homepage and CSV upload
├── dashboard.html      # Main analytics dashboard
├── books.html          # Filtered book listings
├── detail.html         # Individual book details
├── genres.html         # Genre overview page
├── genre.html          # Single genre drill-down
├── dashboard.js        # Logic for main dashboard
├── books.js            # Logic for book listings
├── detail.js           # Logic for book details
├── genres.js           # Logic for genre pages
├── upload.js           # Upload and status polling
├── utils.js            # Shared utility functions
├── config.js.template  # Environment detection template
└── dashboard.css       # Shared styles
```

### URL Structure

- `/` - Homepage (CSV upload)
- `/dashboard?uuid={id}` - Main analytics dashboard
- `/books?uuid={id}&type={filter}&value={value}` - Filtered book listings
- `/detail?uuid={id}&id={book_id}` - Individual book details
- `/genres?uuid={id}` - Genre overview
- `/genre?uuid={id}&genre={genre}` - Single genre drill-down

### Environment Detection

The frontend automatically detects the environment:

```javascript
function detectEnvironment() {
    const host = window.location.host;

    if (host === 'localhost:8000' || host === '127.0.0.1:8000') {
        return {
            mode: 'local-docker',
            apiBase: 'http://localhost:8001'
        };
    } else {
        return {
            mode: 'production',
            apiBase: 'https://goodreads-stats.codebycarson.com/api'
        };
    }
}
```

## AWS Infrastructure

### Services Used

- **API Gateway:** REST endpoints for file uploads, status checks, data retrieval
- **Lambda:** Serverless compute for processing
- **S3:** Storage for CSVs, status files, and dashboard JSONs
- **SQS:** Queue for distributing book processing
- **CloudFront:** CDN for frontend and API caching
- **Route 53:** DNS management
- **Certificate Manager:** SSL/TLS certificates

### S3 Bucket Structure

```
goodreads-stats-data-{env}/
├── uploads/{uuid}/
│   ├── raw.csv              # Original upload
│   └── metadata.json        # Upload metadata
├── status/{uuid}.json       # Processing status
├── processing/{uuid}/
│   ├── original_books.json  # Parsed books (temporary)
│   └── enriched/            # Individual results (temporary)
└── data/{uuid}.json         # Final dashboard JSON
```

## Performance Characteristics

### Backend Performance
- **Async Processing:** Default 10 concurrent tasks (local server uses 15)
- **Rate Limiting:** Configurable delays between requests
- **Retry Logic:** Exponential backoff for failed API calls
- **Batch Processing:** Groups books for optimal throughput

### Actual Performance (564-book library)
- Processing time: 0.39 seconds per book
- Total time: 3.6 minutes
- Success rate: 88.7% enriched

### AWS Lambda Scaling
- Auto-scaling based on demand
- Parallel execution via SQS
- Cost: ~$0.003 per 1000-book library

## Security Model

### Data Privacy
- **No user accounts:** Anonymous processing
- **UUID-based access:** Only users with UUID can access their data
- **User-controlled deletion:** Full data removal available

### API Security
- **CORS:** Restricted to known domains
- **Rate limiting:** Prevents abuse
- **No API keys required:** Public endpoints with usage limits
- **File validation:** CSV format and size limits (50MB max)

## Deployment

### Infrastructure as Code

The entire AWS infrastructure is defined using AWS CDK in the `cdk/` directory.

### CI/CD Pipeline

GitHub Actions workflow:
1. Push to `main` branch triggers deployment
2. CDK deploys/updates AWS resources
3. Frontend synced to S3 website bucket
4. CloudFront cache invalidated

### Deployment Commands

```bash
# Deploy CDK stacks
cd cdk
cdk deploy --all

# Sync frontend to S3
aws s3 sync dashboard/ s3://goodreads-stats-website-prod/

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id XXXX --paths "/*"
```

## Development Workflow

### Adding New Features

#### Backend Changes
1. Modify models in `genres/models/`
2. Update pipeline in `genres/pipeline/`
3. Test with sample data locally
4. Update JSON export format if needed

#### Frontend Changes
1. Update HTML templates in `dashboard/`
2. Modify JavaScript modules
3. Test with existing JSON data
4. Ensure mobile responsiveness

### Testing Strategy
- **Backend:** Unit tests for pipeline components
- **Frontend:** Manual testing with sample datasets
- **Integration:** End-to-end testing with real CSV files
