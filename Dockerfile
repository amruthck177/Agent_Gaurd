# ==============================================================================
# Multi-Stage Production Dockerfile for AgentGuard 2.0
# Stage 1: Build React 18 Frontend
# Stage 2: Minimal Python Runtime with FastAPI & Static Serving
# ==============================================================================

# --- Stage 1: Build Frontend Assets ---
FROM node:20-alpine AS frontend-builder
WORKDIR /build/frontend

# Install dependencies with caching
COPY frontend/package*.json ./
RUN npm ci || npm install

# Copy source and build production bundle
COPY frontend/ ./
RUN npm run build

# --- Stage 2: Production Python Runtime ---
FROM python:3.11-slim AS production

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    DEMO_MODE=1 \
    STATIC_DIR=/app/static \
    AGENTGUARD_DB_PATH=/app/data/agentguard.db

WORKDIR /app

# Install system dependencies (sqlite3 and curl for healthcheck)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application source
COPY backend/app /app/app
COPY benchmarks /app/benchmarks
COPY docs /app/docs

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /build/frontend/dist /app/static

# Create persistent data directory
RUN mkdir -p /app/data

# Expose default port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=20s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Launch uvicorn bound to 0.0.0.0
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
