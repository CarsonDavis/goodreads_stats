# Goodreads Stats - System Architecture

## Overview

The Goodreads Stats system is a cloud-native application that transforms Goodreads CSV exports into enriched JSON datasets, powering interactive dashboards. It is built on a serverless architecture using AWS services, deployed via AWS CDK and GitHub Actions. The system also supports local development and testing.

## High-Level Architecture

The system operates in two primary modes: local development and cloud production.

```
┌─────────────────────────────────────────────────────────────────┐
│                     GOODREADS STATS SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EXECUTION MODE 1: Local Development                            │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐ │
│  │   CSV Upload    │───▶│  Manual Pipeline │───▶│ Static      │ │
│  │   (Frontend)    │    │  (run_smart_*)   │    │ Dashboard   │ │
│  └─────────────────┘    └──────────────────┘    └─────────────┘ │
│           │                       │                       │     │
│           │                       ▼                       │     │
│           │              ┌─────────────────┐              │     │
│           └─────────────▶│ Local JSON Files│◀─────────────┘     │
│                          │ (dashboard_data)│                    │
│                          └─────────────────┘                    │
│                                                                 │
│  EXECUTION MODE 2: Cloud Production (AWS)                       │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐ │
│  │   CSV Upload    │───▶│  Lambda Pipeline │───▶│ Static      │ │
│  │   (Frontend)    │    │  (AWS Serverless)│    │ Dashboard   │ │
│  └─────────────────┘    └──────────────────┘    └─────────────┘ │
│           │                       │                       │     │
│           │                       ▼                       │     │
│           │              ┌─────────────────┐              │     │
│           └─────────────▶│   S3 JSON Files │◀─────────────┘     │
│                          │  (Cloud Storage)│                    │
│                          └─────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow (Production)

1.  **Upload:** The user uploads a Goodreads CSV file via the frontend, which sends it to an API Gateway endpoint.
2.  **Trigger:** API Gateway triggers the `UploadHandler` Lambda function.
3.  **Orchestration:** The `UploadHandler` invokes the `Orchestrator` Lambda function asynchronously to begin processing.
4.  **Enrichment:** The `Orchestrator` function processes the CSV, calling the Google Books and Open Library APIs to enrich the data.
5.  **Storage:** The enriched data is saved as a JSON file in an S3 bucket.
6.  **Status Check:** The frontend polls a `StatusChecker` Lambda function to monitor the processing status.
7.  **Visualization:** Once processing is complete, the frontend retrieves the JSON from S3 and renders the dashboard.

---

## Backend Architecture (AWS Serverless)

### AWS Services

*   **API Gateway:** Provides RESTful endpoints for file uploads, status checks, and data retrieval.
*   **AWS Lambda:**
    *   `UploadHandler`: Receives the uploaded file and triggers the processing pipeline.
    *   `Orchestrator`: The core processing engine that enriches the Goodreads data.
    *   `StatusChecker`: Provides the status of the enrichment process to the frontend.
*   **S3:**
    *   **Data Bucket:** Stores uploaded CSVs, processed JSON data, and status files.
    *   **Website Bucket:** Hosts the static frontend assets (HTML, CSS, JS).
*   **CloudFront:** Acts as a CDN for the static frontend and a reverse proxy for the API Gateway.
*   **Route 53:** Manages the DNS for the application's custom domain.
*   **Certificate Manager:** Provides SSL/TLS certificates for the custom domain.

### Pipeline Components

The core data processing logic is shared between local and cloud environments, located in the `genres/` directory.

#### 1. CSV Processing (`genres/pipeline/csv_loader.py`)

*   **Class**: `AnalyticsCSVProcessor`
*   **Input**: Goodreads CSV export
*   **Processing**:
    *   Parses all CSV fields using pandas.
    *   Handles re-reads (uses latest read date).
    *   Data cleaning and validation.
    *   Creates `BookAnalytics` objects.
*   **Output**: List of analytics-ready book objects.

#### 2. Genre Enrichment (`genres/pipeline/enricher.py`)

*   **Multi-Source API Strategy:**
    *   **Google Books API**: Primary source for mainstream books.
    *   **Open Library API**: Fallback for older/obscure books.
*   **Classes:**
    *   `AsyncGenreEnricher`: High-performance async enricher with rate limiting.
    *   `AdaptiveGenreEnricher`: Fallback strategies and retry logic.

---

## Frontend Architecture (Static Dashboard)

### File Structure

```
dashboard/
├── index.html          # Homepage and CSV upload
├── dashboard.html      # Main analytics dashboard
├── books.html          # Filtered book listings
├── detail.html         # Individual book details
├── dashboard.js        # Logic for the main dashboard
├── books.js            # Logic for book listings
├── detail.js           # Logic for book details
└── dashboard.css       # Shared styles
```

### URL Structure

*   `/`: Homepage (CSV upload)
*   `/dashboard?uuid={id}`: Main analytics dashboard
*   `/books?uuid={id}&type={filter}&value={value}`: Filtered book listings
*   `/detail?uuid={id}&id={book_id}&return={url}`: Individual book details

### CloudFront URL Handling

The CloudFront distribution is configured to handle requests for pages that don't map directly to an S3 object. For example, a request to `/dashboard` (which doesn't exist as an object) results in an S3 404 error. CloudFront catches this error and serves `/index.html` as the response. This is the root cause of the navigation issue. A proper fix involves using a CloudFront Function or Lambda@Edge to rewrite the URI (e.g., `/dashboard` to `/dashboard.html`) before the request hits the S3 origin.

---

## Data Models

### BookAnalytics (Python)

```python
@dataclass
class BookAnalytics:
    # Core identification
    goodreads_id: str
    title: str
    author: str

    # Analytics fields
    my_rating: Optional[int]
    date_read: Optional[date]
    reading_year: Optional[int]
    num_pages: Optional[int]

    # Enriched data
    final_genres: List[str] = field(default_factory=list)
    thumbnail_url: Optional[str] = None
    small_thumbnail_url: Optional[str] = None
