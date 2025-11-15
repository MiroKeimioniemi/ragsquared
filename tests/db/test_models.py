from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from backend.app.db.models import Chunk, Document, EmbeddingJob
from backend.app.db.session import get_session


def test_document_chunk_and_embedding_relationships(app):
    session = get_session()

    doc = Document(
        original_filename="manual.md",
        stored_filename="abc123.md",
        storage_path="uploads/manuals/abc123.md",
        content_type="text/markdown",
        size_bytes=128,
        sha256="a" * 64,
        status="uploaded",
        source_type="manual",
        organization="Test Org",
        description="Test document",
    )
    session.add(doc)
    session.commit()

    chunk = Chunk(
        document_id=doc.id,
        chunk_id="doc-chunk-0001",
        chunk_index=0,
        section_path="Manual > Section 1",
        parent_heading="Section 1",
        content="Section 1 content",
        token_count=42,
        chunk_metadata={"section": "1.0"},
    )
    session.add(chunk)

    job = EmbeddingJob(document_id=doc.id, status="pending", job_type="manual")
    session.add(job)
    session.commit()

    session.refresh(doc)
    assert doc.chunks[0].content == "Section 1 content"
    assert doc.embedding_jobs[0].status == "pending"


def test_chunk_id_unique_constraint(app):
    session = get_session()

    doc = Document(
        original_filename="manual.md",
        stored_filename="abc123.md",
        storage_path="uploads/manuals/abc123.md",
        content_type="text/markdown",
        size_bytes=128,
        sha256="a" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()

    chunk_a = Chunk(
        document_id=doc.id,
        chunk_id="dup-chunk",
        chunk_index=0,
        content="Chunk A",
        token_count=20,
    )
    chunk_b = Chunk(
        document_id=doc.id,
        chunk_id="dup-chunk",
        chunk_index=1,
        content="Chunk B",
        token_count=20,
    )
    session.add_all([chunk_a, chunk_b])

    with pytest.raises(IntegrityError):
        session.commit()
    session.rollback()


