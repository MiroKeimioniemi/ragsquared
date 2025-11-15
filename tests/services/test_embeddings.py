from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from backend.app.db.models import Chunk, Document
from backend.app.services.embeddings import EmbeddingService


def test_embedding_service_gets_pending_chunks(app):
    """Test that the service can retrieve pending chunks."""
    from backend.app.config.settings import AppConfig
    from backend.app.db.session import get_session

    session = get_session()
    config = AppConfig()

    # Create test document and chunks
    doc = Document(
        original_filename="test.pdf",
        stored_filename="test.pdf",
        storage_path="uploads/test.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        sha256="a" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()

    chunk1 = Chunk(
        document_id=doc.id,
        chunk_id="doc-chunk-1",
        chunk_index=0,
        section_path="Manual > 1",
        parent_heading="Section 1",
        content="Test chunk 1",
        token_count=10,
        embedding_status="pending",
    )
    chunk2 = Chunk(
        document_id=doc.id,
        chunk_id="doc-chunk-2",
        chunk_index=1,
        section_path="Manual > 2",
        parent_heading="Section 2",
        content="Test chunk 2",
        token_count=10,
        embedding_status="completed",
    )
    chunk3 = Chunk(
        document_id=doc.id,
        chunk_id="doc-chunk-3",
        chunk_index=2,
        section_path="Manual > 3",
        parent_heading="Section 3",
        content="Test chunk 3",
        token_count=10,
        embedding_status="pending",
    )
    session.add_all([chunk1, chunk2, chunk3])
    session.commit()

    # Test service
    service = EmbeddingService(session, config)
    pending = service.get_pending_chunks(doc_id=doc.external_id, limit=100)

    assert len(pending) == 2
    assert all(chunk.embedding_status == "pending" for chunk in pending)


def test_embedding_service_processes_chunks(app, monkeypatch):
    """Test that the service can process chunks and generate embeddings."""
    from backend.app.config.settings import AppConfig
    from backend.app.db.session import get_session

    session = get_session()
    config = AppConfig()

    # Create test document and chunks
    doc = Document(
        original_filename="test.pdf",
        stored_filename="test.pdf",
        storage_path="uploads/test.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        sha256="a" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()

    chunk1 = Chunk(
        document_id=doc.id,
        chunk_id="doc-chunk-4",
        chunk_index=0,
        section_path="Manual > 1",
        parent_heading="Section 1",
        content="Test chunk content for embedding",
        token_count=10,
        embedding_status="pending",
    )
    session.add(chunk1)
    session.commit()

    # Mock embedding client
    mock_embeddings = [[0.1, 0.2, 0.3] for _ in range(1)]

    with patch.object(
        EmbeddingService, "_store_in_chroma"
    ) as mock_store, patch(
        "backend.app.services.embeddings.EmbeddingClient.embed_texts",
        return_value=mock_embeddings,
    ):
        service = EmbeddingService(session, config)
        result = service.process_chunks([chunk1], collection_name="test_collection")

        assert result["processed"] == 1
        assert result["failed"] == 0

        # Verify chunk status updated
        session.refresh(chunk1)
        assert chunk1.embedding_status == "completed"

        # Verify ChromaDB store was called
        mock_store.assert_called_once()


def test_embedding_cache_key_generation():
    """Test that cache keys are generated consistently."""
    from backend.app.services.embeddings import EmbeddingService
    from backend.app.config.settings import AppConfig
    from backend.app.db.session import get_session

    session = get_session()
    config = AppConfig()
    service = EmbeddingService(session, config)

    text1 = "This is a test"
    text2 = "This is a test"
    text3 = "This is different"

    key1 = service._compute_cache_key(text1)
    key2 = service._compute_cache_key(text2)
    key3 = service._compute_cache_key(text3)

    assert key1 == key2
    assert key1 != key3
    assert len(key1) == 16  # First 16 chars of SHA256


def test_embedding_job_creation(app):
    """Test creating and updating embedding jobs."""
    from backend.app.config.settings import AppConfig
    from backend.app.db.session import get_session

    session = get_session()
    config = AppConfig()

    # Create test document
    doc = Document(
        original_filename="test.pdf",
        stored_filename="test.pdf",
        storage_path="uploads/test.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        sha256="a" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()

    # Create embedding job
    service = EmbeddingService(session, config)
    job = service.create_embedding_job(doc.id, job_type="manual")

    assert job.status == "pending"
    assert job.document_id == doc.id
    assert job.job_type == "manual"

    # Update job status
    service.update_job_status(job, "completed")
    session.refresh(job)

    assert job.status == "completed"
    assert job.completed_at is not None

