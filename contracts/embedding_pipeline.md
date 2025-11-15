# Embedding Pipeline Contract

## Overview

The embedding pipeline generates vector embeddings for document chunks and stores them in ChromaDB for semantic search. This document defines the contracts, data flows, and integration points.

## Architecture

```
┌─────────────────┐
│  Chunk Pipeline │
│   (upstream)    │
└────────┬────────┘
         │
         │ chunks with status='pending'
         ▼
┌─────────────────┐
│ EmbeddingService│
│  - Batch fetch  │
│  - Cache check  │
│  - Generate     │
│  - Store        │
└────────┬────────┘
         │
         ├─────────────────┐
         │                 │
         ▼                 ▼
┌─────────────────┐  ┌──────────────┐
│   ChromaDB      │  │  SQLite DB   │
│  (vectors +     │  │  (status +   │
│   metadata)     │  │   jobs)      │
└─────────────────┘  └──────────────┘
```

## Data Models

### Chunk (SQLite)

```python
class Chunk:
    id: int
    document_id: int
    chunk_index: int
    content: str
    token_count: int
    chunk_metadata: dict
    embedding_status: str  # 'pending' | 'in_progress' | 'completed' | 'failed'
    created_at: datetime
    updated_at: datetime
```

### EmbeddingJob (SQLite)

```python
class EmbeddingJob:
    id: int
    document_id: int
    status: str  # 'pending' | 'in_progress' | 'completed' | 'failed'
    job_type: str  # 'manual' | 'regulation' | 'amc' | 'gm' | 'evidence'
    started_at: datetime | None
    completed_at: datetime | None
    last_error: str | None
    job_metadata: dict
    created_at: datetime
    updated_at: datetime
```

### ChromaDB Document

```python
{
    "id": "chunk_<chunk_id>",
    "embedding": [0.1, 0.2, ...],  # 1536-dim for text-embedding-3-large
    "document": "<chunk text>",
    "metadata": {
        "chunk_id": int,
        "document_id": int,
        "chunk_index": int,
        "section_path": list[str],
        "parent_heading": str,
        "token_count": int,
        # ... additional chunk_metadata fields
    }
}
```

## Service API

### EmbeddingService

```python
class EmbeddingService:
    def __init__(self, session: Session, config: AppConfig):
        """Initialize with database session and app configuration."""
        
    def get_pending_chunks(
        self, 
        doc_id: str | None = None, 
        limit: int = 100
    ) -> list[Chunk]:
        """Retrieve chunks that need embeddings."""
        
    def process_chunks(
        self, 
        chunks: list[Chunk], 
        collection_name: str = "manual_chunks"
    ) -> dict[str, Any]:
        """
        Process a batch of chunks and generate embeddings.
        
        Returns:
            {
                "processed": int,  # Number of successfully processed chunks
                "failed": int,     # Number of failed chunks
                "error": str       # Error message (if any)
            }
        """
        
    def create_embedding_job(
        self, 
        doc_id: int, 
        job_type: str = "manual"
    ) -> EmbeddingJob:
        """Create a new embedding job record."""
        
    def update_job_status(
        self, 
        job: EmbeddingJob, 
        status: str, 
        error: str | None = None
    ) -> None:
        """Update embedding job status."""
```

### EmbeddingClient

```python
class EmbeddingClient:
    def __init__(self, config: EmbeddingConfig):
        """Initialize with embedding configuration."""
        
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for a batch of texts.
        
        Supports:
        - OpenAI API (text-embedding-3-large, text-embedding-ada-002)
        - Sentence Transformers (all-MiniLM-L6-v2, all-mpnet-base-v2)
        """
```

## CLI Interface

### Embedding Generation

```bash
python -m pipelines.embed --doc-id <document-id> [OPTIONS]
```

**Required Arguments:**
- `--doc-id`: Document ID (external UUID or numeric primary key)

**Optional Arguments:**
- `--collection`: ChromaDB collection name (default: `manual_chunks`)
- `--batch-size`: Number of chunks to process per batch (default: 32)
- `--dry-run`: Show pending chunks without generating embeddings
- `--verbose`: Print detailed progress information

**Exit Codes:**
- `0`: Success
- `1`: No pending chunks found or configuration error
- `2`: Processing error

**Example Output:**
```
Found 150 pending chunks for document 'doc-abc123'.
Processing batch 1/5 (32 chunks)...
  ✓ Processed: 32, ✗ Failed: 0
...
Embedding generation complete!
  Total processed: 150
  Total failed: 0
  Collection: manual_chunks
```

### Vector Search Test

```bash
python scripts/vectortest.py --query "<search text>" [OPTIONS]
```

**Required Arguments:**
- `--query`: Query text to search for

**Optional Arguments:**
- `--collection`: ChromaDB collection to query (default: `manual_chunks`)
- `--top-k`: Number of results to retrieve (default: 3)

**Example Output:**
```
┏━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Rank ┃ ID          ┃ Distance ┃ Preview                     ┃
┡━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 1    │ chunk_42    │ 0.2341   │ Personnel qualifications... │
│ 2    │ chunk_87    │ 0.3012   │ Certifying staff must...    │
│ 3    │ chunk_103   │ 0.3456   │ Part-66 license holders...  │
└──────┴─────────────┴──────────┴─────────────────────────────┘
```

## Configuration

### Environment Variables

