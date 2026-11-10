"""
genai_jobs/output/formatters.py
─────────────────────────────────────────────────────────────────────────────
Export helpers: CSV, JSON, Markdown report and Rich terminal table.
All heavy imports are deferred to avoid slowing CLI startup.
"""
from __future__ import annotations

import csv
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ─── Terminal Table (Rich) ────────────────────────────────────────────────────

def render_rich_table(jobs: list, title: str = "Gen-AI Job Postings") -> None:
    """Render a pretty Rich table in the terminal."""
    from rich.console import Console
    from rich.table import Table
    from rich.text import Text

    console = Console()

    if not jobs:
        console.print(
            "\n[bold yellow]⚠  No matching Gen-AI jobs found.[/bold yellow]\n"
            "Try widening filters: --days, --location, or --sources.\n"
        )
        return

    table = Table(
        title=f"[bold cyan]{title}[/bold cyan]",
        show_header=True,
        header_style="bold magenta",
        border_style="bright_blue",
        row_styles=["", "dim"],
        expand=True,
        show_lines=True,
    )

    table.add_column("#", style="bold white", width=4, no_wrap=True)
    table.add_column("Company", style="green", min_width=12, no_wrap=True)
    table.add_column("Job Title", style="bright_white", min_width=26)
    table.add_column("Location", style="yellow", min_width=14)
    table.add_column("Posted", style="cyan", width=12, no_wrap=True)
    table.add_column("Exp", style="magenta", width=9, no_wrap=True)
    table.add_column("Skills", style="bright_green", min_width=14)
    table.add_column("Source", style="blue", min_width=12, no_wrap=True)
    table.add_column("Apply Link", style="bold underline bright_cyan", min_width=20)

    for idx, job in enumerate(jobs, start=1):
        link = Text(job.url, style=f"link {job.url}")
        link.stylize("bold cyan underline")
        table.add_row(
            str(idx),
            job.company,
            job.title,
            job.location or "—",
            job.date_str,
            job.experience_label,
            job.skills_label,
            job.source,
            link,
        )

    console.print()
    console.print(table)
    console.print(
        f"\n[bold green]✓ Total:[/bold green] [white]{len(jobs)} unique Gen-AI job(s) found.[/white]\n"
    )


# ─── CSV export ───────────────────────────────────────────────────────────────

def export_csv(jobs: list, path: Path) -> None:
    """Write jobs to a UTF-8 CSV file with a clickable URL column."""
    fieldnames = ["#", "company", "title", "location", "date_posted", "experience", "skills", "source", "url"]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for idx, job in enumerate(jobs, start=1):
            d = job.to_dict()
            d["#"] = idx
            writer.writerow({k: d.get(k, "") for k in fieldnames})
    logger.info("CSV exported → %s", path)


# ─── JSON export ──────────────────────────────────────────────────────────────

def export_json(jobs: list, path: Path) -> None:
    """Write jobs to a prettily-formatted JSON file."""
    records = [job.to_dict() for job in jobs]
    with path.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "generated_at": datetime.now().isoformat(),
                "total_jobs": len(jobs),
                "jobs": records,
            },
            fh,
            indent=2,
            default=str,
        )
    logger.info("JSON exported → %s", path)


# ─── Markdown report ─────────────────────────────────────────────────────────

def export_markdown(jobs: list, path: Path, run_meta: Optional[dict] = None) -> None:
    """
    Write a Markdown report with clickable job links.

    ``run_meta`` is an optional dict of run parameters shown in the header
    section (e.g. {location: "India", days: 14}).
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines: list[str] = [
        "# 🤖 Gen-AI Job Postings Report",
        "",
        f"**Generated:** {now}  ",
        f"**Total jobs found:** {len(jobs)}  ",
    ]

    if run_meta:
        for k, v in run_meta.items():
            lines.append(f"**{k.replace('_', ' ').title()}:** {v}  ")

    lines += [
        "",
        "---",
        "",
        "| # | Company | Job Title | Location | Date Posted | Exp | Skills | Source | Apply Link |",
        "|---|---------|-----------|----------|-------------|-----|--------|--------|-----------|",
    ]

    for idx, job in enumerate(jobs, start=1):
        title_escaped = job.title.replace("|", "\\|")
        location_escaped = (job.location or "—").replace("|", "\\|")
        link = f"[Apply ↗]({job.url})"
        lines.append(
            f"| {idx} | {job.company} | {title_escaped} | {location_escaped} "
            f"| {job.date_str} | {job.experience_label} | {job.skills_label} | {job.source} | {link} |"
        )

    # Company-wise breakdown section
    lines += ["", "---", "", "## 📊 Breakdown by Company", ""]
    from collections import Counter
    counts = Counter(job.company for job in jobs)
    for company, count in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"- **{company}**: {count} job(s)")

    lines += ["", "---", "", "*Report auto-generated by `genai-jobs` CLI.*", ""]
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Markdown report exported → %s", path)


# ─── Dispatcher ──────────────────────────────────────────────────────────────

def export(
    jobs: list,
    formats: list[str],
    directory: Path,
    run_meta: Optional[dict] = None,
) -> dict[str, Path]:
    """
    Export job list to all requested formats.

    Parameters
    ----------
    jobs      : list of JobPosting objects
    formats   : subset of {"csv", "json", "md"}
    directory : output directory (created if absent)
    run_meta  : metadata dict forwarded to Markdown exporter

    Returns
    -------
    Dict mapping format → output Path.
    """
    directory.mkdir(parents=True, exist_ok=True)
    stem = "genai_jobs_report"
    outputs: dict[str, Path] = {}

    if "csv" in formats:
        p = directory / f"{stem}.csv"
        export_csv(jobs, p)
        outputs["csv"] = p

    if "json" in formats:
        p = directory / f"{stem}.json"
        export_json(jobs, p)
        outputs["json"] = p

    if "md" in formats:
        p = directory / f"{stem}.md"
        export_markdown(jobs, p, run_meta=run_meta)
        outputs["md"] = p

    return outputs
