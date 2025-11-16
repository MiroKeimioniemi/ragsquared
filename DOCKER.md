# Docker Deployment Guide

This guide explains how to deploy the AI Auditing System using Docker. The entire application (Flask backend + Next.js frontend + ChromaDB) runs in a single container for easy deployment.

## Quick Start

### Prerequisites

- Docker installed (version 20.10+)
- Docker Compose installed (optional, for easier local testing)
- At least 2GB of available disk space
- At least 2GB of RAM recommended

### Local Testing with Docker Compose

1. **Create a `.env` file** (optional, for API keys):
   ```bash
   cp .env.example .env  # if you have one
   # Edit .env and add your API keys:
   # LLM_API_KEY=your-key-here
   # OPENAI_API_KEY=your-key-here (if using OpenAI embeddings)
   ```

2. **Build and run with Docker Compose**:
   ```bash
   docker-compose up --build
   ```

3. **Access the application**:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:5000
   - Health check: http://localhost:5000/healthz

4. **Stop the application**:
   ```bash
   docker-compose down
   ```

### Building and Running with Docker

1. **Build the image**:
   ```bash
   docker build -t ragsquared:latest .
   ```

2. **Run the container**:
   ```bash
   docker run -d \
     --name ragsquared-app \
     -p 3000:3000 \
     -p 5000:5000 \
     -v $(pwd)/data:/app/data \
     -e LLM_API_KEY=your-key-here \
     -e OPENAI_API_KEY=your-key-here \
     ragsquared:latest
   ```

3. **View logs**:
   ```bash
   docker logs -f ragsquared-app
   ```

4. **Stop the container**:
   ```bash
   docker stop ragsquared-app
   docker rm ragsquared-app
   ```

## Environment Variables

### Required (for full functionality)

- `LLM_API_KEY` - API key for LLM calls (OpenRouter or Featherless)
- `OPENAI_API_KEY` - Required if using OpenAI embeddings (`text-embedding-3-large`)

### Optional Configuration

- `EMBEDDING_MODEL` - Embedding model (default: `text-embedding-3-large`)
  - For free embeddings: `all-mpnet-base-v2` (no API key needed)