```bash
# Embedding provider (auto-detected from model name)
EMBEDDING_MODEL=text-embedding-3-large  # OpenAI
# EMBEDDING_MODEL=all-MiniLM-L6-v2      # Sentence Transformers

# API key (for OpenAI-compatible providers)
OPENROUTER_API_KEY=sk-...

# Data storage
DATA_ROOT=./data
```

### Supported Models

**OpenAI-compatible:**
- `text-embedding-3-large` (1536 dimensions, recommended)
- `text-embedding-3-small` (512 dimensions)
- `text-embedding-ada-002` (1536 dimensions, legacy)

**Sentence Transformers (local):**
- `all-MiniLM-L6-v2` (384 dimensions, fast)
- `all-mpnet-base-v2` (768 dimensions, quality)
- `sentence-transformers/all-MiniLM-L6-v2` (explicit prefix)

## Caching Strategy

Embeddings are cached on disk to avoid regeneration:

```
./data/cache/embeddings/
  ├── a3f5b2c8d1e4f6a9.npy  # SHA256[:16] of chunk text
  ├── b7c9d2e5f8a1b3c6.npy
  └── ...
```

**Cache Key:** First 16 characters of SHA256(chunk.content)

**Cache Hit:** Load from `.npy` file (instant)

**Cache Miss:** Generate embedding, save to `.npy`, return

## ChromaDB Collections

### Collection Naming Convention

- `manual_chunks`: Organization manuals/procedures
- `regulation_chunks`: EASA Part-145 regulations
- `amc_chunks`: Acceptable Means of Compliance
- `gm_chunks`: Guidance Material
- `evidence_chunks`: Supporting evidence documents

### Collection Schema

All collections share the same schema:

```python
collection.add(
    ids=["chunk_1", "chunk_2", ...],
    embeddings=[[0.1, 0.2, ...], ...],
    documents=["text1", "text2", ...],
    metadatas=[
        {
            "chunk_id": 1,
            "document_id": 42,
            "chunk_index": 0,
            "section_path": ["Manual", "Section 4.2"],
            "parent_heading": "Personnel Qualifications",
            "token_count": 512,
            # ... additional metadata
        },
        ...
    ]
)
```

## Error Handling

### Retry Logic

- **Transient errors** (network, rate limits): Retry up to 3 times with exponential backoff
- **Permanent errors** (invalid API key, model not found): Fail immediately

### Status Tracking

1. `pending` → `in_progress`: Batch claimed for processing
2. `in_progress` → `completed`: Embeddings generated and stored successfully
3. `in_progress` → `failed`: Error occurred, `last_error` populated

### Recovery

Failed chunks can be reprocessed:

```sql
UPDATE chunks SET embedding_status = 'pending' WHERE embedding_status = 'failed';
```

Then re-run the embedding pipeline.

## Performance Characteristics

### Batch Processing

- **Batch size:** 32 chunks (configurable)
- **OpenAI rate limits:** ~3000 requests/min (tier-dependent)
- **Sentence Transformers:** Limited by CPU/GPU

### Throughput Estimates

**OpenAI (text-embedding-3-large):**
- ~1000 chunks/minute (batch size 32)
- ~60,000 chunks/hour

**Sentence Transformers (local, CPU):**
- ~100-500 chunks/minute (model-dependent)
- ~6,000-30,000 chunks/hour

### Storage

- **ChromaDB:** ~6 KB per chunk (1536-dim embedding + metadata)
- **Cache:** ~6 KB per unique chunk text
- **1000 chunks:** ~6 MB (ChromaDB) + ~6 MB (cache)

## Testing

### Unit Tests

`tests/services/test_embeddings.py`:
- `test_embedding_service_gets_pending_chunks`: Verify batch selection
- `test_embedding_service_processes_chunks`: Mock embedding generation
- `test_embedding_cache_key_generation`: Verify cache key consistency
- `test_embedding_job_creation`: Job lifecycle management

### Integration Tests

`tests/pipelines/test_embed_cli.py`:
- `test_embed_cli_shows_pending_chunks_in_dry_run`: CLI dry-run mode
- `test_embed_cli_processes_chunks`: End-to-end with mocked embeddings

### Manual Testing

```bash
# 1. Upload and chunk a document
python -m pipelines.chunk extracted.json --doc-id doc-123

# 2. Generate embeddings
python -m pipelines.embed --doc-id doc-123 --verbose

# 3. Test retrieval
python scripts/vectortest.py --query "personnel qualifications" --top-k 5
```

## Integration Points

### Upstream: Chunking Pipeline

- **Input:** Chunks with `embedding_status='pending'`
- **Trigger:** Manual CLI invocation or scheduled job
- **Contract:** Chunks must have valid `content` and `chunk_metadata`

### Downstream: Context Builder

- **Output:** ChromaDB collections with semantic search capability
- **Query Interface:** `collection.query(query_texts=[...], n_results=k)`
- **Metadata Access:** Full chunk metadata available in results

### Parallel: Audit Runner

- **Shared Resource:** ChromaDB collections (read-only during audits)
- **Coordination:** Embedding pipeline should complete before audit starts
- **Fallback:** Audit can proceed with partial embeddings (warnings logged)

## Future Enhancements

1. **Background Workers:** RQ/Celery for async processing
2. **Incremental Updates:** Only embed new/changed chunks
3. **Multi-model Support:** Ensemble embeddings for improved retrieval
4. **Compression:** Quantization or dimensionality reduction
5. **Monitoring:** Prometheus metrics for throughput/latency

