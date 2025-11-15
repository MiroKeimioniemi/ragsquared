"""Add compliance_scores table

Revision ID: 20251115_compliance_scores
Revises: 20251115_auditor_questions
Create Date: 2025-11-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20251115_compliance_scores"
down_revision: Union[str, None] = "20251115_auditor_questions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "compliance_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("audit_id", sa.Integer(), nullable=False),
        sa.Column("overall_score", sa.Float(), nullable=False),
        sa.Column("red_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("yellow_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("green_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_flags", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.ForeignKeyConstraint(
            ["audit_id"],
            ["audits.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_compliance_scores_audit", "compliance_scores", ["audit_id"])
    op.create_index("idx_compliance_scores_created", "compliance_scores", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_compliance_scores_created", table_name="compliance_scores")
    op.drop_index("idx_compliance_scores_audit", table_name="compliance_scores")
    op.drop_table("compliance_scores")

