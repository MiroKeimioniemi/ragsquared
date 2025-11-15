from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

import typer
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()
app = typer.Typer(add_completion=False, help="Semantic chunking pipeline")


@app.command()
def main(
    extracted_json: Path = typer.Argument(
        ...,
        exists=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the JSON payload emitted by the extraction worker.",
    ),
    doc_id: str = typer.Option(
        ...,
        "--doc-id",
        "-d",
        help="Document ID (external UUID or numeric primary key) to attach chunks to.",
    ),
    replace: bool = typer.Option(
        False,
        "--replace",
        help="Delete existing chunks for the document before inserting new ones.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Generate and display chunks without persisting them to the database.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print each chunk payload as it is processed.",
    ),
) -> None:
    """Chunk an extracted document and persist rows to the SQLite database."""

    from backend.app.config.settings import AppConfig
    from backend.app.db.models import Base, Chunk
    from backend.app.db.session import get_session, init_engine
    from backend.app.services.chunking import SemanticChunker

    config = AppConfig()
    engine = init_engine(config.database_url)
    Base.metadata.create_all(engine)

    sections = _load_sections(extracted_json)
    if not sections:
        console.print("[yellow]No sections with textual content found; exiting.[/yellow]")
        raise typer.Exit(code=1)

    session = get_session()
    try:
        document = _resolve_document(session, doc_id)
        if document is None:
            console.print(
                f"[red]Document '{doc_id}' not found. Upload the file before chunking.[/red]"
            )
            raise typer.Exit(code=2)

        chunker = SemanticChunker(config.chunking)
        # Use section-aware chunking (one chunk per section) for better RAG context
        payloads = chunker.chunk_sections(document.external_id, sections, section_aware=True)

        if not payloads:
            console.print("[yellow]Chunker emitted zero chunks; nothing to persist.[/yellow]")
            raise typer.Exit(code=3)

        if dry_run:
            _print_dry_run(payloads)
            return

        if replace:
            deleted = (
                session.query(Chunk)
                .filter(Chunk.document_id == document.id)
                .delete(synchronize_session=False)
            )
            if deleted:
                console.print(f"[cyan]Removed {deleted} existing chunks for document.[/cyan]")
            session.flush()

        for idx, payload in enumerate(payloads):
            metadata = {
                **payload.metadata,
                "chunk_id": payload.chunk_id,
                "section_path": payload.section_path,
                "parent_heading": payload.parent_heading,
            }
            section_path = " > ".join(payload.section_path).strip() or None
            chunk_row = Chunk(
                document_id=document.id,
                chunk_id=payload.chunk_id,
                chunk_index=idx,
                section_path=section_path,
                parent_heading=payload.parent_heading,
                content=payload.text,
                token_count=payload.token_count,
                chunk_metadata=metadata,
            )
            session.add(chunk_row)

            if verbose:
                console.print(
                    f"[green]chunk {idx:04d}[/green] {payload.chunk_id} "
                    f"[tokens={payload.token_count}] path={' > '.join(payload.section_path)}"
                )

        session.commit()
        console.print(
            f"[green]Persisted {len(payloads)} chunks for document {document.external_id}.[/green]"
        )
    finally:
        session.close()


def _resolve_document(session, identifier: str):
    """Look up a document by external_id or integer primary key."""

    from sqlalchemy import select
    from backend.app.db.models import Document

    stmt = select(Document).where(Document.external_id == identifier)
    document = session.execute(stmt).scalar_one_or_none()
    if document is None and identifier.isdigit():
        document = session.get(Document, int(identifier))
    return document


def _load_sections(path: Path) -> list["SectionText"]:
    """Parse extracted JSON into SectionText objects."""

    from backend.app.services.chunking import SectionText

    data = json.loads(path.read_text(encoding="utf-8"))
    sections_payload = data.get("sections") or []
    sections: list[SectionText] = []

    for idx, raw in enumerate(sections_payload):
        content = str(raw.get("content", "")).strip()
        if not content:
            continue

        metadata = raw.get("metadata") or {}
        section_path = metadata.get("section_path")
        if isinstance(section_path, str):
            section_path = [section_path]
        elif not isinstance(section_path, list):
            section_path = None

        sections.append(
            SectionText(
                index=int(raw.get("index", idx)),
                title=raw.get("title"),
                content=content,
                section_path=[str(part) for part in section_path] if section_path else None,
                metadata=metadata if isinstance(metadata, dict) else {},
            )
        )

    return sections


def _print_dry_run(payloads: Iterable["ChunkPayload"]) -> None:
    from backend.app.services.chunking import ChunkPayload

    payload_list = list(payloads)
    console.print(f"[cyan]Dry run:[/cyan] {len(payload_list)} chunks would be persisted.")
    for payload in payload_list[:5]:
        console.print(
            f"- {payload.chunk_id} tokens={payload.token_count} path={' > '.join(payload.section_path)}"
        )


if __name__ == "__main__":
    app()

