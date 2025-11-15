from __future__ import annotations

import logging
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Audit, Citation, Flag

logger = logging.getLogger(__name__)


class FlagSynthesizer:
    """Maps normalized analysis payloads into persisted flags and citations."""

    def __init__(self, session: Session):
        self.session = session

    def upsert_flag(self, audit_id: int, chunk_id: str, analysis: dict[str, Any]) -> Flag:
        flag_type = self._resolve_flag_type(
            analysis.get("flag"),
            analysis.get("severity_score"),
        )
        severity_score = int(analysis.get("severity_score") or 0)
        findings = analysis.get("findings") or ""
        if not findings:
            findings = "No findings provided."

        stmt = (
            select(Flag)
            .where(Flag.audit_id == audit_id)
            .where(Flag.chunk_id == chunk_id)
        )
        flag = self.session.execute(stmt).scalar_one_or_none()
        if flag is None:
            flag = Flag(audit_id=audit_id, chunk_id=chunk_id)
            self.session.add(flag)

        flag.flag_type = flag_type
        flag.severity_score = severity_score
        flag.findings = findings
        flag.gaps = analysis.get("gaps") or []
        flag.recommendations = analysis.get("recommendations") or []
        flag.analysis_metadata = {
            "flag": analysis.get("flag"),
            "needs_additional_context": analysis.get("needs_additional_context"),
            "refined": analysis.get("refined"),
            "refinement_attempts": analysis.get("refinement_attempts"),
        }

        # Refresh citations
        flag.citations.clear()
        citations = analysis.get("citations") or {}
        manual = citations.get("manual_section")
        if manual:
            flag.citations.append(
                Citation(citation_type="manual", reference=str(manual).strip())
            )
        for ref in citations.get("regulation_sections") or []:
            if ref:
                flag.citations.append(
                    Citation(citation_type="regulation", reference=str(ref).strip())
                )

        return flag

    @staticmethod
    def _resolve_flag_type(flag: str | None, severity_score: Any) -> str:
        normalized = (flag or "").strip().upper()
        score = 0
        try:
            score = int(severity_score)
        except (TypeError, ValueError):
            score = 0

        if normalized in {"RED", "YELLOW", "GREEN"}:
            return normalized
        if score >= 80:
            return "RED"
        if score >= 50:
            return "YELLOW"
        return "GREEN"

