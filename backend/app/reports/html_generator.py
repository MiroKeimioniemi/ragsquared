"""Static HTML report generator for offline viewing."""

from __future__ import annotations

from pathlib import Path

from flask import Flask

from ..db.models import Audit
from ..db.session import get_session
from .generator import ReportRequest


def generate_static_html(audit_id: int, output_dir: Path, app: Flask) -> Path:
    """
    Generate static HTML file for an audit review page.
    
    Args:
        audit_id: Audit ID
        output_dir: Directory to save HTML file
        app: Flask application instance
        
    Returns:
        Path to generated HTML file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    session = get_session()
    audit = session.get(Audit, audit_id)
    if audit is None:
        raise ValueError(f"Audit {audit_id} not found.")
    
    # Render template using Flask's render_template
    with app.app_context():
        from flask import render_template
        from ..api.review import _resolve_audit
        
        # Get audit data (reuse review blueprint logic)
        audit_obj = _resolve_audit(session, str(audit.external_id))
        if audit_obj is None:
            raise ValueError(f"Audit {audit_id} not found.")
        
        # Get filters (none for static HTML)
        from sqlalchemy import select
        from ..db.models import Citation, Flag, AuditorQuestion
        from ..services.compliance_score import get_flag_summary
        
        query = select(Flag).where(Flag.audit_id == audit_obj.id)
        flags = session.execute(query.order_by(Flag.severity_score.desc())).scalars().unique().all()
        
        flag_summary = get_flag_summary(list(flags))
        
        questions = session.execute(
            select(AuditorQuestion)
            .where(AuditorQuestion.audit_id == audit_obj.id)
            .order_by(AuditorQuestion.priority.asc())
        ).scalars().all()
        
        flag_citations = {}
        for flag in flags:
            citations = session.execute(
                select(Citation).where(Citation.flag_id == flag.id)
            ).scalars().all()
            flag_citations[flag.id] = citations
        
        all_regulations = session.execute(
            select(Citation.reference)
            .join(Flag)
            .where(Flag.audit_id == audit_obj.id, Citation.citation_type == "regulation")
            .distinct()
        ).scalars().all()
        
        html_content = render_template(
            "review.html",
            audit=audit_obj,
            flags=flags,
            flag_summary=flag_summary,
            questions=questions,
            flag_citations=flag_citations,
            severity_filter="",
            regulation_filter="",
            regulations=sorted(set(all_regulations)),
        )
    
    # Save to file
    output_path = output_dir / f"audit_{audit_obj.external_id}.html"
    output_path.write_text(html_content, encoding="utf-8")
    
    return output_path

