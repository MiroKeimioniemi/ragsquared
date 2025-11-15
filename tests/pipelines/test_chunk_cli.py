from __future__ import annotations

import importlib
import json
from pathlib import Path

from typer.testing import CliRunner


def test_chunk_cli_persists_chunks(tmp_path: Path, monkeypatch):
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

    document = Document(
        external_id="doc-cli",
        original_filename="manual.md",
        stored_filename="manual.md",
        storage_path="uploads/manual.md",
        content_type="text/markdown",
        size_bytes=1024,
        sha256="b" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(document)
    session.commit()
    session.refresh(document)

    extracted_payload = {
        "sections": [
            {
                "index": 0,
                "title": "Introduction",
                "content": " ".join(["Alpha bravo charlie"] * 80),
                "metadata": {"section_path": ["Manual", "Introduction"]},
            },
            {
                "index": 1,
                "title": "Procedures",
                "content": " ".join(["Delta echo foxtrot"] * 40),
                "metadata": {},
            },
        ]
    }
    extracted_path = tmp_path / "extracted.json"
    extracted_path.write_text(json.dumps(extracted_payload), encoding="utf-8")

    chunk_module = importlib.reload(importlib.import_module("pipelines.chunk"))
    runner = CliRunner()

    result = runner.invoke(
        chunk_module.app,
        [str(extracted_path), "--doc-id", document.external_id, "--replace"],
    )

    assert result.exit_code == 0, result.stdout

    session.expire_all()
    chunks = session.query(Chunk).filter(Chunk.document_id == document.id).all()

    assert len(chunks) > 0
    assert chunks[0].chunk_id.startswith(document.external_id)
    assert chunks[0].section_path is not None

