from __future__ import annotations

from backend.app.config.settings import ChunkingConfig
from backend.app.services.chunking import SectionText, SemanticChunker


def test_semantic_chunker_emits_ordered_chunks():
    config = ChunkingConfig(size=80, overlap=20, tokenizer="cl100k_base", max_section_tokens=400)
    chunker = SemanticChunker(config)

    section_one = SectionText(
        index=0,
        title="Introduction",
        content=" ".join(["Alpha bravo charlie delta echo"] * 60),
    )
    section_two = SectionText(
        index=1,
        title="Scope",
        content=" ".join(["Foxtrot golf hotel"] * 30),
    )

    payloads = chunker.chunk_sections("docXYZ", [section_one, section_two])

    assert payloads, "Expected at least one chunk to be emitted"
    assert payloads[0].chunk_id == "docXYZ_0_0"
    assert payloads[0].metadata["section_index"] == 0
    assert payloads[0].metadata.get("prev_chunk_id") is None

    second_section_idx = next(
        idx for idx, chunk in enumerate(payloads) if chunk.chunk_id.startswith("docXYZ_1_0")
    )
    assert payloads[second_section_idx].metadata["prev_chunk_id"] == payloads[second_section_idx - 1].chunk_id
    assert payloads[second_section_idx - 1].metadata["next_chunk_id"] == payloads[second_section_idx].chunk_id
    assert payloads[second_section_idx].section_path[0] == "Scope"


def test_section_path_metadata_is_respected():
    config = ChunkingConfig(size=60, overlap=10, tokenizer="cl100k_base", max_section_tokens=200)
    chunker = SemanticChunker(config)
    section = SectionText(
        index=0,
        title="Appendix",
        content=" ".join(["Zulu yankee xray"] * 40),
        metadata={"section_path": ["Manual", "Appendix"]},
    )

    payloads = chunker.chunk_sections("docABC", [section])

    assert payloads[0].section_path == ["Manual", "Appendix"]
    assert payloads[0].metadata["section_metadata"]["section_path"] == ["Manual", "Appendix"]

