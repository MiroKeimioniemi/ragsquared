"""Compliance score tracking service."""

from __future__ import annotations

import logging
from collections import Counter
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..db.models import Audit, ComplianceScore, Flag
from .compliance_score import calculate_compliance_score

logger = logging.getLogger(__name__)


class ScoreTracker:
    """Tracks and persists compliance scores for audits."""

    def __init__(self, session: Session):
        self.session = session

    def record_score(self, audit_id: int) -> ComplianceScore:
        """
        Calculate and persist compliance score for an audit.
        
        Returns the created ComplianceScore record.
        """
        # Check if score already exists
        existing = self.session.execute(
            select(ComplianceScore).where(ComplianceScore.audit_id == audit_id)
        ).scalar_one_or_none()
        
        if existing:
            logger.info(f"Score already exists for audit {audit_id}, updating...")
            # Update existing score
            score_record = existing
        else:
            score_record = ComplianceScore(audit_id=audit_id)
            self.session.add(score_record)

        # Fetch all flags for this audit
        flags = self.session.execute(
            select(Flag).where(Flag.audit_id == audit_id)
        ).scalars().all()

        # Calculate metrics
        severity_counts = Counter(flag.flag_type for flag in flags)
        overall_score = calculate_compliance_score(flags)

        # Update score record
        score_record.overall_score = overall_score
        score_record.red_count = severity_counts.get("RED", 0)
        score_record.yellow_count = severity_counts.get("YELLOW", 0)
        score_record.green_count = severity_counts.get("GREEN", 0)
        score_record.total_flags = len(flags)

        self.session.commit()
        logger.info(
            f"Recorded score for audit {audit_id}: {overall_score:.2f} "
            f"(R:{score_record.red_count} Y:{score_record.yellow_count} G:{score_record.green_count})"
        )
        return score_record

    def get_score_history(
        self,
        organization: str | None = None,
        limit: int = 50,
    ) -> list[ComplianceScore]:
        """
        Get score history, optionally filtered by organization.
        
        Args:
            organization: Optional organization name to filter by
            limit: Maximum number of records to return
            
        Returns:
            List of ComplianceScore records, ordered by created_at descending
        """
        from ..db.models import Document
        
        # Build query with optional organization filter
        if organization:
            query = (
                select(ComplianceScore)
                .join(Audit)
                .join(Document)
                .where(Document.organization == organization)
                .order_by(ComplianceScore.created_at.desc())
            )
        else:
            query = (
                select(ComplianceScore)
                .join(Audit)
                .order_by(ComplianceScore.created_at.desc())
            )
        
        # Get unique scores per audit (most recent per audit)
        # Use a subquery to get the latest score per audit
        subquery = (
            select(
                ComplianceScore.audit_id,
                func.max(ComplianceScore.created_at).label("max_created_at")
            )
            .group_by(ComplianceScore.audit_id)
            .subquery()
        )
        
        query = (
            query.join(
                subquery,
                and_(
                    ComplianceScore.audit_id == subquery.c.audit_id,
                    ComplianceScore.created_at == subquery.c.max_created_at
                )
            )
            .limit(limit)
        )
        
        # Execute and get scores
        scores = self.session.execute(query).scalars().all()
        
        return list(scores)

    def get_latest_score(self, organization: str | None = None) -> ComplianceScore | None:
        """Get the most recent compliance score, optionally filtered by organization."""
        history = self.get_score_history(organization=organization, limit=1)
        return history[0] if history else None

