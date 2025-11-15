from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import select

from ..db.models import Audit, AuditorQuestion, Citation, Flag
from ..db.session import get_session

findings_blueprint = Blueprint("findings", __name__, url_prefix="/api")


@findings_blueprint.get("/audits/<audit_id>/flags")
def list_flags(audit_id: str):
    session = get_session()
    audit = _resolve_audit(session, audit_id)
    if audit is None:
        return jsonify({"error": "Audit not found."}), 404

    page = max(1, int(request.args.get("page", 1)))
    page_size = min(100, max(1, int(request.args.get("page_size", 20))))
    offset = (page - 1) * page_size
    include_questions = request.args.get("include_questions", "0") == "1"

    query = select(Flag).where(Flag.audit_id == audit.id)
    severity = request.args.get("severity")
    if severity:
        query = query.where(Flag.flag_type == severity.strip().upper())

    regulation = request.args.get("regulation")
    if regulation:
        query = query.join(Citation).where(
            Citation.citation_type == "regulation",
            Citation.reference.ilike(f"%{regulation.strip()}%"),
        )

    total = len(session.execute(query.with_only_columns(Flag.id)).scalars().unique().all())
    rows = (
        session.execute(
            query.order_by(Flag.severity_score.desc()).offset(offset).limit(page_size)
        )
        .scalars()
        .unique()
        .all()
    )

    response_data = {
        "audit": {"id": audit.id, "external_id": audit.external_id},
        "pagination": {"page": page, "page_size": page_size, "total": total},
        "flags": [
            {
                "flag_id": flag.id,
                "chunk_id": flag.chunk_id,
                "flag_type": flag.flag_type,
                "severity_score": flag.severity_score,
                "findings": flag.findings,
                "gaps": flag.gaps,
                "recommendations": flag.recommendations,
                "citations": [
                    {"type": citation.citation_type, "reference": citation.reference}
                    for citation in flag.citations
                ],
                "analysis_metadata": flag.analysis_metadata,
                "updated_at": flag.updated_at.isoformat(),
            }
            for flag in rows
        ],
    }

    if include_questions:
        questions = (
            session.execute(
                select(AuditorQuestion)
                .where(AuditorQuestion.audit_id == audit.id)
                .order_by(AuditorQuestion.priority.asc(), AuditorQuestion.id.asc())
            )
            .scalars()
            .all()
        )
        response_data["questions"] = [
            {
                "question_id": q.id,
                "regulation_reference": q.regulation_reference,
                "question_text": q.question_text,
                "priority": q.priority,
                "rationale": q.rationale,
                "related_flag_ids": q.related_flag_ids,
                "question_metadata": q.question_metadata,
                "created_at": q.created_at.isoformat(),
            }
            for q in questions
        ]

    return jsonify(response_data)


def _resolve_audit(session, identifier: str):
    if identifier.isdigit():
        return session.get(Audit, int(identifier))
    stmt = select(Audit).where(Audit.external_id == identifier)
    return session.execute(stmt).scalar_one_or_none()