```

### Dashboard JSON Structure

```json
{
  "export_id": "uuid-v4",
  "export_timestamp": "ISO-8601",
  "total_books": 1234,
  "enrichment_stats": {
    "google_success_rate": 0.85,
    "openlibrary_success_rate": 0.73,
    "final_enrichment_rate": 0.91
  },
  "books": [
    {
      "goodreads_id": "12345",
      "title": "Book Title",
      "author": "Author Name",
      "my_rating": 4,
      "date_read": "2023-12-01",
      "reading_year": 2023,
      "num_pages": 320,
      "genres": ["Fiction", "Fantasy"],
      "thumbnail_url": "https://...",
      "small_thumbnail_url": "https://..."
    }
  ]
}
```

---

## Deployment

The application is deployed using a CI/CD pipeline powered by **GitHub Actions** and **AWS CDK**.

*   **Infrastructure as Code:** The entire AWS infrastructure is defined in Python using the AWS CDK in the `cdk/` directory.
*   **Continuous Deployment:** Pushing to the `main` branch triggers a GitHub Actions workflow that deploys the CDK stacks and the frontend to the production environment.
*   **Environments:** The `main` branch deploys to production, while other branches can be deployed to a development environment.

### Deployment Steps

1.  **Push to GitHub:** A push to a configured branch triggers the `deploy.yml` workflow.
2.  **Deploy CDK Stacks:** The workflow installs dependencies, and runs `cdk deploy` to provision or update the AWS resources (S3, Lambda, API Gateway, etc.).
3.  **Deploy Frontend:** The workflow syncs the contents of the `dashboard/` directory to the S3 website bucket.
4.  **Invalidate CloudFront:** The workflow invalidates the CloudFront cache to ensure users get the latest version of the frontend.
  "export_id": "uuid-v4",
  "export_timestamp": "ISO-8601",
  "total_books": 1234,
  "enrichment_stats": {
    "google_success_rate": 0.85,
    "openlibrary_success_rate": 0.73,
    "final_enrichment_rate": 0.91
  },
  "books": [
    {
      "goodreads_id": "12345",
      "title": "Book Title",
      "author": "Author Name",
      "my_rating": 4,
      "date_read": "2023-12-01",
      "reading_year": 2023,
      "num_pages": 320,
      "genres": ["Fiction", "Fantasy"],
      "thumbnail_url": "https://...",
      "small_thumbnail_url": "https://..."
    }
  ]
}
```

