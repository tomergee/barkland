FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
    && curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -m 0755 kubectl /usr/local/bin/kubectl \
    && rm -rf /var/lib/apt/lists/*

# Copy configuration files first for caching
COPY pyproject.toml .
COPY agentic-sandbox-client /app/agentic-sandbox-client

# Create placeholder package directories for setuptools metadata discovery
RUN mkdir -p barkland/models barkland/engine barkland/agents barkland/api barkland/output && \
    touch barkland/__init__.py \
          barkland/models/__init__.py \
          barkland/engine/__init__.py \
          barkland/agents/__init__.py \
          barkland/api/__init__.py \
          barkland/output/__init__.py

# Install dependencies
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install . && \
    SETUPTOOLS_SCM_PRETEND_VERSION=0.1.0 pip install "/app/agentic-sandbox-client[async]"


# Copy source code
COPY barkland/ ./barkland/
COPY k8s/ ./k8s/

# Expose port (FastAPI default, but can be configured)
EXPOSE 8000

# Run FastAPI app
CMD ["uvicorn", "barkland.main:app", "--host", "0.0.0.0", "--port", "8000"]
