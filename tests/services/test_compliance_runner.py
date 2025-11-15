from __future__ import annotations

from typing import Any

from backend.app.config.settings import AppConfig
from backend.app.db.models import Audit, AuditChunkResult, Chunk, Document, Flag
from backend.app.db.session import get_session
from backend.app.services.compliance_runner import ComplianceRunner, RunnerResult
from backend.app.services.context_builder import ContextBundle, ContextSlice


def _create_document(session, external_id: str = "audit-doc") -> Document:
    doc = Document(
        external_id=external_id,
        original_filename=f"{external_id}.md",
        stored_filename=f"{external_id}.md",
        storage_path=f"uploads/{external_id}.md",
        content_type="text/markdown",
        size_bytes=1024,
        sha256="c" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def _create_chunk(session, document: Document, idx: int) -> Chunk:
    chunk = Chunk(
        document_id=document.id,
        chunk_id=f"{document.external_id}_{idx}",
        chunk_index=idx,
        content=f"Chunk content {idx}",
        token_count=30,
        section_path=f"Manual > Section {idx}",
        parent_heading=f"Section {idx}",
        chunk_metadata={"section_path": ["Manual", f"Section {idx}"]},
    )
    session.add(chunk)
    session.commit()
    session.refresh(chunk)
    return chunk


def _create_audit(session, document: Document, *, status: str = "queued", is_draft: bool = False) -> Audit:
    audit = Audit(document_id=document.id, status=status, is_draft=is_draft)
    session.add(audit)
    session.commit()
    session.refresh(audit)
    return audit


class StubContextBuilder:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def build_context(
        self,
        chunk_id: str,
        *,
        include_evidence: bool = False,
        neighbor_window: int | None = None,
        budget_multiplier: float = 1.0,
    ) -> ContextBundle:
        self.calls.append(
            {
                "chunk_id": chunk_id,
                "include_evidence": include_evidence,
                "neighbor_window": neighbor_window,
                "budget_multiplier": budget_multiplier,
            }
        )
        focus = ContextSlice(
            label="Focus",
            source="manual",
            content=f"Context for {chunk_id}",
            token_count=10,
            metadata={"section_path": ["Manual", chunk_id]},
        )
        return ContextBundle(focus=focus)


class StubAnalysisClient:
    def __init__(self, scripted: list[dict[str, Any]] | None = None):
        self.calls: list[dict[str, Any]] = []
        self.scripted = scripted or []

    def analyze(self, chunk: Chunk, context: ContextBundle) -> dict[str, Any]:
        call = {"chunk_id": chunk.chunk_id, "context": context}
        self.calls.append(call)
        index = len(self.calls) - 1
        if index < len(self.scripted):
            response = dict(self.scripted[index])
            response.setdefault("chunk_id", chunk.chunk_id)
            response.setdefault("flag", "GREEN")
            response.setdefault("severity_score", 5)
            response.setdefault("findings", "Placeholder")
            response.setdefault("regulation_references", [])
            response.setdefault("gaps", [])
            response.setdefault("citations", {"manual_section": "1.0", "regulation_sections": []})
            response.setdefault("recommendations", [])
            response.setdefault("needs_additional_context", False)
            return response
        return {
            "chunk_id": chunk.chunk_id,
            "flag": "GREEN",
            "severity_score": 5,
            "findings": "Placeholder",
            "regulation_references": [],
            "gaps": [],
            "citations": {"manual_section": "1.0", "regulation_sections": []},
            "recommendations": [],
            "needs_additional_context": False,
        }


def test_runner_processes_pending_chunks(app):
    session = get_session()
    doc = _create_document(session, external_id="runner-doc")
    for idx in range(3):
        _create_chunk(session, doc, idx)
    audit = _create_audit(session, doc, status="queued")

    builder = StubContextBuilder()
    analysis_client = StubAnalysisClient()
    runner = ComplianceRunner(
        session,
        AppConfig(),
        context_builder=builder,
        analysis_client=analysis_client,
    )

    result = runner.run(audit.external_id)

    session.refresh(audit)
    assert isinstance(result, RunnerResult)
    assert result.processed == 3
    assert result.remaining == 0
    assert audit.status == "completed"
    assert len(builder.calls) == 3
    assert all(call["include_evidence"] is True for call in builder.calls)
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    assert len(flags) == 3


def test_runner_respects_max_chunks_and_resume(app):
    session = get_session()
    doc = _create_document(session, external_id="runner-doc-2")
    for idx in range(4):
        _create_chunk(session, doc, idx)
    audit = _create_audit(session, doc, status="queued", is_draft=True)

    builder = StubContextBuilder()
    analysis_client = StubAnalysisClient()
    runner = ComplianceRunner(
        session,
        AppConfig(),
        context_builder=builder,
        analysis_client=analysis_client,
    )

    first_pass = runner.run(audit.id, max_chunks=2)
    session.refresh(audit)
    assert first_pass.processed == 2
    assert first_pass.remaining == 2
    assert audit.status == "running"

    # include_evidence defaults to False for draft audits
    assert all(call["include_evidence"] is False for call in builder.calls[:2])

    second_pass = runner.run(audit.id)
    session.refresh(audit)
    assert second_pass.remaining == 0
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    assert len(flags) == 4


def test_runner_refines_when_additional_context_needed(app):
    session = get_session()
    doc = _create_document(session, external_id="runner-doc-3")
    chunk = _create_chunk(session, doc, 0)
    audit = _create_audit(session, doc, status="queued")

    builder = StubContextBuilder()
    scripted_responses = [
        {
            "flag": "YELLOW",
            "severity_score": 40,
            "findings": "Need more context.",
            "regulation_references": [],
            "gaps": ["Missing reference"],
            "citations": {"manual_section": "1.0", "regulation_sections": []},
            "recommendations": ["Add reference"],
            "needs_additional_context": True,
        },
        {
            "flag": "GREEN",
            "severity_score": 5,
            "findings": "Resolved.",
            "regulation_references": [],
            "gaps": [],
            "citations": {"manual_section": "1.0", "regulation_sections": []},
            "recommendations": [],
            "needs_additional_context": False,
        },
    ]
    analysis_client = StubAnalysisClient(scripted=scripted_responses)
    config = AppConfig()
    runner = ComplianceRunner(
        session,
        config,
        context_builder=builder,
        analysis_client=analysis_client,
    )

    runner.run(audit.id, max_chunks=1)

    assert len(builder.calls) == 2
    refinement_call = builder.calls[1]
    assert refinement_call["include_evidence"] is True
    assert refinement_call["neighbor_window"] == config.refinement_manual_window
    assert refinement_call["budget_multiplier"] == max(1.0, config.refinement_token_multiplier)

    result_row = (
        session.query(AuditChunkResult).filter(AuditChunkResult.audit_id == audit.id).one()
    )
    assert result_row.analysis["refined"] is True
    assert result_row.analysis["refinement_attempts"] == 1
    flags = session.query(Flag).filter(Flag.audit_id == audit.id).all()
    assert len(flags) == 1
    assert flags[0].flag_type == "GREEN"
    assert audit.status == "completed"

