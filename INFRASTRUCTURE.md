# Goodreads Stats - Infrastructure & Deployment Guide

## Overview

The Goodreads Stats system supports **three execution modes**:
1. **Local Simple Mode** - Static files + manual pipeline (current system)
2. **Local API Mode** - FastAPI server for cloud API development 
3. **Cloud Production** - AWS serverless architecture

The same frontend code works in all three modes with automatic environment detection.

---

## Architecture Comparison

| Component | Local Simple | Local API | Cloud Production |
|-----------|--------------|-----------|------------------|
| **Frontend** | Static files (port 8000) | Static files (port 8000) | S3 + CloudFront |
| **Processing** | Manual `python run_smart_pipeline.py` | FastAPI server (port 8001) | Lambda functions |
| **Data Storage** | Local `dashboard_data/` | Local `dashboard_data/` | S3 bucket |
| **APIs** | None | Local REST endpoints | API Gateway + Lambda |
| **Environment Detection** | `localhost` (no API) | `localhost:8000` → `localhost:8001` | `codebycarson.com` → AWS |

---

## Local Development

### Mode 1: Simple Local (Current System)

**Use Case:** End users who want to process CSV locally

**Setup:**
```bash
# 1. Process your CSV
python run_smart_pipeline.py

# 2. Serve dashboard  
python -m http.server 8000

# 3. Open browser
open http://localhost:8000
```

**How it works:**
- Upload page shows instructions (no actual processing)
- User manually runs Python pipeline
- Dashboard loads JSON from `dashboard_data/` folder
- No API calls, purely static

### Mode 2: Local API Development

**Use Case:** Developers working on cloud features

**Setup:**
```bash
# Terminal 1: Frontend
python -m http.server 8000

# Terminal 2: API Server  
python local_server.py  # Runs on port 8001

# Open browser
open http://localhost:8000
```

**How it works:**
- Frontend detects `localhost:8000` → makes API calls to `localhost:8001`
- Upload works like cloud (drag & drop → API processing)
- FastAPI server uses existing Python pipeline locally
- Same endpoints as cloud for development/testing

---

## Cloud Production Architecture

### Infrastructure Components

```
┌─────────────────────────────────────────────────────────────────┐
│                        AWS CLOUD ARCHITECTURE                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                │
│  Frontend (S3 + CloudFront)                                   │
│  ├── codebycarson.com/goodreads-stats/                        │
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
https://api.codebycarson.com/goodreads-stats/
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
    
    if (host === 'localhost:8000') {
        return {
            mode: 'local-api',
            apiBase: 'http://localhost:8001',
            dataPath: null  // Uses API
        };
    } else if (host.startsWith('localhost') || host.startsWith('127.0.0.1')) {
        return {
            mode: 'local-simple', 
            apiBase: null,  // No API
            dataPath: '../dashboard_data/'  // Local files
        };
    } else {
        return {
            mode: 'cloud',
            apiBase: 'https://api.codebycarson.com/goodreads-stats',
            dataPath: null  // Uses API
        };
    }
}
```

### Upload Flow by Environment

#### Local Simple Mode
```javascript
// upload.js
if (env.mode === 'local-simple') {
    // Show instructions instead of processing
    showInstructions(`
        1. Save your CSV to data/ folder
        2. Run: python run_smart_pipeline.py  
        3. Open dashboard with generated UUID
    `);
}
```

#### Local API / Cloud Mode
```javascript
// upload.js - Same code for both!
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

#### Local Simple Mode
```javascript
// dashboard.js
if (env.mode === 'local-simple') {
    // Try multiple local paths
    const paths = [
        `${env.dataPath}${uuid}.json`,
        `./dashboard_data/${uuid}.json`,
        `../dashboard_data/${uuid}.json`
    ];
    
    for (const path of paths) {
        try {
            const response = await fetch(path);
            if (response.ok) return response.json();
        } catch (e) { continue; }
    }
}
```

#### Local API / Cloud Mode  
```javascript
// dashboard.js - Same code for both!
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

### DELETE /data/{uuid} (Optional)
**Response:**
```json
{
    "message": "Data deleted successfully",
    "deleted_files": ["dashboard.json", "status.json", "raw.csv"]
}
```

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

## Security & Privacy

### Data Handling
- **CSV uploads**: Stored temporarily in S3, deleted after processing
- **Dashboard JSON**: Stored permanently in S3 (user can delete)
- **No user accounts**: Anonymous processing only
- **UUID-based access**: Only users with UUID can access their data

### API Security
- **CORS**: Restricted to codebycarson.com domain
- **Rate limiting**: 10 requests per minute per IP
- **File validation**: CSV format and size limits (50MB max)
- **No API keys required**: Public endpoints with usage limits

### AWS Permissions
- **Lambda execution role**: Read/write to specific S3 buckets only
- **S3 bucket policy**: Public read for dashboard JSONs, private for uploads
- **API Gateway**: No authentication required for simplicity

---

This infrastructure provides a seamless experience from local development to cloud production with automatic environment detection and the same codebase working everywhere.