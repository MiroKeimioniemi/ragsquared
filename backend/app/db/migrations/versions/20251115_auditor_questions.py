"""Add auditor_questions table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20251115_auditor_questions"
down_revision = "20251115_flags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auditor_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.Integer(), sa.ForeignKey("audits.id", ondelete="CASCADE"), nullable=False),
        sa.Column("regulation_reference", sa.String(length=100), nullable=False),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),  # 1=highest, 10=lowest
        sa.Column("rationale", sa.Text(), nullable=True),
        sa.Column("related_flag_ids", sa.JSON(), nullable=True),  # Array of flag IDs
        sa.Column("question_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("idx_auditor_questions_audit", "auditor_questions", ["audit_id", "priority"])
    op.create_index("idx_auditor_questions_regulation", "auditor_questions", ["regulation_reference"])


def downgrade() -> None:
    op.drop_index("idx_auditor_questions_regulation", table_name="auditor_questions")
    op.drop_index("idx_auditor_questions_audit", table_name="auditor_questions")
    op.drop_table("auditor_questions")

