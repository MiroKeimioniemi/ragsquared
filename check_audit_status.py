#!/usr/bin/env python3
"""Check current audit status and diagnose issues."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from backend.app import create_app
from backend.app.db.session import get_session
from backend.app.db.models import Audit, Chunk, AuditChunkResult
from sqlalchemy import func, and_, select

app = create_app()
with app.app_context():
    session = get_session()
    
    # Get latest audit
    latest_audit = session.query(Audit).order_by(Audit.created_at.desc()).first()
    
    if not latest_audit:
        print("No audits found in database.")
        sys.exit(0)
    
    print(f"=== Latest Audit Status ===")
    print(f"Audit ID: {latest_audit.external_id}")
    print(f"Status: {latest_audit.status}")
    print(f"Document ID: {latest_audit.document_id}")
    print(f"Chunk Total: {latest_audit.chunk_total}")
    print(f"Chunk Completed: {latest_audit.chunk_completed}")
    print(f"Last Chunk ID: {latest_audit.last_chunk_id}")
    print(f"Started At: {latest_audit.started_at}")
    print(f"Failed At: {latest_audit.failed_at}")
    if latest_audit.failure_reason:
        print(f"Failure Reason: {latest_audit.failure_reason[:200]}")
    
    # Count total chunks for document
    total_chunks = session.query(func.count(Chunk.id)).filter(
        Chunk.document_id == latest_audit.document_id
    ).scalar()
    print(f"\nTotal Chunks in Document: {total_chunks}")
    
    # Count pending chunks (chunks without results)
    pending_stmt = (
        select(func.count(Chunk.id))
        .select_from(Chunk)
        .outerjoin(
            AuditChunkResult,
            and_(
                AuditChunkResult.audit_id == latest_audit.id,
                AuditChunkResult.chunk_id == Chunk.chunk_id,
            ),
        )
        .where(
            Chunk.document_id == latest_audit.document_id,
            AuditChunkResult.id.is_(None),
        )
    )
    pending_count = session.execute(pending_stmt).scalar()
    print(f"Pending Chunks: {pending_count}")
    
    # Count completed results
    completed_count = session.query(func.count(AuditChunkResult.id)).filter(
        AuditChunkResult.audit_id == latest_audit.id
    ).scalar()
    print(f"Completed Results: {completed_count}")
    
    # Get a few pending chunks to see what should be processed
    if pending_count > 0:
        pending_chunks_stmt = (
            select(Chunk)
            .where(Chunk.document_id == latest_audit.document_id)
            .outerjoin(
                AuditChunkResult,
                and_(
                    AuditChunkResult.audit_id == latest_audit.id,
                    AuditChunkResult.chunk_id == Chunk.chunk_id,
                ),
            )
            .where(AuditChunkResult.id.is_(None))
            .order_by(Chunk.chunk_index.asc())
            .limit(5)
        )
        pending_chunks = session.execute(pending_chunks_stmt).scalars().all()
        print(f"\nFirst 5 Pending Chunks:")
        for chunk in pending_chunks:
            print(f"  - Chunk {chunk.chunk_index}: {chunk.chunk_id[:32]}... (index: {chunk.chunk_index})")
    
    # Check if there are any recent results
    recent_results = session.query(AuditChunkResult).filter(
        AuditChunkResult.audit_id == latest_audit.id
    ).order_by(AuditChunkResult.created_at.desc()).limit(3).all()
    
    if recent_results:
        print(f"\nLast 3 Processed Chunks:")
        for result in recent_results:
            print(f"  - {result.chunk_id[:32]}... (status: {result.status}, created: {result.created_at})")
    else:
        print(f"\nNo chunks have been processed yet.")

