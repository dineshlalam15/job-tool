"""
genai_jobs/pipeline.py
─────────────────────────────────────────────────────────────────────────────
Orchestrator that coordinates all four engines concurrently under a unified
Rich progress display.

Responsibilities
────────────────
1. Decide which engines to invoke (amazon-api / ats / jobspy / dork).
2. Run enabled engines in parallel via ThreadPoolExecutor so wall-clock latency
   equals the slowest active engine rather than their sum.
3. Merge, deduplicate, enforce strict India + <4 yr experience + 7-day rules,
   and sort the final result list.
4. Drive the Rich live progress display and export Markdown / CSV / JSON reports.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

from genai_jobs.config import get_config
from genai_jobs.constants import (
    CANONICAL_COMPANIES,
    DEFAULT_DAYS,
    DEFAULT_MAX_RESULTS,
)
from genai_jobs.engines.amazon_api import _AMAZON_SEARCH_TERMS, fetch_amazon_jobs
from genai_jobs.engines.ats_engine import fetch_via_ats_apis, get_supported_ats_companies
from genai_jobs.engines.dork_engine import fetch_via_dork
from genai_jobs.engines.jobspy_engine import fetch_via_jobspy
from genai_jobs.models import JobPosting
from genai_jobs.output.formatters import export, render_rich_table
from genai_jobs.utils.filters import (
    EXPERIENCE_UNKNOWN,
    infer_seniority_from_title,
    is_india_location,
    job_matches_experience,
    matches_experience,
    parse_experience,
    parse_experience_filter,
)

logger = logging.getLogger(__name__)
console = Console()


# ─── Deduplication & Sorting ──────────────────────────────────────────────────

def _deduplicate(jobs: list[JobPosting]) -> list[JobPosting]:
    """Remove duplicate jobs using their dedup_key; preserve insertion order."""
    seen: set[str] = set()
    unique: list[JobPosting] = []
    for job in jobs:
        if job.dedup_key not in seen:
            seen.add(job.dedup_key)
            unique.append(job)
    return unique


def _sort_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    """Sort: company name ↑, then date_posted ↓ (most recent first)."""
    return sorted(
        jobs,
        key=lambda j: (j.company, -(j.date_posted.toordinal() if j.date_posted else 0)),
    )


def _filter_by_experience(
    jobs: list[JobPosting],
    exp_spec: str | int,
    strict_mode: bool = True,
) -> tuple[list[JobPosting], int, str]:
    """
    Retain jobs whose stated experience requirement satisfies ``exp_spec``
    (e.g., "4", "2-4", "<4", "fresher").

    When strict_mode is True, jobs with completely unstated/unverified experience
    (Exp: N/A) are rejected so senior roles never slip through.
    """
    target_lo, target_hi = parse_experience_filter(exp_spec)
    if target_lo == -1 and target_hi == -1:
        return jobs, 0, "any"

    if target_lo == 0 and target_hi == 0:
        label = "Freshers / Entry-Level"
    elif str(exp_spec).strip().startswith("<"):
        label = f"< {target_hi + 1} yr"
    elif target_lo == 0:
        label = f"≤ {target_hi} yr"
    else:
        label = f"{target_lo}–{target_hi} yr"

    kept: list[JobPosting] = []
    skipped = 0
    for job in jobs:
        if job.exp_min == -1 and job.exp_max == -1:
            t_lo, t_hi = infer_seniority_from_title(job.title)
            if t_lo != -1 or t_hi != -1:
                job.exp_min, job.exp_max = t_lo, t_hi
            else:
                p_lo, p_hi = parse_experience(job.description_snippet, title=job.title)
                if p_lo != -1 or p_hi != -1:
                    job.exp_min, job.exp_max = p_lo, p_hi

        if job_matches_experience(job.exp_min, job.exp_max, target_lo, target_hi, strict_mode=strict_mode):
            kept.append(job)
        else:
            skipped += 1

    return kept, skipped, label


# ─── Progress helpers ─────────────────────────────────────────────────────────

def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        TaskProgressColumn(),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
        expand=True,
    )


# ─── Main pipeline ────────────────────────────────────────────────────────────

def run_pipeline(
    companies: list[str],
    location: str,
    days: int,
    max_results: int,
    sources: str,          # "jobspy" | "dork" | "ats" | "all"
    export_formats: list[str],
    output_dir: Path,
    experience: str | int = "<4",
    strict_experience: bool = True,
) -> list[JobPosting]:
    """
    Run the full Gen-AI job-fetch pipeline concurrently across active engines.
    """
    t_start = time.monotonic()
    all_jobs: list[JobPosting] = []

    exp_label = str(experience) if str(experience).lower() not in ("0", "all", "none") else "any"
    console.print(
        Panel.fit(
            f"[bold cyan]genai-jobs[/bold cyan] · "
            f"Companies: [yellow]{len(companies)}[/yellow] · "
            f"Location: [yellow]{location}[/yellow] · "
            f"Days: [yellow]{days}[/yellow] · "
            f"Sources: [yellow]{sources}[/yellow] · "
            f"Experience: [yellow]{exp_label}[/yellow]",
            border_style="bright_blue",
            title="[bold]🤖 Gen-AI & Python Job Fetcher[/bold]",
        )
    )

    use_amazon = sources in ("ats", "all") and "Amazon" in companies
    ats_supported = get_supported_ats_companies()
    ats_companies = [c for c in companies if c in ats_supported and c != "Amazon"] if sources in ("ats", "all") else []
    use_ats = bool(ats_companies)
    spy_companies = [c for c in companies if not (use_amazon and c == "Amazon")] if sources in ("jobspy", "all") else []
    use_jobspy = bool(spy_companies)
    use_dork = sources in ("dork", "all") and bool(companies)

    summary_lines: dict[str, str] = {}
    lock = threading.Lock()

    with _make_progress() as progress:
        engine_futures = []

        # Create all tasks upfront for clean stacked display
        amz_task = progress.add_task("[cyan]Amazon JSON API[/cyan]", total=len(_AMAZON_SEARCH_TERMS)) if use_amazon else None
        ats_task = progress.add_task("[green]Direct ATS APIs[/green]", total=len(ats_companies)) if use_ats else None

        spy_task = None
        if use_jobspy:
            sites = get_config().settings.jobspy_sites
            tracks = (1 if any(s.lower() != "linkedin" for s in sites) else 0) + (1 if any(s.lower() == "linkedin" for s in sites) else 0)
            spy_total = len(spy_companies) * max(1, tracks)
            spy_task = progress.add_task("[magenta]JobSpy (Aggregators)[/magenta]", total=spy_total)

        dork_task = progress.add_task("[yellow]DDG ATS Dork[/yellow]", total=len(companies)) if use_dork else None

        # Thread-safe callbacks
        def _run_amazon() -> tuple[str, list[JobPosting]]:
            counter = {"n": 0}
            amz_total = len(_AMAZON_SEARCH_TERMS)

            def _cb(company: str, term: str) -> None:
                with lock:
                    counter["n"] += 1
                    progress.update(
                        amz_task,
                        completed=min(counter["n"], amz_total),
                        description=f"[cyan]Amazon API[/cyan] ▶ {term[:32]}",
                    )

            jobs = fetch_amazon_jobs(
                location=location, days=days, max_results=max_results, progress_callback=_cb
            )
            with lock:
                progress.update(amz_task, completed=amz_total)
            return ("amazon", jobs)

        def _run_ats() -> tuple[str, list[JobPosting]]:
            visited: set[str] = set()

            def _cb(company: str, detail: str) -> None:
                with lock:
                    if company not in visited:
                        visited.add(company)
                        progress.advance(ats_task)
                    progress.update(ats_task, description=f"[green]Direct ATS[/green] ▶ {company[:25]}")

            jobs = fetch_via_ats_apis(
                companies=ats_companies, location=location, days=days, max_results=max_results, progress_callback=_cb
            )
            with lock:
                progress.update(ats_task, completed=len(ats_companies))
            return ("ats", jobs)

        def _run_jobspy() -> tuple[str, list[JobPosting]]:
            visited: set[str] = set()

            def _cb(step_key: str, term: str) -> None:
                co_display = step_key.split(":", 1)[0]
                with lock:
                    if step_key not in visited:
                        visited.add(step_key)
                        progress.advance(spy_task)
                    progress.update(spy_task, description=f"[magenta]JobSpy[/magenta] ▶ {co_display[:18]} · {term[:22]}")

            jobs = fetch_via_jobspy(
                companies=spy_companies, location=location, days=days, max_results=max_results, progress_callback=_cb
            )
            with lock:
                progress.update(spy_task, completed=progress.tasks[spy_task].total)
            return ("jobspy", jobs)

        def _run_dork() -> tuple[str, list[JobPosting]]:
            visited: set[str] = set()

            def _cb(company: str, query: str) -> None:
                with lock:
                    if company not in visited:
                        visited.add(company)
                        progress.advance(dork_task)
                    progress.update(dork_task, description=f"[yellow]DDG Dork[/yellow] ▶ {company[:25]}")

            jobs = fetch_via_dork(
                companies=companies, location=location, days=days, max_results=max_results, progress_callback=_cb
            )
            with lock:
                progress.update(dork_task, completed=len(companies))
            return ("dork", jobs)

        with ThreadPoolExecutor(max_workers=4) as pool:
            if use_amazon:
                engine_futures.append(("amazon", pool.submit(_run_amazon)))
            if use_ats:
                engine_futures.append(("ats", pool.submit(_run_ats)))
            if use_jobspy:
                engine_futures.append(("jobspy", pool.submit(_run_jobspy)))
            if use_dork:
                engine_futures.append(("dork", pool.submit(_run_dork)))

            for eng_name, fut in engine_futures:
                try:
                    _, jobs = fut.result()
                    all_jobs.extend(jobs)
                    if eng_name == "amazon":
                        summary_lines["amazon"] = f"  [green]✓[/green] Amazon API → [bold]{len(jobs)}[/bold] job(s)"
                    elif eng_name == "ats":
                        summary_lines["ats"] = f"  [green]✓[/green] Direct ATS APIs ({len(ats_companies)} portals) → [bold]{len(jobs)}[/bold] job(s)"
                    elif eng_name == "jobspy":
                        summary_lines["jobspy"] = f"  [green]✓[/green] JobSpy Aggregators → [bold]{len(jobs)}[/bold] job(s)"
                    elif eng_name == "dork":
                        summary_lines["dork"] = f"  [green]✓[/green] DDG ATS Dork → [bold]{len(jobs)}[/bold] job(s)"
                except Exception as exc:
                    logger.error("%s engine crashed: %s", eng_name, exc)
                    summary_lines[eng_name] = f"  [red]✗[/red] {eng_name} → failed ({exc})"

    # Print clean per-engine summary lines after Rich progress exits
    for key in ("amazon", "ats", "jobspy", "dork"):
        if key in summary_lines:
            console.print(summary_lines[key])

    # ── Merge & clean ─────────────────────────────────────────────────────────
    merged = _sort_jobs(_deduplicate(all_jobs))

    # ── Strict India location enforcement ─────────────────────────────────────
    if location.strip().lower() in ("india", "ind"):
        before_loc = len(merged)
        merged = [
            j for j in merged
            if is_india_location(j.location, f"{j.title} {j.description_snippet}")
        ]
        non_india_skipped = before_loc - len(merged)
        if non_india_skipped > 0:
            console.print(f"  [dim]Strict India location filter: skipped {non_india_skipped} non-India job(s)[/dim]")

    # ── Experience filter ─────────────────────────────────────────────────────
    final_jobs, skipped, exp_active_label = _filter_by_experience(
        merged, experience, strict_mode=strict_experience
    )
    elapsed = time.monotonic() - t_start
    if exp_active_label != "any":
        mode_str = "strict verified only" if strict_experience else "unstated allowed"
        console.print(
            f"  [bold]Experience filter[/bold] ({exp_active_label}, {mode_str}): "
            f"[green]{len(final_jobs)} kept[/green], "
            f"[yellow]{skipped} skipped[/yellow] "
            f"([dim]{len(merged)} before filter · {elapsed:.1f}s total[/dim])"
        )
    else:
        console.print(f"  [dim]Completed in {elapsed:.1f}s[/dim]")

    # ── Render terminal table ─────────────────────────────────────────────────
    exp_tag = f" · Exp {exp_active_label}" if exp_active_label != "any" else ""
    render_rich_table(
        final_jobs,
        title=f"Gen-AI Jobs — {location} — last {days} days{exp_tag}",
    )

    # ── Auto-save reports ─────────────────────────────────────────────────────
    auto_formats = set(["csv", "md", "json"]) | set(export_formats)
    run_meta = {
        "location": location,
        "days": days,
        "companies": ", ".join(companies),
        "sources": sources,
        "max_results_per_company": "all" if not max_results or max_results <= 0 else max_results,
        "experience_filter": exp_active_label,
        "strict_experience": strict_experience,
    }
    output_paths = export(
        jobs=final_jobs,
        formats=list(auto_formats),
        directory=output_dir,
        run_meta=run_meta,
    )

    if output_paths:
        console.print("[bold]📂 Saved reports:[/bold]")
        for fmt, path in output_paths.items():
            console.print(f"  [cyan]{fmt.upper()}[/cyan] → {path}")
    console.print()

    return final_jobs
