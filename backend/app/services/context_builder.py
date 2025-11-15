from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from ..config.settings import AppConfig, ContextBuilderConfig
from ..db.models import Chunk

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ContextSlice:
    """Normalized representation of a context snippet."""

    label: str
    source: str
    content: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float | None = None


@dataclass(slots=True)
class ContextBundle:
    """Full context package returned to the compliance runner."""

    focus: ContextSlice
    manual_neighbors: list[ContextSlice] = field(default_factory=list)
    regulation_slices: list[ContextSlice] = field(default_factory=list)
    guidance_slices: list[ContextSlice] = field(default_factory=list)
    evidence_slices: list[ContextSlice] = field(default_factory=list)
    token_breakdown: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    total_tokens: int = 0
    truncated: bool = False

    def all_slices(self) -> list[ContextSlice]:
        slices: list[ContextSlice] = []
        slices.extend(self.manual_neighbors)
        slices.extend(self.regulation_slices)
        slices.extend(self.guidance_slices)
        slices.extend(self.evidence_slices)
        return slices

    def render_text(self) -> str:
        """Render the bundle as prompt-ready text."""

        sections: list[str] = []
        for prefix, collection in [
            ("Manual Context", self.manual_neighbors),
            ("Regulation Context", self.regulation_slices),
            ("Guidance Context", self.guidance_slices),
            ("Evidence Context", self.evidence_slices),
        ]:
            if not collection:
                continue
            section_lines = [f"### {prefix}"]
            for slice_ in collection:
                heading = slice_.metadata.get("heading") or ""
                section_lines.append(f"- {slice_.label}{f' [{heading}]' if heading else ''}:")
                section_lines.append(slice_.content)
            sections.append("\n".join(section_lines))
        return "\n\n".join(sections)


@dataclass(slots=True)
class VectorMatch:
    content: str
    metadata: dict[str, Any]
    score: float | None = None


class VectorClient:
    """Interface for vector retrieval backends."""

    def query(self, collection: str, query_text: str, n_results: int) -> list[VectorMatch]:
        raise NotImplementedError


class NullVectorClient(VectorClient):
    """Fallback client used when ChromaDB (or other backend) is unavailable."""

    def query(self, collection: str, query_text: str, n_results: int) -> list[VectorMatch]:
        return []


