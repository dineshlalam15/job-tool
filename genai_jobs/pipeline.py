"""
genai_jobs/pipeline.py
─────────────────────────────────────────────────────────────────────────────
Orchestrator that coordinates the company career-portal engines concurrently
under a unified Rich progress display.

Responsibilities
────────────────
1. Decide which career-portal engines to invoke (amazon-api / ats / dork).
2. Run enabled engines in parallel via ThreadPoolExecutor so wall-clock latency
   equals the slowest active engine rather than their sum.
3. Merge, deduplicate, enforce strict India + <4 yr experience + 7-day rules,
   and sort the final result list.
4. Render the Rich progress display and terminal results table with job URLs.
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor

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
from rich.table import Table
from rich.text import Text

from genai_jobs.engines.amazon_api import fetch_amazon_jobs, get_amazon_search_terms
from genai_jobs.engines.ats_engine import fetch_via_ats_apis, get_supported_ats_companies
from genai_jobs.engines.dork_engine import fetch_via_dork
from genai_jobs.models import JobPosting
from genai_jobs.utils.filters import (
    infer_seniority_from_title,
    is_india_location,
    job_matches_experience,
    parse_experience,
    parse_experience_filter,
)

logger = logging.getLogger(__name__)
console = Console()


# ─── Deduplication & Sorting ──────────────────────────────────────────────────

def _deduplicate(jobs: list[JobPosting]) -> list[JobPosting]:
    """
    Remove duplicate job postings using each posting's canonical ``dedup_key``
    while preserving original insertion order.

    Args:
        jobs (list[JobPosting]): Raw list of collected job postings across engines.

    Returns:
        list[JobPosting]: Deduplicated list retaining the first occurrence per ``dedup_key``.
    """
    seen: set[str] = set()
    unique: list[JobPosting] = []
    for job in jobs:
        if job.dedup_key not in seen:
            seen.add(job.dedup_key)
            unique.append(job)
    return unique


def _sort_jobs(jobs: list[JobPosting]) -> list[JobPosting]:
    """
    Sort job postings alphabetically by company name (ascending) and then by
    posting date (most recent first, placing unstated dates last).

    Args:
        jobs (list[JobPosting]): Deduplicated list of job postings.

    Returns:
        list[JobPosting]: Newly sorted list of job postings.
    """
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
    Filter job postings against an experience requirement expression (such as
    ``"<4"``, ``"2-4"``, ``"4"``, ``"fresher"``, or ``"all"``), hydrating missing
    bounds from job titles and descriptions before applying matching logic.

    Args:
        jobs (list[JobPosting]): Candidate job postings after deduplication.
        exp_spec (str | int): Experience requirement filter string or year cap.
        strict_mode (bool): When True, rejects postings with unstated experience
            (``exp_min == -1`` and ``exp_max == -1``).

    Returns:
        tuple[list[JobPosting], int, str]: Three-element tuple containing:
            - filtered list of kept ``JobPosting`` records,
            - count of skipped postings,
            - human-readable label describing the active experience filter.
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
    """
    Construct the shared Rich multi-task progress bar used to display live
    completion across concurrent career-portal engines.

    Args:
        None.

    Returns:
        Progress: Configured Rich ``Progress`` widget bound to the module console.
    """
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


# ─── Terminal Output (Rich) ──────────────────────────────────────────────────

def render_rich_table(jobs: list[JobPosting], title: str = "Gen-AI Job Postings") -> None:
    """
    Print matching job postings directly in the terminal as a formatted Rich
    summary table followed by an indexed, untruncated clickable URL list, or print
    a warning message when no jobs match.

    Args:
        jobs (list[JobPosting]): Final sorted and filtered list of job postings.
        title (str): Header title displayed above the Rich summary table.

    Returns:
        None: Writes formatted output directly to the Rich terminal console.
    """
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

    table.add_column("#", style="bold white", width=3, justify="right", no_wrap=True)
    table.add_column("Company", style="green", min_width=8, ratio=2, overflow="fold")
    table.add_column("Job Title", style="bright_white", min_width=16, ratio=4, overflow="fold")
    table.add_column("Location", style="yellow", min_width=10, ratio=2, overflow="fold")
    table.add_column("Posted", style="cyan", width=10, no_wrap=True)
    table.add_column("Exp", style="magenta", width=6, no_wrap=True)
    table.add_column("Skills", style="bright_green", min_width=10, ratio=2, overflow="fold")
    table.add_column("Source", style="blue", width=12, no_wrap=True)

    for idx, job in enumerate(jobs, start=1):
        title_link = Text(job.title, style=f"link {job.url}")
        table.add_row(
            str(idx),
            job.company,
            title_link,
            job.location or "—",
            job.date_str,
            job.experience_label,
            job.skills_label,
            job.source,
        )

    console.print()
    console.print(table)
    console.print("[bold magenta]Job URLs:[/bold magenta]")
    for idx, job in enumerate(jobs, start=1):
        loc = f" · {job.location}" if job.location else ""
        console.print(
            f"  [bold white][{idx}][/bold white] [green]{job.company}[/green] — {job.title}[dim]{loc}[/dim]"
        )
        url_line = Text("      ") + Text(job.url, style=f"link {job.url} bold cyan underline")
        console.print(url_line, soft_wrap=True)

    console.print(
        f"\n[bold green]✓ Total:[/bold green] [white]{len(jobs)} unique Gen-AI job(s) found.[/white]\n"
    )


# ─── Main pipeline ────────────────────────────────────────────────────────────

def run_pipeline(
    companies: list[str],
    location: str,
    days: int,
    max_results: int,
    sources: str,          # "ats" | "dork" | "all"
    experience: str | int = "<4",
    strict_experience: bool = True,
) -> list[JobPosting]:
    """
    Orchestrate concurrent execution across enabled career-portal engines
    (Amazon JSON API, Direct ATS APIs, and DDG ATS dorking), merge and clean
    all discovered postings, apply India location and experience filters, and
    render the final results with URLs in the terminal.

    Args:
        companies (list[str]): Canonical company names to query.
        location (str): Target location string (e.g. ``"India"``, ``"Bengaluru"``).
        days (int): Maximum posting age window in days.
        max_results (int): Maximum results per company per engine (0 means unlimited).
        sources (str): Engine selector (``"ats"``, ``"dork"``, or ``"all"``).
        experience (str | int): Experience filter expression (default: ``"<4"``).
        strict_experience (bool): Reject unstated experience roles when True.

    Returns:
        list[JobPosting]: Final deduplicated, sorted, and filtered job postings.
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
            title="[bold]🤖 Gen-AI Career Portal Job Fetcher[/bold]",
        )
    )

    use_amazon = sources in ("ats", "all") and "Amazon" in companies
    ats_supported = get_supported_ats_companies()
    ats_companies = [c for c in companies if c in ats_supported and c != "Amazon"] if sources in ("ats", "all") else []
    use_ats = bool(ats_companies)
    use_dork = sources in ("dork", "all") and bool(companies)

    summary_lines: dict[str, str] = {}
    lock = threading.Lock()

    with _make_progress() as progress:
        engine_futures = []

        # Create all tasks upfront for clean stacked display
        amz_terms = get_amazon_search_terms() if use_amazon else []
        amz_task = progress.add_task("[cyan]Amazon JSON API[/cyan]", total=len(amz_terms)) if use_amazon else None
        ats_task = progress.add_task("[green]Direct ATS APIs[/green]", total=len(ats_companies)) if use_ats else None
        dork_task = progress.add_task("[yellow]DDG ATS Dork[/yellow]", total=len(companies)) if use_dork else None

        # Thread-safe callbacks
        def _run_amazon() -> tuple[str, list[JobPosting]]:
            """
            Execute the Amazon JSON API engine inside a worker thread and keep its
            Rich progress bar updated as each search term completes.

            Args:
                None.

            Returns:
                tuple[str, list[JobPosting]]: Pair of ``("amazon", fetched_jobs)``.
            """
            counter = {"n": 0}
            amz_total = len(amz_terms)

            def _cb(company: str, term: str) -> None:
                """
                Update the Amazon progress bar safely whenever a search term starts.

                Args:
                    company (str): Company identifier supplied by the engine.
                    term (str): Search query term currently being queried.

                Returns:
                    None.
                """
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
            """
            Execute the Direct ATS Portals engine inside a worker thread and track
            completed company portals on its Rich progress bar.

            Args:
                None.

            Returns:
                tuple[str, list[JobPosting]]: Pair of ``("ats", fetched_jobs)``.
            """
            visited: set[str] = set()

            def _cb(company: str, detail: str) -> None:
                """
                Advance the Direct ATS progress bar when a company portal completes.

                Args:
                    company (str): Canonical company name being queried.
                    detail (str): Status or adapter descriptor string.

                Returns:
                    None.
                """
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

        def _run_dork() -> tuple[str, list[JobPosting]]:
            """
            Execute the DuckDuckGo career-portal dorking engine inside a worker
            thread and update its Rich progress bar per company.

            Args:
                None.

            Returns:
                tuple[str, list[JobPosting]]: Pair of ``("dork", fetched_jobs)``.
            """
            visited: set[str] = set()

            def _cb(company: str, query: str) -> None:
                """
                Advance the DDG Dork progress bar when a company query starts.

                Args:
                    company (str): Canonical company name being searched.
                    query (str): Constructed site-restricted query or skip message.

                Returns:
                    None.
                """
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

        with ThreadPoolExecutor(max_workers=3) as pool:
            if use_amazon:
                engine_futures.append(("amazon", pool.submit(_run_amazon)))
            if use_ats:
                engine_futures.append(("ats", pool.submit(_run_ats)))
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
                    elif eng_name == "dork":
                        summary_lines["dork"] = f"  [green]✓[/green] DDG ATS Dork → [bold]{len(jobs)}[/bold] job(s)"
                except Exception as exc:
                    logger.error("%s engine crashed: %s", eng_name, exc)
                    summary_lines[eng_name] = f"  [red]✗[/red] {eng_name} → failed ({exc})"

    # Print clean per-engine summary lines after Rich progress exits
    for key in ("amazon", "ats", "dork"):
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

    # ── Render terminal output ────────────────────────────────────────────────
    exp_tag = f" · Exp {exp_active_label}" if exp_active_label != "any" else ""
    render_rich_table(
        final_jobs,
        title=f"Gen-AI Jobs — {location} — last {days} days{exp_tag}",
    )

    return final_jobs
