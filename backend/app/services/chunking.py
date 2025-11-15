from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

from ..config.settings import ChunkingConfig

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SectionText:
    """Lightweight container describing a structured section to be chunked."""

    index: int
    title: str | None
    content: str
    section_path: list[str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ChunkPayload:
    """Normalized payload emitted by the semantic chunker."""

    chunk_id: str
    doc_id: str
    text: str
    token_count: int
    section_path: list[str]
    parent_heading: str | None
    metadata: dict[str, Any]


class SemanticChunker:
    """Section-aware chunker that preserves structure and overlap metadata."""

    def __init__(self, config: ChunkingConfig):
        self.config = config
        self._encoding = self._load_encoding(config.tokenizer)

    def chunk_sections(
        self, 
        doc_id: str, 
        sections: Sequence[SectionText],
        *,
        section_aware: bool = False,
    ) -> list[ChunkPayload]:
        """Chunk a sequence of sections and return normalized payloads.
        
        Args:
            doc_id: Document identifier
            sections: Sections to chunk
            section_aware: If True, each section becomes one chunk (unless it exceeds max size).
                          If False, uses fixed-size token-based chunking with overlap.
        """

        payloads: list[ChunkPayload] = []
        previous_chunk_id: str | None = None

        for section in sections:
            normalized_content = self._prepare_section_content(section.content)
            if not normalized_content:
                continue

            section_path = self._resolve_section_path(section)
            
            # Section-aware mode: one chunk per section (unless too large)
            if section_aware:
                section_text = self._truncate_section(normalized_content)
                token_length = self._token_length(section_text)
                
                # If section is too large, still split it
                if token_length > self.config.max_section_tokens:
                    logger.warning(
                        f"Section {section.index} exceeds max size ({token_length} > {self.config.max_section_tokens}), splitting..."
                    )
                    splits = self._split_text(section_text)
                else:
                    splits = [section_text]
                
                for chunk_idx, chunk_text in enumerate(splits):
                    cleaned_text = chunk_text.strip()
                    if not cleaned_text:
                        continue

                    token_length = self._token_length(cleaned_text)
                    chunk_id = f"{doc_id}_{section.index}_{chunk_idx}"
                    metadata = {
                        "section_index": section.index,
                        "chunk_index": chunk_idx,
                        "token_count": token_length,
                        "section_metadata": section.metadata,
                        "chunking_mode": "section_aware",
                    }

                    if previous_chunk_id:
                        metadata["prev_chunk_id"] = previous_chunk_id
                        if payloads:
                            payloads[-1].metadata["next_chunk_id"] = chunk_id

                    payload = ChunkPayload(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        text=cleaned_text,
                        token_count=token_length,
                        section_path=section_path,
                        parent_heading=section.title,
                        metadata=metadata,
                    )
                    payloads.append(payload)
                    previous_chunk_id = chunk_id
            else:
                # Original token-based chunking with overlap
                section_text = self._truncate_section(normalized_content)
                splits = self._split_text(section_text)
                if not splits:
                    continue

                token_cursor = 0

                for chunk_idx, chunk_text in enumerate(splits):
                    cleaned_text = chunk_text.strip()
                    if not cleaned_text:
                        continue

                    token_length = self._token_length(cleaned_text)
                    chunk_id = f"{doc_id}_{section.index}_{chunk_idx}"
                    metadata = {
                        "section_index": section.index,
                        "chunk_index": chunk_idx,
                        "token_start": token_cursor,
                        "token_end": token_cursor + token_length,
                        "section_metadata": section.metadata,
                        "chunking_mode": "token_based",
                    }

                    if previous_chunk_id:
                        metadata["prev_chunk_id"] = previous_chunk_id
                        payloads[-1].metadata["next_chunk_id"] = chunk_id

                    payload = ChunkPayload(
                        chunk_id=chunk_id,
                        doc_id=doc_id,
                        text=cleaned_text,
                        token_count=token_length,
                        section_path=section_path,
                        parent_heading=section.title,
                        metadata=metadata,
                    )
                    payloads.append(payload)

                    previous_chunk_id = chunk_id
                    token_cursor = max(
                        0, token_cursor + max(token_length - self.config.overlap, 0)
                    )

        return payloads

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _prepare_section_content(self, content: str) -> str:
        return "\n".join(line.rstrip() for line in content.splitlines()).strip()

    def _truncate_section(self, text: str) -> str:
        limit = self.config.max_section_tokens
        if limit <= 0:
            return text
        if self._encoding is None:
            approx_chars = limit * 4
            return text[:approx_chars]

        tokens = self._encoding.encode(text)
        if len(tokens) <= limit:
            return text
        truncated = tokens[:limit]
        logger.debug(
            "Truncated section from %s to %s tokens (limit=%s).",
            len(tokens),
            len(truncated),
            limit,
        )
        return self._encoding.decode(truncated)

    def _resolve_section_path(self, section: SectionText) -> list[str]:
        candidates: Iterable[str] | None = None
        if section.section_path:
            candidates = section.section_path
        elif isinstance(section.metadata.get("section_path"), list):
            candidates = section.metadata["section_path"]
        elif isinstance(section.metadata.get("heading_path"), list):
            candidates = section.metadata["heading_path"]

        resolved = [str(part).strip() for part in candidates or [] if str(part).strip()]
        if resolved:
            return resolved

        fallback = section.title.strip() if section.title else f"section_{section.index:04d}"
        return [fallback]

    def _token_length(self, text: str) -> int:
        if self._encoding is None:
            return max(1, math.ceil(len(text) / 4))
        return len(self._encoding.encode(text))

    def _split_text(self, text: str) -> list[str]:
        if not text:
            return []
        if self._encoding is not None:
            token_ids = self._encoding.encode(text)
            return self._split_token_ids(token_ids)
        approx_chunk_chars = max(1, self.config.size * 4)
        approx_overlap_chars = max(0, self.config.overlap * 4)
        return self._split_characters(text, approx_chunk_chars, approx_overlap_chars)

    def _split_token_ids(self, token_ids: list[int]) -> list[str]:
        if not token_ids:
            return []
        chunks: list[str] = []
        start = 0
        total = len(token_ids)
        while start < total:
            end = min(total, start + self.config.size)
            chunk_tokens = token_ids[start:end]
            chunks.append(self._encoding.decode(chunk_tokens))
            if end >= total:
                break
            start = max(0, end - self.config.overlap)
        return chunks

    def _split_characters(self, text: str, chunk_chars: int, overlap_chars: int) -> list[str]:
        chunks: list[str] = []
        start = 0
        total = len(text)
        while start < total:
            end = min(total, start + chunk_chars)
            chunk_text = text[start:end]
            chunks.append(chunk_text)
            if end >= total:
                break
            start = max(0, end - overlap_chars)
        return chunks

    def _load_encoding(self, name: str):
        try:
            import tiktoken
        except Exception:  # pragma: no cover - optional dependency failure
            logger.warning("tiktoken not available; falling back to char counting.")
            return None

        for loader in (
            lambda: tiktoken.get_encoding(name),
            lambda: tiktoken.encoding_for_model(name),
            lambda: tiktoken.get_encoding("cl100k_base"),
        ):
            try:
                return loader()
            except Exception:
                continue

        logger.warning(
            "Unable to resolve tokenizer '%s'; falling back to char counting.", name
        )
        return None