class ChromaVectorClient(VectorClient):
    """Thin wrapper around ChromaDB queries to simplify testing."""

    def __init__(self, chroma_path: Path, app_config=None):
        try:
            import chromadb  # type: ignore
        except ImportError:  # pragma: no cover - optional dependency
            logger.warning("chromadb is not installed; vector retrieval will be disabled.")
            self._client = None
            self._embedding_client = None
            return

        self._client = chromadb.PersistentClient(path=str(chroma_path))
        
        # Initialize embedding client to generate query embeddings with the same model as storage
        self._embedding_client = None
        if app_config:
            try:
                from .embeddings import EmbeddingClient, EmbeddingConfig
                cache_dir = Path(app_config.data_root) / "cache" / "embeddings"
                cache_dir.mkdir(parents=True, exist_ok=True)
                
                # Use OpenRouter for embeddings
                api_key = app_config.openrouter_api_key or app_config.llm_api_key
                if not api_key:
                    logger.warning("No API key found for embedding client; query embeddings will be disabled")
                else:
                    embedding_config = EmbeddingConfig(
                        model=app_config.embedding_model,
                        api_key=api_key,
                        api_base_url=app_config.embedding_api_base_url,
                        batch_size=32,
                        cache_dir=cache_dir,
                    )
                    self._embedding_client = EmbeddingClient(embedding_config)
            except Exception as exc:
                logger.warning("Failed to initialize embedding client for queries: %s", exc)

    def query(self, collection: str, query_text: str, n_results: int, document_id: int | None = None) -> list[VectorMatch]:
        if self._client is None or not query_text or n_results <= 0:
            return []

        try:
            collection_obj = self._client.get_collection(name=collection)
        except Exception as exc:  # pragma: no cover - collection missing
            logger.debug("Vector collection '%s' not available: %s", collection, exc)
            return []

        try:
            # Build where clause to filter by document_id if provided
            where_clause = None
            if document_id is not None:
                where_clause = {"document_id": document_id}
            
            # Generate query embedding using the same model as storage
            # This ensures dimension compatibility
            if self._embedding_client:
                query_embeddings = self._embedding_client.embed_texts([query_text])
                if query_embeddings:
                    # Validate query embedding dimension matches collection dimension
                    query_dim = len(query_embeddings[0])
                    collection_count = collection_obj.count()
                    if collection_count > 0:
                        # Check collection dimension by peeking at existing embeddings
                        sample_result = collection_obj.peek(limit=1)
                        if sample_result.get("embeddings") and len(sample_result["embeddings"]) > 0:
                            collection_dim = len(sample_result["embeddings"][0])
                            if query_dim != collection_dim:
                                logger.error(
                                    f"Dimension mismatch in query for collection '{collection}': "
                                    f"collection has {collection_dim} dimensions, "
                                    f"but query embedding has {query_dim} dimensions. "
                                    f"This will cause query failures. "
                                    f"Please ensure EMBEDDING_MODEL matches the model used to create the collection."
                                )
                                return []  # Return empty results rather than failing
                    
                    query_kwargs = {
                        "query_embeddings": query_embeddings,
                        "n_results": n_results
                    }
                    if where_clause:
                        query_kwargs["where"] = where_clause
                    results = collection_obj.query(**query_kwargs)
                else:
                    # Fallback to text query if embedding generation fails
                    query_kwargs = {"query_texts": [query_text], "n_results": n_results}
                    if where_clause:
                        query_kwargs["where"] = where_clause
                    results = collection_obj.query(**query_kwargs)
            else:
                # Fallback: use text query (may fail if dimension mismatch)
                logger.warning(
                    "Embedding client not available, using text query (may cause dimension mismatch)"
                )
                query_kwargs = {"query_texts": [query_text], "n_results": n_results}
                if where_clause:
                    query_kwargs["where"] = where_clause
                results = collection_obj.query(**query_kwargs)
        except Exception as exc:  # pragma: no cover - query failure
            logger.warning("Vector query failed for %s: %s", collection, exc)
            return []

        matches: list[VectorMatch] = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for doc, meta, score in zip(documents, metadatas, distances):
            matches.append(VectorMatch(content=doc, metadata=meta or {}, score=score))
        return matches
    
    def close(self):
        """Close the embedding client if it exists."""
        if self._embedding_client:
            self._embedding_client.close()


