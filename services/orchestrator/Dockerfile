# Orchestrator Service Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install debugpy for debugging support
RUN pip install --no-cache-dir debugpy

# Copy shared modules
COPY shared/ ./shared/

# Copy all services (orchestrator imports from other services)
COPY services/ ./services/

# Copy config
COPY config/ ./config/

# Copy debug entrypoint script
COPY scripts/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PORT=8080

# Expose ports (8080 for service, 5678 for debug)
EXPOSE 8080 5678

# Use entrypoint script for flexible startup (supports debugging)
ENTRYPOINT ["/entrypoint.sh"]
CMD ["services.orchestrator.main:app"]