---

## Performance & Scalability

### Backend Performance
- **Async Processing**: Up to 15 concurrent API calls
- **Rate Limiting**: Configurable delays between requests
- **Retry Logic**: Exponential backoff for failed API calls
- **Batch Processing**: Groups books for optimal throughput

### Frontend Performance
- **Static Files**: No server-side rendering needed
- **Lazy Loading**: Charts rendered only when data is available
- **Caching**: Browser caches JSON data and dark mode preferences
- **Responsive**: Mobile-friendly design with Tailwind CSS

### AWS Lambda Scaling
- **Serverless**: Auto-scaling based on demand
- **Parallel Execution**: One Lambda per book for maximum speed
- **Cost-Effective**: Pay-per-request pricing (~$2.70 per 1000-book library)

---

## Deployment Strategies

### Local Development
1. Clone repository
2. Place CSV in `data/` folder
3. Run `python run_smart_pipeline.py`
4. Serve dashboard with `python -m http.server`
5. Access via `http://localhost:8000/dashboard?uuid={generated-uuid}`

### Production Deployment

#### Option 1: Static Hosting + S3
- Frontend: Netlify/Vercel/GitHub Pages
- Data Storage: S3 bucket for JSON files
- Processing: Local or CI/CD pipeline

#### Option 2: Full AWS
- Frontend: S3 + CloudFront
- Processing: Lambda functions
- Data: S3 bucket
- API: API Gateway for upload triggers

#### Option 3: Self-Hosted
- Frontend: Nginx/Apache static files
- Processing: Docker containers
- Data: Local filesystem or object storage

---

## Security Considerations

### Data Privacy
- **Client-Side Processing**: Basic CSV parsing happens in browser
- **No Data Persistence**: Upload page doesn't store user data
- **Local Processing**: Full enrichment runs locally by default

### API Security
- **Rate Limiting**: Prevents API abuse
- **No API Keys**: Uses public endpoints only
- **Error Handling**: Graceful degradation on API failures

### Frontend Security
- **Static Files**: No server-side vulnerabilities
- **HTTPS**: Recommended for production deployment
- **Content Security Policy**: Can be implemented for XSS protection

---

## Development Workflow

### Adding New Features

#### Backend Changes
1. Modify models in `genres/models/`
2. Update pipeline in `genres/pipeline/`
3. Test with sample data
4. Update JSON export format if needed

#### Frontend Changes
1. Update HTML templates
2. Modify JavaScript classes
3. Test with existing JSON data
4. Ensure mobile responsiveness

### Testing Strategy
- **Backend**: Unit tests for each pipeline component
- **Frontend**: Manual testing with sample datasets
- **Integration**: End-to-end testing with real CSV files
- **Performance**: Load testing with large libraries

---

## Future Architecture Considerations

### Potential Enhancements
1. **Real-time Processing**: WebSocket-based progress updates
2. **Multiple File Formats**: Support for other export formats
3. **User Accounts**: Personal dashboards with data persistence
4. **Collaborative Features**: Shared reading lists and recommendations
5. **Advanced Analytics**: Machine learning-based insights

### Scaling Considerations
1. **Database Migration**: Move from JSON files to proper database
2. **API Gateway**: Centralized API management
3. **Microservices**: Split enrichment sources into separate services
4. **CDN Integration**: Global content delivery for better performance