class TokenEstimator:
    """Helper for estimating token counts."""

    def __init__(self, tokenizer_name: str):
        self.tokenizer_name = tokenizer_name
        self._encoding = self._load_encoding(tokenizer_name)

    def count(self, text: str) -> int:
        if not text:
            return 0
        if self._encoding is None:
            return max(1, len(text) // 4)
        return len(self._encoding.encode(text))

    @staticmethod
    def _load_encoding(name: str):
        try:
            import tiktoken  # type: ignore
        except Exception:  # pragma: no cover - tokenizer optional
            logger.debug("tiktoken not available; using character-based token estimates.")
            return None

        for resolver in (
            lambda: tiktoken.get_encoding(name),
            lambda: tiktoken.encoding_for_model(name),
            lambda: tiktoken.get_encoding("cl100k_base"),
        ):
            try:
                return resolver()
            except Exception:
                continue
        logger.warning("Unable to resolve tokenizer '%s'; falling back to character heuristic.", name)
        return None


class TokenBudget:
    """Tracks token consumption across context categories."""

    def __init__(self, total_limit: int):
        self.total_limit = max(0, total_limit)
        self.total_used = 0
        self.bucket_used: dict[str, int] = defaultdict(int)
        self.truncated = False

    def allow(self, bucket: str, token_limit: int, tokens: int) -> bool:
        if token_limit <= 0 or tokens <= 0:
            return False
        if self.total_used + tokens > self.total_limit:
            self.truncated = True
            return False
        if self.bucket_used[bucket] + tokens > token_limit:
            self.truncated = True
            return False
        self.total_used += tokens
        self.bucket_used[bucket] += tokens
        return True


class ContextBuilder:
    """Deterministic retrieval helper that assembles context bundles."""

    def __init__(
        self,
        session: Session,
        app_config: AppConfig,
        *,
        vector_client: VectorClient | None = None,
    ):
        self.session = session
        self.app_config = app_config
        self.config: ContextBuilderConfig = app_config.context_builder
        self.token_estimator = TokenEstimator(self.config.tokenizer)
        chroma_path = Path(app_config.data_root) / "chroma"
        self.vector = vector_client or ChromaVectorClient(chroma_path, app_config=app_config)
        self._query_cache: dict[tuple[str, str], list[VectorMatch]] = {}

    def build_context(
        self,
        chunk_id: str,
        *,
        include_evidence: bool = False,
        neighbor_window: int | None = None,
        budget_multiplier: float = 1.0,
        context_query: str | None = None,
    ) -> ContextBundle:
        chunk = self._load_chunk(chunk_id)
        if chunk is None:
            raise ValueError(f"Chunk '{chunk_id}' not found.")

        focus_slice = self._chunk_to_slice(chunk, label="Focus Chunk", source="manual")
        bundle = ContextBundle(focus=focus_slice)

        budget = TokenBudget(int(self.config.total_token_budget * budget_multiplier))

        manual_window = neighbor_window if neighbor_window is not None else self.config.manual_neighbor_window
        manual_limit = int(self.config.manual_token_budget * budget_multiplier)
        regulation_limit = int(self.config.regulation_token_budget * budget_multiplier)
        guidance_limit = int(self.config.guidance_token_budget * budget_multiplier)
        evidence_limit = int(self.config.evidence_token_budget * budget_multiplier)

        # Collect manual neighbors (sequential chunks)
        manual_neighbors = self._collect_manual_neighbors(chunk, manual_window)
        
        # Also use RAG to find semantically similar chunks within the manual
        # Per spec (Section 3.2): "Vector search: top-5 similar chunks from same manual"
        # IMPORTANT: Filter by document_id to only get chunks from the same document
        # If context_query is provided, use it for targeted search
        manual_query = context_query if context_query else chunk.content
        manual_rag_slices = self._collect_vector_context(
            chunk,
            collection="manual_chunks",
            label_prefix="Manual (similar)",
            source="manual",
            top_k=5,  # Spec requires top-5 similar chunks from same manual via RAG
            query_override=manual_query,
            filter_by_document=True,  # Only get chunks from same document
        )
        # Combine sequential neighbors with RAG results, avoiding duplicates
        seen_chunk_ids = {chunk.chunk_id}
        for neighbor in manual_neighbors:
            seen_chunk_ids.add(neighbor.metadata.get("chunk_id"))
        # Add RAG results that aren't already in neighbors
        for rag_slice in manual_rag_slices:
            rag_chunk_id = rag_slice.metadata.get("chunk_id")
            if rag_chunk_id and rag_chunk_id not in seen_chunk_ids:
                manual_neighbors.append(rag_slice)
                seen_chunk_ids.add(rag_chunk_id)
        
        bundle.manual_neighbors = self._apply_budget(
            budget, bucket="manual", limit=manual_limit, slices=manual_neighbors
        )

        # Per spec (Section 3.2): "Vector search: top-10 relevant regulation chunks"
        # If context_query is provided, use it for targeted search; otherwise use chunk content
        regulation_query = context_query if context_query else chunk.content
        regulation_slices = self._collect_vector_context(
            chunk,
            collection="regulation_chunks",
            label_prefix="Regulation",
            source="regulation",
            top_k=self.config.regulation_top_k,  # top-10 per spec
            query_override=regulation_query,  # Use custom query if provided
        )
        bundle.regulation_slices = self._apply_budget(
            budget,
            bucket="regulation",
            limit=regulation_limit,
            slices=regulation_slices,
        )

        # Per spec (Section 3.2): "Vector search: top-5 relevant AMC/GM chunks"
        # We interpret this as top-5 from AMC and top-5 from GM (separate collections)
        # giving up to 10 total guidance chunks
        # If context_query is provided, use it for targeted search
        guidance_query = context_query if context_query else chunk.content
        guidance_slices: list[ContextSlice] = []
        guidance_slices.extend(
            self._collect_vector_context(
                chunk,
                collection="amc_chunks",
                label_prefix="AMC",
                source="amc",
                top_k=self.config.guidance_top_k,  # top-5 per spec
                query_override=guidance_query,
            )
        )
        guidance_slices.extend(
            self._collect_vector_context(
                chunk,
                collection="gm_chunks",
                label_prefix="GM",
                source="gm",
                top_k=self.config.guidance_top_k,  # top-5 per spec
                query_override=guidance_query,
            )
        )
        bundle.guidance_slices = self._apply_budget(
            budget,
            bucket="guidance",
            limit=guidance_limit,
            slices=guidance_slices,
        )

        if include_evidence and self.config.evidence_top_k > 0:
            # If context_query is provided, use it for targeted evidence search
            evidence_query = context_query if context_query else chunk.content
            evidence_slices = self._collect_vector_context(
                chunk,
                collection="evidence_chunks",
                label_prefix="Evidence",
                source="evidence",
                top_k=self.config.evidence_top_k,
                query_override=evidence_query,
            )
            bundle.evidence_slices = self._apply_budget(
                budget,
                bucket="evidence",
                limit=evidence_limit,
                slices=evidence_slices,
            )

        bundle.total_tokens = budget.total_used
        bundle.truncated = budget.truncated
        bundle.token_breakdown = dict(budget.bucket_used)
        
        # Log context summary at INFO level for visibility - this is critical for debugging RAG usage
        logger.info(
            "Context built for chunk %s: %d manual neighbors (including RAG), %d regulations, %d guidance, %d evidence, total tokens: %d%s",
            chunk.chunk_id[:16],
            len(bundle.manual_neighbors),
            len(bundle.regulation_slices),
            len(bundle.guidance_slices),
            len(bundle.evidence_slices),
            bundle.total_tokens,
            " [TRUNCATED]" if bundle.truncated else "",
        )
        
        # Warn if critical context is missing
        if len(bundle.regulation_slices) == 0:
            logger.warning(
                "⚠️  No regulation context retrieved for chunk %s - LLM will not have regulation references to compare against!",
                chunk.chunk_id[:16],
            )
        if len(bundle.guidance_slices) == 0:
            logger.warning(
                "⚠️  No guidance (AMC/GM) context retrieved for chunk %s - LLM will not have guidance material!",
                chunk.chunk_id[:16],
            )
        
        return bundle

    # ------------------------------------------------------------------ #
    # Manual neighbor retrieval
    # ------------------------------------------------------------------ #
    def _collect_manual_neighbors(self, chunk: Chunk, window: int | None = None) -> list[ContextSlice]:
        window = self.config.manual_neighbor_window if window is None else max(0, window)
        if window <= 0:
            return []

        lower = chunk.chunk_index - window
        upper = chunk.chunk_index + window

        stmt: Select[Chunk] = (
            select(Chunk)
            .where(
                Chunk.document_id == chunk.document_id,
                Chunk.chunk_index >= lower,
                Chunk.chunk_index <= upper,
            )
            .order_by(Chunk.chunk_index.asc())
        )
        neighbors = list(self.session.execute(stmt).scalars())

        slices: list[ContextSlice] = []
        for neighbor in neighbors:
            if neighbor.chunk_id == chunk.chunk_id:
                continue
            offset = neighbor.chunk_index - chunk.chunk_index
            direction = "next" if offset > 0 else "previous"
            label = f"Manual neighbor ({direction} {abs(offset)})"
            slices.append(self._chunk_to_slice(neighbor, label=label, source="manual"))
        return slices

    # ------------------------------------------------------------------ #
    # Vector retrieval helpers
    # ------------------------------------------------------------------ #
    def _collect_vector_context(
        self,
        chunk: Chunk,
        *,
        collection: str,
        label_prefix: str,
        source: str,
        top_k: int,
        query_override: str | None = None,
        filter_by_document: bool = False,
    ) -> list[ContextSlice]:
        if top_k <= 0:
            return []

        # Use custom query if provided, otherwise use chunk content
        query_text = query_override if query_override else chunk.content
        # Filter by document_id if requested (e.g., for manual_chunks to only get same document)
        document_id = chunk.document_id if filter_by_document else None
        matches = self._vector_query(collection, query_text, chunk.chunk_id, top_k, document_id=document_id)
        
        # Log RAG usage - always log at INFO level for visibility
        if matches:
            logger.info(
                "RAG retrieval: Found %d matches from collection '%s' for chunk %s",
                len(matches),
                collection,
                chunk.chunk_id[:16],
            )
        else:
            logger.warning(
                "RAG retrieval: No matches found in collection '%s' for chunk %s (collection may be empty or not exist)",
                collection,
                chunk.chunk_id[:16],
            )
        
        slices: list[ContextSlice] = []
        for idx, match in enumerate(matches):
            # Filter out low-quality matches (ChromaDB returns distances, lower is better)
            if match.score is not None and match.score > 1.5:  # Filter out poor matches
                continue
            
            # Filter out corrupted content
            if match.content and (len(match.content.strip()) < 10 or 
                                 re.match(r'^[\d\s\.\-]+$', match.content.strip()) or
                                 '-1097280' in match.content or '-448310' in match.content):
                continue
            
            label = f"{label_prefix} ref #{idx + 1}"
            metadata = dict(match.metadata or {})
            metadata.setdefault("chunk_id", metadata.get("chunk_id"))
            metadata.setdefault("source", source)
            metadata.setdefault("heading", metadata.get("parent_heading"))
            tokens = metadata.get("token_count")
            if not isinstance(tokens, int):
                tokens = self.token_estimator.count(match.content)
            
            # Convert distance to similarity score for display (1 / (1 + distance))
            # This gives a score between 0 and 1, where 1 is perfect match
            display_score = 1.0 / (1.0 + match.score) if match.score is not None else None
            
            slices.append(
                ContextSlice(
                    label=label,
                    source=source,
                    content=match.content,
                    token_count=tokens,
                    metadata=metadata,
                    score=display_score,  # Use similarity score for display
                )
            )
        return slices

    def vector_query(
        self, collection: str, query_text: str, cache_key: str, top_k: int, document_id: int | None = None
    ) -> list[VectorMatch]:
        """Public method for vector queries (used by recursive context builder)."""
        return self._vector_query(collection, query_text, cache_key, top_k, document_id)
    
    def _vector_query(
        self, collection: str, query_text: str, cache_key: str, top_k: int, document_id: int | None = None
    ) -> list[VectorMatch]:
        if not query_text or top_k <= 0:
            return []
        key = (collection, cache_key, document_id)
        if key in self._query_cache:
            return self._query_cache[key]
        
        # Query vector database for similar chunks (RAG)
        logger.info(
            "RAG query: Searching '%s' collection (top_k=%d) with query (first 50 chars): %s...%s",
            collection,
            top_k,
            query_text[:50],
            f" (filtered by document_id={document_id})" if document_id else "",
        )
        matches = self.vector.query(collection, query_text, top_k, document_id=document_id)
        
        # Log results for visibility - always at INFO level
        if matches:
            logger.info(
                "RAG query: Found %d/%d similar chunks in '%s' collection",
                len(matches),
                top_k,
                collection,
            )
        else:
            logger.warning(
                "RAG query: No results from '%s' collection (collection may be empty or not exist) - RAG will not work for this collection!",
                collection,
            )
        
        self._query_cache[key] = matches
        return matches

    # ------------------------------------------------------------------ #
    # Slice helpers
    # ------------------------------------------------------------------ #
    def _chunk_to_slice(self, chunk: Chunk, *, label: str, source: str) -> ContextSlice:
        metadata = {
            "chunk_id": chunk.chunk_id,
            "chunk_index": chunk.chunk_index,
            "section_path": self._resolve_section_path(chunk),
            "heading": chunk.parent_heading,
            "document_id": chunk.document_id,
        }
        if chunk.chunk_metadata:
            metadata.update(chunk.chunk_metadata)
        token_count = chunk.token_count or self.token_estimator.count(chunk.content)
        return ContextSlice(
            label=label,
            source=source,
            content=chunk.content,
            token_count=token_count,
            metadata=metadata,
        )

    def _apply_budget(
        self,
        budget: TokenBudget,
        *,
        bucket: str,
        limit: int,
        slices: Iterable[ContextSlice],
    ) -> list[ContextSlice]:
        accepted: list[ContextSlice] = []
        for slice_ in slices:
            tokens = slice_.token_count or self.token_estimator.count(slice_.content)
            if budget.allow(bucket, limit, tokens):
                accepted.append(slice_)
            else:
                break
        return accepted

    # ------------------------------------------------------------------ #
    # Utilities
    # ------------------------------------------------------------------ #
    def load_chunk(self, chunk_id: str) -> Chunk | None:
        """Public method to load a chunk (used by recursive context builder)."""
        return self._load_chunk(chunk_id)
    
    def _load_chunk(self, chunk_id: str) -> Chunk | None:
        stmt = select(Chunk).where(Chunk.chunk_id == chunk_id)
        return self.session.execute(stmt).scalar_one_or_none()

    def _resolve_section_path(self, chunk: Chunk) -> list[str]:
        metadata = chunk.chunk_metadata or {}
        path = metadata.get("section_path")
        if isinstance(path, list):
            return [str(part).strip() for part in path if str(part).strip()]
        if isinstance(path, str):
            return [part.strip() for part in path.split(">") if part.strip()]
        if chunk.section_path:
            return [part.strip() for part in chunk.section_path.split(">") if part.strip()]
        return []

