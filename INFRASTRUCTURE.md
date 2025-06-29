# Goodreads Stats - Infrastructure & Deployment Guide

## Overview

The Goodreads Stats system supports **two execution modes**:
1. **Local Docker Development** - Dockerized FastAPI + frontend for local development
2. **Cloud Production** - AWS serverless architecture

The same frontend code works in both modes with automatic environment detection.

---

## Architecture Comparison

| Component | Local Docker | Cloud Production |
|-----------|--------------|------------------|
| **Frontend** | nginx:8000 | S3 + CloudFront |
| **Processing** | FastAPI:8001 | Lambda functions |
| **Data Storage** | Local `dashboard_data/` | S3 bucket |
| **APIs** | Local REST endpoints | API Gateway + Lambda |
| **Environment Detection** | `localhost:8000` → `localhost:8001` | `goodreads-stats.codebycarson.com` → AWS |

---

## Local Development

### Docker Development Setup

**Use Case:** Local development with full API integration

**Setup:**
```bash
# Start both frontend and API
docker-compose up -d

# Open browser
open http://localhost:8000
```

**How it works:**
- Frontend served by nginx on port 8000
- API served by FastAPI on port 8001
- Upload works like cloud (drag & drop → API processing)
- FastAPI server uses existing Python pipeline locally
- Same endpoints as cloud for development/testing

**Manual Pipeline Option:**
For advanced users who want to run the pipeline manually:
```bash
python run_smart_pipeline.py
```
However, this bypasses the coordinated frontend/upload system.

---

## Cloud Production Architecture

### Infrastructure Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS CLOUD ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                │
│  Frontend (S3 + CloudFront)                                   │
│  ├── goodreads-stats.codebycarson.com                         │
│  ├── Static HTML/CSS/JS files                                 │
│  └── Environment detection → API calls                        │
│                           ↓                                    │
│  API Layer (API Gateway)                                      │
│  ├── POST /upload        → Lambda Upload Handler              │
│  ├── GET  /status/{uuid} → Lambda Status Checker              │
│  └── DELETE /data/{uuid} → Lambda Delete Handler              │
│                           ↓                                    │
│  Processing Layer (Lambda Functions)                          │
│  ├── Upload Handler      → Saves CSV, triggers orchestrator   │
│  ├── Orchestrator       → Runs pipeline, spawns processors    │
│  ├── Book Processors    → Individual book enrichment          │
│  └── Status Checker     → Returns processing status           │
│                           ↓                                    │
│  Storage Layer (S3)                                           │
│  ├── Raw CSV uploads    → goodreads-stats-uploads/            │
│  ├── Processing status  → goodreads-stats-status/             │
│  └── Dashboard JSONs    → goodreads-stats-data/               │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

### AWS Resources

#### S3 Buckets
```
goodreads-stats-uploads/     # Temporary CSV storage
├── {uuid}/
│   ├── raw.csv             # Original upload
│   └── metadata.json       # Processing info

goodreads-stats-status/      # Processing status tracking  
├── {uuid}.json             # Status: processing/complete/error

goodreads-stats-data/        # Final dashboard data
├── {uuid}.json             # Public-readable dashboard JSON
└── thumbnails/             # Cached book covers (optional)
```

#### Lambda Functions
```
goodreads-stats-upload       # Handles file uploads
goodreads-stats-orchestrator # Main processing pipeline  
goodreads-stats-status       # Status checking
goodreads-stats-delete       # Data cleanup (optional)
```

#### API Gateway
```
https://goodreads-stats.codebycarson.com/api/
├── POST   /upload          # File upload endpoint
├── GET    /status/{uuid}   # Check processing status  
├── GET    /data/{uuid}     # Get dashboard JSON (redirects to S3)
└── DELETE /data/{uuid}     # Delete user data (optional)
```

---

## Environment Detection & Frontend Logic

### Automatic Environment Detection
```javascript
// In upload.js and dashboard.js
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

### Upload Flow by Environment

#### Both Local Docker and Cloud Mode
```javascript
// upload.js - Same code for both environments!
const formData = new FormData();
formData.append('csv', file);

const response = await fetch(`${env.apiBase}/upload`, {
    method: 'POST',
    body: formData
});

const { uuid } = await response.json();
pollStatus(uuid);  // Check processing status
```

### Dashboard Loading by Environment

#### Both Local Docker and Cloud Mode
```javascript
// dashboard.js - Same code for both environments!
const response = await fetch(`${env.apiBase}/data/${uuid}`);
return response.json();
```

---

## API Endpoints Specification

### POST /upload
**Request:**
```http
POST /upload
Content-Type: multipart/form-data

file: goodreads_export.csv
```

**Response:**
```json
{
    "uuid": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "message": "Upload successful, processing started"
}
```

### GET /status/{uuid}
**Response:**
```json
{
    "uuid": "550e8400-e29b-41d4-a716-446655440000", 
    "status": "processing|complete|error",
    "progress": {
        "total_books": 1247,
        "processed_books": 856,
        "percent_complete": 68.7
    },
    "data_url": "https://goodreads-stats-data.s3.amazonaws.com/{uuid}.json", // when complete
    "error_message": "API rate limit exceeded", // when error
    "estimated_completion": "2024-01-15T10:30:00Z"
}
```

### GET /data/{uuid}
**Response:**
```json
{
    "export_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_timestamp": "2024-01-15T10:25:33Z",
    "total_books": 1247,
    "enrichment_stats": {
        "google_success_rate": 0.89,
        "openlibrary_success_rate": 0.76
    },
    "books": [...]
}
```

### DELETE /data/{uuid}
**Use Case:** Allow users to delete their processed data from the system

**Response:**
```json
{
    "message": "Data deleted successfully",
    "deleted_files": ["dashboard.json", "status.json", "raw.csv"]
}
```

**Error Responses:**
- `404`: No data found to delete
- `500`: Deletion failed

---

## Development Workflow

### Working on Frontend Features
```bash
# Use simple local mode
python -m http.server 8000
# Test with existing JSON files
```

### Working on API Features
```bash
# Terminal 1: Frontend
python -m http.server 8000

