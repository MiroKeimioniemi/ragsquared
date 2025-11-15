"""Service for automatically processing uploaded documents through the full pipeline."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from ..config.settings import AppConfig
from ..db.models import Audit, Document
from ..processing.extraction import DocumentExtractor
from .chunking import SemanticChunker
from .embeddings import EmbeddingService
from .compliance_runner import ComplianceRunner

logger = logging.getLogger(__name__)


class DocumentProcessingError(Exception):
    """Raised when document processing fails."""


class DocumentProcessor:
    """Orchestrates the full document processing pipeline: extract → chunk → embed."""

    def __init__(self, data_root: Path, session: Session, config: AppConfig | None = None):
        self.data_root = Path(data_root)
        self.session = session
        self.config = config or AppConfig()
        self.extractor = DocumentExtractor()
        self.chunker = SemanticChunker(self.config.chunking)
        self.embedding_service = EmbeddingService(session, self.config)

    def process_document(
        self,
        document: Document,
        *,
        run_audit: bool = True,
        is_draft: bool = False,
    ) -> dict[str, Any]:
        """
        Process a document through the full pipeline.
        
        Args:
            document: The document to process
            run_audit: Whether to automatically run the audit after processing
            is_draft: Whether this is a draft audit (affects processing depth)
            
        Returns:
            Dictionary with processing results and status
        """
        try:
            # Step 1: Extract text
            logger.info(f"Extracting text from document {document.id}")
            document_path = self.data_root / document.storage_path
            if not document_path.exists():
                raise DocumentProcessingError(f"Document file not found: {document_path}")
            
            extracted = self.extractor.extract(document_path)
            
            # Save extracted JSON to processed directory
            processed_dir = self.data_root / "processed" / document.external_id
            processed_dir.mkdir(parents=True, exist_ok=True)
            extracted_json_path = processed_dir / "extracted.json"
            extracted_json_path.write_text(extracted.to_json(indent=2), encoding="utf-8")
            
            # Step 2: Chunk the document
            logger.info(f"Chunking document {document.id}")
            from .chunking import SectionText
            
            # Convert extracted sections to SectionText objects
            sections = [
                SectionText(
                    index=section.index,
                    title=section.title,
                    content=section.content,
                    section_path=None,  # Will be resolved by chunker
                    metadata=section.metadata,
                )
                for section in extracted.sections
            ]
            
            # Generate chunks
            # Use section-aware chunking for all document types (regulations, AMC, GM, and manuals)
            # This provides better RAG context - each section/subsection becomes one chunk
            # (unless it exceeds max_section_tokens, in which case it's split)
            doc_id = str(document.external_id)
            chunk_payloads = self.chunker.chunk_sections(
                doc_id, 
                sections,
                section_aware=True,  # Use section-aware for all documents
            )
            
            if not chunk_payloads:
                raise DocumentProcessingError("No chunks generated from document")
            
            # Persist chunks to database
            from ..db.models import Chunk
            
            existing_chunks = (
                self.session.query(Chunk)
                .filter(Chunk.document_id == document.id)
                .all()
            )
            if existing_chunks:
                # Delete existing chunks
                for chunk in existing_chunks:
                    self.session.delete(chunk)
                self.session.flush()
            
            chunk_count = 0
            for idx, chunk_payload in enumerate(chunk_payloads):
                # Convert section_path list to string
                section_path_str = " > ".join(chunk_payload.section_path) if chunk_payload.section_path else None
                
                chunk = Chunk(
                    document_id=document.id,
                    chunk_id=chunk_payload.chunk_id,
                    chunk_index=idx,  # Use sequential index
                    section_path=section_path_str,
                    parent_heading=chunk_payload.parent_heading,
                    content=chunk_payload.text,
                    token_count=chunk_payload.token_count,
                    chunk_metadata=chunk_payload.metadata,
                    embedding_status="pending",
                )
                self.session.add(chunk)
                chunk_count += 1
            
            self.session.commit()
            logger.info(f"Created {chunk_count} chunks for document {document.id}")
            
            # Step 3: Generate embeddings
            logger.info(f"Generating embeddings for document {document.id}")
            collection_name = self._get_collection_name(document.source_type)
            
            # Fetch chunks for this document
            from ..db.models import Chunk
            chunks = (
                self.session.query(Chunk)
                .filter(Chunk.document_id == document.id)
                .filter(Chunk.embedding_status == "pending")
                .all()
            )
            
            if chunks:
                result = self.embedding_service.process_chunks(
                    chunks,
                    collection_name=collection_name,
                )
                processed_count = result.get("processed", 0)
                logger.info(f"Generated {processed_count} embeddings for document {document.id}")
            else:
                processed_count = 0
                logger.warning(f"No pending chunks found for document {document.id}")
            
            # Step 4: Optionally run audit
            audit_id = None
            if run_audit:
                from ..db.models import Audit
                
                # Find or create audit for this document
                audit = (
                    self.session.query(Audit)
                    .filter(Audit.document_id == document.id)
                    .order_by(Audit.created_at.desc())
                    .first()
                )
                
                audit_result = None
                if audit:
                    audit_id = audit.id
                    logger.info(f"Running audit {audit_id} for document {document.id}")
                    runner = ComplianceRunner(self.session, self.config)
                    audit_result = runner.run(
                        audit_id,
                        max_chunks=5 if is_draft else None,
                        include_evidence=not is_draft,
                    )
                    logger.info(
                        f"Audit {audit_id} completed: {audit_result.processed} chunks processed, "
                        f"{audit_result.remaining} remaining, status: {audit_result.status}"
                    )
                    # If audit failed, log but don't raise - let the audit status communicate the failure
                    if audit_result.status == "failed":
                        logger.warning(
                            f"Audit {audit_id} failed: {audit_result.processed} chunks processed before failure. "
                            f"Check audit status for details."
                        )
                        # Refresh audit to get updated failure_reason
                        self.session.refresh(audit)
                else:
                    logger.warning(f"No audit found for document {document.id}, skipping audit run")
            
            # Update document status
            document.status = "processed"
            self.session.commit()
            
            # Check if audit failed gracefully (rate limit, etc.)
            if audit and audit_result and audit_result.status == "failed":
                return {
                    "document_id": document.id,
                    "chunks_created": chunk_count,
                    "embeddings_generated": processed_count,
                    "audit_id": audit.external_id if audit else None,
                    "status": "processed",  # Document processed successfully
                    "audit_status": "failed",  # But audit failed
                    "error": audit.failure_reason,
                }
            
            return {
                "document_id": document.id,
                "chunks_created": chunk_count,
                "embeddings_generated": processed_count,
                "audit_id": audit.external_id if audit else None,
                "status": "completed",
            }
            
        except Exception as exc:
            logger.exception(f"Error processing document {document.id}: {exc}")
            # Check if audit failed gracefully before marking document as failed
            audit = (
                self.session.query(Audit)
                .filter(Audit.document_id == document.id)
                .order_by(Audit.created_at.desc())
                .first()
            )
            if audit and audit.status == "failed" and audit.failure_reason:
                # Audit failed gracefully (e.g., rate limit) - document is still processed
                document.status = "processed"
                logger.warning(
                    f"Document processing completed but audit failed: {audit.failure_reason}"
                )
                self.session.commit()
                return {
                    "document_id": document.id,
                    "status": "processed",
                    "audit_status": "failed",
                    "audit_id": audit.external_id,
                    "error": audit.failure_reason,
                }
            # Otherwise, mark document as failed for unexpected errors
            document.status = "failed"
            self.session.commit()
            raise DocumentProcessingError(f"Failed to process document: {exc}") from exc

    @staticmethod
    def _get_collection_name(source_type: str) -> str:
        """Map document source type to ChromaDB collection name."""
        mapping = {
            "manual": "manual_chunks",
            "regulation": "regulation_chunks",
            "amc": "amc_chunks",
            "gm": "gm_chunks",
            "evidence": "evidence_chunks",
        }
        return mapping.get(source_type, "manual_chunks")

