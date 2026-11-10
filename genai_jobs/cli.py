"""
genai_jobs/cli.py
─────────────────────────────────────────────────────────────────────────────
Typer-based CLI entry point for `genai-jobs`.

Usage examples
──────────────
  genai-jobs                                     # all 36 companies, India, 7 days, <4 yrs
  genai-jobs -c Amazon -c IBM -l Hyderabad       # two companies, one city
  genai-jobs -d 7 -m 20 -s dork                 # dork only, 7 days, 20 results
  genai-jobs --list-companies                    # print all configured companies
"""
from __future__ import annotations

import logging
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
    DEFAULT_SOURCES,
    refresh_constants,
)
from genai_jobs.pipeline import run_pipeline
from genai_jobs.utils.filters import validate_company_names

# ─── App setup ───────────────────────────────────────────────────────────────

app = typer.Typer(
    name="genai-jobs",
    help=(
        "Fetch active Generative AI job postings from 36 target companies "
        "(Google, Microsoft, Apple, Amazon, Salesforce, Disney, Caterpillar, Ericsson, …) "
        "strictly from their official career portals (direct ATS APIs, Amazon API, and ATS dorking)."
    ),
    add_completion=False,
    rich_markup_mode="rich",
    no_args_is_help=False,
)

console = Console()

# ─── Logging ─────────────────────────────────────────────────────────────────

def _configure_logging(verbose: bool) -> None:
    """
    Configure root logging verbosity and suppress noisy third-party library logs.

    Args:
        verbose (bool): When True, sets root logging level to DEBUG; otherwise sets
            WARNING and silences non-critical logs from ddgs, httpx, httpcore, and primp.

    Returns:
        None: Updates Python's global logging configuration in place.
    """
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    if not verbose:
        # Suppress noisy internal error outputs from third-party libraries
        for noisy in ("ddgs", "httpx", "httpcore", "primp"):
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
                "Accepts full names or aliases e.g. 'Google', 'Microsoft', 'Caterpillar', 'Ericsson'. "
                "Default: all 36 companies."
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
                "Career-portal engines to use. "
                "Choices: 'ats' (Amazon API + direct career portal APIs), "
                "'dork' (DuckDuckGo career-portal ATS dorking), "
                "'all' (all company career-portal engines). Default: all."
            ),
        ),
    ] = DEFAULT_SOURCES,

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
            help="Print the 36 target companies and exit.",
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
    Fetch active [bold cyan]Generative AI, Agentic AI, LLM & RAG[/bold cyan] job postings from 36 target companies.

    By default queries [bold]all 36 companies[/bold] with [bold]all career-portal engines[/bold]
    in [bold]India[/bold] for jobs posted in the [bold]last 7 days[/bold], strictly filtered for
    < 4 years experience, and prints matching jobs with their URLs directly in the terminal.

    Args:
        company: Optional list of company names or aliases to filter by.
        location: Target geographic location string (default: India).
        days: Lookback window in days between 1 and 90 (default: 7).
        max_results: Maximum jobs per company per engine, or 0 for unlimited (default: 0).
        experience: Required experience filter expression such as '<4', '2-4', 'fresher', or 'all'.
        strict_exp: Optional override for strict experience verification mode.
        sources: Engine selector ('ats', 'dork', or 'all').
        config_dir: Optional custom directory containing companies, skills, and settings JSON files.
        list_companies: When True, prints all configured company names and exits.
        verbose: When True, enables DEBUG logging output.

    Returns:
        None: Exits after printing the configured company list or terminal job results.
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
    valid_sources = {"ats", "dork", "all"}
    if sources not in valid_sources:
        console.print(
            f"[bold red]Error:[/bold red] --sources must be one of {sorted(valid_sources)} "
            f"(only company career portals are enabled). Got: {sources!r}"
        )
        raise typer.Exit(code=1)

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