- `LLM_MODEL_COMPLIANCE` - LLM model for compliance analysis (default: `openrouter/horizon-beta`)
- `DATA_ROOT` - Data directory path (default: `/app/data`)
- `DATABASE_URL` - Database connection string (default: `sqlite:///data/app.db`)
- `CHUNK_SIZE` - Chunk size for document processing (default: `800`)
- `CHUNK_OVERLAP` - Chunk overlap (default: `80`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

### Example with all options:

```bash
docker run -d \
  --name ragsquared-app \
  -p 3000:3000 \
  -p 5000:5000 \
  -v $(pwd)/data:/app/data \
  -e LLM_API_KEY=sk-or-v1-... \
  -e OPENAI_API_KEY=sk-... \
  -e EMBEDDING_MODEL=text-embedding-3-large \
  -e LLM_MODEL_COMPLIANCE=openrouter/horizon-beta \
  -e CHUNK_SIZE=800 \
  -e LOG_LEVEL=INFO \
  ragsquared:latest
```

## Data Persistence

The application stores data in the `/app/data` directory inside the container:

- `data/app.db` - SQLite database
- `data/chroma/` - ChromaDB vector store (most important for persistence)
- `data/uploads/` - Uploaded documents
- `data/processed/` - Processed documents
- `data/cache/embeddings/` - Cached embeddings
- `data/reports/` - Generated reports

**Important**: Always mount the data directory as a volume to persist data:

```bash
-v $(pwd)/data:/app/data
```

Without this volume mount, all data will be lost when the container is removed!

## ChromaDB Persistence

ChromaDB uses a persistent client that stores data in `data/chroma/`. This directory must be:

1. **Mounted as a volume** to persist across container restarts
2. **Backed up regularly** as it contains all vector embeddings
3. **Given sufficient disk space** (can grow large with many documents)

The ChromaDB data is the most critical part to preserve - without it, you'll need to regenerate all embeddings.

## Deployment to Cloud Services

### Railway

1. Connect your GitHub repository
2. Add environment variables in Railway dashboard
3. Railway will automatically detect and build the Dockerfile
4. Set port to `3000` (or configure both ports)

### Render

1. Create a new Web Service
2. Connect your repository
3. Set build command: `docker build -t app .`
4. Set start command: `docker run -p $PORT:3000 app`
5. Add environment variables in dashboard

### Fly.io

1. Install Fly CLI: `curl -L https://fly.io/install.sh | sh`
2. Create app: `fly launch`
3. Deploy: `fly deploy`
4. Set secrets: `fly secrets set LLM_API_KEY=... OPENAI_API_KEY=...`

### DigitalOcean App Platform

1. Connect repository
2. Select Dockerfile
3. Add environment variables
4. Set health check path: `/healthz`
5. Deploy

### AWS ECS / Google Cloud Run / Azure Container Instances

All support Docker containers. Use the same Dockerfile and ensure:
- Environment variables are set
- Data volume is configured (or use managed storage)
- Ports 3000 and 5000 are exposed

## Troubleshooting

### Container won't start

1. Check logs: `docker logs ragsquared-app`
2. Verify environment variables are set
3. Ensure ports 3000 and 5000 are not in use
4. Check disk space: `docker system df`

### Database migration errors

Run migrations manually:
```bash
docker exec ragsquared-app docker-entrypoint.sh migrate
```

### ChromaDB issues

If ChromaDB data is corrupted:
1. Stop container
2. Backup `data/chroma/` directory
3. Clear and regenerate: Remove `data/chroma/` and restart
4. Re-run embedding pipeline for your documents

### Out of memory

The container needs at least 2GB RAM. Increase Docker memory limit:
- Docker Desktop: Settings → Resources → Memory
- Or use a larger instance on cloud platforms

### Frontend not connecting to backend

1. Check backend is running: `curl http://localhost:5000/healthz`
2. Check frontend logs: `docker logs ragsquared-app | grep frontend`
3. Verify `BACKEND_URL` environment variable if using custom setup

## Development vs Production

### Development (local)
- Uses `docker-compose.yml` for easy setup
- Mounts source code for hot reload (if configured)
- More verbose logging

### Production
- Single container deployment
- Optimized build with minimal layers
- Production logging
- Health checks enabled

## Security Considerations

1. **Never commit `.env` files** with API keys
2. **Use secrets management** on cloud platforms
3. **Limit exposed ports** - only expose what's necessary
4. **Use HTTPS** in production (configure reverse proxy)
5. **Regular backups** of the data directory
6. **Update dependencies** regularly for security patches

## Cost Optimization

For the cheapest deployment:

1. **Use free tier embeddings**: Set `EMBEDDING_MODEL=all-mpnet-base-v2`
2. **Use smaller instances**: 1GB RAM minimum (2GB recommended)
3. **Optimize storage**: Regular cleanup of old data
4. **Use SQLite**: Already configured, no database service needed
5. **Single container**: No need for separate services

**Recommended cheap hosting**:
- Railway (free tier available)
- Render (free tier available)
- Fly.io (pay-as-you-go)
- DigitalOcean App Platform ($5/month)

## Monitoring

Check application health:
```bash
curl http://localhost:5000/healthz
```

Response includes:
- Database connectivity
- Pending jobs
- Data root status

## Backup Strategy

1. **Regular backups** of `/app/data` directory:
   ```bash
   docker exec ragsquared-app tar -czf /tmp/backup.tar.gz /app/data
   docker cp ragsquared-app:/tmp/backup.tar.gz ./backup-$(date +%Y%m%d).tar.gz
   ```

2. **Most critical**: `data/chroma/` - contains all embeddings
3. **Database**: `data/app.db` - contains all metadata
4. **Uploads**: `data/uploads/` - original documents

## Support

For issues or questions:
1. Check logs: `docker logs ragsquared-app`
2. Review this guide
3. Check the main README.md for application-specific help

