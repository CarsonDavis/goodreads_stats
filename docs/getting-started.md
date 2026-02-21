# Getting Started

This guide will help you set up your development environment and run Goodreads Stats locally.

## Prerequisites

- **Python 3.11+**
- **Node.js 18+** (for frontend tooling, optional)
- **Docker** (recommended for local development)
- **uv** (Python package manager) - [Installation](https://github.com/astral-sh/uv)

## Quick Start (Docker - Required for Full Functionality)

> **Use Docker Compose for local development.** The dashboard uses clean URLs (`/books`, `/dashboard`) that require nginx routing. Running without Docker will result in broken navigation.

The easiest way to run Goodreads Stats locally is with Docker Compose:

```bash
# Clone the repository
git clone https://github.com/carsondavis/goodreads_stats.git
cd goodreads_stats

# Start both frontend and API
docker-compose up -d

# Open your browser
open http://localhost:8000
```

This starts:
- **Frontend** (nginx) on port 8000
- **API** (FastAPI) on port 8001

You can now upload a Goodreads CSV export and watch it process in real-time.

## Manual Setup (Without Docker)

> **Warning**: The manual setup has limitations. The simple Python HTTP server does NOT handle clean URL routing, so links like `/books?uuid=...` will return 404 errors. **Use Docker Compose for the full experience.**

### 1. Install Python Dependencies

```bash
# Create and activate virtual environment with uv
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -r requirements.txt
```

### 2. Run the API Server

```bash
# Start the FastAPI development server
uv run uvicorn local_server:app --host 0.0.0.0 --port 8001
```

The API will be available at `http://localhost:8001`.

### 3. Serve the Frontend

In a separate terminal:

```bash
# Simple Python HTTP server
cd dashboard
python -m http.server 8000
```

The frontend will be available at `http://localhost:8000`.

**Important**: With this setup, you must use `.html` extensions in URLs:
- `http://localhost:8000/dashboard.html?uuid=...` (NOT `/dashboard?uuid=...`)
- `http://localhost:8000/books.html?uuid=...` (NOT `/books?uuid=...`)

Internal navigation links will break. For proper routing, use Docker Compose.

## Getting Your Goodreads Export

1. Go to [Goodreads Export](https://www.goodreads.com/review/import)
2. Click "Export Library"
3. Download the generated CSV file
4. Upload it to `http://localhost:8000`

## Running the Pipeline Manually

For development or testing, use Docker Compose or the local server directly:

```bash
# Option 1: Docker Compose (recommended)
docker compose up

# Option 2: Run the FastAPI server directly
uv run python local_server.py
```

Then upload your CSV at `http://localhost:8000`. The output will be saved to `dashboard_data/{uuid}.json`.

## Project Structure

```
goodreads_stats/
├── genres/                 # Core Python pipeline
│   ├── __init__.py        # Package exports
│   ├── models/            # Data models
│   │   ├── book.py       # BookInfo, EnrichedBook
│   │   └── analytics.py  # BookAnalytics
│   ├── pipeline/          # Processing components
│   │   ├── csv_loader.py # AnalyticsCSVProcessor
│   │   ├── enricher.py   # AsyncGenreEnricher
│   │   └── exporter.py   # create_dashboard_json
│   ├── sources/           # Genre sources
│   │   ├── goodreads.py  # Goodreads scraping (primary)
│   │   ├── google.py     # Google Books API (fallback)
│   │   └── openlibrary.py # Open Library API (fallback)
│   └── utils/             # Shared utilities
├── dashboard/             # Static frontend
│   ├── index.html        # Upload page
│   ├── dashboard.html    # Main dashboard
│   ├── books.html        # Book listing
│   ├── detail.html       # Book details
│   └── *.js              # JavaScript modules
├── local_server.py        # FastAPI development server
├── docker-compose.yml     # Docker configuration
└── requirements.txt       # Python dependencies
```

## Testing Your Setup

### 1. Check API Health

```bash
curl http://localhost:8001/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "uptime": 3600.5,
  "active_jobs": 0
}
```

### 2. Upload a Test File

```bash
curl -X POST http://localhost:8001/upload \
  -F "csv=@data/goodreads_library_export.csv"
```

Expected response:
```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Upload successful, processing started"
}
```

### 3. Check Processing Status

```bash
curl http://localhost:8001/status/{uuid}
```

### 4. View the Dashboard

Once processing is complete, visit:
```
http://localhost:8000/dashboard?uuid={uuid}
```

## Environment Configuration

The local server uses sensible defaults, but you can configure:

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `PYTHONPATH` | `/app` | Python module path |

For Docker, these are set in `docker-compose.yml`.

## Development Workflow

### Frontend Development

Edit files in `dashboard/` - changes are reflected immediately (refresh browser).

### Backend Development

The FastAPI server has hot-reload enabled. Edit `local_server.py` or files in `genres/` and the server will restart automatically.

### Testing API Changes

Use the FastAPI interactive docs:
```
http://localhost:8001/docs
```

## Common Issues

See [Troubleshooting](troubleshooting.md) for solutions to common problems.

## Next Steps

- [Architecture](architecture.md) - Understand the system design
- [Data Models](data-models.md) - Learn about BookInfo, EnrichedBook, BookAnalytics
- [API Reference](api-reference.md) - Full API documentation
