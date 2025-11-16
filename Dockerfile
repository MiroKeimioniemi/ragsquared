# Multi-stage Dockerfile for AI Auditing System
# Stage 1: Build Next.js frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files
COPY frontend/package*.json ./

# Install dependencies
RUN npm ci

# Copy frontend source
COPY frontend/ ./

# Create public directory if it doesn't exist (Next.js may need it)
RUN mkdir -p public

# Build Next.js app
RUN npm run build

# Stage 2: Python backend
FROM python:3.11-slim AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml setup.py ./
COPY backend/ ./backend/
COPY contracts/ ./contracts/
COPY pipelines/ ./pipelines/
COPY workers/ ./workers/
COPY alembic.ini ./

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Stage 3: Final image with both frontend and backend
FROM python:3.11-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for running Next.js
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy Python backend from builder
COPY --from=backend /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=backend /usr/local/bin /usr/local/bin
COPY --from=backend /app /app

# Copy built Next.js frontend (only runtime files needed)
COPY --from=frontend-builder /app/frontend/.next /app/frontend/.next
COPY --from=frontend-builder /app/frontend/node_modules /app/frontend/node_modules
COPY --from=frontend-builder /app/frontend/package*.json /app/frontend/
COPY --from=frontend-builder /app/frontend/next.config.js /app/frontend/
# Copy public directory (created in frontend-builder stage, even if empty)
COPY --from=frontend-builder /app/frontend/public /app/frontend/public
# Copy config files that might be needed at runtime
COPY --from=frontend-builder /app/frontend/tsconfig.json /app/frontend/tsconfig.json
COPY --from=frontend-builder /app/frontend/tailwind.config.ts /app/frontend/tailwind.config.ts
COPY --from=frontend-builder /app/frontend/postcss.config.js /app/frontend/postcss.config.js

# Create data directory for persistence
RUN mkdir -p /app/data/{uploads,processed,logs,chroma,cache/embeddings,reports} && \
    chmod -R 755 /app/data

# Copy startup script and other necessary files
COPY docker-entrypoint.sh /usr/local/bin/
COPY cli.py /app/cli.py
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Expose ports
# 5000 for Flask backend
# 3000 for Next.js frontend
EXPOSE 5000 3000

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    FLASK_APP=backend.app \
    FLASK_ENV=production \
    DATA_ROOT=/app/data \
    DATABASE_URL=sqlite:///data/app.db \
    PORT=3000

# Use entrypoint script
ENTRYPOINT ["docker-entrypoint.sh"]

# Default command (can be overridden)
CMD ["start"]

