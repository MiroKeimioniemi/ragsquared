from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config.settings import AppConfig
from ..db.models import Chunk, EmbeddingJob, Legislation, LegislationChunk

logger = logging.getLogger(__name__)

# Model dimension mapping for validation
MODEL_DIMENSIONS = {
    "text-embedding-3-large": 3072,
    "text-embedding-3-small": 1536,
    "text-embedding-ada-002": 1536,
    # Add other OpenRouter-supported embedding models here
}


def get_expected_dimensions(model_name: str) -> int | None:
    """Get expected embedding dimensions for a given model name."""
    return MODEL_DIMENSIONS.get(model_name)


def validate_embedding_dimension(embedding: list[float], expected_dim: int | None, model_name: str) -> None:
    """Validate that an embedding has the expected dimension."""
    actual_dim = len(embedding)
    if expected_dim is not None and actual_dim != expected_dim:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dim} (for model '{model_name}'), "
            f"but got {actual_dim}. This usually means the embedding model configuration is incorrect."
        )


@dataclass
class EmbeddingConfig:
    """Configuration for embedding generation."""

    model: str
    api_key: str
    api_base_url: str
    batch_size: int
    cache_dir: Path | None = None


class EmbeddingClient:
    """Client for generating embeddings via OpenRouter API."""

    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.client = httpx.Client(timeout=60.0)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a batch of texts using OpenRouter."""
        if not texts:
            return []

        return self._embed_openrouter(texts)

    def _embed_openrouter(self, texts: list[str]) -> list[list[float]]:
        """Call OpenRouter embedding API."""
        url = f"{self.config.api_base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/your-org/ai-auditing-backend",  # Optional: for OpenRouter tracking
        }
        payload = {"input": texts, "model": self.config.model}

        response = self.client.post(url, json=payload, headers=headers)
        response.raise_for_status()

        data = response.json()
        embeddings = [item["embedding"] for item in data["data"]]
        return embeddings

    def close(self):
        """Close the HTTP client."""
        self.client.close()


class EmbeddingService:
    """Service for managing embedding jobs and vector storage."""

    def __init__(self, session: Session, config: AppConfig):
        self.session = session
        self.config = config
        self.embedding_config = self._build_embedding_config()
        self.client = EmbeddingClient(self.embedding_config)

    def _build_embedding_config(self) -> EmbeddingConfig:
        """Build embedding configuration from app config."""
        cache_dir = Path(self.config.data_root) / "cache" / "embeddings"
        cache_dir.mkdir(parents=True, exist_ok=True)

        # Use OpenRouter for embeddings
        api_key = self.config.openrouter_api_key or self.config.llm_api_key
        if not api_key:
            raise ValueError(
                "OPENROUTER_API_KEY or LLM_API_KEY must be set for embedding generation"
            )

        return EmbeddingConfig(
            model=self.config.embedding_model,
            api_key=api_key,
            api_base_url=self.config.embedding_api_base_url,
            batch_size=32,
            cache_dir=cache_dir,
        )

    def get_pending_chunks(self, doc_id: str | None = None, limit: int = 100) -> list[Chunk]:
        """Retrieve chunks that need embeddings."""
        stmt = select(Chunk).where(Chunk.embedding_status == "pending")

        if doc_id:
            from ..db.models import Document

            doc_stmt = select(Document).where(Document.external_id == doc_id)
            document = self.session.execute(doc_stmt).scalar_one_or_none()
            if document:
                stmt = stmt.where(Chunk.document_id == document.id)

        stmt = stmt.limit(limit)
        result = self.session.execute(stmt)
        return list(result.scalars().all())

    def process_chunks(
        self, chunks: list[Chunk], collection_name: str = "manual_chunks"
    ) -> dict[str, Any]:
        """Process a batch of chunks and generate embeddings."""
        if not chunks:
            return {"processed": 0, "failed": 0}

        # Mark chunks as in-progress
        for chunk in chunks:
            chunk.embedding_status = "in_progress"
        self.session.flush()

        try:
            # Extract texts
            texts = [chunk.content for chunk in chunks]

            # Check cache
            cached_embeddings = self._load_cached_embeddings(texts)
            texts_to_embed = [
                text for i, text in enumerate(texts) if cached_embeddings.get(i) is None
            ]

            # Generate new embeddings
            if texts_to_embed:
                logger.info(f"Generating {len(texts_to_embed)} new embeddings...")
                new_embeddings = self.client.embed_texts(texts_to_embed)

                # Cache new embeddings
                for text, embedding in zip(texts_to_embed, new_embeddings):
                    self._cache_embedding(text, embedding)

                # Merge cached and new
                import numpy as np
                new_idx = 0
                all_embeddings = []
                for i, text in enumerate(texts):
                    if cached_embeddings.get(i) is not None:
                        # Ensure cached embedding is a list
                        emb = cached_embeddings[i]
                        if isinstance(emb, np.ndarray):
                            emb = emb.tolist()
                        all_embeddings.append(emb)
                    else:
                        # Ensure new embedding is a list
                        emb = new_embeddings[new_idx]
                        if isinstance(emb, np.ndarray):
                            emb = emb.tolist()
                        all_embeddings.append(emb)
                        new_idx += 1
            else:
                logger.info("All embeddings loaded from cache.")
                import numpy as np
                all_embeddings = []
                for i in range(len(texts)):
                    emb = cached_embeddings[i]
                    if isinstance(emb, np.ndarray):
                        emb = emb.tolist()
                    all_embeddings.append(emb)

            # Store in ChromaDB
            self._store_in_chroma(chunks, all_embeddings, collection_name)

            # Mark as completed
            for chunk in chunks:
                chunk.embedding_status = "completed"
            self.session.commit()

            logger.info(f"Successfully processed {len(chunks)} chunks.")
            return {"processed": len(chunks), "failed": 0}

        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            logger.error(f"Embedding processing failed: {e}\n{error_details}")
            # Mark as failed
            for chunk in chunks:
                chunk.embedding_status = "failed"
            self.session.commit()
            return {"processed": 0, "failed": len(chunks), "error": str(e)}

    def _load_cached_embeddings(self, texts: list[str]) -> dict[int, list[float]]:
        """Load cached embeddings for texts."""
        if not self.embedding_config.cache_dir:
            return {}

        cached = {}
        for i, text in enumerate(texts):
            cache_key = self._compute_cache_key(text)
            cache_file = self.embedding_config.cache_dir / f"{cache_key}.npy"

            if cache_file.exists():
                try:
                    import numpy as np

                    embedding = np.load(cache_file).tolist()
                    cached[i] = embedding
                except Exception as e:
                    logger.warning(f"Failed to load cached embedding: {e}")

        return cached

    def _cache_embedding(self, text: str, embedding: list[float]) -> None:
        """Cache an embedding to disk."""
        if not self.embedding_config.cache_dir:
            return

        try:
            import numpy as np

            cache_key = self._compute_cache_key(text)
            cache_file = self.embedding_config.cache_dir / f"{cache_key}.npy"
            np.save(cache_file, np.array(embedding))
        except Exception as e:
            logger.warning(f"Failed to cache embedding: {e}")

    def _compute_cache_key(self, text: str) -> str:
        """Compute SHA256 hash of text for cache key."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    def _store_in_chroma(
        self, chunks: list[Chunk], embeddings: list[list[float]], collection_name: str
    ) -> None:
        """Store embeddings in ChromaDB with dimension validation."""
        try:
            import chromadb
        except ImportError:
            raise RuntimeError("chromadb not installed. Install with: pip install chromadb")

        chroma_path = Path(self.config.data_root) / "chroma"
        chroma_path.mkdir(parents=True, exist_ok=True)

        client = chromadb.PersistentClient(path=str(chroma_path))
        
        # Validate embedding dimensions before storing
        expected_dim = get_expected_dimensions(self.embedding_config.model)
        if embeddings:
            import numpy as np
            # Convert first embedding to list if it's a numpy array
            first_emb = embeddings[0]
            if isinstance(first_emb, np.ndarray):
                first_emb = first_emb.tolist()
            first_dim = len(first_emb)
            validate_embedding_dimension(first_emb, expected_dim, self.embedding_config.model)
            
            # Validate all embeddings have the same dimension
            for i, emb in enumerate(embeddings):
                # Convert to list if it's a numpy array
                if isinstance(emb, np.ndarray):
                    emb = emb.tolist()
                if len(emb) != first_dim:
                    raise ValueError(
                        f"Embedding dimension inconsistency: first embedding has {first_dim} dimensions, "
                        f"but embedding {i} has {len(emb)} dimensions"
                    )
        
        # Check if collection exists and validate dimension compatibility
        try:
            existing_collection = client.get_collection(name=collection_name)
            collection_count = existing_collection.count()
            
            if collection_count > 0:
                # Collection exists and has data - check dimension compatibility
                # Get a sample embedding from the collection to check dimension
                sample_result = existing_collection.peek(limit=1)
                import numpy as np
                sample_embeddings = sample_result.get("embeddings")
                # Check if embeddings exist and convert to list if needed
                if sample_embeddings is not None:
                    # Convert to list if it's a numpy array
                    if isinstance(sample_embeddings, np.ndarray):
                        sample_embeddings = sample_embeddings.tolist()
                    if len(sample_embeddings) > 0:
                        sample_emb = sample_embeddings[0]
                        if isinstance(sample_emb, np.ndarray):
                            sample_emb = sample_emb.tolist()
                        existing_dim = len(sample_emb)
                        if embeddings:
                            # Ensure embeddings[0] is a list for comparison
                            first_emb = embeddings[0]
                            if isinstance(first_emb, np.ndarray):
                                first_emb = first_emb.tolist()
                            if len(first_emb) != existing_dim:
                                raise ValueError(
                                    f"Dimension mismatch in collection '{collection_name}': "
                                    f"existing embeddings have {existing_dim} dimensions, "
                                    f"but new embeddings have {len(first_emb)} dimensions. "
                                    f"This usually means the embedding model was changed. "
                                    f"To fix this, either:\n"
                                    f"  1. Delete the ChromaDB collection using: "
                                    f"     python -c \"import chromadb; c = chromadb.PersistentClient(path='{chroma_path}'); c.delete_collection('{collection_name}')\"\n"
                                    f"  2. Or use the same embedding model ({self.embedding_config.model} -> {existing_dim} dims) "
                                    f"that was used to create the collection"
                                )
                            else:
                                logger.debug(
                                    f"Collection '{collection_name}' dimension validated: {existing_dim} dimensions"
                                )
        except Exception as e:
            # Collection doesn't exist yet or other error - will be created or re-raised
            if "does not exist" not in str(e).lower() and "not found" not in str(e).lower():
                # Re-raise if it's not a "collection doesn't exist" error
                raise
        
        collection = client.get_or_create_collection(name=collection_name)

        # Prepare data
        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.content for chunk in chunks]
        metadatas = []
        for chunk in chunks:
            # ChromaDB only accepts primitive types in metadata (str, int, float, bool, None)
            # Flatten nested dicts and convert complex types to strings
            metadata = {
                "chunk_pk": chunk.id,
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "chunk_index": chunk.chunk_index,
                "section_path": chunk.section_path or "",
                "parent_heading": chunk.parent_heading or "",
                "token_count": chunk.token_count or 0,
            }
            # Flatten chunk_metadata, converting dicts to JSON strings
            if chunk.chunk_metadata:
                import json
                for key, value in chunk.chunk_metadata.items():
                    if isinstance(value, (dict, list)):
                        metadata[key] = json.dumps(value)
                    elif isinstance(value, (str, int, float, bool)) or value is None:
                        metadata[key] = value
                    else:
                        metadata[key] = str(value)
            metadatas.append(metadata)

        # Add to collection with error handling for dimension mismatches
        try:
            collection.add(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)
            if embeddings:
                logger.info(
                    f"Stored {len(chunks)} embeddings ({len(embeddings[0])} dimensions) "
                    f"in ChromaDB collection '{collection_name}'."
                )
        except Exception as e:
            error_msg = str(e)
            if "dimension" in error_msg.lower() or "size" in error_msg.lower():
                raise ValueError(
                    f"Failed to store embeddings in collection '{collection_name}': {error_msg}\n"
                    f"This is likely a dimension mismatch. Current model '{self.embedding_config.model}' "
                    f"produces {len(embeddings[0]) if embeddings else 'unknown'} dimensional embeddings. "
                    f"Please ensure all embeddings in the collection use the same dimension."
                ) from e
            raise

    def create_embedding_job(self, doc_id: int, job_type: str = "manual") -> EmbeddingJob:
        """Create a new embedding job record."""
        job = EmbeddingJob(
            document_id=doc_id,
            status="pending",
            job_type=job_type,
            provider="openrouter",
            job_metadata={"created_by": "embedding_service"},
        )
        self.session.add(job)
        self.session.commit()
        return job

    def update_job_status(
        self, job: EmbeddingJob, status: str, error: str | None = None
    ) -> None:
        """Update embedding job status."""
        job.status = status
        if error:
            job.last_error = error
        if status == "completed":
            job.completed_at = datetime.utcnow()
        self.session.commit()

    def close(self):
        """Close resources."""
        self.client.close()


