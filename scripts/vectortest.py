#!/usr/bin/env python
"""Test script for verifying ChromaDB vector retrieval."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

load_dotenv()

console = Console()
app = typer.Typer(add_completion=False, help="ChromaDB vector retrieval test")


@app.command()
def main(
    query: str = typer.Option(
        ...,
        "--query",
        "-q",
        help="Query text to search for similar chunks.",
    ),
    collection: str = typer.Option(
        "manual_chunks",
        "--collection",
        "-c",
        help="ChromaDB collection name to query.",
    ),
    top_k: int = typer.Option(
        3,
        "--top-k",
        "-k",
        help="Number of top results to retrieve.",
    ),
) -> None:
    """Query ChromaDB for similar chunks and display results."""

    try:
        import chromadb
    except ImportError:
        console.print("[red]chromadb not installed. Install with: pip install chromadb[/red]")
        raise typer.Exit(code=1)

    data_root = Path(os.getenv("DATA_ROOT", "./data"))
    chroma_path = data_root / "chroma"

    if not chroma_path.exists():
        console.print(f"[red]ChromaDB path does not exist: {chroma_path}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Connecting to ChromaDB at {chroma_path}...[/cyan]")
    client = chromadb.PersistentClient(path=str(chroma_path))

    try:
        collection_obj = client.get_collection(name=collection)
    except Exception as e:
        console.print(f"[red]Collection '{collection}' not found: {e}[/red]")
        raise typer.Exit(code=1)

    console.print(f"[cyan]Querying collection '{collection}' for: '{query}'[/cyan]\n")

    # Query the collection
    results = collection_obj.query(query_texts=[query], n_results=top_k)

    if not results["ids"] or not results["ids"][0]:
        console.print("[yellow]No results found.[/yellow]")
        raise typer.Exit(code=0)

    # Display results in a table
    table = Table(title=f"Top {top_k} Results")
    table.add_column("Rank", style="cyan", width=6)
    table.add_column("ID", style="magenta")
    table.add_column("Distance", style="green", width=10)
    table.add_column("Preview", style="white")

    for i, (doc_id, distance, document, metadata) in enumerate(
        zip(
            results["ids"][0],
            results["distances"][0],
            results["documents"][0],
            results["metadatas"][0],
        )
    ):
        preview = document[:100] + "..." if len(document) > 100 else document
        table.add_row(
            str(i + 1),
            doc_id,
            f"{distance:.4f}",
            preview,
        )

    console.print(table)

    # Display metadata for first result
    if results["metadatas"] and results["metadatas"][0]:
        console.print("\n[cyan]Metadata for top result:[/cyan]")
        for key, value in results["metadatas"][0][0].items():
            console.print(f"  {key}: {value}")


if __name__ == "__main__":
    app()

