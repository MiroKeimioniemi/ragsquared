from __future__ import annotations

import threading
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from ..config.settings import AppConfig
from ..db.models import Audit
from ..db.session import get_session
from ..logging_config import get_logger
from ..services.documents import DocumentService, DocumentUploadError
from ..services.document_processor import DocumentProcessor, DocumentProcessingError

documents_blueprint = Blueprint("documents", __name__, url_prefix="/api")
documents_pages_blueprint = Blueprint("documents_pages", __name__)
logger = get_logger(__name__)


@documents_pages_blueprint.route("/documents/upload", methods=["GET"])
def upload_page():
    """Render the document upload page."""
    return render_template("upload.html")


def _process_document_background(document_id: int, is_draft: bool, data_root: Path) -> None:
    """Background thread function to process document."""
    from .. import create_app
    from datetime import datetime
    
    app = create_app()
    with app.app_context():
        session = get_session()
        config = AppConfig()
        
        try:
            from ..db.models import Document, Audit
            
            document = session.get(Document, document_id)
            if not document:
                logger.error(f"Document {document_id} not found for processing")
                return
            
            # Find the audit and update status to "running"
            audit = (
                session.query(Audit)
                .filter(Audit.document_id == document.id)
                .order_by(Audit.created_at.desc())
                .first()
            )
            
            if audit:
                audit.status = "running"
                if audit.started_at is None:
                    from datetime import timezone
                    audit.started_at = datetime.now(timezone.utc)
                session.commit()
                logger.info(f"Started processing document {document_id}, audit {audit.id}")
            
            processor = DocumentProcessor(data_root, session, config)
            result = processor.process_document(
                document,
                run_audit=True,
                is_draft=is_draft,
            )
            logger.info(f"Document {document_id} processed successfully: {result}")
        except Exception as exc:
            logger.exception(f"Error processing document {document_id} in background: {exc}")
            # Update audit status to failed
            try:
                from ..db.models import Audit
                audit = (
                    session.query(Audit)
                    .filter(Audit.document_id == document_id)
                    .order_by(Audit.created_at.desc())
                    .first()
                )
                if audit:
                    audit.status = "failed"
                    from datetime import timezone
                    audit.failed_at = datetime.now(timezone.utc)
                    audit.failure_reason = str(exc)
                    session.commit()
                    logger.error(f"Marked audit {audit.id} as failed due to error: {exc}")
            except Exception as update_exc:
                logger.exception(f"Failed to update audit status: {update_exc}")


@documents_blueprint.post("/documents")
def upload_document() -> tuple[dict[str, object], int]:
    if "file" not in request.files:
        return jsonify({"error": "Request must include a file field named 'file'."}), 400

    upload = request.files["file"]
    session = get_session()
    data_root = current_app.config.get("data_root") or current_app.config.get("DATA_ROOT") or "./data"
    service = DocumentService(Path(data_root), session)

    try:
        document = service.create_from_upload(
            upload,
            source=request.form.get("source"),
            source_type=request.form.get("source_type"),
            organization=request.form.get("organization"),
            description=request.form.get("description"),
        )
    except DocumentUploadError as exc:
        session.rollback()
        return jsonify({"error": str(exc)}), 400

    # Automatically create an audit for the uploaded document
    # Check if draft mode is requested (default to False for full audit)
    is_draft = request.form.get("is_draft", "false").lower() in ("true", "1", "yes")
    
    audit = Audit(
        document_id=document.id,
        is_draft=is_draft,
        status="queued",
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)

    # Start background processing
    # Only process manuals automatically (regulations/AMC/GM need manual processing)
    if document.source_type == "manual":
        processing_thread = threading.Thread(
            target=_process_document_background,
            args=(document.id, is_draft, Path(data_root)),
            daemon=True,
        )
        processing_thread.start()
        logger.info(f"Started background processing for document {document.id}")

    return jsonify({
        "document": document.to_dict(),
        "audit": {
            "id": audit.id,
            "external_id": audit.external_id,
            "document_id": audit.document_id,
            "status": audit.status,
            "is_draft": audit.is_draft,
            "created_at": audit.created_at.isoformat(),
        },
        "processing": {
            "status": "queued" if document.source_type == "manual" else "manual",
            "message": "Document will be processed automatically" if document.source_type == "manual" else "Document uploaded. Process manually via CLI.",
        }
    }), 201


