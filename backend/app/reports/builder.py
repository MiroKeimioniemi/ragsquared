from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from sqlalchemy import select

from ..db.models import Audit, Citation, Document, Flag
from ..db.session import get_session


@dataclass
class MarkdownReport:
    audit: Audit
    document: Document | None
    flags: list[Flag]


class ReportBuilder:
    def __init__(self, output_root: Path):
        self.output_root = output_root
        self.output_root.mkdir(parents=True, exist_ok=True)

    def build(self, audit_id: int, include_appendix: bool = True) -> Path:
        session = get_session()
        audit = session.get(Audit, audit_id)
        if audit is None:
            raise ValueError(f"Audit {audit_id} not found.")

        document = session.get(Document, audit.document_id)
        flags = (
            session.execute(select(Flag).where(Flag.audit_id == audit.id).order_by(Flag.severity_score.desc()))
            .scalars()
            .all()
        )

        md = self._render_markdown(MarkdownReport(audit, document, flags), include_appendix)
        output_path = self.output_root / f"audit_{audit.external_id}.md"
        output_path.write_text(md, encoding="utf-8")

        return output_path

    def _render_markdown(self, report: MarkdownReport, include_appendix: bool) -> str:
        audit = report.audit
        lines = [
            f"# Audit Report {audit.external_id}",
            "",
            "## Executive Summary",
            f"- Status: **{audit.status}**",
            f"- Total Chunks: {audit.chunk_total}",
            f"- Completed Chunks: {audit.chunk_completed}",
            f"- Flags: {len(report.flags)}",
        ]
        if report.document:
            lines.append(f"- Document: {report.document.original_filename}")
        lines.append("")
        lines.append("## Findings")

        if not report.flags:
            lines.append("No flags generated.")
        else:
            for flag in report.flags:
                lines.extend(self._render_flag(flag))

        if include_appendix:
            lines.append("")
            lines.append("## Appendix")
            lines.append("Additional metadata and raw findings can be added here.")

        return "\n".join(lines)

    def _render_flag(self, flag: Flag) -> list[str]:
        lines = [
            f"### Chunk {flag.chunk_id}",
            f"- Flag: **{flag.flag_type}** (Severity {flag.severity_score})",
            f"- Findings: {flag.findings}",
        ]
        if flag.gaps:
            lines.append(f"- Gaps: {', '.join(flag.gaps)}")
        if flag.recommendations:
            lines.append(f"- Recommendations: {', '.join(flag.recommendations)}")

        if flag.citations:
            lines.append("- Citations:")
            for citation in flag.citations:
                lines.append(f"  - {citation.citation_type.title()}: {citation.reference}")
        return lines

