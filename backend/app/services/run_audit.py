from __future__ import annotations

import typer
from rich.console import Console

from .. import create_app
from ..config.settings import AppConfig
from ..db.session import get_session
from .compliance_runner import ComplianceRunner

console = Console()
app = typer.Typer(add_completion=False, help="Execute compliance audits chunk-by-chunk.")


@app.command()
def main(
    audit_id: str = typer.Option(..., "--audit-id", "-a", help="Audit ID or external ID to process."),
    max_chunks: int | None = typer.Option(
        None,
        "--max-chunks",
        "-m",
        min=1,
        help="Optional cap for number of chunks to process this run.",
    ),
    include_evidence: bool | None = typer.Option(
        None,
        "--include-evidence/--skip-evidence",
        help="Override evidence retrieval (defaults to enabled for non-draft audits).",
    ),
):
    """Run the compliance runner for a specific audit."""

    create_app()
    session = get_session()
    config = AppConfig()

    runner = ComplianceRunner(session, config)
    result = runner.run(
        audit_id,
        max_chunks=max_chunks,
        include_evidence=include_evidence,
    )

    console.print(
        f"[green]Processed {result.processed} chunks."
        f" Remaining: {result.remaining}. Status: {result.status}.[/green]"
    )


if __name__ == "__main__":
    app()

