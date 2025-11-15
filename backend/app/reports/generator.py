from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import select

from ..db.models import Audit, AuditorQuestion, Citation, Document, Flag
from ..db.session import get_session


@dataclass
class ReportRequest:
    audit_id: int
    include_appendix: bool = True


class ReportGenerator:
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

    def render_markdown(self, request: ReportRequest) -> Path:
        session = get_session()
        audit = session.get(Audit, request.audit_id)
        if audit is None:
            raise ValueError(f"Audit {request.audit_id} not found.")

        document = session.get(Document, audit.document_id)
        flags = (
            session.execute(select(Flag).where(Flag.audit_id == audit.id).order_by(Flag.severity_score.desc()))
            .scalars()
            .all()
        )
        questions = (
            session.execute(
                select(AuditorQuestion)
                .where(AuditorQuestion.audit_id == audit.id)
                .order_by(AuditorQuestion.priority.asc(), AuditorQuestion.id.asc())
            )
            .scalars()
            .all()
        )

        md = self._render_md(audit, document, flags, questions, request.include_appendix)
        output_path = self.output_root / f"audit_{audit.external_id}.md"
        output_path.write_text(md, encoding="utf-8")
        return output_path

    def render_pdf(self, request: ReportRequest) -> Path:
        markdown_path = self.render_markdown(request)
        pdf_path = markdown_path.with_suffix(".pdf")
        try:
            from md2pdf.core import md2pdf  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("md2pdf is required for PDF export. Install with `pip install md2pdf`.") from exc

        md2pdf(pdf_path, source_file=markdown_path)
        return pdf_path

    def render_html(self, request: ReportRequest, app: Flask) -> Path:
        """Render a static HTML review page for an audit."""
        from .html_generator import generate_static_html
        
        html_dir = self.output_root / "html"
        return generate_static_html(request.audit_id, html_dir, app)

    def _render_md(
        self,
        audit: Audit,
        document: Document | None,
        flags: Iterable[Flag],
        questions: Iterable[AuditorQuestion],
        include_appendix: bool,
    ) -> str:
        flag_list = list(flags)
        severity_counts = Counter(flag.flag_type for flag in flag_list)

        lines = [
            f"# Audit Report: {audit.external_id}",
            "",
            "## Executive Summary",
            f"- Status: **{audit.status.upper()}**",
        ]
        if audit.is_draft:
            lines.append("- **Mode: DRAFT** (Limited processing - reduced chunks and context)")
        lines.extend(
            [
                f"- Total Chunks: {audit.chunk_total}",
                f"- Completed Chunks: {audit.chunk_completed}",
                f"- Flags: {len(flag_list)} (RED: {severity_counts.get('RED', 0)}, "
                f"YELLOW: {severity_counts.get('YELLOW', 0)}, GREEN: {severity_counts.get('GREEN', 0)})",
            ]
        )
        if document:
            lines.append(f"- Document: {document.original_filename}")
        lines.append("")
        lines.append("## Detailed Findings")

        for flag in flag_list:
            lines.extend(self._render_flag_section(flag))

        # Add auditor questions section
        question_list = list(questions)
        if question_list:
            lines.append("")
            lines.append("## Auditor Questions")
            lines.append("Prioritized review questions for manual auditors:")
            lines.append("")

            # Group by regulation reference
            from collections import defaultdict

            by_regulation = defaultdict(list)
            for q in question_list:
                by_regulation[q.regulation_reference].append(q)

            for reg_ref, reg_questions in sorted(by_regulation.items()):
                lines.append(f"### {reg_ref}")
                for q in reg_questions:
                    lines.append(f"{q.priority}. **{q.question_text}**")
                    if q.rationale:
                        lines.append(f"   *Rationale: {q.rationale}*")
                    lines.append("")

        if include_appendix:
            lines.append("")
            lines.append("## Appendix")
            lines.append("Full flag metadata, citations, and timestamps can be expanded here.")

        return "\n".join(lines)

    def _render_flag_section(self, flag: Flag) -> list[str]:
        entries = [
            f"### Chunk {flag.chunk_id}",
            f"- Flag: **{flag.flag_type}** ({flag.severity_score})",
            f"- Findings: {flag.findings}",
        ]
        if flag.gaps:
            entries.append(f"- Gaps: {', '.join(flag.gaps)}")
        if flag.recommendations:
            entries.append(f"- Recommendations: {', '.join(flag.recommendations)}")

        citation_lines = []
        for citation in flag.citations:
            citation_lines.append(f"  - {citation.citation_type.title()}: {citation.reference}")
        if citation_lines:
            entries.append("- Citations:\n" + "\n".join(citation_lines))

        return entries

