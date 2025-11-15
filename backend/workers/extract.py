from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from backend.app.processing import DocumentExtractor, ExtractionError

console = Console(stderr=True)
app = typer.Typer(add_completion=False, help="Document extraction worker")


@app.command()
def main(
    document_path: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the document that should be extracted.",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional destination for the JSON payload. Defaults to stdout.",
    ),
    pretty: bool = typer.Option(
        False, "--pretty", "-p", help="Pretty-print JSON with indentation."
    ),
    ocr: bool = typer.Option(
        False,
        "--ocr",
        help="Enable OCR fallback for images or scanned PDFs (requires pytesseract).",
    ),
    ocr_lang: str = typer.Option(
        "eng", "--ocr-lang", help="Language hint passed to Tesseract when OCR is enabled."
    ),
) -> None:
    """CLI entrypoint for the text extraction worker."""
    extractor = DocumentExtractor(use_ocr=ocr, ocr_lang=ocr_lang)

    try:
        result = extractor.extract(document_path)
    except ExtractionError as exc:
        console.print(f"[red]Extraction failed:[/red] {exc}")
        raise typer.Exit(code=1) from exc

    json_payload = result.to_json(indent=2 if pretty else None)

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_payload, encoding="utf-8")
        console.print(f"[green]Extraction written to[/green] {output}")
    else:
        typer.echo(json_payload)


if __name__ == "__main__":
    app()


