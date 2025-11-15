from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Sequence

from sqlalchemy import Select, and_, func, select
from sqlalchemy.orm import Session

from ..config.settings import AppConfig
from ..db.models import Audit, AuditChunkResult, Chunk
from ..logging_config import get_logger, set_audit_id, set_chunk_id
from .analysis import ComplianceLLMClient
from .analysis_base import AnalysisClient
from .context_builder import ContextBuilder, ContextBundle, ContextSlice
from .recursive_context_builder import RecursiveContextBuilder
from .flagging import FlagSynthesizer
from .metrics import get_metrics
from .score_tracker import ScoreTracker

logger = get_logger(__name__)


class EchoAnalysisClient(AnalysisClient):
    """Fallback analysis client that emits placeholder findings."""

    def analyze(self, chunk: Chunk, context: ContextBundle) -> dict[str, Any]:
        return {
            "chunk_id": chunk.chunk_id,
            "flag": "GREEN",
            "severity_score": 10,
            "findings": "Placeholder analysis - real LLM integration pending.",
            "regulation_references": [],
            "gaps": [],
            "citations": {
                "manual_section": context.focus.metadata.get("section_path"),
                "regulation_sections": [],
            },
            "recommendations": [],
            "needs_additional_context": False,
        }


@dataclass
class RunnerResult:
    processed: int
    remaining: int
    status: str


