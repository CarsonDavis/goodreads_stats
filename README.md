# Goodreads Stats

Transform your Goodreads library export into an interactive dashboard with rich analytics, genre insights, and reading visualizations.

![Dashboard Preview](dashboard/graphbooks.png)

## Features

- **Reading Analytics** - Track books read over time, by month and year
- **Genre Enrichment** - Automatic genre classification via Google Books and Open Library APIs
- **Rating Analysis** - Compare your ratings to community averages
- **Book Details** - Cover images, descriptions, and your personal notes
- **Smart Filtering** - Filter by genre, rating, year, or any combination

## Quick Start

### Using Docker (Recommended)

```bash
# Clone and start
git clone https://github.com/carsondavis/goodreads_stats.git
cd goodreads_stats
docker-compose up -d

# Open http://localhost:8000 and upload your Goodreads CSV export
```

### Manual Setup

```bash
# Install dependencies with uv
uv venv && source .venv/bin/activate
uv pip install -r requirements.txt

# Start API server
uv run python local_server.py

# In another terminal, serve frontend
cd dashboard && python -m http.server 8000
```

## Getting Your Goodreads Export

1. Go to [Goodreads Export](https://www.goodreads.com/review/import)
2. Click "Export Library"
3. Upload the CSV to the app

## Project Structure

```
goodreads_stats/
├── genres/                 # Core Python pipeline
│   ├── models/            # Data models (BookInfo, EnrichedBook, BookAnalytics)
│   ├── pipeline/          # CSV loading, enrichment, export
│   ├── sources/           # API clients (Google Books, Open Library)
│   └── utils/             # Shared utilities
├── dashboard/             # Static frontend (HTML/JS/CSS)
├── cdk/                   # AWS CDK infrastructure
│   └── lambda_code/       # Lambda function handlers
├── local_server.py        # FastAPI development server
├── docker-compose.yml     # Local development setup
└── docs/                  # Documentation
```

## Documentation

| Document | Description |
|----------|-------------|
| [Getting Started](docs/getting-started.md) | Set up your development environment |
| [Architecture](docs/architecture.md) | System overview and data flow |
| [Data Models](docs/data-models.md) | BookInfo, EnrichedBook, BookAnalytics |
| [API Reference](docs/api-reference.md) | REST endpoint documentation |
| [Lambda Functions](docs/lambda-functions.md) | AWS Lambda handler details |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |

## How It Works

```
Goodreads CSV Export
        |
        v
  [Upload to System]
        |
        v
  [Genre Enrichment]  <-- Google Books API
        |             <-- Open Library API
        v
  [Dashboard JSON]
        |
        v
  [Interactive Dashboard]
```

## Two Execution Modes

| Mode | Frontend | Processing | Storage |
|------|----------|------------|---------|
| **Local** | nginx:8000 | FastAPI:8001 | `dashboard_data/` |
| **Cloud** | S3 + CloudFront | AWS Lambda | S3 |

## Live Demo

View a sample dashboard: [Sample Dashboard](https://goodreads-stats.codebycarson.com/dashboard?uuid=759f8950-6946-4101-9c16-2aafc54d672d)

## Development

### API Server with Hot Reload

```bash
uv run python local_server.py
# API docs: http://localhost:8001/docs
```

## License

MIT
