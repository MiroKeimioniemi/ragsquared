"""
Recursive RAG Context Builder

Implements recursive RAG that:
1. Extracts section/subsection references from chunks
2. Recursively fetches referenced sections
3. Finds litigation related to each chunk
4. Recursively processes litigation references
5. Builds comprehensive context for analysis
"""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from ..config.settings import AppConfig
from ..db.models import Chunk
from .context_builder import ContextBuilder, ContextBundle, ContextSlice

logger = logging.getLogger(__name__)


@dataclass
class Reference:
    """Represents a reference to another section/subsection."""
    text: str
    section_path: str | None = None
    section_number: str | None = None


class ReferenceExtractor:
    """Extracts section/subsection references from text."""
    
    # Patterns for common section reference formats
    SECTION_PATTERNS = [
        # "Section 4.2", "section 4.2", "Sect. 4.2"
        re.compile(r'(?:section|sect\.?)\s+(\d+(?:\.\d+)*(?:\.\d+)?)', re.IGNORECASE),
        # "Chapter 3", "chapter 3"
        re.compile(r'(?:chapter|ch\.?)\s+(\d+)', re.IGNORECASE),
        # "Part 145.A.30", "Part-145.A.30" (but not just "Part-145" alone)
        re.compile(r'part[-\s]?(\d+)[\.\s]?([A-Z])?[\.\s]?(\d+)', re.IGNORECASE),
        # "OSA 5", "OSA 5.2"
        re.compile(r'osa\s+(\d+(?:\.\d+)?)', re.IGNORECASE),
        # "Kohdassa 3.4", "kohdassa 3.4" (Finnish)
        re.compile(r'kohdassa\s+(\d+(?:\.\d+)?)', re.IGNORECASE),
        # "Section 4.2.1", "4.2.1" - but only if it looks like a section number (not dates, IDs, etc.)
        re.compile(r'\b(\d+\.\d+(?:\.\d+)?)\b'),
    ]
    
    # Patterns to exclude (dates, IDs, etc.)
    EXCLUDE_PATTERNS = [
        re.compile(r'\d{1,2}\.\d{1,2}\.\d{4}'),  # Dates like 3.11.2025
        re.compile(r'FI\.\d+\.\d+'),  # Organization IDs like FI.145.9999
        re.compile(r'^\d{4}$'),  # 4-digit years
        re.compile(r'^\d+\.\d+\.\d+\.\d+$'),  # IP addresses
    ]
    
    def extract_references(self, text: str) -> list[Reference]:
        """Extract all section/subsection references from text."""
        references: list[Reference] = []
        seen = set()
        
        for pattern in self.SECTION_PATTERNS:
            for match in pattern.finditer(text):
                ref_text = match.group(0).strip()
                section_num = match.group(1) if match.groups() else None
                
                # Skip if matches exclusion patterns
                if any(exclude_pattern.search(ref_text) for exclude_pattern in self.EXCLUDE_PATTERNS):
                    continue
                
                # Skip very short matches that are likely false positives
                if len(ref_text) < 3:
                    continue
                
                # Skip if it's just a number without context (likely not a section reference)
                if pattern == self.SECTION_PATTERNS[-1]:  # The generic \d+\.\d+ pattern
                    # Check if it's preceded/followed by section-related words
                    start_pos = match.start()
                    end_pos = match.end()
                    context_before = text[max(0, start_pos-20):start_pos].lower()
                    context_after = text[end_pos:min(len(text), end_pos+20)].lower()
                    
                    # Skip if no section-related context
                    section_keywords = ['section', 'chapter', 'part', 'osa', 'kohdassa', 'kohta', 'appendix']
                    if not any(keyword in context_before or keyword in context_after for keyword in section_keywords):
                        # Also skip if it looks like a date or version number
                        if re.search(r'\d{4}', ref_text) or re.search(r'v?\d+\.\d+\.\d+', ref_text):
                            continue
                
                # Avoid duplicates
                if ref_text.lower() not in seen:
                    seen.add(ref_text.lower())
                    references.append(Reference(
                        text=ref_text,
                        section_number=section_num,
                        section_path=None  # Will be resolved during RAG
                    ))
        
        return references


