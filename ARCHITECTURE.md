# Goodreads Stats - System Architecture

## Overview

The Goodreads Stats system is a **flexible architecture** that supports three execution modes: local simple processing, local API development, and cloud production. The system transforms Goodreads CSV exports into enriched JSON datasets that power interactive dashboards with automatic environment detection.

## High-Level Architecture

The system supports **three execution modes** with environment auto-detection:

```
┌─────────────────────────────────────────────────────────────────┐
│                     GOODREADS STATS SYSTEM                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  EXECUTION MODE 1: Local Simple (Current)                      │
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
│  EXECUTION MODE 2: Local API Development                       │
│  ┌─────────────────┐    ┌──────────────────┐    ┌─────────────┐ │
│  │   CSV Upload    │───▶│   FastAPI Server │───▶│ Static      │ │
│  │   (Frontend)    │    │  (local_server)  │    │ Dashboard   │ │
│  └─────────────────┘    └──────────────────┘    └─────────────┘ │
│           │                       │                       │     │
│           │                       ▼                       │     │
│           │              ┌─────────────────┐              │     │
│           └─────────────▶│ Local JSON Files│◀─────────────┘     │
│                          │ (dashboard_data)│                    │
│                          └─────────────────┘                    │
│                                                                 │
│  EXECUTION MODE 3: Cloud Production                            │
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

## Data Flow

1. **CSV Input** → User uploads Goodreads export CSV
2. **Processing** → Python pipeline enriches data with genres/thumbnails 
3. **JSON Output** → Structured dashboard JSON with UUID filename
4. **Visualization** → Frontend loads JSON and renders interactive dashboard

---

## Backend Architecture (Python Pipeline)

### Main Entry Point: `run_smart_pipeline.py`

**Environment-Aware Execution Strategy:**
- **Local Development**: 15 concurrent async threads (4-6 minutes, free)
- **AWS Lambda**: 1 Lambda function per book (0.39 seconds, ~$0.000002)

### Pipeline Components

#### 1. CSV Processing (`genres/pipeline/csv_loader.py`)
- **Class**: `AnalyticsCSVProcessor`
- **Input**: Goodreads CSV export
- **Processing**: 
  - Parses all CSV fields using pandas
  - Handles re-reads (uses latest read date)
  - Data cleaning and validation
  - Creates `BookAnalytics` objects
- **Output**: List of analytics-ready book objects

#### 2. Genre Enrichment (`genres/pipeline/enricher.py`)

**Multi-Source API Strategy:**
- **Google Books API**: Primary source for mainstream books
- **Open Library API**: Fallback for older/obscure books
- **Parallel Processing**: Both APIs called simultaneously

**Classes:**
- `AsyncGenreEnricher`: High-performance async enricher with rate limiting
- `EnvironmentAwareBookPipeline`: Smart execution (local vs Lambda)
- `AdaptiveGenreEnricher`: Fallback strategies and retry logic

**Concurrency Control:**
- Semaphore-based rate limiting
- Exponential backoff for failed requests
- Circuit breaker patterns for API failures

#### 3. Data Processing Flow

```python
BookInfo → API Calls → EnrichedBook → BookAnalytics → Dashboard JSON
     ↓         ↓            ↓             ↓              ↓
  Basic    Genre Data   Thumbnails   Time Series    Final Export
  Fields     +          + Covers     Analytics      (UUID.json)
           Subjects
```

#### 4. JSON Export (`genres/pipeline/exporter.py`)
- **Class**: `FinalJSONExporter`
- **Output**: UUID-named JSON files in `dashboard_data/`
- **Structure**: Optimized for frontend consumption
- **Metadata**: Export timestamps, processing statistics

### Data Sources Integration

#### Google Books API (`genres/sources/google.py`)
- **Endpoint**: `https://www.googleapis.com/books/v1/volumes`
- **Search Strategy**: ISBN → Title+Author fallback
- **Extracts**: mainCategory, categories[], thumbnail URLs

#### Open Library API (`genres/sources/openlibrary.py`)
- **Endpoints**: 
  - Search: `https://openlibrary.org/search.json`
  - Works: `https://openlibrary.org/works/{id}.json`
  - Books: `https://openlibrary.org/api/books`
- **Extracts**: subjects[], cover URLs

#### Genre Merging (`genres/utils/genre_merger.py`)
- Deduplication and normalization
- Hierarchical genre mapping
- Quality scoring and ranking

---

## Frontend Architecture (Static Dashboard)

### File Structure
```
dashboard/
├── index.html          # Main dashboard (analytics & charts)
├── books.html          # Filtered book listings  
├── detail.html         # Individual book details
├── dashboard.js        # Main dashboard logic
├── books.js           # Book listing logic
├── detail.js          # Book detail logic
└── dashboard.css      # Shared styles
```

### URL Structure
```
/                                    → Homepage (CSV upload) 
/dashboard?uuid={id}                 → Main analytics dashboard
/books?uuid={id}&type={filter}&value={value}  → Filtered book listings
/detail?uuid={id}&id={book_id}&return={url}   → Individual book details
```

### Frontend Components

#### 1. Homepage (`/index.html`)
- **Purpose**: Entry point and CSV upload
- **Features**:
  - Project explanation
  - Drag-and-drop CSV upload
  - Client-side CSV parsing (basic)
  - Instructions for full processing
  - Link to sample dashboard

#### 2. Dashboard (`/dashboard.html`)
- **Class**: `ReadingDashboard` (dashboard.js)
- **Data Loading**: UUID-based JSON fetching
- **Visualizations**: Chart.js for interactive charts
- **Features**:
  - Summary statistics cards
  - Books by year (line chart)
  - Rating distribution (bar chart)  
  - Top genres (pie chart)
  - Pages read timeline
  - Recent books table
  - Dark mode toggle

#### 3. Books Listing (`/books.html`)
- **Class**: `BooksPage` (books.js)
- **Filtering**: Genre, rating, year, pages-per-year
- **Features**:
  - Grid layout with book cards
  - Thumbnail images (when available)
  - Click-through to detail pages
  - Breadcrumb navigation

#### 4. Book Details (`/detail.html`)
- **Class**: `BookDetailPage` (detail.js)
- **Features**:
  - Full book information display
  - Cover image and metadata
  - Genre tags and ratings
  - Navigation back to filtered views

### Data Loading Strategy

#### Local Development
```javascript
// Direct path to UUID JSON files from dashboard folder
const dataUrl = `dashboard_data/${uuid}.json`;
```

#### Production Deployment
```javascript
// S3 or CDN-based loading
const baseUrl = window.S3_BASE_URL || 'https://your-bucket.s3.amazonaws.com';
const dataUrl = `${baseUrl}/${uuid}.json`;
```

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