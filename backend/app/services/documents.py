from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from sqlalchemy.orm import Session
from werkzeug.datastructures import FileStorage

from ..db.models import Document


class DocumentUploadError(Exception):
    """Raised when a document upload fails validation or persistence."""


@dataclass
class StoredUpload:
    relative_path: Path
    stored_filename: str
    size_bytes: int
    sha256: str
    content_type: str
    original_filename: str


class DocumentService:
    ALLOWED_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".html"}
    ALLOWED_SOURCE_TYPES = {"manual", "regulation", "amc", "gm", "evidence"}
    DEFAULT_SOURCE_TYPE = "manual"

    def __init__(self, data_root: Path, session: Session):
        self.data_root = Path(data_root)
        self.session = session
        self.upload_root = self.data_root / "uploads"

    def create_from_upload(
        self,
        upload: FileStorage,
        *,
        source: str | None = None,
        source_type: str | None = None,
        organization: str | None = None,
        description: str | None = None,
    ) -> Document:
        if upload is None:
            raise DocumentUploadError("File payload is required.")
        if not upload.filename:
            raise DocumentUploadError("Uploaded file must include a filename.")

        extension = Path(upload.filename).suffix.lower()
        if extension not in self.ALLOWED_EXTENSIONS:
            allowed = ", ".join(sorted(ext.strip(".") for ext in self.ALLOWED_EXTENSIONS))
            raise DocumentUploadError(f"Unsupported file type '{extension}'. Allowed: {allowed}.")

        stored = self._persist_file(upload, extension)

        resolved_source = self.DEFAULT_SOURCE_TYPE
        if source_type:
            resolved_source = self._normalize_source_type(source_type)
        elif source and source.lower() in self.ALLOWED_SOURCE_TYPES:
            resolved_source = self._normalize_source_type(source)

        org_value = organization
        if org_value is None and source and source.lower() not in self.ALLOWED_SOURCE_TYPES:
            org_value = source

        document = Document(
            original_filename=stored.original_filename,
            stored_filename=stored.stored_filename,
            storage_path=str(stored.relative_path).replace("\\", "/"),
            content_type=stored.content_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            status="uploaded",
            source_type=resolved_source,
            organization=org_value,
            description=description,
        )

        self.session.add(document)
        self.session.commit()
        self.session.refresh(document)
        return document

    def _persist_file(self, upload: FileStorage, extension: str) -> StoredUpload:
        date_folder = datetime.utcnow().strftime("%Y/%m/%d")
        target_dir = self.upload_root / date_folder
        target_dir.mkdir(parents=True, exist_ok=True)

        stored_filename = f"{uuid4().hex}{extension}"
        destination = target_dir / stored_filename

        stream = upload.stream
        try:
            stream.seek(0)
        except (AttributeError, OSError):
            pass

        size_bytes, sha256_hash = self._stream_to_disk(stream, destination)
        if size_bytes == 0:
            raise DocumentUploadError("Uploaded file is empty.")

        content_type = (
            upload.mimetype
            or mimetypes.guess_type(upload.filename)[0]
            or "application/octet-stream"
        )

        return StoredUpload(
            relative_path=destination.relative_to(self.data_root),
            stored_filename=stored_filename,
            size_bytes=size_bytes,
            sha256=sha256_hash,
            content_type=content_type,
            original_filename=Path(upload.filename).name,
        )

    @staticmethod
    def _stream_to_disk(stream: BinaryIO, destination: Path) -> tuple[int, str]:
        sha256 = hashlib.sha256()
        total_bytes = 0
        with destination.open("wb") as output:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                sha256.update(chunk)
                total_bytes += len(chunk)
                output.write(chunk)

        return total_bytes, sha256.hexdigest()

    def _normalize_source_type(self, candidate: str | None) -> str:
        if not candidate:
            return self.DEFAULT_SOURCE_TYPE
        normalized = candidate.strip().lower()
        if normalized not in self.ALLOWED_SOURCE_TYPES:
            allowed = ", ".join(sorted(self.ALLOWED_SOURCE_TYPES))
            raise DocumentUploadError(
                f"Unsupported source_type '{candidate}'. Allowed values: {allowed}."
            )
        return normalized


