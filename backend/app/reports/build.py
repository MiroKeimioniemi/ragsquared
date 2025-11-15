from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from .. import create_app
from ..config.settings import AppConfig
from .generator import ReportGenerator, ReportRequest

console = Console()
app = typer.Typer(add_completion=False, help="Audit report builder")


@app.command()
def main(
    audit_id: int = typer.Option(..., "--audit-id", "-a", help="Audit ID to render."),
    output_dir: Path = typer.Option(Path("data/reports"), "--output-dir", "-o", help="Output directory"),
    include_appendix: bool = typer.Option(True, "--appendix/--no-appendix"),
    pdf: bool = typer.Option(False, "--pdf", help="Also render a PDF copy"),
    html: bool = typer.Option(False, "--html", help="Also render a static HTML copy"),
):
    """Render a Markdown (and optional PDF/HTML) report for an audit."""

    app = create_app()
    generator = ReportGenerator(output_dir)
    request = ReportRequest(audit_id=audit_id, include_appendix=include_appendix)
    md_path = generator.render_markdown(request)
    console.print(f"[green]Markdown report created at {md_path}[/green]")

    if pdf:
        pdf_path = generator.render_pdf(request)
        console.print(f"[cyan]PDF report created at {pdf_path}[/cyan]")
    
    if html:
        html_path = generator.render_html(request, app)
        console.print(f"[cyan]HTML report created at {html_path}[/cyan]")


if __name__ == "__main__":
    app()

