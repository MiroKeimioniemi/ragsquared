"""Add flags and citations tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251115_flags"
down_revision = "20251115_audits_runner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "flags",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.Integer(), sa.ForeignKey("audits.id", ondelete="CASCADE")),
        sa.Column("chunk_id", sa.String(length=128), nullable=False),
        sa.Column("flag_type", sa.String(length=10), nullable=False),
        sa.Column("severity_score", sa.Integer(), nullable=False),
        sa.Column("findings", sa.Text(), nullable=False),
        sa.Column("gaps", sa.JSON(), nullable=True),
        sa.Column("recommendations", sa.JSON(), nullable=True),
        sa.Column("analysis_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("audit_id", "chunk_id", name="uq_flag_audit_chunk"),
    )

    op.create_table(
        "citations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("flag_id", sa.Integer(), sa.ForeignKey("flags.id", ondelete="CASCADE")),
        sa.Column("citation_type", sa.String(length=20), nullable=False),
        sa.Column("reference", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_flags_audit", "flags", ["audit_id", "flag_type"])
    op.create_index("idx_citations_flag", "citations", ["flag_id"])


def downgrade() -> None:
    op.drop_index("idx_citations_flag", table_name="citations")
    op.drop_table("citations")
    op.drop_index("idx_flags_audit", table_name="flags")
    op.drop_table("flags")

