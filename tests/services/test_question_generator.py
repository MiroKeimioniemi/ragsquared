"""Tests for the question generator service."""

from __future__ import annotations

import json
from unittest.mock import Mock, patch

import httpx
import pytest

from backend.app.config.settings import AppConfig
from backend.app.db.models import Audit, AuditorQuestion, Citation, Document, Flag
from backend.app.services.question_generator import QuestionGenerator, QuestionItem, QuestionPlan


@pytest.fixture
def sample_audit(app, db_session):
    """Create a sample audit with flags for testing."""
    session = db_session
    doc = Document(
        original_filename="test_manual.pdf",
        stored_filename="test_manual.pdf",
        storage_path="uploads/test_manual.pdf",
        content_type="application/pdf",
        size_bytes=1000,
        sha256="a" * 64,
        source_type="manual",
        organization="TestOrg",
        status="processed",
    )
    session.add(doc)
    session.flush()

    audit = Audit(
        external_id="test-audit-001",
        document_id=doc.id,
        status="completed",
        chunk_total=10,
        chunk_completed=10,
    )
    session.add(audit)
    session.flush()

    # Create flags with citations
    flag1 = Flag(
        audit_id=audit.id,
        chunk_id="chunk_001",
        flag_type="RED",
        severity_score=85,
        findings="Missing mandatory procedure documentation",
        gaps=["Procedure X not documented"],
        recommendations=["Add procedure X"],
    )
    session.add(flag1)
    session.flush()

    citation1 = Citation(
        flag_id=flag1.id,
        citation_type="regulation",
        reference="Part-145.A.30",
    )
    session.add(citation1)

    flag2 = Flag(
        audit_id=audit.id,
        chunk_id="chunk_002",
        flag_type="YELLOW",
        severity_score=60,
        findings="Ambiguous language in section Y",
        gaps=["Clarification needed"],
        recommendations=["Revise wording"],
    )
    session.add(flag2)
    session.flush()

    citation2 = Citation(
        flag_id=flag2.id,
        citation_type="regulation",
        reference="Part-145.A.30",
    )
    session.add(citation2)

    session.commit()
    return audit


def test_question_generator_groups_flags_by_regulation(sample_audit, db_session):
    """Test that flags are correctly grouped by regulation reference."""
    session = db_session
    generator = QuestionGenerator()
    flags = session.query(Flag).filter(Flag.audit_id == sample_audit.id).all()
    groups = generator._group_flags_by_regulation(flags)

    assert "Part-145.A.30" in groups
    assert len(groups["Part-145.A.30"]) == 2


def test_question_generator_heuristic_questions(sample_audit, db_session):
    """Test heuristic question generation when LLM is unavailable."""
    session = db_session
    generator = QuestionGenerator(config=AppConfig())
    flags = session.query(Flag).filter(Flag.audit_id == sample_audit.id).all()

    questions = generator._generate_heuristic_questions(flags, count=3)
    assert len(questions) == 3
    assert all(isinstance(q, QuestionItem) for q in questions)
    assert all(1 <= q.priority <= 10 for q in questions)
    assert all(len(q.question_text) >= 10 for q in questions)


def test_question_generator_llm_integration(sample_audit, db_session):
    """Test question generation with mocked LLM response."""
    mock_response = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "questions": [
                                {
                                    "question_text": "Can you provide evidence for the missing procedure?",
                                    "priority": 1,
                                    "rationale": "Critical compliance issue",
                                },
                                {
                                    "question_text": "Please clarify the ambiguous language in section Y",
                                    "priority": 3,
                                    "rationale": "Needs clarification",
                                },
                            ]
                        }
                    )
                }
            }
        ]
    }

    with patch("httpx.Client.post") as mock_post:
        mock_post.return_value = Mock(
            status_code=200,
            json=lambda: mock_response,
            raise_for_status=Mock(),
        )

        import os
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            config = AppConfig()
            generator = QuestionGenerator(config=config)

            session = db_session
            questions = generator._generate_questions_for_regulation(
                sample_audit.id, "Part-145.A.30", session.query(Flag).filter(Flag.audit_id == sample_audit.id).all(), 2
            )

            assert len(questions) >= 2
            assert all(isinstance(q, AuditorQuestion) for q in questions)
            assert all(q.regulation_reference == "Part-145.A.30" for q in questions)


def test_question_generator_fallback_to_heuristic(sample_audit, db_session):
    """Test that heuristic questions are used when LLM fails."""
    with patch("httpx.Client.post") as mock_post:
        mock_post.side_effect = httpx.HTTPError("Connection failed")

        import os
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            config = AppConfig()
            generator = QuestionGenerator(config=config)

            session = db_session
            questions = generator._generate_questions_for_regulation(
                sample_audit.id, "Part-145.A.30", session.query(Flag).filter(Flag.audit_id == sample_audit.id).all(), 3
            )

            # Should fallback to heuristic questions
            assert len(questions) >= 3
            assert all(q.question_metadata.get("generated_by") == "heuristic" for q in questions)


def test_question_generator_generate_for_audit(sample_audit, db_session):
    """Test full question generation for an audit."""
    with patch.object(QuestionGenerator, "_call_llm") as mock_llm:
        mock_llm.return_value = json.dumps(
            {
                "questions": [
                    {
                        "question_text": "Test question 1",
                        "priority": 1,
                        "rationale": "Test rationale",
                    }
                ]
            }
        )

        import os
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}, clear=False):
            config = AppConfig()
            generator = QuestionGenerator(config=config)

            count = generator.generate_for_audit(sample_audit.id, min_questions_per_section=1)
            assert count > 0

            # Verify questions were persisted
            session = db_session
            questions = (
                session.query(AuditorQuestion).filter(AuditorQuestion.audit_id == sample_audit.id).all()
            )
            assert len(questions) == count


def test_question_generator_skips_existing_questions(sample_audit, db_session):
    """Test that existing questions are not regenerated."""
    session = db_session
    # Create an existing question
    existing = AuditorQuestion(
        audit_id=sample_audit.id,
        regulation_reference="Part-145.A.30",
        question_text="Existing question",
        priority=1,
        rationale="Existing rationale",
    )
    session.add(existing)
    session.commit()

    generator = QuestionGenerator()
    questions = generator._generate_questions_for_regulation(
        sample_audit.id, "Part-145.A.30", session.query(Flag).filter(Flag.audit_id == sample_audit.id).all(), 3
    )

    # Should return existing question
    assert len(questions) == 1
    assert questions[0].question_text == "Existing question"


def test_question_plan_validation():
    """Test that QuestionPlan validates correctly."""
    valid_data = {
        "questions": [
            {"question_text": "Test question?", "priority": 1, "rationale": "Test rationale"}
        ]
    }
    plan = QuestionPlan.model_validate(valid_data)
    assert len(plan.questions) == 1

    # Should fail with empty questions
    with pytest.raises(Exception):
        QuestionPlan.model_validate({"questions": []})

