"""
genai_jobs/cli.py
─────────────────────────────────────────────────────────────────────────────
Typer-based CLI entry point for `genai-jobs`.

Usage examples
──────────────
  genai-jobs                                     # all 34 companies, India, 7 days, <4 yrs
  genai-jobs -c Amazon -c IBM -l Hyderabad       # two companies, one city
  genai-jobs -d 7 -m 20 -s dork                 # dork only, 7 days, 20 results
  genai-jobs -e json -e md -l "USA"             # US jobs, export JSON + MD
  genai-jobs --list-companies                    # print all configured companies
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console

from genai_jobs.config import get_config, load_config
from genai_jobs.constants import (
    CANONICAL_COMPANIES,
    DEFAULT_DAYS,
    DEFAULT_EXPERIENCE,
    DEFAULT_LOCATION,
    DEFAULT_MAX_RESULTS,
    refresh_constants,
)
from genai_jobs.pipeline import run_pipeline
from genai_jobs.utils.filters import validate_company_names

# ─── App setup ───────────────────────────────────────────────────────────────

app = typer.Typer(
    name="genai-jobs",
    help=(
        "Fetch active Generative AI and ML job postings from 34 target companies "
        "(Google, Microsoft, Apple, Amazon, Salesforce, Disney, JPMC, Goldman Sachs, …) across Indeed, "
        "LinkedIn, DuckDuckGo ATS dorking, and native APIs."
    ),
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,
)

console = Console()

# ─── Logging ─────────────────────────────────────────────────────────────────

def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if not verbose:
        # Suppress noisy internal error outputs from third-party scraping libraries
        for noisy in ("jobspy", "ddgs", "duckduckgo_search", "httpx", "httpcore", "primp"):
            logging.getLogger(noisy).setLevel(logging.CRITICAL)


# ─── Main command ─────────────────────────────────────────────────────────────

@app.command()
def main(
    # ── company filter ──────────────────────────────────────────────────────
    company: Annotated[
        Optional[list[str]],
        typer.Option(
            "--company", "-c",
            help=(
                "Filter by company name (repeatable). "
                "Accepts full names or aliases e.g. 'Google', 'Microsoft', 'Disney', 'Apple'. "
                "Default: all 34 companies."
            ),
        ),
    ] = None,

    # ── location ────────────────────────────────────────────────────────────
    location: Annotated[
        str,
        typer.Option(
            "--location", "-l",
            help=(
                "Location to search. E.g. 'India', 'Hyderabad', 'Bengaluru', "
                "'Pune', 'Mumbai', 'USA', 'Global'. Default: India."
            ),
        ),
    ] = DEFAULT_LOCATION,

    # ── days ────────────────────────────────────────────────────────────────
    days: Annotated[
        int,
        typer.Option(
            "--days", "-d",
            help="Only include jobs posted within last N days. Default: 7.",
            min=1,
            max=90,
        ),
    ] = DEFAULT_DAYS,

    # ── max results ─────────────────────────────────────────────────────────
    max_results: Annotated[
        int,
        typer.Option(
            "--max-results", "-m",
            help="Maximum results fetched per company per engine. Default: 0 (fetch all matching openings).",
            min=0,
            max=1000,
        ),
    ] = DEFAULT_MAX_RESULTS,

    # ── experience filter ────────────────────────────────────────────────────
    experience: Annotated[
        str,
        typer.Option(
            "--experience", "-x",
            help=(
                "Filter by required experience. Supports single numbers or ranges: "
                "'4' (≤ 4 yrs), '2-4' (2 to 4 yrs), '<4' (less than 4 yrs), "
                "'fresher', or 'all' to disable. Default: <4."
            ),
        ),
    ] = DEFAULT_EXPERIENCE,

    # ── strict experience ────────────────────────────────────────────────────
    strict_exp: Annotated[
        Optional[bool],
        typer.Option(
            "--strict-exp/--allow-unstated",
            help=(
                "Strictly require verified experience (reject jobs with unstated/N/A experience). "
                "Default is loaded from config/settings.json (true)."
            ),
        ),
    ] = None,

    # ── sources ─────────────────────────────────────────────────────────────
    sources: Annotated[
        str,
        typer.Option(
            "--sources", "-s",
            help=(
                "Engines to use. "
                "Choices: 'ats' (Amazon API + direct career portal APIs — ultra-fast ~15s), "
                "'jobspy' (Indeed/Naukri/LinkedIn aggregators), 'dork' (DDG ATS dorking), "
                "'all' (all engines). Default: all."
            ),
        ),
    ] = "all",

    # ── export format(s) ─────────────────────────────────────────────────────
    export_format: Annotated[
        Optional[list[str]],
        typer.Option(
            "--export", "-e",
            help=(
                "Export format(s) in addition to the auto-saved CSV + MD. "
                "Choices: csv, json, md. Repeatable."
            ),
        ),
    ] = None,

    # ── output directory ─────────────────────────────────────────────────────
    output_dir: Annotated[
        Path,
        typer.Option(
            "--output-dir", "-o",
            help="Directory where report files are saved. Default: current directory.",
        ),
    ] = Path("."),

    # ── external config directory ───────────────────────────────────────────
    config_dir: Annotated[
        Optional[Path],
        typer.Option(
            "--config-dir",
            help=(
                "Path to custom config directory containing companies.json, "
                "skills.json, and settings.json. Default: ./config"
            ),
        ),
    ] = None,

    # ── utility flags ────────────────────────────────────────────────────────
    list_companies: Annotated[
        bool,
        typer.Option(
            "--list-companies",
            help="Print the 34 target companies and exit.",
            is_flag=True,
        ),
    ] = False,

    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose", "-v",
            help="Enable debug-level logging.",
            is_flag=True,
        ),
    ] = False,
) -> None:
    """
    Fetch active [bold cyan]Generative AI & ML[/bold cyan] job postings from 34 target companies.

    By default queries [bold]all 34 companies[/bold] with [bold]all engines[/bold] in [bold]India[/bold]
    for jobs posted in the [bold]last 7 days[/bold], strictly filtered for candidates with < 4 years
    experience, then prints a table and saves reports to the current directory.
    """
    _configure_logging(verbose)

    # ── Custom Config Directory ───────────────────────────────────────────────
    if config_dir:
        load_config(config_dir, reload=True)
        refresh_constants()

    # ── --list-companies ──────────────────────────────────────────────────────
    if list_companies:
        companies_list = CANONICAL_COMPANIES
        console.print(f"\n[bold cyan]Configured Companies ({len(companies_list)})[/bold cyan]\n")
        for i, name in enumerate(companies_list, 1):
            console.print(f"  [green]{i:2}.[/green] {name}")
        console.print()
        raise typer.Exit()

    # ── Validate --sources ────────────────────────────────────────────────────
    valid_sources = {"jobspy", "dork", "ats", "all"}
    if sources not in valid_sources:
        console.print(
            f"[bold red]Error:[/bold red] --sources must be one of {valid_sources}. "
            f"Got: {sources!r}"
        )
        raise typer.Exit(code=1)

    # ── Validate --export ─────────────────────────────────────────────────────
    valid_formats = {"csv", "json", "md"}
    requested_formats: list[str] = []
    if export_format:
        bad_formats = [f for f in export_format if f.lower() not in valid_formats]
        if bad_formats:
            console.print(
                f"[bold red]Error:[/bold red] Unknown export format(s): {bad_formats}. "
                f"Valid: {valid_formats}"
            )
            raise typer.Exit(code=1)
        requested_formats = [f.lower() for f in export_format]

    # ── Resolve company names ─────────────────────────────────────────────────
    target_companies: list[str]
    if company:
        try:
            target_companies = validate_company_names(list(company))
        except ValueError as exc:
            console.print(f"[bold red]Error:[/bold red] {exc}")
            raise typer.Exit(code=1)
    else:
        target_companies = list(CANONICAL_COMPANIES)  # all configured companies

    # ── Resolve strict experience setting ─────────────────────────────────────
    cfg = get_config()
    strict_mode = strict_exp if strict_exp is not None else cfg.settings.strict_experience

    # ── Run ───────────────────────────────────────────────────────────────────
    try:
        run_pipeline(
            companies=target_companies,
            location=location,
            days=days,
            max_results=max_results,
            sources=sources,
            export_formats=requested_formats,
            output_dir=output_dir.expanduser().resolve(),
            experience=experience,
            strict_experience=strict_mode,
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user.[/yellow]")
        raise typer.Exit(code=130)
    except Exception as exc:
        logging.getLogger(__name__).exception("Fatal pipeline error")
        console.print(f"[bold red]Fatal error:[/bold red] {exc}")
        raise typer.Exit(code=1)


# ─── Entry point for `python -m genai_jobs` ──────────────────────────────────

if __name__ == "__main__":
    app()