class RecursiveContextBuilder:
    """Builds context using recursive RAG following references."""
    
    def __init__(
        self,
        session: Session,
        app_config: AppConfig,
        *,
        base_context_builder: ContextBuilder | None = None,
        max_depth: int = 3,
        max_references_per_chunk: int = 10,
    ):
        self.session = session
        self.app_config = app_config
        self.base_builder = base_context_builder or ContextBuilder(session, app_config)
        self.reference_extractor = ReferenceExtractor()
        self.max_depth = max_depth
        self.max_references_per_chunk = max_references_per_chunk
        
        # Track processed chunks to avoid infinite loops
        self._processed_chunk_ids: set[str] = set()
        self._processed_references: set[str] = set()
    
    def build_recursive_context(
        self,
        chunk_id: str,
        *,
        include_evidence: bool = False,
        include_litigation: bool = True,
        neighbor_window: int | None = None,
        budget_multiplier: float = 1.0,
        context_query: str | None = None,
    ) -> ContextBundle:
        """
        Build comprehensive context using recursive RAG.
        
        Process:
        1. Initial RAG for the focus chunk
        2. Extract references from focus chunk
        3. Recursively fetch referenced sections
        4. For each chunk (original + references), find litigation
        5. Recursively process litigation references
        6. Build final context bundle
        """
        self._processed_chunk_ids.clear()
        self._processed_references.clear()
        
        # Start with base context
        logger.info(f"Building recursive context for chunk {chunk_id[:16]}...")
        base_bundle = self.base_builder.build_context(
            chunk_id,
            include_evidence=include_evidence,
            neighbor_window=neighbor_window,
            budget_multiplier=budget_multiplier,
        )
        
        # Track all chunks we need to process
        chunks_to_process: deque[tuple[str, int]] = deque([(chunk_id, 0)])  # (chunk_id, depth)
        all_manual_chunks: list[ContextSlice] = list(base_bundle.manual_neighbors)
        all_regulation_chunks: list[ContextSlice] = list(base_bundle.regulation_slices)
        all_guidance_chunks: list[ContextSlice] = list(base_bundle.guidance_slices)
        all_litigation_chunks: list[ContextSlice] = []
        
        # Process chunks recursively
        while chunks_to_process:
            current_chunk_id, depth = chunks_to_process.popleft()
            
            if depth >= self.max_depth:
                logger.debug(f"Skipping chunk {current_chunk_id[:16]} - max depth reached")
                continue
            
            if current_chunk_id in self._processed_chunk_ids:
                continue
            
            self._processed_chunk_ids.add(current_chunk_id)
            
            # Load chunk
            chunk = self.base_builder.load_chunk(current_chunk_id)
            if not chunk:
                continue
            
            logger.info(f"Processing chunk {current_chunk_id[:16]} at depth {depth}")
            
            # Extract references from this chunk
            references = self.reference_extractor.extract_references(chunk.content)
            
            # If a context_query is provided (from refinement), also search for that
            if context_query and depth == 0:  # Only on first pass
                logger.info(f"Processing context_query: {context_query[:100]}...")
                # Create a synthetic reference from the query to search for it
                query_ref = Reference(text=context_query, section_path=None, section_number=None)
                references.append(query_ref)
                
                # Also do a direct semantic search for the concept (not just as a reference)
                concept_chunks = self._search_for_concept(context_query, chunk.document_id, current_chunk_id)
                for concept_chunk in concept_chunks:
                    if not any(c.metadata.get("chunk_id") == concept_chunk.metadata.get("chunk_id")
                              for c in all_manual_chunks):
                        all_manual_chunks.append(concept_chunk)
                        # Add to queue for recursive processing
                        concept_chunk_id = concept_chunk.metadata.get("chunk_id")
                        if concept_chunk_id and concept_chunk_id not in self._processed_chunk_ids:
                            chunks_to_process.append((concept_chunk_id, depth + 1))
            
            logger.info(f"Found {len(references)} references in chunk {current_chunk_id[:16]}")
            
            # For each reference, try to find the referenced section via RAG
            for ref in references[:self.max_references_per_chunk]:
                if ref.text.lower() in self._processed_references:
                    continue
                
                self._processed_references.add(ref.text.lower())
                
                # Search for referenced section in manual chunks
                ref_chunks = self._find_referenced_section(
                    ref,
                    document_id=chunk.document_id,
                    current_chunk_id=current_chunk_id,
                )
                
                # Also search in regulations if it looks like a regulation reference or is a context_query
                if any(keyword in ref.text.lower() for keyword in ['part', 'amc', 'gm', 'regulation']) or context_query:
                    reg_chunks = self._find_in_regulations(ref, current_chunk_id)
                    # Add regulation chunks to all_regulation_chunks
                    for reg_chunk in reg_chunks:
                        if not any(c.metadata.get("chunk_id") == reg_chunk.metadata.get("chunk_id")
                                  for c in all_regulation_chunks):
                            all_regulation_chunks.append(reg_chunk)
                
                for ref_chunk in ref_chunks:
                    # Add to manual chunks if not already present
                    if not any(c.metadata.get("chunk_id") == ref_chunk.metadata.get("chunk_id") 
                              for c in all_manual_chunks):
                        all_manual_chunks.append(ref_chunk)
                        # Add to queue for recursive processing
                        ref_chunk_id = ref_chunk.metadata.get("chunk_id")
                        if ref_chunk_id and ref_chunk_id not in self._processed_chunk_ids:
                            chunks_to_process.append((ref_chunk_id, depth + 1))
            
            # Find litigation related to this chunk
            if include_litigation:
                litigation_chunks = self._find_litigation(chunk)
                for lit_chunk in litigation_chunks:
                    if not any(c.metadata.get("chunk_id") == lit_chunk.metadata.get("chunk_id")
                              for c in all_litigation_chunks):
                        all_litigation_chunks.append(lit_chunk)
                        # Recursively process litigation references
                        lit_chunk_id = lit_chunk.metadata.get("chunk_id")
                        if lit_chunk_id and lit_chunk_id not in self._processed_chunk_ids:
                            chunks_to_process.append((lit_chunk_id, depth + 1))
        
        # Build final bundle
        final_bundle = ContextBundle(focus=base_bundle.focus)
        final_bundle.manual_neighbors = all_manual_chunks[:50]  # Limit to avoid token overflow
        final_bundle.regulation_slices = all_regulation_chunks[:50]
        final_bundle.guidance_slices = all_guidance_chunks[:50]
        final_bundle.evidence_slices = base_bundle.evidence_slices
        
        # Add litigation as a new category (or merge into evidence)
        if all_litigation_chunks:
            # For now, add to evidence slices
            final_bundle.evidence_slices.extend(all_litigation_chunks[:20])
        
        # Recalculate tokens
        token_estimator = self.base_builder.token_estimator
        final_bundle.total_tokens = (
            token_estimator.count(final_bundle.focus.content) +
            sum(token_estimator.count(c.content) for c in final_bundle.manual_neighbors) +
            sum(token_estimator.count(c.content) for c in final_bundle.regulation_slices) +
            sum(token_estimator.count(c.content) for c in final_bundle.guidance_slices) +
            sum(token_estimator.count(c.content) for c in final_bundle.evidence_slices)
        )
        
        logger.info(
            f"Recursive context built: {len(final_bundle.manual_neighbors)} manual chunks, "
            f"{len(final_bundle.regulation_slices)} regulations, "
            f"{len(final_bundle.guidance_slices)} guidance, "
            f"{len(all_litigation_chunks)} litigation chunks, "
            f"{final_bundle.total_tokens} total tokens"
        )
        
        return final_bundle
    
    def _find_referenced_section(
        self,
        reference: Reference,
        document_id: int,
        current_chunk_id: str,
    ) -> list[ContextSlice]:
        """Find chunks that match a section reference."""
        # Use the reference text as a query for RAG
        query_text = reference.text
        
        # Also try searching by section number if available
        if reference.section_number:
            query_text = f"{reference.text} {reference.section_number}"
        
        # Search in manual_chunks collection filtered by document_id
        matches = self.base_builder.vector_query(
            collection="manual_chunks",
            query_text=query_text,
            cache_key=f"{current_chunk_id}_ref_{reference.text}",
            top_k=5,
            document_id=document_id,
        )
        
        slices: list[ContextSlice] = []
        for idx, match in enumerate(matches):
            # Filter out low-quality matches (ChromaDB returns distances, lower is better)
            # Typical good matches have distances < 1.0, very poor matches > 2.0
            if match.score is not None and match.score > 1.5:  # Filter out poor matches
                continue
            
            # Filter out corrupted content (looks like binary data or coordinates)
            if match.content and (len(match.content.strip()) < 10 or 
                                 re.match(r'^[\d\s\.\-]+$', match.content.strip()) or
                                 '-1097280' in match.content or '-448310' in match.content):
                continue
            
            label = f"Referenced section: {reference.text} (match {idx + 1})"
            metadata = dict(match.metadata or {})
            metadata["reference_source"] = reference.text
            metadata["reference_type"] = "section_reference"
            
            tokens = self.base_builder.token_estimator.count(match.content)
            # Convert distance to similarity score for display (1 / (1 + distance))
            # This gives a score between 0 and 1, where 1 is perfect match
            display_score = 1.0 / (1.0 + match.score) if match.score is not None else None
            slices.append(
                ContextSlice(
                    label=label,
                    source="manual",
                    content=match.content,
                    token_count=tokens,
                    metadata=metadata,
                    score=display_score,  # Use similarity score for display
                )
            )
        
        return slices
    
    def _find_in_regulations(
        self,
        reference: Reference,
        current_chunk_id: str,
    ) -> list[ContextSlice]:
        """Search for information in regulation chunks."""
        query_text = reference.text
        
        matches = self.base_builder.vector_query(
            collection="regulation_chunks",
            query_text=query_text,
            cache_key=f"{current_chunk_id}_reg_{reference.text}",
            top_k=5,
            document_id=None,
        )
        
        slices: list[ContextSlice] = []
        for idx, match in enumerate(matches):
            # Filter out low-quality matches
            if match.score is not None and match.score > 1.5:
                continue
            
            # Filter out corrupted content
            if match.content and (len(match.content.strip()) < 10 or 
                                 re.match(r'^[\d\s\.\-]+$', match.content.strip()) or
                                 '-1097280' in match.content or '-448310' in match.content):
                continue
            
            label = f"Regulation search: {reference.text} (match {idx + 1})"
            metadata = dict(match.metadata or {})
            metadata["reference_source"] = reference.text
            metadata["reference_type"] = "regulation_search"
            
            tokens = self.base_builder.token_estimator.count(match.content)
            # Convert distance to similarity score for display
            display_score = 1.0 / (1.0 + match.score) if match.score is not None else None
            slices.append(
                ContextSlice(
                    label=label,
                    source="regulation",
                    content=match.content,
                    token_count=tokens,
                    metadata=metadata,
                    score=display_score,
                )
            )
        
        return slices
    
    def _search_for_concept(
        self,
        concept_query: str,
        document_id: int,
        current_chunk_id: str,
    ) -> list[ContextSlice]:
        """Search for a concept/topic in the document (not a section reference)."""
        # Search in manual_chunks for the concept
        matches = self.base_builder.vector_query(
            collection="manual_chunks",
            query_text=concept_query,
            cache_key=f"{current_chunk_id}_concept_{concept_query[:50]}",
            top_k=10,  # More results for concept searches
            document_id=document_id,
        )
        
        slices: list[ContextSlice] = []
        for idx, match in enumerate(matches):
            label = f"Concept search: {concept_query[:50]}... (match {idx + 1})"
            metadata = dict(match.metadata or {})
            metadata["concept_query"] = concept_query
            metadata["reference_type"] = "concept_search"
            
            tokens = self.base_builder.token_estimator.count(match.content)
            slices.append(
                ContextSlice(
                    label=label,
                    source="manual",
                    content=match.content,
                    token_count=tokens,
                    metadata=metadata,
                    score=match.score,
                )
            )
        
        # Also search in regulations
        reg_matches = self.base_builder.vector_query(
            collection="regulation_chunks",
            query_text=concept_query,
            cache_key=f"{current_chunk_id}_concept_reg_{concept_query[:50]}",
            top_k=5,
            document_id=None,
        )
        
        for idx, match in enumerate(reg_matches):
            label = f"Regulation concept: {concept_query[:50]}... (match {idx + 1})"
            metadata = dict(match.metadata or {})
            metadata["concept_query"] = concept_query
            metadata["reference_type"] = "regulation_concept_search"
            
            tokens = self.base_builder.token_estimator.count(match.content)
            slices.append(
                ContextSlice(
                    label=label,
                    source="regulation",
                    content=match.content,
                    token_count=tokens,
                    metadata=metadata,
                    score=match.score,
                )
            )
        
        return slices
    
    def _find_litigation(self, chunk: Chunk) -> list[ContextSlice]:
        """Find litigation/case law related to this chunk."""
        # Search in evidence_chunks or a dedicated litigation collection
        # For now, use evidence_chunks as litigation storage
        matches = self.base_builder.vector_query(
            collection="evidence_chunks",
            query_text=chunk.content,
            cache_key=f"{chunk.chunk_id}_litigation",
            top_k=5,
            document_id=None,  # Litigation spans multiple documents
        )
        
        slices: list[ContextSlice] = []
        for idx, match in enumerate(matches):
            label = f"Litigation/Case Law (match {idx + 1})"
            metadata = dict(match.metadata or {})
            metadata["reference_type"] = "litigation"
            metadata["source_chunk_id"] = chunk.chunk_id
            
            tokens = self.base_builder.token_estimator.count(match.content)
            slices.append(
                ContextSlice(
                    label=label,
                    source="evidence",
                    content=match.content,
                    token_count=tokens,
                    metadata=metadata,
                    score=match.score,
                )
            )
        
        return slices

