"""Review UI blueprint for viewing audit findings."""

from __future__ import annotations

from flask import Blueprint, jsonify, render_template, request

from ..config.settings import AppConfig
from ..db.models import Audit, AuditChunkResult, AuditorQuestion, Citation, Flag
from ..db.session import get_session
from ..logging_config import get_logger
from ..services.compliance_score import get_flag_summary
from ..services.final_report_generator import FinalReportGenerator

review_blueprint = Blueprint("review", __name__, url_prefix="/review")
logger = get_logger(__name__)


def _resolve_audit(session, identifier: str) -> Audit | None:
    """Resolve audit by ID or external_id."""
    if identifier.isdigit():
        return session.get(Audit, int(identifier))
    from sqlalchemy import select

    stmt = select(Audit).where(Audit.external_id == identifier)
    return session.execute(stmt).scalar_one_or_none()


@review_blueprint.route("/<audit_id>")
def review_audit(audit_id: str):
    """Render review page for an audit."""
    session = get_session()
    audit = _resolve_audit(session, audit_id)
    
    if audit is None:
        return render_template("error.html", message=f"Audit '{audit_id}' not found."), 404
    
    # Get filters from query parameters
    severity_filter = request.args.get("severity", "").upper()
    regulation_filter = request.args.get("regulation", "")
    
    # Build query
    from sqlalchemy import select
    
    query = select(Flag).where(Flag.audit_id == audit.id)
    
    if severity_filter:
        query = query.where(Flag.flag_type == severity_filter)
    
    if regulation_filter:
        query = query.join(Citation).where(
            Citation.citation_type == "regulation",
            Citation.reference.ilike(f"%{regulation_filter}%"),
        )
    
    flags = session.execute(query.order_by(Flag.severity_score.desc())).scalars().unique().all()
    
    # Get flag summary
    flag_summary = get_flag_summary(list(flags))
    
    # Get auditor questions
    questions = session.execute(
        select(AuditorQuestion)
        .where(AuditorQuestion.audit_id == audit.id)
        .order_by(AuditorQuestion.priority.asc())
    ).scalars().all()
    
    # Get citations for each flag
    flag_citations = {}
    # Get chunk results (which contain context summaries) for each flag
    flag_contexts = {}
    for flag in flags:
        citations = session.execute(
            select(Citation).where(Citation.flag_id == flag.id)
        ).scalars().all()
        flag_citations[flag.id] = citations
        
        # Get the chunk result to access context summary
        chunk_result = session.execute(
            select(AuditChunkResult).where(
                AuditChunkResult.audit_id == audit.id,
                AuditChunkResult.chunk_id == flag.chunk_id
            )
        ).scalar_one_or_none()
        
        if chunk_result and chunk_result.analysis:
            # Extract context summary from analysis
            context_summary = chunk_result.analysis.get("context_summary")
            if context_summary:
                flag_contexts[flag.id] = context_summary
    
    # Get unique regulation references for filter dropdown
    all_regulations = session.execute(
        select(Citation.reference)
        .join(Flag)
        .where(Flag.audit_id == audit.id, Citation.citation_type == "regulation")
        .distinct()
    ).scalars().all()
    
    return render_template(
        "review.html",
        audit=audit,
        flags=flags,
        flag_summary=flag_summary,
        questions=questions,
        flag_citations=flag_citations,
        flag_contexts=flag_contexts,
        severity_filter=severity_filter,
        regulation_filter=regulation_filter,
        regulations=sorted(set(all_regulations)),
    )


@review_blueprint.route("/<audit_id>/final-report", methods=["POST"])
def generate_final_report(audit_id: str):
    """Generate a comprehensive final report addressing all compliance issues."""
    session = get_session()
    audit = _resolve_audit(session, audit_id)
    
    if audit is None:
        return jsonify({"error": f"Audit '{audit_id}' not found."}), 404
    
    if audit.status != "completed":
        return jsonify({"error": "Audit must be completed before generating final report."}), 400
    
    try:
        config = AppConfig()
        generator = FinalReportGenerator(session, config)
        report = generator.generate_report(audit.id)
        
        # Convert to dict for JSON response
        return jsonify({
            "audit_id": audit.id,
            "external_id": audit.external_id,
            "executive_summary": report.executive_summary,
            "critical_issues": report.critical_issues,
            "warnings": report.warnings,
            "recommendations": report.recommendations,
            "overall_assessment": report.overall_assessment,
            "raw_content": report.raw_content,
        })
    except Exception as e:
        logger.exception(f"Error generating final report for audit {audit_id}: {e}")
        return jsonify({"error": str(e)}), 500

