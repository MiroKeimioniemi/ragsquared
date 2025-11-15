"""Developer CLI for interacting with the AI Auditing System."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

from backend.app import create_app
from backend.app.config.settings import AppConfig
from backend.app.db.models import Audit, Document, Flag
from backend.app.db.session import get_session
from backend.app.reports.generator import ReportGenerator, ReportRequest
from backend.app.services.compliance_score import get_flag_summary
from backend.app.services.score_plotter import format_score_table, plot_ascii_trend
from backend.app.services.score_tracker import ScoreTracker

console = Console()
app = typer.Typer(add_completion=False, help="Developer CLI for AI Auditing System")


def _resolve_audit(session, identifier: str) -> Audit | None:
    """Resolve audit by ID or external_id."""
    if identifier.isdigit():
        return session.get(Audit, int(identifier))
    from sqlalchemy import select

    stmt = select(Audit).where(Audit.external_id == identifier)
    return session.execute(stmt).scalar_one_or_none()


@app.command()
def status(
    audit_id: str = typer.Argument(..., help="Audit ID or external ID"),
    poll: bool = typer.Option(False, "--poll", "-p", help="Poll until completion"),
    interval: int = typer.Option(2, "--interval", "-i", help="Polling interval in seconds"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show audit status and progress."""
    create_app()
    session = get_session()

    audit = _resolve_audit(session, audit_id)
    if audit is None:
        console.print(f"[red]Audit '{audit_id}' not found.[/red]")
        raise typer.Exit(code=1)

    if poll:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task(f"Polling audit {audit.external_id}...", total=None)
            while audit.status not in ("completed", "failed"):
                time.sleep(interval)
                session.refresh(audit)
                progress.update(task, description=f"Status: {audit.status}, Chunks: {audit.chunk_completed}/{audit.chunk_total}")
            progress.update(task, description=f"Final status: {audit.status}")

    document = session.get(Document, audit.document_id) if audit.document_id else None

    if json_output:
        output = {
            "audit_id": audit.id,
            "external_id": audit.external_id,
            "status": audit.status,
            "chunk_total": audit.chunk_total,
            "chunk_completed": audit.chunk_completed,
            "chunk_remaining": audit.chunk_total - audit.chunk_completed,
            "progress_percent": (audit.chunk_completed / audit.chunk_total * 100) if audit.chunk_total > 0 else 0,
            "is_draft": audit.is_draft,
            "document": {
                "id": document.id if document else None,
                "filename": document.original_filename if document else None,
            },
            "started_at": audit.started_at.isoformat() if audit.started_at else None,
            "completed_at": audit.completed_at.isoformat() if audit.completed_at else None,
        }
        typer.echo(json.dumps(output, indent=2))
    else:
        table = Table(title=f"Audit Status: {audit.external_id}")
        table.add_column("Field", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("ID", str(audit.id))
        table.add_row("External ID", audit.external_id)
        table.add_row("Status", f"[bold]{audit.status.upper()}[/bold]")
        if audit.is_draft:
            table.add_row("Mode", "[yellow]DRAFT[/yellow] (Limited processing)")
        table.add_row("Progress", f"{audit.chunk_completed}/{audit.chunk_total} chunks")
        if audit.chunk_total > 0:
            progress_pct = (audit.chunk_completed / audit.chunk_total) * 100
            table.add_row("Progress %", f"{progress_pct:.1f}%")
        if document:
            table.add_row("Document", document.original_filename)
        if audit.started_at:
            table.add_row("Started", audit.started_at.strftime("%Y-%m-%d %H:%M:%S"))
        if audit.completed_at:
            table.add_row("Completed", audit.completed_at.strftime("%Y-%m-%d %H:%M:%S"))

        console.print(table)

        # Show report links if completed
        if audit.status == "completed":
            config = AppConfig()
            report_dir = Path(config.data_root) / "reports"
            md_path = report_dir / f"audit_{audit.external_id}.md"
            pdf_path = report_dir / f"audit_{audit.external_id}.pdf"

            console.print("\n[bold]Report Links:[/bold]")
            if md_path.exists():
                console.print(f"  Markdown: [cyan]{md_path}[/cyan]")
            if pdf_path.exists():
                console.print(f"  PDF: [cyan]{pdf_path}[/cyan]")


@app.command()
def flags(
    audit_id: str = typer.Argument(..., help="Audit ID or external ID"),
    severity: Optional[str] = typer.Option(None, "--severity", "-s", help="Filter by severity (RED/YELLOW/GREEN)"),
    regulation: Optional[str] = typer.Option(None, "--regulation", "-r", help="Filter by regulation reference"),
    page: int = typer.Option(1, "--page", "-p", help="Page number"),
    page_size: int = typer.Option(20, "--page-size", help="Items per page"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """List compliance flags for an audit."""
    create_app()
    session = get_session()

    audit = _resolve_audit(session, audit_id)
    if audit is None:
        console.print(f"[red]Audit '{audit_id}' not found.[/red]")
        raise typer.Exit(code=1)

    from sqlalchemy import select, func

    query = select(Flag).where(Flag.audit_id == audit.id)
    if severity:
        query = query.where(Flag.flag_type == severity.strip().upper())

    if regulation:
        from backend.app.db.models import Citation

        query = query.join(Citation).where(
            Citation.citation_type == "regulation",
            Citation.reference.ilike(f"%{regulation.strip()}%"),
        )

    total = session.scalar(select(func.count()).select_from(query.subquery()))
    flags_list = (
        session.execute(
            query.order_by(Flag.severity_score.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .unique()
        .all()
    )

    if json_output:
        output = {
            "audit_id": audit.id,
            "external_id": audit.external_id,
            "pagination": {"page": page, "page_size": page_size, "total": total},
            "flags": [
                {
                    "flag_id": flag.id,
                    "chunk_id": flag.chunk_id,
                    "flag_type": flag.flag_type,
                    "severity_score": flag.severity_score,
                    "findings": flag.findings,
                    "gaps": flag.gaps,
                    "recommendations": flag.recommendations,
                }
                for flag in flags_list
            ],
        }
        typer.echo(json.dumps(output, indent=2))
    else:
        table = Table(title=f"Flags for Audit: {audit.external_id} (Page {page}, Total: {total})")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="bold")
        table.add_column("Score", justify="right")
        table.add_column("Chunk", style="yellow")
        table.add_column("Findings", style="white")

        for flag in flags_list:
            flag_color = {
                "RED": "red",
                "YELLOW": "yellow",
                "GREEN": "green",
            }.get(flag.flag_type, "white")
            table.add_row(
                str(flag.id),
                f"[{flag_color}]{flag.flag_type}[/{flag_color}]",
                str(flag.severity_score),
                flag.chunk_id,
                flag.findings[:80] + "..." if len(flag.findings) > 80 else flag.findings,
            )

        console.print(table)


@app.command()
def report(
    audit_id: str = typer.Argument(..., help="Audit ID or external ID"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    include_appendix: bool = typer.Option(True, "--appendix/--no-appendix"),
    pdf: bool = typer.Option(False, "--pdf", help="Also generate PDF"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output paths as JSON"),
):
    """Generate audit report (Markdown and optional PDF)."""
    create_app()
    session = get_session()

    audit = _resolve_audit(session, audit_id)
    if audit is None:
        console.print(f"[red]Audit '{audit_id}' not found.[/red]")
        raise typer.Exit(code=1)

    config = AppConfig()
    if output_dir is None:
        output_dir = Path(config.data_root) / "reports"
    else:
        output_dir = Path(output_dir)

    generator = ReportGenerator(output_dir)
    request = ReportRequest(audit_id=audit.id, include_appendix=include_appendix)

    try:
        md_path = generator.render_markdown(request)

        pdf_path = None
        if pdf:
            pdf_path = generator.render_pdf(request)

        if json_output:
            output = {
                "audit_id": audit.id,
                "external_id": audit.external_id,
                "markdown_path": str(md_path).replace("\\", "/"),  # Normalize path separators
                "pdf_path": str(pdf_path).replace("\\", "/") if pdf_path else None,
            }
            typer.echo(json.dumps(output, indent=2))
        else:
            console.print(f"[green]✓[/green] Markdown report: [cyan]{md_path}[/cyan]")
            if pdf_path:
                console.print(f"[green]✓[/green] PDF report: [cyan]{pdf_path}[/cyan]")
    except Exception as e:
        console.print(f"[red]Error generating report: {e}[/red]")
        raise typer.Exit(code=1) from e


@app.command()
def compare(
    audit_a: str = typer.Argument(..., help="First audit ID or external ID"),
    audit_b: str = typer.Argument(..., help="Second audit ID or external ID"),
    regulation: Optional[str] = typer.Option(None, "--regulation", "-r", help="Filter by regulation reference"),
    severity: Optional[str] = typer.Option(None, "--severity", "-s", help="Filter by severity (RED/YELLOW/GREEN)"),
    output_format: str = typer.Option("text", "--format", "-f", help="Output format: text, markdown, json"),
    cache: bool = typer.Option(False, "--cache", help="Cache comparison result to disk"),
):
    """Compare two audits, highlighting differences in flags and compliance scores."""
    create_app()
    session = get_session()

    audit_a_obj = _resolve_audit(session, audit_a)
    audit_b_obj = _resolve_audit(session, audit_b)

    if audit_a_obj is None:
        console.print(f"[red]Audit '{audit_a}' not found.[/red]")
        raise typer.Exit(code=1)
    if audit_b_obj is None:
        console.print(f"[red]Audit '{audit_b}' not found.[/red]")
        raise typer.Exit(code=1)

    from sqlalchemy import select
    from backend.app.db.models import Citation

    # Fetch flags with optional filtering
    query_a = select(Flag).where(Flag.audit_id == audit_a_obj.id)
    query_b = select(Flag).where(Flag.audit_id == audit_b_obj.id)

    if severity:
        query_a = query_a.where(Flag.flag_type == severity.strip().upper())
        query_b = query_b.where(Flag.flag_type == severity.strip().upper())

    if regulation:
        query_a = query_a.join(Citation).where(
            Citation.citation_type == "regulation",
            Citation.reference.ilike(f"%{regulation.strip()}%"),
        )
        query_b = query_b.join(Citation).where(
            Citation.citation_type == "regulation",
            Citation.reference.ilike(f"%{regulation.strip()}%"),
        )

    flags_a = session.execute(query_a).scalars().unique().all()
    flags_b = session.execute(query_b).scalars().unique().all()

    # Calculate compliance scores
    from backend.app.services.compliance_score import calculate_compliance_score

    score_a = calculate_compliance_score(flags_a)
    score_b = calculate_compliance_score(flags_b)
    score_delta = score_b - score_a

    # Build flag maps for diff analysis
    flags_a_map = {f.chunk_id: f for f in flags_a}
    flags_b_map = {f.chunk_id: f for f in flags_b}

    # Find added, removed, and changed flags
    added_chunks = set(flags_b_map.keys()) - set(flags_a_map.keys())
    removed_chunks = set(flags_a_map.keys()) - set(flags_b_map.keys())
    common_chunks = set(flags_a_map.keys()) & set(flags_b_map.keys())
    changed_flags = []
    severity_shifts = []

    for chunk_id in common_chunks:
        flag_a = flags_a_map[chunk_id]
        flag_b = flags_b_map[chunk_id]
        if flag_a.flag_type != flag_b.flag_type or flag_a.severity_score != flag_b.severity_score:
            changed_flags.append((flag_a, flag_b))
            if flag_a.flag_type != flag_b.flag_type:
                severity_shifts.append(
                    {
                        "chunk_id": chunk_id,
                        "from": flag_a.flag_type,
                        "to": flag_b.flag_type,
                        "score_delta": flag_b.severity_score - flag_a.severity_score,
                    }
                )

    summary_a = get_flag_summary(flags_a)
    summary_b = get_flag_summary(flags_b)

    # Generate output based on format
    if output_format == "json":
        output = {
            "audit_a": {
                "id": audit_a_obj.id,
                "external_id": audit_a_obj.external_id,
                "summary": summary_a,
            },
            "audit_b": {
                "id": audit_b_obj.id,
                "external_id": audit_b_obj.external_id,
                "summary": summary_b,
            },
            "comparison": {
                "compliance_score_delta": round(score_delta, 2),
                "flag_count_delta": summary_b["total_flags"] - summary_a["total_flags"],
                "added_flags": len(added_chunks),
                "removed_flags": len(removed_chunks),
                "changed_flags": len(changed_flags),
                "severity_shifts": severity_shifts,
            },
        }
        typer.echo(json.dumps(output, indent=2))
    elif output_format == "markdown":
        lines = [
            f"# Audit Comparison",
            "",
            f"**Audit A:** {audit_a_obj.external_id} (ID: {audit_a_obj.id})",
            f"**Audit B:** {audit_b_obj.external_id} (ID: {audit_b_obj.id})",
            "",
            "## Summary",
            "",
            "| Metric | Audit A | Audit B | Delta |",
            "|--------|---------|---------|-------|",
            f"| Compliance Score | {summary_a['compliance_score']} | {summary_b['compliance_score']} | {score_delta:+.2f} |",
            f"| Total Flags | {summary_a['total_flags']} | {summary_b['total_flags']} | {summary_b['total_flags'] - summary_a['total_flags']:+d} |",
            f"| RED | {summary_a['red_count']} | {summary_b['red_count']} | {summary_b['red_count'] - summary_a['red_count']:+d} |",
            f"| YELLOW | {summary_a['yellow_count']} | {summary_b['yellow_count']} | {summary_b['yellow_count'] - summary_a['yellow_count']:+d} |",
            f"| GREEN | {summary_a['green_count']} | {summary_b['green_count']} | {summary_b['green_count'] - summary_a['green_count']:+d} |",
            "",
        ]

        if severity_shifts:
            lines.extend(
                [
                    "## Severity Shifts",
                    "",
                    "| Chunk ID | From | To | Score Delta |",
                    "|----------|------|----|-------------|",
                ]
            )
            for shift in severity_shifts:
                lines.append(f"| {shift['chunk_id']} | {shift['from']} | {shift['to']} | {shift['score_delta']:+d} |")
            lines.append("")

        if added_chunks:
            lines.extend(["## Added Flags", ""])
            for chunk_id in sorted(added_chunks):
                flag = flags_b_map[chunk_id]
                lines.append(f"- **{chunk_id}**: {flag.flag_type} (score: {flag.severity_score})")
            lines.append("")

        if removed_chunks:
            lines.extend(["## Removed Flags", ""])
            for chunk_id in sorted(removed_chunks):
                flag = flags_a_map[chunk_id]
                lines.append(f"- **{chunk_id}**: {flag.flag_type} (score: {flag.severity_score})")
            lines.append("")

        output_text = "\n".join(lines)
        typer.echo(output_text)

        # Cache if requested
        if cache:
            from datetime import datetime

            config = AppConfig()
            cache_dir = Path(config.data_root) / "reports" / "compare"
            cache_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cache_file = cache_dir / f"compare_{audit_a_obj.external_id}_{audit_b_obj.external_id}_{timestamp}.md"
            cache_file.write_text(output_text, encoding="utf-8")
            console.print(f"[green]Comparison cached to:[/green] [cyan]{cache_file}[/cyan]")
    else:  # text format
        table = Table(title="Audit Comparison")
        table.add_column("Metric", style="cyan")
        table.add_column(f"Audit A ({audit_a_obj.external_id})", style="green")
        table.add_column(f"Audit B ({audit_b_obj.external_id})", style="blue")
        table.add_column("Delta", style="yellow")

        # Format delta with color
        def format_delta(value: float, is_score: bool = False) -> str:
            if is_score:
                formatted = f"{value:.2f}"
            else:
                formatted = f"{value:.0f}"
            if value > 0:
                return f"[green]+{formatted}[/green]"
            elif value < 0:
                return f"[red]{formatted}[/red]"
            return "0"

        table.add_row(
            "Compliance Score",
            f"{summary_a['compliance_score']:.2f}",
            f"{summary_b['compliance_score']:.2f}",
            format_delta(score_delta, is_score=True),
        )
        table.add_row("Total Flags", str(summary_a["total_flags"]), str(summary_b["total_flags"]), format_delta(summary_b["total_flags"] - summary_a["total_flags"]))
        table.add_row("RED", str(summary_a["red_count"]), str(summary_b["red_count"]), format_delta(summary_b["red_count"] - summary_a["red_count"]))
        table.add_row("YELLOW", str(summary_a["yellow_count"]), str(summary_b["yellow_count"]), format_delta(summary_b["yellow_count"] - summary_a["yellow_count"]))
        table.add_row("GREEN", str(summary_a["green_count"]), str(summary_b["green_count"]), format_delta(summary_b["green_count"] - summary_a["green_count"]))

        console.print(table)

        # Show severity shifts
        if severity_shifts:
            console.print("\n[bold]Severity Shifts:[/bold]")
            shift_table = Table()
            shift_table.add_column("Chunk ID", style="cyan")
            shift_table.add_column("From", style="yellow")
            shift_table.add_column("To", style="green")
            shift_table.add_column("Score Δ", justify="right")

            for shift in severity_shifts[:10]:  # Limit to first 10 for display
                shift_table.add_row(
                    shift["chunk_id"],
                    shift["from"],
                    shift["to"],
                    format_delta(shift["score_delta"]),
                )
            if len(severity_shifts) > 10:
                shift_table.add_row("...", f"+{len(severity_shifts) - 10} more", "", "")
            console.print(shift_table)

        # Show added/removed flags summary
        if added_chunks or removed_chunks:
            console.print("\n[bold]Flag Changes:[/bold]")
            if added_chunks:
                console.print(f"[green]+{len(added_chunks)} flags added[/green]")
            if removed_chunks:
                console.print(f"[red]-{len(removed_chunks)} flags removed[/red]")
            if changed_flags:
                console.print(f"[yellow]{len(changed_flags)} flags changed[/yellow]")


@app.command()
def scores(
    organization: Optional[str] = typer.Option(None, "--organization", "-o", help="Filter by organization"),
    limit: int = typer.Option(20, "--limit", "-l", help="Number of scores to show"),
    plot: bool = typer.Option(False, "--plot", "-p", help="Show ASCII trend plot"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Show compliance score history with optional trend visualization."""
    create_app()
    session = get_session()

    tracker = ScoreTracker(session)
    score_history = tracker.get_score_history(organization=organization, limit=limit)

    if json_output:
        output = {
            "organization": organization,
            "count": len(score_history),
            "scores": [
                {
                    "audit_id": score.audit_id,
                    "overall_score": score.overall_score,
                    "red_count": score.red_count,
                    "yellow_count": score.yellow_count,
                    "green_count": score.green_count,
                    "total_flags": score.total_flags,
                    "created_at": score.created_at.isoformat() if score.created_at else None,
                }
                for score in score_history
            ],
        }
        typer.echo(json.dumps(output, indent=2))
    else:
        if plot and score_history:
            # Reverse to show oldest to newest for trend
            trend_scores = list(reversed(score_history))
            console.print("\n[bold]Compliance Score Trend[/bold]")
            console.print(plot_ascii_trend(trend_scores))
            console.print("")

        console.print(f"\n[bold]Score History[/bold] (showing {len(score_history)} scores)")
        if organization:
            console.print(f"Organization: [cyan]{organization}[/cyan]")
        console.print("")
        console.print(format_score_table(score_history))


if __name__ == "__main__":
    app()

