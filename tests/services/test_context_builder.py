from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from backend.app.config.settings import AppConfig
from backend.app.db.models import Chunk, Document
from backend.app.db.session import get_session
from backend.app.services.context_builder import (
    ContextBuilder,
    VectorClient,
    VectorMatch,
)


@dataclass
class FakeVectorClient(VectorClient):
    responses: Dict[str, List[VectorMatch]]

    def query(self, collection: str, query_text: str, n_results: int) -> list[VectorMatch]:
        return list(self.responses.get(collection, []))[:n_results]


def _make_document(session, source_type: str, external_id: str) -> Document:
    doc = Document(
        external_id=external_id,
        original_filename=f"{external_id}.md",
        stored_filename=f"{external_id}.md",
        storage_path=f"uploads/{external_id}.md",
        content_type="text/markdown",
        size_bytes=128,
        sha256=external_id.ljust(64, external_id[-1]),
        status="uploaded",
        source_type=source_type,
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def _make_chunk(
    session,
    document: Document,
    *,
    chunk_index: int,
    chunk_id: str,
    text: str,
    token_count: int,
) -> Chunk:
    chunk = Chunk(
        document_id=document.id,
        chunk_id=chunk_id,
        chunk_index=chunk_index,
        content=text,
        token_count=token_count,
        section_path=f"{document.original_filename} > Section {chunk_index}",
        parent_heading=f"Section {chunk_index}",
        chunk_metadata={"section_path": [document.original_filename, f"Section {chunk_index}"]},
    )
    session.add(chunk)
    session.commit()
    session.refresh(chunk)
    return chunk


def test_context_builder_assembles_manual_and_regulation_slices(app, monkeypatch):
    monkeypatch.setenv("CONTEXT_MANUAL_WINDOW", "1")
    monkeypatch.setenv("CONTEXT_MANUAL_TOKEN_LIMIT", "200")
    monkeypatch.setenv("CONTEXT_REGULATION_TOP_K", "3")
    monkeypatch.setenv("CONTEXT_REGULATION_TOKEN_LIMIT", "400")
    monkeypatch.setenv("CONTEXT_GUIDANCE_TOP_K", "2")
    monkeypatch.setenv("CONTEXT_GUIDANCE_TOKEN_LIMIT", "200")
    monkeypatch.setenv("CONTEXT_TOTAL_TOKEN_LIMIT", "2000")

    session = get_session()
    manual_doc = _make_document(session, "manual", "manual-doc")
    regulation_doc = _make_document(session, "regulation", "reg-doc")
    guidance_doc = _make_document(session, "amc", "amc-doc")

    chunk_prev = _make_chunk(
        session,
        manual_doc,
        chunk_index=0,
        chunk_id="manual-doc_0",
        text="Previous procedures chunk.",
        token_count=20,
    )
    focus_chunk = _make_chunk(
        session,
        manual_doc,
        chunk_index=1,
        chunk_id="manual-doc_1",
        text="Focus chunk content describing maintenance steps.",
        token_count=25,
    )
    chunk_next = _make_chunk(
        session,
        manual_doc,
        chunk_index=2,
        chunk_id="manual-doc_2",
        text="Next chunk with supporting details.",
        token_count=22,
    )

    vector_client = FakeVectorClient(
        responses={
            "regulation_chunks": [
                VectorMatch(
                    content="Part-145.A.30 requires qualified personnel.",
                    metadata={
                        "chunk_id": "reg-1",
                        "document_id": regulation_doc.id,
                        "token_count": 30,
                        "parent_heading": "Part-145.A.30",
                    },
                    score=0.07,
                )
            ],
            "amc_chunks": [
                VectorMatch(
                    content="AMC 145.A.30 details the acceptable means of compliance.",
                    metadata={
                        "chunk_id": "amc-1",
                        "document_id": guidance_doc.id,
                        "token_count": 28,
                        "parent_heading": "AMC 145.A.30",
                    },
                    score=0.09,
                )
            ],
        }
    )

    builder = ContextBuilder(session, AppConfig(), vector_client=vector_client)
    bundle = builder.build_context(focus_chunk.chunk_id)

    assert bundle.focus.content.startswith("Focus chunk content")
    assert len(bundle.manual_neighbors) == 2  # window=1 includes both previous and next
    neighbor_chunk_ids = {slice_.metadata["chunk_id"] for slice_ in bundle.manual_neighbors}
    assert chunk_prev.chunk_id in neighbor_chunk_ids
    assert chunk_next.chunk_id in neighbor_chunk_ids

    assert len(bundle.regulation_slices) == 1
    assert bundle.regulation_slices[0].metadata["chunk_id"] == "reg-1"
    assert len(bundle.guidance_slices) == 1
    assert bundle.guidance_slices[0].metadata["chunk_id"] == "amc-1"
    assert bundle.evidence_slices == []
    assert bundle.token_breakdown["manual"] > 0
    assert bundle.token_breakdown["regulation"] > 0


def test_context_builder_respects_token_budgets(app, monkeypatch):
    monkeypatch.setenv("CONTEXT_MANUAL_WINDOW", "2")
    monkeypatch.setenv("CONTEXT_MANUAL_TOKEN_LIMIT", "10")
    monkeypatch.setenv("CONTEXT_REGULATION_TOP_K", "2")
    monkeypatch.setenv("CONTEXT_REGULATION_TOKEN_LIMIT", "8")
    monkeypatch.setenv("CONTEXT_GUIDANCE_TOP_K", "1")
    monkeypatch.setenv("CONTEXT_GUIDANCE_TOKEN_LIMIT", "5")
    monkeypatch.setenv("CONTEXT_EVIDENCE_TOP_K", "1")
    monkeypatch.setenv("CONTEXT_EVIDENCE_TOKEN_LIMIT", "5")
    monkeypatch.setenv("CONTEXT_TOTAL_TOKEN_LIMIT", "12")

    session = get_session()
    manual_doc = _make_document(session, "manual", "manual-budget")

    focus = _make_chunk(
        session,
        manual_doc,
        chunk_index=10,
        chunk_id="manual-budget_10",
        text="Focus chunk for budget test.",
        token_count=4,
    )
    # Create neighbors with known token counts
    for offset in (-2, -1, 1, 2):
        _make_chunk(
            session,
            manual_doc,
            chunk_index=10 + offset,
            chunk_id=f"manual-budget_{10 + offset}",
            text=f"Neighbor {offset}",
            token_count=6,
        )

    vector_client = FakeVectorClient(
        responses={
            "regulation_chunks": [
                VectorMatch(
                    content="Regulation reference exceeds budget.",
                    metadata={"chunk_id": "reg-budget", "token_count": 6},
                )
            ],
            "evidence_chunks": [
                VectorMatch(
                    content="Evidence attachment.",
                    metadata={"chunk_id": "evidence-1", "token_count": 4},
                )
            ],
        }
    )

    builder = ContextBuilder(session, AppConfig(), vector_client=vector_client)
    bundle = builder.build_context(focus.chunk_id, include_evidence=True)

    # Manual token budget is 10, each neighbor is 6 tokens so only one should be accepted.
    assert len(bundle.manual_neighbors) == 1
    # Regulation slice should be trimmed due to per-bucket limit (8) when candidate is 6 but total budget of 12
    # leaves room only if manual slice consumed 6 tokens.
    assert len(bundle.regulation_slices) in (0, 1)
    # Evidence slice should be accepted only if tokens remain in total budget.
    if bundle.evidence_slices:
        assert bundle.evidence_slices[0].metadata["chunk_id"] == "evidence-1"
    assert bundle.total_tokens <= 12
    assert bundle.truncated is True

