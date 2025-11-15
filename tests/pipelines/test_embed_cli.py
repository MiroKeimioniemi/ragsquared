from __future__ import annotations

import importlib
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner


def test_embed_cli_shows_pending_chunks_in_dry_run(tmp_path: Path, monkeypatch):
    """Test that embed CLI shows pending chunks in dry-run mode."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    db_path = tmp_path / "app.db"

    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")

    from backend.app import create_app
    from backend.app.db.models import Chunk, Document
    from backend.app.db.session import get_session

    create_app()
    session = get_session()

    # Create test document with pending chunks
    document = Document(
        external_id="doc-embed-test",
        original_filename="manual.pdf",
        stored_filename="manual.pdf",
        storage_path="uploads/manual.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        sha256="c" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    # Add pending chunks
    for i in range(5):
        chunk = Chunk(
            document_id=document.id,
            chunk_id=f"{document.external_id}_{i}",
            chunk_index=i,
            section_path=f"Manual > Section {i}",
            parent_heading=f"Section {i}",
            content=f"Test chunk content {i}" * 20,
            token_count=50,
            embedding_status="pending",
        )
        session.add(chunk)
    session.commit()

    # Run CLI in dry-run mode
    embed_module = importlib.reload(importlib.import_module("pipelines.embed"))
    runner = CliRunner()

    result = runner.invoke(
        embed_module.app,
        ["--doc-id", document.external_id, "--dry-run"],
    )

    assert result.exit_code == 0, result.stdout
    assert "Found 5 pending chunks" in result.stdout
    assert "Dry run mode" in result.stdout


def test_embed_cli_processes_chunks(tmp_path: Path, monkeypatch):
    """Test that embed CLI processes chunks and updates status."""
    data_root = tmp_path / "data"
    data_root.mkdir()
    db_path = tmp_path / "app.db"

    monkeypatch.setenv("DATA_ROOT", str(data_root))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("EMBEDDING_MODEL", "text-embedding-3-small")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    from backend.app import create_app
    from backend.app.db.models import Chunk, Document
    from backend.app.db.session import get_session

    create_app()
    session = get_session()

    # Create test document with pending chunks
    document = Document(
        external_id="doc-embed-real",
        original_filename="manual.pdf",
        stored_filename="manual.pdf",
        storage_path="uploads/manual.pdf",
        content_type="application/pdf",
        size_bytes=2048,
        sha256="d" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    # Add pending chunks
    chunks_to_add = []
    for i in range(3):
        chunk = Chunk(
            document_id=document.id,
            chunk_id=f"{document.external_id}_{i}",
            chunk_index=i,
            section_path=f"Manual > Section {i}",
            parent_heading=f"Section {i}",
            content=f"Test chunk content {i}" * 20,
            token_count=50,
            embedding_status="pending",
        )
        chunks_to_add.append(chunk)
    session.add_all(chunks_to_add)
    session.commit()

    # Mock the embedding generation and ChromaDB storage
    mock_embeddings = [[0.1, 0.2, 0.3] for _ in range(3)]

    with patch(
        "backend.app.services.embeddings.EmbeddingClient.embed_texts",
        return_value=mock_embeddings,
    ), patch(
        "backend.app.services.embeddings.EmbeddingService._store_in_chroma"
    ):
        embed_module = importlib.reload(importlib.import_module("pipelines.embed"))
        runner = CliRunner()

        result = runner.invoke(
            embed_module.app,
            ["--doc-id", document.external_id, "--batch-size", "10"],
        )

        assert result.exit_code == 0, result.stdout
        assert "Embedding generation complete" in result.stdout

        # Verify chunks are marked as completed
        session.expire_all()
        completed_chunks = (
            session.query(Chunk)
            .filter(
                Chunk.document_id == document.id,
                Chunk.embedding_status == "completed",
            )
            .all()
        )

        assert len(completed_chunks) == 3

