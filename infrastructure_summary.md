# Goodreads Stats Infrastructure

## Overview
This CDK application deploys a serverless infrastructure for processing Goodreads CSV exports and generating analytics dashboards. The system uses AWS Lambda for processing, S3 for storage, and CloudFront for content delivery.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                Frontend Stack                                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐              │
│  │  CloudFront     │    │  Route53        │    │  ACM Cert       │              │
│  │  Distribution   │◄───┤  A Record       │    │  (SSL/TLS)      │              │
│  │  + Rewrite Fn   │    │                 │    │                 │              │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘              │
│           │                                                                     │
│           ▼                                                                     │
│  ┌─────────────────┐    ┌─────────────────┐                                     │
│  │  S3 Website     │    │  API Gateway    │                                     │
│  │  Bucket         │    │  (via CF)       │                                     │
│  │  (Static Files) │    │                 │                                     │
│  └─────────────────┘    └─────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
           │                          │
           │                          ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                  API Stack                                      │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐              │
│  │  Upload Handler │    │  Status Checker │    │  Orchestrator   │              │
│  │  Lambda         │    │  Lambda         │    │  Lambda         │              │
│  │  (CSV Upload)   │    │  (Status/Data)  │    │  (Job Queue)    │              │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘              │
│           │                          │                   │                      │
│           │                          │                   ▼                      │
│           │                          │          ┌─────────────────┐             │
│           │                          │          │  SQS Queue      │             │
│           │                          │          │  (Book Jobs)    │             │
│           │                          │          │  + DLQ          │             │
│           │                          │          └─────────────────┘             │
│           │                          │                   │                      │
│           │                          │                   ▼                      │
│           │                          │          ┌─────────────────┐             │
│           │                          │          │  Book Processor │             │
│           │                          │          │  Lambda         │             │
│           │                          │          │  (API Calls)    │             │
│           │                          │          └─────────────────┘             │
│           │                          │                   │                      │
│           │                          │                   │                      │
│           │                          │          ┌─────────────────┐             │
│           │                          │          │  Aggregator     │             │
│           │                          │          │  Lambda         │             │
│           │                          │          │  (Combine Data) │             │
│           │                          │          └─────────────────┘             │
│           │                          │                   ▲                      │
│           │                          │                   │                      │
│           │                          │          ┌─────────────────┐             │
│           │                          │          │  CloudWatch     │             │
│           │                          │          │  Events Rule    │             │
│           │                          │          │  (Every 1 min)  │             │
│           │                          │          └─────────────────┘             │
└─────────────────────────────────────────────────────────────────────────────────┘
           │                          │                   │
           ▼                          ▼                   ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                Storage Stack                                    │
├─────────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────┐    ┌─────────────────┐                                     │
│  │  Data Bucket    │    │  Website Bucket │                                     │
│  │  (goodreads-    │    │  (Static Site   │                                     │
│  │   stats)        │    │   Hosting)      │                                     │
│  │                 │    │                 │                                     │
│  │  /uploads/      │    │  /index.html    │                                     │
│  │  /data/         │    │  /dashboard.js  │                                     │
│  │  /status/       │    │  /etc...        │                                     │
│  └─────────────────┘    └─────────────────┘                                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Storage Stack (`storage_stack.py`)
**Purpose**: Manages S3 buckets and storage configuration

**Key Resources**:
- **Data Bucket** (`goodreads-stats`): Stores CSV uploads, processed data, and status files
  - `/uploads/`: Temporary CSV uploads (auto-delete after 7 days)
  - `/data/`: Final JSON analytics files
  - `/status/`: Processing status files
- **Website Bucket**: Hosts static frontend files (HTML, CSS, JS)
- **CloudFront OAI**: Secure access to website bucket (prod only)

**Configuration**:
- Public read access for dashboard data
- CORS settings for cross-origin requests
- Lifecycle policies for cost optimization

### 2. API Stack (`api_stack.py`)
**Purpose**: Serverless processing pipeline for CSV analysis

**Key Resources**:

#### Lambda Functions:
- **Upload Handler**: Receives CSV uploads via API Gateway
- **Orchestrator**: Parses CSV and queues individual book processing jobs
- **Book Processor**: Processes individual books using external APIs (SQS-triggered)
- **Aggregator**: Combines results into final analytics JSON (CloudWatch-triggered)
- **Status Checker**: Provides status updates and serves final data

#### Infrastructure:
- **SQS Queue**: Manages book processing jobs with dead letter queue
- **API Gateway**: REST API with CORS support
- **CloudWatch Events**: Triggers aggregator every minute
- **Lambda Layer**: Shared dependencies for all functions

**API Endpoints**:
- `POST /api/upload`: Upload CSV file
- `GET /api/status/{uuid}`: Check processing status
- `GET /api/data/{uuid}`: Retrieve analytics JSON
- `DELETE /api/data/{uuid}`: Delete user data

### 3. Frontend Stack (`frontend_stack.py`)
**Purpose**: Content delivery and domain management

**Key Resources**:
- **CloudFront Distribution**: CDN with custom domain
- **Route53 A Record**: DNS routing
- **ACM Certificate**: SSL/TLS encryption
- **CloudFront Function**: URL rewriting for SPA routing

**Behaviors**:
- Static assets: Cached and compressed
- API calls: Not cached, proxy to API Gateway
- Default: Serve from S3 with URL rewriting

## Data Flow

1. **Upload**: User uploads CSV via dashboard → API Gateway → Upload Handler
2. **Processing**: Upload Handler → Orchestrator → SQS Queue → Book Processor (parallel)
3. **Aggregation**: CloudWatch Events → Aggregator → Final JSON to S3
4. **Delivery**: CloudFront → User gets analytics dashboard

## Environment Configuration

**Production**:
- Domain: `goodreads-stats.codebycarson.com`
- Buckets: `goodreads-stats`, `goodreads-stats-website-prod`
- Enhanced security with OAI

**Development**:
- Domain: `dev.goodreads-stats.codebycarson.com`
- Buckets: `goodreads-stats-dev`, `goodreads-stats-website-dev`
- Simplified configuration for testing

## Security Features

- **IAM Roles**: Least privilege access for each Lambda function
- **CORS**: Restricted origins for API access
- **SSL/TLS**: Enforced HTTPS via CloudFront
- **OAI**: Secure S3 access (production)
- **Request Validation**: API Gateway input validation

## Monitoring & Logging

- **CloudWatch Logs**: Separate log groups for each Lambda
- **Log Retention**: 1 week (dev), 1 month (prod)
- **Dead Letter Queue**: Failed processing job tracking
- **CloudWatch Events**: Automated aggregation scheduling

## Cost Optimization

- **Lifecycle Policies**: Auto-archive old data to IA storage
- **Auto-deletion**: Remove temporary uploads after 7 days
- **Memory Sizing**: Optimized Lambda memory allocation
- **Price Class**: CloudFront limited to US/Canada/Europe

## Deployment

```bash
# Deploy all stacks
cdk deploy --all

# Deploy specific environment
cdk deploy --context environment=dev

# Deploy specific stack
cdk deploy GoodreadsStats-Prod-Storage
```

## Dependencies

**Stack Dependencies**:
1. Storage Stack (independent)
2. API Stack (depends on Storage)
3. Frontend Stack (depends on API + Storage)

**External Dependencies**:
- Route53 hosted zone for domain
- External APIs for book data enrichment