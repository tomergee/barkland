FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration files first for caching
COPY pyproject.toml .

# Create placeholder package directories for setuptools metadata discovery
RUN mkdir -p barkland/models barkland/engine barkland/agents barkland/api barkland/output && \
    touch barkland/__init__.py \
          barkland/models/__init__.py \
          barkland/engine/__init__.py \
          barkland/agents/__init__.py \
          barkland/api/__init__.py \
          barkland/output/__init__.py

# Install dependencies
RUN pip install --no-cache-dir .

# Copy source code
COPY barkland/ ./barkland/

# Expose port (FastAPI default, but can be configured)
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "barkland.main:app", "--host", "0.0.0.0", "--port", "8000"]
