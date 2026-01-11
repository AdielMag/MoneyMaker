# Market Scraper Service Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared/ ./shared/

# Copy scraper service
COPY services/scraper/ ./services/scraper/
COPY services/__init__.py ./services/

# Copy config
COPY config/ ./config/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port (Cloud Run uses 8080)
EXPOSE 8080

# Run the service - use PORT env var from Cloud Run
CMD uvicorn services.scraper.main:app --host 0.0.0.0 --port $PORT
