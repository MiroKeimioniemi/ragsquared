from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from backend.app.db.models import Document
from backend.app.db.session import get_session


def test_upload_document_success(client, app):
    payload = BytesIO(b"This is a sample Part-145 manual excerpt.")
    response = client.post(
        "/documents",
        data={
            "file": (payload, "sample.pdf"),
            "source": "unit-test",
            "description": "Test upload",
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 201
    data = response.json["document"]

    assert data["original_filename"] == "sample.pdf"
    assert data["status"] == "uploaded"
    assert data["source"] == "unit-test"

    expected_sha = hashlib.sha256(b"This is a sample Part-145 manual excerpt.").hexdigest()
    assert data["sha256"] == expected_sha

    data_root = app.config.get("data_root") or app.config.get("DATA_ROOT") or "./data"
    stored_path = Path(data_root) / data["storage_path"]
    assert stored_path.exists()
    assert stored_path.read_bytes() == b"This is a sample Part-145 manual excerpt."

    session = get_session()
    db_document = session.get(Document, data["id"])
    assert db_document is not None
    assert db_document.sha256 == expected_sha


def test_upload_document_rejects_invalid_extension(client):
    response = client.post(
        "/documents",
        data={"file": (BytesIO(b"bad"), "script.exe")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert "Unsupported file type" in response.json["error"]


