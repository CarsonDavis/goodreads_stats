# API Reference

This document describes the REST API endpoints for Goodreads Stats. The same endpoints are available in both local development and cloud production modes.

## Base URLs

| Environment | Base URL |
|-------------|----------|
| Local Development | `http://localhost:8001` |
| Cloud Production | `https://goodreads-stats.codebycarson.com/api` |

## Authentication

No authentication is required. Access is controlled via UUID - only users who have the processing UUID can access their data.

---

## Endpoints

### Upload CSV

Upload a Goodreads CSV export file and start processing.

```
POST /upload
```

#### Request

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `csv` | file | Yes | Goodreads CSV export file |

#### Example Request

```bash
curl -X POST http://localhost:8001/upload \
  -F "csv=@goodreads_library_export.csv"
```

#### Response

**Status:** `200 OK`

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "message": "Upload successful, processing started"
}
```

#### Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `400` | `{"detail": "File must be a CSV"}` | Wrong file type |
| `400` | `{"detail": "Invalid CSV format or not a Goodreads export"}` | Missing required columns |
| `400` | `{"detail": "File too large. Maximum size: 50MB"}` | File exceeds size limit |
| `500` | `{"detail": "Failed to save uploaded file"}` | Server error |

#### Validation

The CSV must contain these Goodreads export headers:
- `Title`
- `Author`
- `My Rating`
- `Date Read`

---

### Check Processing Status

Get the current processing status for a given UUID.

```
GET /status/{uuid}
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `uuid` | string | The UUID returned from the upload endpoint |

#### Example Request

```bash
curl http://localhost:8001/status/550e8400-e29b-41d4-a716-446655440000
```

#### Response (Processing)

**Status:** `200 OK`

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "upload_time": "2024-01-15T10:25:00.000Z",
  "filename": "goodreads_library_export.csv",
  "file_size": 1234567,
  "progress": {
    "total_books": 1247,
    "processed_books": 856,
    "percent_complete": 68.7
  },
  "message": "Starting genre enrichment",
  "estimated_completion": 1705315800.5
}
```

#### Response (Complete)

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "complete",
  "upload_time": "2024-01-15T10:25:00.000Z",
  "filename": "goodreads_library_export.csv",
  "file_size": 1234567,
  "progress": {
    "total_books": 1247,
    "processed_books": 1247,
    "percent_complete": 100
  },
  "message": "Processing complete",
  "data_url": "/data/550e8400-e29b-41d4-a716-446655440000",
  "completion_time": "2024-01-15T10:32:15.000Z"
}
```

#### Response (Error)

```json
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "error",
  "upload_time": "2024-01-15T10:25:00.000Z",
  "error_message": "API rate limit exceeded",
  "completion_time": "2024-01-15T10:28:00.000Z"
}
```

#### Status Values

| Status | Description |
|--------|-------------|
| `processing` | CSV is being processed |
| `complete` | Processing finished successfully |
| `error` | Processing failed |

#### Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `404` | `{"detail": "UUID not found"}` | No processing job with this UUID |

---

### Get Dashboard Data

Retrieve the dashboard JSON data for a completed processing job.