class ComplianceRunner:
    """Sequential runner responsible for executing queued audits chunk-by-chunk."""

    def __init__(
        self,
        session: Session,
        config: AppConfig,
        *,
        context_builder: ContextBuilder | None = None,
        analysis_client: AnalysisClient | None = None,
        flag_synthesizer: FlagSynthesizer | None = None,
        use_recursive_rag: bool = True,
    ):
        self.session = session
        self.config = config
        base_builder = context_builder or ContextBuilder(session, config)
        # Use recursive RAG by default for comprehensive context
        if use_recursive_rag:
            self.context_builder = RecursiveContextBuilder(session, config, base_context_builder=base_builder)
        else:
            self.context_builder = base_builder
        self.flag_synthesizer = flag_synthesizer or FlagSynthesizer(session)
        self.score_tracker = ScoreTracker(session)
        if analysis_client is not None:
            self.analysis_client = analysis_client
        elif config.llm_api_key or config.openrouter_api_key:
            try:
                self.analysis_client = ComplianceLLMClient(config)
            except ValueError as exc:
                logger.warning("ComplianceLLMClient unavailable; falling back to echo client", error=str(exc))
                self.analysis_client = EchoAnalysisClient()
        else:
            self.analysis_client = EchoAnalysisClient()

    def run(
        self,
        audit_identifier: int | str,
        *,
        max_chunks: int | None = None,
        include_evidence: bool | None = None,
    ) -> RunnerResult:
        audit = self._resolve_audit(audit_identifier)
        if audit is None:
            raise ValueError(f"Audit '{audit_identifier}' not found.")

        # Set audit context for logging
        set_audit_id(audit.external_id)
        logger.info("Starting compliance runner", audit_id=audit.external_id, is_draft=audit.is_draft)
        self._ensure_chunk_counts(audit)

        if audit.status not in {"queued", "running"}:
            logger.info("Audit already in terminal status", audit_id=audit.external_id, status=audit.status)
            return RunnerResult(processed=0, remaining=self._pending_chunk_count(audit), status=audit.status)

        audit.status = "running"
        if audit.started_at is None:
            from datetime import timezone
            audit.started_at = datetime.now(timezone.utc)
        
        # Ensure chunk_total is set and committed so frontend can see progress
        self._ensure_chunk_counts(audit)
        self.session.commit()  # Commit so frontend can see chunk_total immediately

        processed = 0
        metrics = get_metrics()
        # For draft mode, limit to first 5 chunks for faster processing
        effective_limit = max_chunks
        if audit.is_draft and effective_limit is None:
            effective_limit = 5
        
        # Get pending chunks and log for debugging
        pending_chunks = list(self._pending_chunks(audit, limit=effective_limit))
        pending_count = self._pending_chunk_count(audit)
        
        logger.info(
            "Retrieved pending chunks",
            audit_id=audit.external_id,
            chunks_found=len(pending_chunks),
            total_pending=pending_count,
            limit=effective_limit,
            chunk_total=audit.chunk_total,
            chunk_completed=audit.chunk_completed,
        )
        
        if not pending_chunks:
            logger.warning(
                "No pending chunks found to process",
                audit_id=audit.external_id,
                total_pending=pending_count,
                chunk_total=audit.chunk_total,
                chunk_completed=audit.chunk_completed,
            )
            # If no chunks but we have a total, something might be wrong
            if audit.chunk_total > 0 and audit.chunk_completed == 0:
                logger.error(
                    "Audit has chunks but none are pending - possible query issue",
                    audit_id=audit.external_id,
                    document_id=audit.document_id,
                )

        import time
        from ..services.analysis import OpenRouterError
        
        try:
            for chunk_idx, chunk in enumerate(pending_chunks, 1):
                logger.info(
                    "Processing chunk",
                    audit_id=audit.external_id,
                    chunk_id=chunk.chunk_id,
                    chunk_index=chunk.chunk_index,
                    progress=f"{chunk_idx}/{len(pending_chunks)}",
                )
                set_chunk_id(chunk.chunk_id)
                try:
                    self._process_chunk(
                        audit,
                        chunk,
                        include_evidence=include_evidence
                        if include_evidence is not None
                        else (not audit.is_draft),
                    )
                    processed += 1
                    # Record metrics (estimate token usage from context)
                    metrics.record_chunk_processed(tokens_used=0)  # TODO: track actual token usage
                    
                    # Commit progress after each chunk so frontend can see updates
                    self.session.commit()
                    logger.debug(
                        "Chunk processed and committed",
                        audit_id=audit.external_id,
                        chunk_id=chunk.chunk_id,
                        processed_count=processed,
                    )
                    
                except OpenRouterError as rate_limit_error:
                    # Handle rate limit errors gracefully
                    error_msg = str(rate_limit_error)
                    if "429" in error_msg or "rate limit" in error_msg.lower() or "Too Many Requests" in error_msg:
                        logger.error(
                            "Rate limit exceeded during audit processing",
                            audit_id=audit.external_id,
                            chunk_id=chunk.chunk_id,
                            error=error_msg,
                        )
                        # Mark audit as failed with a user-friendly message
                        audit.status = "failed"
                        from datetime import timezone
                        audit.failed_at = datetime.now(timezone.utc)
                        audit.failure_reason = (
                            f"Rate limit exceeded while processing chunk {processed + 1} of {audit.chunk_total}. "
                            f"Please wait a few minutes and retry the audit. "
                            f"Progress: {audit.chunk_completed}/{audit.chunk_total} chunks completed."
                        )
                        self.session.commit()
                        return RunnerResult(
                            processed=processed,
                            remaining=self._pending_chunk_count(audit),
                            status="failed",
                        )
                    else:
                        # Re-raise non-rate-limit errors
                        raise
                except Exception as chunk_exc:
                    # Log any other exceptions during chunk processing
                    logger.exception(
                        "Error processing chunk",
                        audit_id=audit.external_id,
                        chunk_id=chunk.chunk_id,
                        error=str(chunk_exc),
                        error_type=type(chunk_exc).__name__,
                    )
                    # Re-raise to be caught by outer exception handler
                    raise
                
                # Add configurable delay between chunks to avoid rate limits
                if processed < len(pending_chunks):  # Don't delay after last chunk
                    delay = self.config.chunk_processing_delay
                    logger.debug(f"Waiting {delay}s before next chunk to avoid rate limits")
                    time.sleep(delay)

            remaining = self._pending_chunk_count(audit)
            if remaining == 0:
                audit.status = "completed"
                from datetime import timezone
                audit.completed_at = datetime.now(timezone.utc)
                logger.info("Audit completed successfully", audit_id=audit.external_id, chunks_processed=processed)
                # Emit final metrics
                metrics.emit_metrics()
                # Record compliance score
                try:
                    self.score_tracker.record_score(audit.id)
                except Exception as score_exc:
                    logger.warning("Failed to record compliance score", audit_id=audit.external_id, error=str(score_exc))
            else:
                logger.info(
                    "Audit paused with chunks remaining",
                    audit_id=audit.external_id,
                    chunks_remaining=remaining,
                    chunks_processed=processed,
                )
            self.session.commit()
            return RunnerResult(processed=processed, remaining=remaining, status=audit.status)
        except Exception as exc:  # pragma: no cover - catastrophic failure
            logger.exception("Audit failed", audit_id=audit.external_id, error=str(exc))
            audit.status = "failed"
            from datetime import timezone
            audit.failed_at = datetime.now(timezone.utc)
            # Truncate failure reason if too long
            failure_reason = str(exc)
            if len(failure_reason) > 500:
                failure_reason = failure_reason[:497] + "..."
            audit.failure_reason = failure_reason
            self.session.commit()
            # Don't raise - return failed result instead so caller can handle gracefully
            return RunnerResult(
                processed=processed,
                remaining=self._pending_chunk_count(audit),
                status="failed",
            )
        finally:
            # Clear context
            set_audit_id(None)
            set_chunk_id(None)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _process_chunk(self, audit: Audit, chunk: Chunk, *, include_evidence: bool) -> None:
        logger.info(
            "Starting chunk processing",
            chunk_id=chunk.chunk_id,
            audit_id=audit.external_id,
            draft=audit.is_draft,
            include_evidence=include_evidence,
        )
        try:
            analysis, bundle = self._analyze_with_optional_refinement(
                chunk,
                include_evidence=include_evidence,
                is_draft=audit.is_draft,
            )
            logger.debug(
                "Analysis completed",
                chunk_id=chunk.chunk_id,
                audit_id=audit.external_id,
                flag=analysis.get("flag"),
                needs_context=analysis.get("needs_additional_context"),
            )
        except Exception as analysis_exc:
            logger.exception(
                "Error during chunk analysis",
                chunk_id=chunk.chunk_id,
                audit_id=audit.external_id,
                error=str(analysis_exc),
                error_type=type(analysis_exc).__name__,
            )
            raise

        # Store context summary for UI display
        context_summary = {
            "total_tokens": bundle.total_tokens,
            "truncated": bundle.truncated,
            "token_breakdown": bundle.token_breakdown,
            "manual_neighbors_count": len(bundle.manual_neighbors),
            "regulation_slices_count": len(bundle.regulation_slices),
            "guidance_slices_count": len(bundle.guidance_slices),
            "evidence_slices_count": len(bundle.evidence_slices),
            "manual_neighbors": [
                {
                    "label": slice_.label,
                    "content_preview": slice_.content[:200] + "..." if len(slice_.content) > 200 else slice_.content,
                    "tokens": slice_.token_count,
                    "metadata": slice_.metadata,
                    "score": slice_.score,
                }
                for slice_ in bundle.manual_neighbors[:20]  # Limit for storage
            ],
            "regulation_slices": [
                {
                    "label": slice_.label,
                    "content_preview": slice_.content[:200] + "..." if len(slice_.content) > 200 else slice_.content,
                    "tokens": slice_.token_count,
                    "metadata": slice_.metadata,
                    "score": slice_.score,
                }
                for slice_ in bundle.regulation_slices[:20]  # Limit for storage
            ],
            "guidance_slices": [
                {
                    "label": slice_.label,
                    "content_preview": slice_.content[:200] + "..." if len(slice_.content) > 200 else slice_.content,
                    "tokens": slice_.token_count,
                    "metadata": slice_.metadata,
                    "score": slice_.score,
                }
                for slice_ in bundle.guidance_slices[:20]  # Limit for storage
            ],
            "evidence_slices": [
                {
                    "label": slice_.label,
                    "content_preview": slice_.content[:200] + "..." if len(slice_.content) > 200 else slice_.content,
                    "tokens": slice_.token_count,
                    "metadata": slice_.metadata,
                    "score": slice_.score,
                }
                for slice_ in bundle.evidence_slices[:20]  # Limit for storage
            ],
        }
        
        # Add context summary to analysis for easy access
        analysis_with_context = dict(analysis)
        analysis_with_context["context_summary"] = context_summary
        
        result = AuditChunkResult(
            audit_id=audit.id,
            chunk_id=chunk.chunk_id,
            chunk_index=chunk.chunk_index,
            status="completed",
            analysis=analysis_with_context,
            context_token_count=bundle.total_tokens,
        )
        self.session.add(result)
        self.flag_synthesizer.upsert_flag(audit.id, chunk.chunk_id, analysis)

        audit.chunk_completed += 1
        audit.last_chunk_id = chunk.chunk_id
        self.session.flush()

    def _analyze_with_optional_refinement(
        self,
        chunk: Chunk,
        *,
        include_evidence: bool,
        is_draft: bool = False,
    ) -> tuple[dict[str, Any], ContextBundle]:
        # For draft mode, use reduced context budgets
        neighbor_window = 0 if is_draft else None  # No neighbors for draft
        budget_multiplier = 0.5 if is_draft else 1.0  # Half budget for draft

        logger.info(
            "Building RAG context for chunk %s (draft=%s, evidence=%s, recursive=%s)",
            chunk.chunk_id[:16],
            is_draft,
            include_evidence,
            isinstance(self.context_builder, RecursiveContextBuilder),
        )
        
        # Use recursive context builder if available
        if isinstance(self.context_builder, RecursiveContextBuilder):
            bundle = self.context_builder.build_recursive_context(
                chunk.chunk_id,
                include_evidence=include_evidence,
                include_litigation=True,
                neighbor_window=neighbor_window,
                budget_multiplier=budget_multiplier,
            )
        else:
            bundle = self.context_builder.build_context(
                chunk.chunk_id,
                include_evidence=include_evidence,
                neighbor_window=neighbor_window,
                budget_multiplier=budget_multiplier,
            )
        logger.info(
            "RAG context ready: %d regulations, %d guidance, %d manual neighbors",
            len(bundle.regulation_slices),
            len(bundle.guidance_slices),
            len(bundle.manual_neighbors),
        )
        analysis = self.analysis_client.analyze(chunk, bundle)
        attempts = 0

        # Skip refinement for draft mode
        # Allow multiple refinement attempts for comprehensive searching
        max_refinement_attempts = max(0, self.config.refinement_max_attempts) if not is_draft else 0
        # Increase limit for recursive RAG to allow more thorough searching
        if isinstance(self.context_builder, RecursiveContextBuilder):
            max_refinement_attempts = max(max_refinement_attempts, 5)  # Allow up to 5 searches with recursive RAG
        
        if not is_draft:
            while (
                analysis.get("needs_additional_context")
                and attempts < max_refinement_attempts
            ):
                attempts += 1
                # Use context_query from previous analysis for targeted RAG search
                context_query = analysis.get("context_query")
                if context_query:
                    logger.info(
                        f"Refinement attempt {attempts}/{max_refinement_attempts}: Searching for: {context_query[:100]}..."
                    )
                else:
                    logger.warning(
                        f"Refinement attempt {attempts} requested but no context_query provided - skipping"
                    )
                    break
                
                # Build context with targeted query
                if isinstance(self.context_builder, RecursiveContextBuilder):
                    bundle = self.context_builder.build_recursive_context(
                        chunk.chunk_id,
                        include_evidence=self.config.refinement_include_evidence or include_evidence,
                        include_litigation=True,
                        neighbor_window=self.config.refinement_manual_window,
                        budget_multiplier=max(1.0, self.config.refinement_token_multiplier),
                        context_query=context_query,  # Pass the search query
                    )
                else:
                    bundle = self.context_builder.build_context(
                        chunk.chunk_id,
                        include_evidence=self.config.refinement_include_evidence or include_evidence,
                        neighbor_window=self.config.refinement_manual_window,
                        budget_multiplier=max(1.0, self.config.refinement_token_multiplier),
                        context_query=context_query,  # Pass query for targeted RAG
                    )
                
                # Re-analyze with expanded context
                analysis = self.analysis_client.analyze(chunk, bundle)
                
                # If still needs context but we've made progress, continue
                # Otherwise, break to avoid infinite loops
                if analysis.get("needs_additional_context") and attempts >= 3:
                    # After 3 attempts, check if we're making progress
                    # If context_query changed, continue; otherwise break
                    new_query = analysis.get("context_query")
                    if new_query == context_query:
                        logger.info(f"Context query unchanged after {attempts} attempts - stopping refinement")
                        break

        if attempts:
            analysis["refined"] = True
            analysis["refinement_attempts"] = attempts

        return analysis, bundle

    def _resolve_audit(self, audit_identifier: int | str) -> Audit | None:
        stmt: Select[Audit]
        if isinstance(audit_identifier, int):
            stmt = select(Audit).where(Audit.id == audit_identifier)
        elif isinstance(audit_identifier, str) and audit_identifier.isdigit():
            stmt = select(Audit).where(Audit.id == int(audit_identifier))
        else:
            stmt = select(Audit).where(Audit.external_id == str(audit_identifier))

        return self.session.execute(stmt).scalar_one_or_none()

    def _ensure_chunk_counts(self, audit: Audit) -> None:
        if audit.chunk_total and audit.chunk_total > 0:
            return
        stmt = select(func.count()).select_from(Chunk).where(Chunk.document_id == audit.document_id)
        chunk_total = self.session.execute(stmt).scalar_one()
        audit.chunk_total = int(chunk_total or 0)
        self.session.flush()

    def _pending_chunks(self, audit: Audit, *, limit: int | None = None) -> Iterable[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == audit.document_id)
            .outerjoin(
                AuditChunkResult,
                and_(
                    AuditChunkResult.audit_id == audit.id,
                    AuditChunkResult.chunk_id == Chunk.chunk_id,
                ),
            )
            .where(AuditChunkResult.id.is_(None))
            .order_by(Chunk.chunk_index.asc())
        )
        if limit:
            stmt = stmt.limit(limit)
        result = self.session.execute(stmt)
        return result.scalars().all()

    def _pending_chunk_count(self, audit: Audit) -> int:
        stmt = (
            select(func.count())
            .select_from(Chunk)
            .outerjoin(
                AuditChunkResult,
                and_(
                    AuditChunkResult.audit_id == audit.id,
                    AuditChunkResult.chunk_id == Chunk.chunk_id,
                ),
            )
            .where(
                Chunk.document_id == audit.document_id,
                AuditChunkResult.id.is_(None),
            )
        )
        count = self.session.execute(stmt).scalar_one()
        return int(count or 0)