def process_legislation_file(file, filename: str, db_session: Session, config: AppConfig | None = None) -> dict[str, Any]:
    """Save file, extract text, chunk, embed, and store in DB.
    
    This follows the same process as regenerate_regulation_vectors.py:
    1. Create Document with source_type="regulation"
    2. Extract text and create Chunk objects
    3. Use EmbeddingService.process_chunks() to store in ChromaDB collection "regulation_chunks"
    
    Args:
        file: FileStorage object from Flask request
        filename: Original filename
        db_session: Database session
        config: AppConfig instance (if None, will create new one)
        
    Returns:
        Dictionary with id, filename, num_chunks, text_length
        
    Raises:
        ValueError: For validation errors
        DocumentUploadError: For file upload errors
        ExtractionError: For text extraction errors
    """
    from pathlib import Path
    
    from ..config.settings import AppConfig
    from ..db.models import Document, Chunk, Legislation
    from .documents import DocumentService, DocumentUploadError
    from .chunking import SemanticChunker, SectionText
    from ..processing.extraction import DocumentExtractor, ExtractionError
    
    if config is None:
        config = AppConfig()
    
    document = None
    legislation = None
    
    try:
        # Step 1: Create Document using DocumentService (same as regulations)
        logger.info("Creating document for legislation upload...")
        # Normalize data_root for DocumentService to avoid double /data in paths
        data_root_for_service = config.data_root.rstrip('/')
        if data_root_for_service.endswith('/data'):
            data_root_for_service = data_root_for_service[:-5]
        logger.info(f"Using data_root for DocumentService: {data_root_for_service} (original: {config.data_root})")
        doc_service = DocumentService(Path(data_root_for_service), db_session)
        document = doc_service.create_from_upload(
            file,
            source_type="regulation",  # Store as regulation so it's used in context building
            organization="Legislation",
            description=f"Legislation document: {filename}"
        )
        logger.info(f"Created document: {document.original_filename} (ID: {document.id}, External ID: {document.external_id})")
        
        # Step 2: Extract text from document
        logger.info("Extracting text from document...")
        # Resolve storage path - document.storage_path is relative to data_root
        # DocumentService stores paths relative to data_root (e.g., "uploads/2025/11/16/file.pdf")
        
        # Normalize data_root - remove any trailing /data if present to avoid /app/data/data
        data_root_str = config.data_root.rstrip('/')
        if data_root_str.endswith('/data'):
            # Remove trailing /data to avoid double data in path
            data_root_str = data_root_str[:-5]
            logger.warning(f"Normalized data_root from '{config.data_root}' to '{data_root_str}' to avoid double 'data' in path")
        
        data_root_path = Path(data_root_str).resolve()
        storage_path_str = document.storage_path.strip()
        
        logger.info(f"Resolving storage path - data_root: {config.data_root} -> normalized: {data_root_str} (resolved: {data_root_path}), storage_path from DB: {storage_path_str}")
        
        # If storage_path is already absolute, use it directly
        if Path(storage_path_str).is_absolute():
            storage_path = Path(storage_path_str).resolve()
            logger.info(f"Storage path is absolute, using directly: {storage_path}")
        else:
            # Remove leading slashes
            storage_path_str = storage_path_str.lstrip('/')
            
            # Check if storage_path_str already starts with data_root components
            # This handles cases where storage_path might accidentally include "data/" prefix
            data_root_name = data_root_path.name  # "data"
            if storage_path_str.startswith(f"{data_root_name}/"):
                logger.warning(f"Storage path includes '{data_root_name}/' prefix, removing it: {storage_path_str}")
                storage_path_str = storage_path_str[len(f"{data_root_name}/"):]
            
            # Construct path relative to data_root
            storage_path = (data_root_path / storage_path_str).resolve()
            logger.info(f"Constructed storage path: {storage_path}")
        
        # Verify the path exists
        if not storage_path.exists():
            # Try alternative path resolutions for debugging
            alt_paths = [
                data_root_path / document.storage_path,  # Normalized path
                Path(data_root_str) / document.storage_path,  # Normalized string path
                Path("/app/data") / document.storage_path,  # Hardcoded fallback
                Path(config.data_root) / document.storage_path,  # Original config (might have double data)
            ]
            
            logger.error(f"Storage path does not exist: {storage_path}")
            logger.error(f"  Config data_root: {config.data_root}")
            logger.error(f"  Resolved data_root: {data_root_path}")
            logger.error(f"  Storage path from DB: {document.storage_path}")
            
            for i, alt_path in enumerate(alt_paths, 1):
                exists = alt_path.exists()
                logger.error(f"  Alternative {i}: {alt_path} (exists: {exists})")
                if exists:
                    logger.warning(f"  Found file at alternative path {i}, using it")
                    storage_path = alt_path.resolve()
                    break
            
            if not storage_path.exists():
                # List uploads directory to help debug
                uploads_dir = data_root_path / "uploads"
                if uploads_dir.exists():
                    logger.error(f"  Uploads directory exists: {uploads_dir}")
                    try:
                        files = list(uploads_dir.rglob("*.pdf"))[:5]  # List first 5 PDFs
                        logger.error(f"  Sample files in uploads: {[str(f) for f in files]}")
                    except Exception as e:
                        logger.error(f"  Could not list uploads directory: {e}")
                else:
                    logger.error(f"  Uploads directory does not exist: {uploads_dir}")
                
                raise ValueError(
                    f"Storage path does not exist: {storage_path} "
                    f"(resolved from '{document.storage_path}', data_root: '{config.data_root}')"
                )
        
        logger.info(f"Extracting from storage path: {storage_path}")
        extractor = DocumentExtractor()
        
        try:
            extracted_doc = extractor.extract(storage_path)
            extraction_data = extracted_doc.to_dict()
        except ExtractionError as e:
            logger.error(f"Extraction failed: {e}")
            raise ValueError(f"Failed to extract text from file: {e}") from e
        except Exception as e:
            logger.exception(f"Unexpected error during extraction: {e}")
            raise ValueError(f"Unexpected error extracting text: {e}") from e
        
        # Convert to SectionText objects for chunking
        sections = []
        for idx, section_data in enumerate(extraction_data.get("sections", [])):
            section_path = section_data.get("metadata", {}).get("section_path")
            if isinstance(section_path, str):
                section_path = [section_path]
            elif not isinstance(section_path, list):
                section_path = None
            
            sections.append(
                SectionText(
                    index=section_data.get("index", idx),
                    title=section_data.get("title"),
                    content=section_data.get("content", ""),
                    section_path=[str(p) for p in section_path] if section_path else None,
                    metadata=section_data.get("metadata", {}),
                )
            )
        
        if not sections:
            # Fallback: create a single section from the full text
            full_text = extraction_data.get("metadata", {}).get("full_text", "")
            if not full_text:
                # Try to read the file directly
                logger.warning("No sections found, attempting direct file read...")
                try:
                    if storage_path.suffix.lower() == ".pdf":
                        from PyPDF2 import PdfReader
                        try:
                            reader = PdfReader(str(storage_path))
                            text_parts = []
                            for page in reader.pages:
                                text_parts.append(page.extract_text() or "")
                            full_text = "\n".join(text_parts)
                        except Exception as e:
                            logger.error(f"PyPDF2 extraction failed: {e}")
                            raise ValueError(f"Failed to extract text from PDF: {e}") from e
                    else:
                        try:
                            with open(storage_path, "r", encoding="utf-8", errors="ignore") as f:
                                full_text = f.read()
                        except Exception as e:
                            logger.error(f"File read failed: {e}")
                            raise ValueError(f"Failed to read file: {e}") from e
                except Exception as e:
                    if isinstance(e, ValueError):
                        raise
                    logger.exception(f"Unexpected error in fallback extraction: {e}")
                    raise ValueError(f"Failed to extract text: {e}") from e
            
            if not full_text.strip():
                raise ValueError("No text extracted from file - file may be empty or corrupted")
            
            sections = [SectionText(index=0, title=None, content=full_text, section_path=None, metadata={})]
            logger.info(f"Created fallback section with {len(full_text)} characters")
        
        # Step 3: Chunk the document (same as regulations)
        logger.info(f"Chunking {len(sections)} sections...")
        try:
            chunker = SemanticChunker(config.chunking)
            # Use section-aware chunking for legislation (one chunk per section)
            payloads = chunker.chunk_sections(document.external_id, sections, section_aware=True)
            logger.info(f"Generated {len(payloads)} chunks")
        except Exception as e:
            logger.exception(f"Chunking failed: {e}")
            raise ValueError(f"Failed to chunk document: {e}") from e
        
        if not payloads:
            raise ValueError("No chunks generated from document")
        
        # Step 4: Create Chunk objects in database
        chunk_objects = []
        try:
            for idx, payload in enumerate(payloads):
                metadata = {
                    **payload.metadata,
                    "chunk_id": payload.chunk_id,
                    "section_path": payload.section_path,
                    "parent_heading": payload.parent_heading,
                }
                section_path = " > ".join(payload.section_path).strip() if payload.section_path else None
                chunk_row = Chunk(
                    document_id=document.id,
                    chunk_id=payload.chunk_id,
                    chunk_index=idx,
                    section_path=section_path,
                    parent_heading=payload.parent_heading,
                    content=payload.text,
                    token_count=payload.token_count,
                    chunk_metadata=metadata,
                    embedding_status="pending",  # Mark as pending for embedding
                )
                chunk_objects.append(chunk_row)
                db_session.add(chunk_row)
            
            db_session.commit()
            logger.info(f"Saved {len(chunk_objects)} chunks to database")
        except Exception as e:
            logger.exception(f"Failed to save chunks to database: {e}")
            db_session.rollback()
            raise ValueError(f"Database error saving chunks: {e}") from e
        
        # Step 5: Generate embeddings and store in ChromaDB (same as regulations)
        logger.info("Generating embeddings and storing in ChromaDB...")
        embedding_service = None
        try:
            embedding_service = EmbeddingService(db_session, config)
            # Process in batches (same as regenerate_regulation_vectors.py)
            batch_size = 1024
            total_processed = 0
            total_failed = 0
            
            for i in range(0, len(chunk_objects), batch_size):
                batch = chunk_objects[i:i + batch_size]
                batch_num = (i // batch_size) + 1
                total_batches = (len(chunk_objects) + batch_size - 1) // batch_size
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} chunks)...")
                
                try:
                    # Use the same collection name as regulations
                    result = embedding_service.process_chunks(batch, collection_name="regulation_chunks")
                    
                    total_processed += result["processed"]
                    total_failed += result["failed"]
                    
                    logger.info(f"  Processed: {result['processed']}, Failed: {result['failed']}")
                    
                    if result.get("error"):
                        logger.warning(f"Batch {batch_num} had errors: {result['error']}")
                except Exception as e:
                    logger.exception(f"Failed to process batch {batch_num}: {e}")
                    total_failed += len(batch)
                    # Continue with next batch instead of failing completely
                    continue
            
            if total_failed > 0:
                logger.warning(f"Embedding generation completed with {total_failed} failures out of {len(chunk_objects)} chunks")
            else:
                logger.info(f"Embedding generation complete: {total_processed} processed")
        except Exception as e:
            logger.exception(f"Embedding service failed: {e}")
            # Don't fail completely - chunks are already saved
            raise ValueError(f"Failed to generate embeddings: {e}") from e
        finally:
            if embedding_service:
                embedding_service.close()
        
        # Also create a Legislation record for UI tracking
        try:
            legislation = Legislation(
                filename=document.original_filename,
                file_path=document.storage_path,
                text_length=sum(len(s.content) for s in sections),
                num_chunks=len(chunk_objects),
            )
            db_session.add(legislation)
            db_session.commit()
            logger.info(f"Created legislation record: {legislation.id}")
        except Exception as e:
            logger.exception(f"Failed to create legislation record: {e}")
            db_session.rollback()
            raise ValueError(f"Database error creating legislation record: {e}") from e
        
        return {
            "id": legislation.id,
            "filename": document.original_filename,
            "path": document.storage_path,
            "text_length": sum(len(s.content) for s in sections),
            "num_chunks": len(chunk_objects),
        }
    
    except (ValueError, DocumentUploadError, ExtractionError) as e:
        # These are expected errors - log and re-raise
        logger.error(f"Legislation upload failed: {e}")
        if document:
            try:
                # Try to clean up the document if it was created
                db_session.delete(document)
                db_session.commit()
            except Exception:
                db_session.rollback()
        raise
    except Exception as e:
        # Unexpected errors - log and clean up
        logger.exception(f"Unexpected error in process_legislation_file: {e}")
        if document:
            try:
                db_session.delete(document)
                db_session.commit()
            except Exception:
                db_session.rollback()
        raise ValueError(f"Unexpected error processing legislation file: {e}") from e

