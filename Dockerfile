# ==============================================================================
# Stage 1: Build the frontend Next.js application
# ==============================================================================
FROM node:20-slim AS frontend-builder
WORKDIR /app/frontend

# Copy package descriptors first to leverage Docker layer caching
COPY frontend/package.json frontend/package-lock.json ./

# Install Node dependencies
RUN npm ci

# Copy the rest of the frontend source code
COPY frontend/ ./

# Run the build which exports static assets to /app/frontend/out/
RUN npm run build

# ==============================================================================
# Stage 2: Set up FastAPI Python backend environment and serve static files
# ==============================================================================
FROM python:3.12-slim AS backend-runner

# Install uv for rapid package management and synchronization
RUN pip install --no-cache-dir uv

WORKDIR /app/backend

# Copy python project descriptors to leverage layer caching
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./

# Copy backend app source code
COPY backend/app/ ./app/

# Sync only production dependencies (frozen versions, exclude development tools)
RUN uv sync --frozen --no-dev

# Copy static frontend export build output into FastAPI static serving directory
COPY --from=frontend-builder /app/frontend/out/ ./static/

# Create a dedicated directory for the SQLite database volume and ensure open write permissions
RUN mkdir -p /app/db && chmod 777 /app/db
VOLUME ["/app/db"]

# Expose port 8000 for serving FastAPI
EXPOSE 8000

# Set Python output buffering behavior for real-time logs
ENV PYTHONUNBUFFERED=1

# Run Uvicorn via uv in production mode
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
