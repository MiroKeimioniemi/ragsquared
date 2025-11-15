"""Add audits and audit chunk results tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251115_audits_runner"
down_revision = "20251114_chunks_embeddings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("external_id", sa.String(length=40), nullable=False, unique=True),
        sa.Column("document_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE")),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="queued"),
        sa.Column("is_draft", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("chunk_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("chunk_completed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_chunk_id", sa.String(length=128), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "audit_chunk_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.Integer(), sa.ForeignKey("audits.id", ondelete="CASCADE")),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("analysis", sa.JSON(), nullable=True),
        sa.Column("context_token_count", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("audit_id", "chunk_id", name="uq_audit_chunk_unique"),
    )

    op.create_index(
        "idx_audits_status", "audits", ["status"], unique=False
    )
    op.create_index(
        "idx_audit_chunk_results_audit", "audit_chunk_results", ["audit_id", "status"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_audit_chunk_results_audit", table_name="audit_chunk_results")
    op.drop_table("audit_chunk_results")
    op.drop_index("idx_audits_status", table_name="audits")
    op.drop_table("audits")