```
GET /data/{uuid}
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `uuid` | string | The UUID returned from the upload endpoint |

#### Example Request

```bash
curl http://localhost:8001/data/550e8400-e29b-41d4-a716-446655440000
```

#### Response

**Status:** `200 OK`

```json
{
  "export_id": "550e8400-e29b-41d4-a716-446655440000",
  "books": [
    {
      "goodreads_id": "12345",
      "title": "The Hobbit",
      "author": "J.R.R. Tolkien",
      "isbn": "0547928227",
      "isbn13": "9780547928227",
      "date_read": "2023-12-01",
      "reading_year": 2023,
      "reading_month_year": "2023-12",
      "my_rating": 5,
      "average_rating": 4.28,
      "is_rated": true,
      "num_pages": 310,
      "publisher": "Mariner Books",
      "binding": "Paperback",
      "publication_year": 1937,
      "page_category": "Medium (200-350)",
      "reading_status": "read",
      "bookshelves": ["fantasy", "favorites"],
      "genres": ["Fantasy", "Fiction", "Classics"],
      "thumbnail_url": "https://books.google.com/...",
      "small_thumbnail_url": "https://books.google.com/...",
      "my_review": "A wonderful adventure...",
      "private_notes": null,
      "has_spoilers": false,
      "has_review": true,
      "genre_enriched": true,
      "was_reread": false,
      "original_read_count": 1
    }
  ],
  "summary": {
    "total_books": 1247,
    "read_books": 564,
    "rated_books": 520,
    "genre_enriched_books": 500,
    "genre_enrichment_rate": 88.7,
    "unique_authors": 380,
    "unique_genres": 45,
    "total_pages": 150000,
    "reading_date_range": {"earliest": "2010-01-15", "latest": "2024-12-20"},
    "reading_years": [2010, 2011, 2023, 2024],
    "average_rating": 3.8,
    "most_common_genres": [{"genre": "Fiction", "count": 200, "percentage": 15.5}]
  },
  "metadata": {
    "export_id": "550e8400-e29b-41d4-a716-446655440000",
    "export_timestamp": "2024-01-15T10:32:15Z",
    "exporter_version": "1.0.0",
    "data_schema_version": "1.0.0",
    "export_source": "goodreads_csv_with_genre_enrichment",
    "processing_notes": ["..."],
    "validation": {"...": "..."}
  }
}
```

See [Data Models](data-models.md#dashboard-json-structure) for full schema documentation.

#### Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `202` | `{"detail": "Still processing"}` | Processing not complete |
| `404` | `{"detail": "Data not found"}` | No data for this UUID |
| `500` | `{"detail": "Processing failed: {message}"}` | Processing encountered an error |

---

### Delete User Data

Delete all data associated with a given UUID.

```
DELETE /data/{uuid}
```

#### Path Parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `uuid` | string | The UUID to delete data for |

#### Example Request

```bash
curl -X DELETE http://localhost:8001/data/550e8400-e29b-41d4-a716-446655440000
```

#### Response

**Status:** `200 OK`

```json
{
  "message": "Data deleted successfully",
  "deleted_files": ["dashboard.json", "status.json", "raw.csv"]
}
```

#### What Gets Deleted

| Environment | Files Deleted |
|-------------|---------------|
| Local | `dashboard_data/{uuid}.json`, in-memory status, temp CSV |
| Cloud | `data/{uuid}.json`, `status/{uuid}.json`, `uploads/{uuid}/*` |

#### Error Responses

| Status | Body | Cause |
|--------|------|-------|
| `404` | `{"detail": "No data found to delete"}` | No data exists for this UUID |
| `500` | `{"detail": "Failed to delete data"}` | Deletion failed |

---

### Health Check (Local Only)

Check if the local server is running.

```
GET /health
```

#### Example Request

```bash
curl http://localhost:8001/health
```

#### Response

**Status:** `200 OK`

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00.000Z",
  "uptime": 3600.5,
  "active_jobs": 2
}
```

---

### API Info (Local Only)

Get information about the API.

```
GET /
```

#### Response

```json
{
  "name": "Goodreads Stats Local API",
  "version": "1.0.0",
  "description": "Local development server for Goodreads Stats processing",
  "endpoints": {
    "POST /upload": "Upload CSV file and start processing",
    "GET /status/{uuid}": "Check processing status",
    "GET /data/{uuid}": "Get dashboard JSON data",
    "DELETE /data/{uuid}": "Delete user data"
  },
  "frontend_url": "http://localhost:8000",
  "active_jobs": 0
}
```

---

## CORS

The API supports Cross-Origin Resource Sharing (CORS).

### Local Development

```
Access-Control-Allow-Origin: http://localhost:8000, http://127.0.0.1:8000
Access-Control-Allow-Methods: GET, POST, DELETE
Access-Control-Allow-Headers: *
```

### Cloud Production

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

---

## Rate Limiting

### Local Development

No rate limiting.

### Cloud Production

- **Upload:** 10 requests per minute per IP
- **Status/Data:** 60 requests per minute per IP
- **File size limit:** 50MB

---

## Error Response Format

The local server (FastAPI) uses `HTTPException`, which produces:

```json
{
  "detail": "Error message describing what went wrong"
}
```

---

## Polling Strategy

When waiting for processing to complete, use exponential backoff:

```javascript
async function pollStatus(uuid) {
  let delay = 1000; // Start with 1 second
  const maxDelay = 10000; // Max 10 seconds

  while (true) {
    const response = await fetch(`/status/${uuid}`);
    const data = await response.json();

    if (data.status === 'complete') {
      return fetchData(uuid);
    }

    if (data.status === 'error') {
      throw new Error(data.error_message);
    }

    await sleep(delay);
    delay = Math.min(delay * 1.5, maxDelay);
  }
}
```

---

## OpenAPI Documentation

When running locally, interactive API documentation is available at:

```
http://localhost:8001/docs     # Swagger UI
http://localhost:8001/redoc    # ReDoc
```