# Terminal 2: Local API
python local_server.py

# Test full upload → processing → dashboard flow
```

### Deploying to Cloud
```bash
# 1. Deploy Lambda functions
sam deploy --guided

# 2. Deploy frontend to S3
aws s3 sync dashboard/ s3://codebycarson.com/goodreads-stats/

# 3. Update CloudFront distribution
aws cloudfront create-invalidation --distribution-id ABCD --paths "/*"
```

---

## File Structure Changes

```
goodreads_stats/
├── ARCHITECTURE.md          # Current system architecture
├── INFRASTRUCTURE.md        # This file - deployment guide
├── local_server.py          # NEW: FastAPI development server
├── lambda/                  # NEW: Cloud functions
│   ├── upload_handler.py    
│   ├── orchestrator.py      
│   ├── status_checker.py    
│   └── requirements.txt     
├── deployment/              # NEW: Infrastructure as Code
│   ├── template.yaml        # SAM template
│   ├── deploy.sh           # Deployment script
│   └── env_vars.json       # Environment configuration
├── dashboard/              # Frontend (unchanged)
│   ├── index.html          
│   ├── upload.js           # MODIFIED: Environment detection
│   ├── dashboard.js        # MODIFIED: Environment detection
│   └── ...
├── genres/                 # Python pipeline (unchanged)
└── run_smart_pipeline.py   # Local processing (unchanged)
```

---

## Cost Estimates (Cloud)

### Actual Performance Data
**Based on real 564-book library processing:**
- **Processing time**: 0.39 seconds per book (vs estimated 15s)
- **Total time**: 3.6 minutes for 564 books 
- **Concurrency**: 15 async threads locally
- **Success rate**: 500/564 books enriched (88.7%)

### Updated Per 1000-Book Library Processing
- **Lambda execution**: ~$0.0023 (0.39s × 1000 books × $0.0000166667 per GB-second × 0.512GB)
- **Lambda requests**: ~$0.0002 (1000 books × $0.0000002 per request)
- **API Gateway calls**: ~$0.000018 (5 requests per user)  
- **S3 storage**: ~$0.0001 (5MB JSON file)
- **S3 requests**: ~$0.00002 (10 PUT/GET operations)
- **Data transfer**: ~$0.0001 (5MB download)
- **Total per user**: ~**$0.0027** (0.27 cents)

### Updated Monthly Estimates
- **100 users/month**: ~$0.27
- **1,000 users/month**: ~$2.70  
- **10,000 users/month**: ~$27.00

### Free Tier Coverage
- **Lambda**: 1M requests + 400k GB-seconds free
- **API Gateway**: 1M requests free  
- **S3**: 5GB storage + 20k GET requests free
- **GB-seconds per 1000-book library**: ~200 (0.39s × 1000 × 0.512GB ÷ 2)
- **Estimated free usage**: ~2,000 libraries/month (limited by GB-seconds)

---

## Data Management Features

### Data Deletion
Users can delete their processed data at any time from the dashboard:

#### **Local Docker Environment**
- **Delete button**: Available on main dashboard page
- **What gets deleted**: 
  - Dashboard JSON file (`dashboard_data/{uuid}.json`)
  - Processing status (in-memory)
  - Any temporary upload files
- **Confirmation**: Required before deletion
- **Redirect**: After deletion, user redirected to upload page

#### **Cloud Production Environment**
- **Delete button**: Same UI as local
- **What gets deleted**:
  - Dashboard JSON (`goodreads-stats-data/{uuid}.json`)
  - Processing status (`goodreads-stats-status/{uuid}.json`)
  - Original CSV upload (`goodreads-stats-uploads/{uuid}/`)
- **Lambda function**: Handles S3 object deletion
- **Confirmation**: Required before deletion

#### **Security Model**
- **UUID-based deletion**: Users can only delete data they have the UUID for
- **No authentication required**: UUID serves as the access token
- **Immediate deletion**: No recovery option once confirmed

---

## Security & Privacy

### Data Handling
- **CSV uploads**: Stored temporarily, deleted after processing or on user request
- **Dashboard JSON**: Stored until user deletion or system cleanup
- **No user accounts**: Anonymous processing only
- **UUID-based access**: Only users with UUID can access or delete their data
- **User-controlled deletion**: Full data removal available at any time

### API Security
- **CORS**: Restricted to goodreads-stats.codebycarson.com and goodreads-stats-dev.codebycarson.com domains
- **Rate limiting**: 10 requests per minute per IP
- **File validation**: CSV format and size limits (50MB max)
- **No API keys required**: Public endpoints with usage limits
- **UUID-based permissions**: Users can only manage data they have UUIDs for

### AWS Permissions
- **Lambda execution role**: Read/write/delete to specific S3 buckets only
- **S3 bucket policy**: Public read for dashboard JSONs, private for uploads
- **API Gateway**: No authentication required for simplicity

---

This infrastructure provides a seamless experience from local development to cloud production with automatic environment detection and the same codebase working everywhere.