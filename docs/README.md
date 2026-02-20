# Goodreads Stats Documentation

Welcome to the Goodreads Stats documentation. This guide will help you understand, run, and contribute to the project.

## Quick Links

| Document | Description |
|----------|-------------|
| [Getting Started](getting-started.md) | Set up your development environment |
| [Architecture](architecture.md) | System overview and data flow |
| [Data Models](data-models.md) | BookInfo, EnrichedBook, BookAnalytics |
| [API Reference](api-reference.md) | REST endpoint documentation |
| [Lambda Functions](lambda-functions.md) | AWS Lambda handler details |
| [Genre Enrichment](genre-enrichment.md) | Genre pipeline and source strategy |
| [Logging Strategy](logging-strategy.md) | Structured logging and CloudWatch queries |
| [Troubleshooting](troubleshooting.md) | Common issues and solutions |

## What is Goodreads Stats?

Goodreads Stats transforms your Goodreads library export into an interactive dashboard with:

- **Reading analytics** - Trends over time, books per year/month
- **Genre insights** - Enriched genre data from Goodreads scraping (primary) with Google Books and Open Library API fallback
- **Rating analysis** - Your ratings vs community averages
- **Book details** - Cover images, page counts, publication info

## How It Works

```
Goodreads CSV Export
        |
        v
  [Upload to System]
        |
        v
  [Genre Enrichment]  <-- Goodreads Scraping (primary)
        |             <-- Google Books + Open Library APIs (fallback)
        v
  [Dashboard JSON]
        |
        v
  [Interactive Dashboard]
```

## Project Structure

```
goodreads_stats/
├── genres/                 # Core Python pipeline
│   ├── models/            # Data models (BookInfo, EnrichedBook, BookAnalytics)
│   ├── pipeline/          # CSV loading, enrichment, export
│   ├── sources/           # Genre sources (Goodreads, Google Books, Open Library)
│   └── utils/             # Shared utilities
├── dashboard/             # Static frontend (HTML/JS/CSS)
├── cdk/                   # AWS CDK infrastructure
│   └── lambda_code/       # Lambda function handlers
├── local_server.py        # FastAPI development server
└── docs/                  # Documentation (you are here)
```

## Two Execution Modes

### Local Development
- Docker Compose runs FastAPI backend + nginx frontend
- Processing happens locally using Python pipeline
- Data stored in `dashboard_data/` directory

### Cloud Production (AWS)
- Serverless architecture with Lambda functions
- Processing distributed via SQS queues
- Data stored in S3 buckets
- Frontend served via CloudFront CDN

## Next Steps

1. **New to the project?** Start with [Getting Started](getting-started.md)
2. **Understanding the system?** Read [Architecture](architecture.md)
3. **Working with data?** Check [Data Models](data-models.md)
4. **Building integrations?** See [API Reference](api-reference.md)

## Component Documentation

Additional documentation exists within specific components:

- [`genres/README.md`](../genres/README.md) - Genre enrichment pipeline details
- [`dashboard/README.md`](../dashboard/README.md) - Frontend implementation guide
