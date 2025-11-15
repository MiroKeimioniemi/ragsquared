from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class for all ORM models."""


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class Document(Base, TimestampMixin):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('manual','regulation','amc','gm','evidence')",
            name="ck_documents_source_type",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=lambda: uuid4().hex, nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(512), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    organization: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(String(500))

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all,delete")
    embedding_jobs: Mapped[list["EmbeddingJob"]] = relationship(
        back_populates="document", cascade="all,delete"
    )
    audits: Mapped[list["Audit"]] = relationship(back_populates="document", cascade="all,delete")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "external_id": self.external_id,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "storage_path": self.storage_path,
            "content_type": self.content_type,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "status": self.status,
            "source_type": self.source_type,
            "source": self.organization or self.source_type,
            "organization": self.organization,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class Chunk(Base, TimestampMixin):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("idx_chunks_doc_status", "document_id", "embedding_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    chunk_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_path: Mapped[str | None] = mapped_column(String(512))
    parent_heading: Mapped[str | None] = mapped_column(String(255))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    chunk_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    embedding_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")


class EmbeddingJob(Base, TimestampMixin):
    __tablename__ = "embedding_jobs"
    __table_args__ = (
        Index("idx_embedding_jobs_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    job_type: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    provider: Mapped[str | None] = mapped_column(String(50))
    chunk_ids: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    job_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    document: Mapped[Document | None] = relationship(back_populates="embedding_jobs")


class Audit(Base, TimestampMixin):
    __tablename__ = "audits"
    __table_args__ = (
        Index("idx_audits_status", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(40), unique=True, default=lambda: uuid4().hex, nullable=False
    )
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="queued", nullable=False)
    is_draft: Mapped[bool] = mapped_column(default=False, nullable=False)
    chunk_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    chunk_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_chunk_id: Mapped[str | None] = mapped_column(String(128))
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    document: Mapped[Document] = relationship(back_populates="audits")
    chunk_results: Mapped[list["AuditChunkResult"]] = relationship(
        back_populates="audit", cascade="all,delete-orphan"
    )


class AuditChunkResult(Base, TimestampMixin):
    __tablename__ = "audit_chunk_results"
    __table_args__ = (
        Index("idx_audit_chunk_results_audit", "audit_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(128), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    analysis: Mapped[dict[str, Any] | None] = mapped_column(JSON)
    context_token_count: Mapped[int | None] = mapped_column(Integer)

    audit: Mapped[Audit] = relationship(back_populates="chunk_results")


class Flag(Base, TimestampMixin):
    __tablename__ = "flags"
    __table_args__ = (
        Index("idx_flags_audit", "audit_id", "flag_type"),
        Index("uq_flag_audit_chunk", "audit_id", "chunk_id", unique=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(String(128), nullable=False)
    flag_type: Mapped[str] = mapped_column(String(10), nullable=False)
    severity_score: Mapped[int] = mapped_column(Integer, nullable=False)
    findings: Mapped[str] = mapped_column(Text, nullable=False)
    gaps: Mapped[list[str] | None] = mapped_column(JSON)
    recommendations: Mapped[list[str] | None] = mapped_column(JSON)
    analysis_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    audit: Mapped[Audit] = relationship()
    citations: Mapped[list["Citation"]] = relationship(
        back_populates="flag", cascade="all,delete-orphan"
    )


class Citation(Base, TimestampMixin):
    __tablename__ = "citations"
    __table_args__ = (
        Index("idx_citations_flag", "flag_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    flag_id: Mapped[int] = mapped_column(ForeignKey("flags.id", ondelete="CASCADE"), nullable=False)
    citation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    reference: Mapped[str] = mapped_column(String(255), nullable=False)

    flag: Mapped[Flag] = relationship(back_populates="citations")


class AuditorQuestion(Base, TimestampMixin):
    __tablename__ = "auditor_questions"
    __table_args__ = (
        Index("idx_auditor_questions_audit", "audit_id", "priority"),
        Index("idx_auditor_questions_regulation", "regulation_reference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    regulation_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=highest, 10=lowest
    rationale: Mapped[str | None] = mapped_column(Text)
    related_flag_ids: Mapped[list[int] | None] = mapped_column(JSON)  # Array of flag IDs
    question_metadata: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    audit: Mapped[Audit] = relationship()


class ComplianceScore(Base, TimestampMixin):
    __tablename__ = "compliance_scores"
    __table_args__ = (
        Index("idx_compliance_scores_audit", "audit_id"),
        Index("idx_compliance_scores_created", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    audit_id: Mapped[int] = mapped_column(ForeignKey("audits.id", ondelete="CASCADE"), nullable=False)
    overall_score: Mapped[float] = mapped_column(nullable=False)  # 0-100
    red_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    yellow_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    green_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_flags: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    audit: Mapped[Audit] = relationship()


