from __future__ import annotations

from datetime import datetime
from pathlib import Path

from flask import Blueprint, current_app, jsonify
from sqlalchemy import select, func

from ..db.models import Audit, EmbeddingJob
from ..db.session import get_session
from ..logging_config import get_logger

api_blueprint = Blueprint("core", __name__)
logger = get_logger(__name__)


@api_blueprint.get("/")
def root() -> tuple[dict[str, str], int]:
    return (
        {
            "message": "AI-Assisted auditing backend is alive.",
            "docs": "Refer to AI_Auditing_System_Design.md for scope.",
        },
        200,
    )


@api_blueprint.get("/healthz")
def healthcheck() -> tuple[dict[str, object], int]:
    """Enhanced health check endpoint with DB connectivity and queue status."""
    data_root = Path(current_app.config.get("data_root", "./data"))
    health_status = "ok"
    checks = {}
    
    # Check data root
    checks["data_root"] = "ok" if data_root.exists() else "missing"
    if not data_root.exists():
        health_status = "degraded"
    
    # Check database connectivity
    try:
        session = get_session()
        # Simple query to test connectivity
        session.execute(select(func.count()).select_from(Audit)).scalar()
        checks["database"] = "ok"
        session.close()
    except Exception as e:
        logger.warning("Database health check failed", error=str(e))
        checks["database"] = "error"
        health_status = "unhealthy"
    
    # Check pending jobs
    try:
        session = get_session()
        pending_audits = session.execute(
            select(func.count()).select_from(Audit).where(Audit.status.in_(["queued", "running"]))
        ).scalar() or 0
        
        pending_embeddings = session.execute(
            select(func.count()).select_from(EmbeddingJob).where(EmbeddingJob.status == "pending")
        ).scalar() or 0
        
        checks["pending_audits"] = pending_audits
        checks["pending_embeddings"] = pending_embeddings
        session.close()
    except Exception as e:
        logger.warning("Job status check failed", error=str(e))
        checks["pending_audits"] = "unknown"
        checks["pending_embeddings"] = "unknown"
    
    response = {
        "status": health_status,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "checks": checks,
    }
    
    status_code = 200 if health_status == "ok" else 503 if health_status == "unhealthy" else 200
    return response, status_code

