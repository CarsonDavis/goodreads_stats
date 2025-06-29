# Dockerfile for Goodreads Stats Local API Server
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies (avoiding system packages for now)
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create necessary directories
RUN mkdir -p data/uploads data/status dashboard_data

# Expose the port
EXPOSE 8001

# Health check (using python instead of curl to avoid needing system packages)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

# Run the FastAPI server
CMD ["python", "local_server.py"]