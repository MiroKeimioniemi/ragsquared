from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console

load_dotenv()

console = Console()
app = typer.Typer(add_completion=False, help="Embedding generation pipeline")


@app.command()
def main(
    doc_id: str = typer.Option(
        ...,
        "--doc-id",
        "-d",
        help="Document ID (external UUID or numeric primary key) to generate embeddings for.",
    ),
    collection: str = typer.Option(
        "manual_chunks",
        "--collection",
        "-c",
        help="ChromaDB collection name (manual_chunks, regulation_chunks, etc.).",
    ),
    batch_size: int = typer.Option(
        32,
        "--batch-size",
        "-b",
        help="Number of chunks to process per batch.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show pending chunks without generating embeddings.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Print detailed progress information.",
    ),
) -> None:
    """Generate embeddings for document chunks and store them in ChromaDB."""

    from backend.app.config.settings import AppConfig
    from backend.app.db.models import Base
    from backend.app.db.session import get_session, init_engine
    from backend.app.services.embeddings import EmbeddingService

    config = AppConfig()
    engine = init_engine(config.database_url)
    Base.metadata.create_all(engine)

    session = get_session()
    try:
        service = EmbeddingService(session, config)

        # Get pending chunks
        pending_chunks = service.get_pending_chunks(doc_id=doc_id, limit=batch_size * 10)

        if not pending_chunks:
            console.print(
                f"[yellow]No pending chunks found for document '{doc_id}'.[/yellow]"
            )
            raise typer.Exit(code=0)

        console.print(
            f"[cyan]Found {len(pending_chunks)} pending chunks for document '{doc_id}'.[/cyan]"
        )

        if dry_run:
            console.print("[yellow]Dry run mode - not generating embeddings.[/yellow]")
            for chunk in pending_chunks[:10]:
                console.print(
                    f"  - Chunk {chunk.id}: {chunk.token_count} tokens, "
                    f"status={chunk.embedding_status}"
                )
            if len(pending_chunks) > 10:
                console.print(f"  ... and {len(pending_chunks) - 10} more chunks.")
            raise typer.Exit(code=0)

        # Process in batches
        total_processed = 0
        total_failed = 0

        for i in range(0, len(pending_chunks), batch_size):
            batch = pending_chunks[i : i + batch_size]
            batch_num = (i // batch_size) + 1
            total_batches = (len(pending_chunks) + batch_size - 1) // batch_size

            if verbose:
                console.print(
                    f"[cyan]Processing batch {batch_num}/{total_batches} "
                    f"({len(batch)} chunks)...[/cyan]"
                )

            result = service.process_chunks(batch, collection_name=collection)

            total_processed += result["processed"]
            total_failed += result["failed"]

            if verbose:
                console.print(
                    f"  [green]✓[/green] Processed: {result['processed']}, "
                    f"[red]✗[/red] Failed: {result['failed']}"
                )

        console.print(
            f"\n[green]Embedding generation complete![/green]\n"
            f"  Total processed: {total_processed}\n"
            f"  Total failed: {total_failed}\n"
            f"  Collection: {collection}"
        )

        service.close()

    finally:
        session.close()


if __name__ == "__main__":
    app()

