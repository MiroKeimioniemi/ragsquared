"""API endpoints for audit management."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from ..db.models import Audit, Document
from ..db.session import get_session

audits_blueprint = Blueprint("audits", __name__, url_prefix="/api")
audits_pages_blueprint = Blueprint("audits_pages", __name__)


@audits_blueprint.get("/audits")
def list_audits() -> tuple[dict[str, object], int]:
    """List all audits with optional filtering."""
    session = get_session()
    from sqlalchemy import select, desc
    
    # Get query parameters
    status_filter = request.args.get("status")
    is_draft = request.args.get("is_draft")
    limit = request.args.get("limit", type=int, default=50)
    
    # Build query
    query = select(Audit)
    
    if status_filter:
        query = query.where(Audit.status == status_filter)
    
    if is_draft is not None:
        is_draft_bool = str(is_draft).lower() in ("true", "1", "yes")
        query = query.where(Audit.is_draft == is_draft_bool)
    
    # Order by created_at descending
    query = query.order_by(desc(Audit.created_at)).limit(limit)
    
    audits = session.execute(query).scalars().all()
    
    # Get documents and scores for each audit
    from ..services.compliance_score import get_flag_summary
    from ..db.models import Flag
    
    result = []
    for audit in audits:
        document = session.get(Document, audit.document_id) if audit.document_id else None
        
        # Get flag summary if audit is completed
        flag_summary = None
        if audit.status == "completed":
            flags = session.execute(
                select(Flag).where(Flag.audit_id == audit.id)
            ).scalars().all()
            flag_summary = get_flag_summary(list(flags))
        
        result.append({
            "id": audit.id,
            "external_id": audit.external_id,
            "document_id": audit.document_id,
            "status": audit.status,
            "is_draft": audit.is_draft,
            "chunk_total": audit.chunk_total,
            "chunk_completed": audit.chunk_completed,
            "document": {
                "id": document.id if document else None,
                "external_id": document.external_id if document else None,
                "original_filename": document.original_filename if document else None,
            } if document else None,
            "started_at": audit.started_at.isoformat() if audit.started_at else None,
            "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
            "created_at": audit.created_at.isoformat(),
            "flag_summary": {
                "compliance_score": flag_summary.get("compliance_score") if flag_summary else None,
                "total_flags": flag_summary.get("total_flags", 0) if flag_summary else 0,
                "red_count": flag_summary.get("red_count", 0) if flag_summary else 0,
                "yellow_count": flag_summary.get("yellow_count", 0) if flag_summary else 0,
                "green_count": flag_summary.get("green_count", 0) if flag_summary else 0,
            } if flag_summary else None,
        })
    
    return jsonify({"audits": result, "count": len(result)})


@audits_blueprint.post("/audits")
def create_audit() -> tuple[dict[str, object], int]:
    """Create a new audit job for a document."""
    session = get_session()
    data = request.get_json() or {}

    document_id = data.get("document_id")
    if not document_id:
        return jsonify({"error": "document_id is required"}), 400

    # Resolve document (can be ID or external_id)
    if isinstance(document_id, str) and not document_id.isdigit():
        from sqlalchemy import select

        document = session.execute(select(Document).where(Document.external_id == document_id)).scalar_one_or_none()
    else:
        document = session.get(Document, int(document_id))

    if document is None:
        return jsonify({"error": f"Document '{document_id}' not found"}), 404

    # Check if draft mode is requested
    is_draft = data.get("is_draft", False)
    if not isinstance(is_draft, bool):
        is_draft = str(is_draft).lower() in ("true", "1", "yes")

    # Create audit
    audit = Audit(
        document_id=document.id,
        is_draft=is_draft,
        status="queued",
    )
    session.add(audit)
    session.commit()
    session.refresh(audit)

    return (
        jsonify(
            {
                "audit": {
                    "id": audit.id,
                    "external_id": audit.external_id,
                    "document_id": audit.document_id,
                    "status": audit.status,
                    "is_draft": audit.is_draft,
                    "created_at": audit.created_at.isoformat(),
                }
            }
        ),
        201,
    )


@audits_blueprint.get("/audits/<audit_id>")
def get_audit(audit_id: str) -> tuple[dict[str, object], int]:
    """Get audit details."""
    session = get_session()
    audit = _resolve_audit(session, audit_id)
    if audit is None:
        return jsonify({"error": "Audit not found"}), 404

    document = session.get(Document, audit.document_id) if audit.document_id else None

    return jsonify(
        {
            "audit": {
                "id": audit.id,
                "external_id": audit.external_id,
                "document_id": audit.document_id,
                "status": audit.status,
                "is_draft": audit.is_draft,
                "chunk_total": audit.chunk_total,
                "chunk_completed": audit.chunk_completed,
                "document": {
                    "id": document.id if document else None,
                    "external_id": document.external_id if document else None,
                    "original_filename": document.original_filename if document else None,
                    "filename": document.original_filename if document else None,
                }
                if document
                else None,
                "started_at": audit.started_at.isoformat() if audit.started_at else None,
                "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
                "created_at": audit.created_at.isoformat(),
            }
        }
    )


@audits_blueprint.get("/audits/<audit_id>/status")
def get_audit_status(audit_id: str) -> tuple[dict[str, object], int]:
    """Get audit status for polling - lightweight endpoint for real-time updates."""
    session = get_session()
    audit = _resolve_audit(session, audit_id)
    if audit is None:
        return jsonify({"error": "Audit not found"}), 404

    # Calculate progress percentage
    progress_percent = 0.0
    if audit.chunk_total > 0:
        progress_percent = (audit.chunk_completed / audit.chunk_total) * 100

    # Determine current activity message
    current_activity = None
    if audit.status == "queued":
        current_activity = "Waiting in queue..."
    elif audit.status == "running":
        if audit.chunk_total == 0:
            current_activity = "Initializing audit process..."
        elif audit.chunk_completed == 0:
            current_activity = f"Starting analysis of {audit.chunk_total} chunks..."
        elif audit.last_chunk_id:
            # Show more detailed progress
            progress_pct = (audit.chunk_completed / audit.chunk_total * 100) if audit.chunk_total > 0 else 0
            current_activity = (
                f"Analyzing chunk {audit.chunk_completed + 1} of {audit.chunk_total} "
                f"({progress_pct:.1f}% complete)"
            )
        else:
            current_activity = f"Analyzing chunk {audit.chunk_completed + 1} of {audit.chunk_total}"
    elif audit.status == "completed":
        current_activity = f"Audit completed successfully - {audit.chunk_completed} chunks analyzed"
    elif audit.status == "failed":
        # Truncate failure reason for display if too long
        failure_msg = audit.failure_reason or "Unknown error"
        if len(failure_msg) > 200:
            failure_msg = failure_msg[:197] + "..."
        current_activity = f"Audit failed: {failure_msg}"
    else:
        current_activity = f"Status: {audit.status}"

    # Calculate ETA if running
    eta_seconds = None
    eta_formatted = None
    if audit.status == "running" and audit.started_at and audit.chunk_completed > 0 and audit.chunk_total > 0:
        from datetime import datetime, timezone
        # Handle both timezone-aware and naive datetimes
        if audit.started_at.tzinfo is None:
            # Naive datetime - assume UTC
            started_at_aware = audit.started_at.replace(tzinfo=timezone.utc)
        else:
            started_at_aware = audit.started_at
        elapsed = (datetime.now(timezone.utc) - started_at_aware).total_seconds()
        if elapsed > 0 and audit.chunk_completed > 0:
            rate = audit.chunk_completed / elapsed  # chunks per second
            remaining_chunks = audit.chunk_total - audit.chunk_completed
            if rate > 0:
                eta_seconds = remaining_chunks / rate
                # Format ETA
                if eta_seconds < 60:
                    eta_formatted = f"{int(eta_seconds)}s"
                elif eta_seconds < 3600:
                    eta_formatted = f"{int(eta_seconds / 60)}m {int(eta_seconds % 60)}s"
                else:
                    hours = int(eta_seconds / 3600)
                    minutes = int((eta_seconds % 3600) / 60)
                    eta_formatted = f"{hours}h {minutes}m"

    return jsonify(
        {
            "status": audit.status,
            "chunk_total": audit.chunk_total,
            "chunk_completed": audit.chunk_completed,
            "progress_percent": round(progress_percent, 1),
            "current_activity": current_activity,
            "last_chunk_id": audit.last_chunk_id,
            "eta_seconds": eta_seconds,
            "eta_formatted": eta_formatted,
            "started_at": audit.started_at.isoformat() if audit.started_at else None,
            "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
            "failed_at": audit.failed_at.isoformat() if audit.failed_at else None,
            "failure_reason": audit.failure_reason,
            "is_draft": audit.is_draft,
        }
    )


@audits_blueprint.post("/audits/<audit_id>/resume")
def resume_audit(audit_id: str) -> tuple[dict[str, object], int]:
    """Resume/restart processing of a stuck or failed audit."""
    import threading
    from flask import current_app
    
    session = get_session()
    audit = _resolve_audit(session, audit_id)
    
    if not audit:
        return jsonify({"error": f"Audit '{audit_id}' not found."}), 404
    
    # Check if audit can be resumed
    if audit.status == "completed":
        return jsonify({"error": "Cannot resume a completed audit."}), 400
    
    # Reset status to "running" if it was "failed"
    if audit.status == "failed":
        audit.status = "running"
        audit.failure_reason = None
        session.commit()
    
    # Import here to avoid circular imports
    from ..config.settings import AppConfig
    from ..services.compliance_runner import ComplianceRunner
    from ..logging_config import get_logger
    
    logger = get_logger(__name__)
    
    def resume_audit_background():
        """Background thread function to resume audit processing."""
        app = current_app._get_current_object()
        with app.app_context():
            session = get_session()
            config = AppConfig()
            try:
                runner = ComplianceRunner(session, config)
                result = runner.run(
                    audit_id,
                    max_chunks=None,  # Process all remaining chunks
                    include_evidence=not audit.is_draft,
                )
                logger.info(
                    "Audit resume completed",
                    audit_id=audit_id,
                    processed=result.processed,
                    remaining=result.remaining,
                    status=result.status,
                )
            except Exception as exc:
                logger.exception(
                    "Error resuming audit in background",
                    audit_id=audit_id,
                    error=str(exc),
                )
                # Mark audit as failed if it wasn't already
                session = get_session()
                audit = _resolve_audit(session, audit_id)
                if audit and audit.status == "running":
                    audit.status = "failed"
                    audit.failure_reason = f"Resume failed: {str(exc)}"
                    session.commit()
    
    # Start background thread to resume audit
    resume_thread = threading.Thread(
        target=resume_audit_background,
        daemon=True,
    )
    resume_thread.start()
    logger.info("Started background thread to resume audit", audit_id=audit_id)
    
    return jsonify({
        "message": "Audit resume started in background",
        "audit_id": audit_id,
        "status": "running",
    }), 200


@audits_pages_blueprint.route("/dashboard", methods=["GET"])
def list_audits_page():
    """Render the audit dashboard page."""
    session = get_session()
    from sqlalchemy import select, desc
    
    # Get query parameters
    status_filter = request.args.get("status")
    is_draft = request.args.get("is_draft")
    limit = request.args.get("limit", type=int, default=50)
    
    # Build query
    query = select(Audit)
    
    if status_filter:
        query = query.where(Audit.status == status_filter)
    
    if is_draft is not None:
        is_draft_bool = str(is_draft).lower() in ("true", "1", "yes")
        query = query.where(Audit.is_draft == is_draft_bool)
    
    # Order by created_at descending
    query = query.order_by(desc(Audit.created_at)).limit(limit)
    
    audits = session.execute(query).scalars().all()
    
    # Get documents and scores for each audit
    from ..services.compliance_score import get_flag_summary
    from ..db.models import Flag
    
    audit_list = []
    for audit in audits:
        document = session.get(Document, audit.document_id) if audit.document_id else None
        
        # Get flag summary if audit is completed
        flag_summary = None
        if audit.status == "completed":
            flags = session.execute(
                select(Flag).where(Flag.audit_id == audit.id)
            ).scalars().all()
            flag_summary = get_flag_summary(list(flags))
        
        audit_list.append({
            "audit": audit,
            "document": document,
            "flag_summary": flag_summary,
        })
    
    return render_template("dashboard.html", audits=audit_list, status_filter=status_filter, is_draft=is_draft)


def _resolve_audit(session, identifier: str):
    """Resolve audit by ID or external_id."""
    if identifier.isdigit():
        return session.get(Audit, int(identifier))
    from sqlalchemy import select

    stmt = select(Audit).where(Audit.external_id == identifier)
    return session.execute(stmt).scalar_one_or_none()

