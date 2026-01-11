# Dashboard Service Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy shared modules
COPY shared/ ./shared/

# Copy dashboard service
COPY services/dashboard/ ./services/dashboard/

# Copy config
COPY config/ ./config/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose port (Cloud Run uses 8080)
EXPOSE 8080

# Run the service - use PORT env var from Cloud Run
CMD uvicorn services.dashboard.main:app --host 0.0.0.0 --port $PORT
