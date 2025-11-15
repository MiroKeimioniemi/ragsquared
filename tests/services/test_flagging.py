from __future__ import annotations

from backend.app.db.models import Audit, Document
from backend.app.db.session import get_session
from backend.app.services.flagging import FlagSynthesizer


def _make_document(session) -> Document:
    doc = Document(
        original_filename="manual.md",
        stored_filename="manual.md",
        storage_path="uploads/manual.md",
        content_type="text/markdown",
        size_bytes=100,
        sha256="d" * 64,
        status="uploaded",
        source_type="manual",
    )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def _make_audit(session, document: Document) -> Audit:
    audit = Audit(document_id=document.id, status="queued")
    session.add(audit)
    session.commit()
    session.refresh(audit)
    return audit


def test_flag_synthesizer_creates_flag(app):
    session = get_session()
    doc = _make_document(session)
    audit = _make_audit(session, doc)

    synth = FlagSynthesizer(session)
    analysis = {
        "flag": "RED",
        "severity_score": 90,
        "findings": "Critical gap.",
        "gaps": ["Missing procedure"],
        "citations": {
            "manual_section": "4.2",
            "regulation_sections": ["Part-145.A.30"],
        },
        "recommendations": ["Add procedure"],
    }

    flag = synth.upsert_flag(audit.id, "chunk-1", analysis)
    session.commit()

    assert flag.flag_type == "RED"
    assert len(flag.citations) == 2


def test_flag_synthesizer_updates_existing_flag(app):
    session = get_session()
    doc = _make_document(session)
    audit = _make_audit(session, doc)
    synth = FlagSynthesizer(session)

    first = {
        "flag": "GREEN",
        "severity_score": 20,
        "findings": "Initial pass.",
        "citations": {},
    }
    synth.upsert_flag(audit.id, "chunk-2", first)
    session.commit()

    second = {
        "flag": "YELLOW",
        "severity_score": 70,
        "findings": "New info.",
        "gaps": ["Clarify references"],
        "citations": {"manual_section": "2.0"},
    }
    flag = synth.upsert_flag(audit.id, "chunk-2", second)
    session.commit()

    assert flag.flag_type == "YELLOW"
    assert flag.severity_score == 70
    assert len(flag.citations) == 1

