from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from backend.app.processing import DocumentExtractor, ExtractionError
from workers.extract import app as extract_cli


def _write_markdown(tmp_path: Path) -> Path:
    content = """# General

This is a sample manual excerpt that references EASA guidance.

## Responsibilities

All certifying staff shall meet Part-66 requirements and recurrent training.
"""
    path = tmp_path / "sample_manual.md"
    path.write_text(content, encoding="utf-8")
    return path


def test_markdown_extraction_returns_sections(tmp_path: Path):
    sample_path = _write_markdown(tmp_path)
    extractor = DocumentExtractor()

    result = extractor.extract(sample_path)

    assert len(result.sections) == 2
    assert result.sections[0].title == "General"
    assert "sample manual" in result.sections[0].content.lower()
    assert result.sections[1].title == "Responsibilities"
    assert "Part-66 requirements" in result.sections[1].content


def test_extractor_rejects_missing_file(tmp_path: Path):
    extractor = DocumentExtractor()
    with pytest.raises(ExtractionError):
        extractor.extract(tmp_path / "missing.md")


def test_cli_emits_json(tmp_path: Path):
    runner = CliRunner()
    sample_path = _write_markdown(tmp_path)

    result = runner.invoke(extract_cli, [str(sample_path), "--pretty"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["source_extension"] == ".md"
    assert payload["section_count"] == 2
    assert payload["sections"][0]["title"] == "General"


