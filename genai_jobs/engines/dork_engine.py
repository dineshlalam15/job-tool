"""
genai_jobs/engines/dork_engine.py
─────────────────────────────────────────────────────────────────────────────
Secondary Engine — DuckDuckGo "ATS Dorking".

Strategy
────────
For every target company we build a DuckDuckGo search query that restricts
results to the company's known ATS / career domains (site: operator) combined
with Gen-AI keywords.  This catches roles that are live on official portals
but NOT yet indexed by job aggregators.

Example query:
  site:amazon.jobs ("Generative AI" OR "GenAI" OR "LLM") "India"

The DDGS.text() results return title + URL + body snippet, which we parse
to infer job title and validate the Gen-AI match.

Robustness
──────────
* We rate-limit calls to avoid DuckDuckGo 202 / Ratelimit errors.
* Tenacity retries on RatelimitException with longer back-off.
* Each company query is wrapped in try/except so one failure never aborts all.
"""
from __future__ import annotations

import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional
from urllib.parse import urlparse

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from genai_jobs.constants import (
    COMPANY_ATS_DOMAINS,
    DEFAULT_DAYS,
    DEFAULT_MAX_RESULTS,
    MAX_RETRY_ATTEMPTS,
    RETRY_WAIT_MAX,
    RETRY_WAIT_MIN,
)
from genai_jobs.models import JobPosting
from genai_jobs.utils.filters import (
    company_from_url,
    matches_genai,
    resolve_company,
    truncate,
    detect_skills,
    parse_experience,
    extract_india_location,
    is_india_location,
)
from genai_jobs.utils.security import apply_jitter_delay

logger = logging.getLogger(__name__)

# DDG rate-limit guard: seconds to sleep between consecutive company queries
_DDG_INTER_QUERY_SLEEP: float = 0.35

# Updated DDG clause matching GenAI, Artificial Intelligence/Engineering, Agentic AI
_GENAI_DDG_CLAUSE = '("Generative AI" OR "Agentic AI" OR "Artificial Intelligence" OR "AI Engineer" OR "LLM")'

_INDIA_LOCATIONS_QUERY = '("India" OR "Bengaluru" OR "Hyderabad" OR "Pune")'


def _build_dork_query(company: str, location: str) -> str:
    """
    Build a site-restricted DDG query for a company using its known ATS domains.
    Falls back to a plain company-name query if no ATS domains are configured.
    """
    domains = COMPANY_ATS_DOMAINS.get(company, [])
    if location:
        if location.strip().lower() in ("india", "ind"):
            location_part = _INDIA_LOCATIONS_QUERY
        else:
            location_part = f'"{location}"'
    else:
        location_part = ""

    if domains:
        site_part = " OR ".join(f"site:{d}" for d in domains)
        query = f"({site_part}) {_GENAI_DDG_CLAUSE}"
    else:
        query = f'"{company}" {_GENAI_DDG_CLAUSE} jobs'

    if location_part:
        query += f" {location_part}"

    return query


# ─── DDG fetch with retry ─────────────────────────────────────────────────────

def _ddg_search(query: str, max_results: int, timelimit: Optional[str] = None) -> list[dict]:
    """
    Call DDGS.text() with retry; returns raw result list.

    Supports both the new ``ddgs`` package and the legacy
    ``duckduckgo_search`` package (which now just re-exports from ``ddgs``).
    """
    # Prefer the canonical renamed package; fall back to the legacy wrapper.
    try:
        from ddgs import DDGS
        from ddgs.exceptions import DDGSException
    except ImportError:
        try:
            from duckduckgo_search import DDGS  # type: ignore[no-redef]
            from duckduckgo_search.exceptions import DuckDuckGoSearchException as DDGSException  # type: ignore[no-redef]
        except ImportError:
            logger.error(
                "Neither 'ddgs' nor 'duckduckgo-search' is installed. "
                "Run: pip install ddgs"
            )
            return []

    attempts = min(2, MAX_RETRY_ATTEMPTS)
    for attempt in range(1, attempts + 1):
        try:
            kwargs = {"max_results": max_results}
            if timelimit:
                kwargs["timelimit"] = timelimit
            with DDGS(timeout=6) as ddgs:
                results = list(ddgs.text(query, **kwargs))
            return results
        except DDGSException as exc:
            msg = str(exc).lower()
            if "no results" in msg:
                return []
            if "ratelimit" in msg or "429" in msg or "202" in msg:
                logger.debug("DDG rate-limited (attempt %d/%d): %s", attempt, attempts, exc)
                if attempt < attempts:
                    time.sleep(1.0 * attempt)
                else:
                    raise  # notify circuit breaker
            else:
                logger.debug("DDG search exception for query %r: %s", query, exc)
                return []
        except Exception as exc:
            logger.debug("DDG search error (attempt %d/%d): %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(1.0)

    return []


# ─── Row parser ───────────────────────────────────────────────────────────────

def _parse_ddg_result(
    result: dict,
    company: str,
    target_location: str = "India",
) -> Optional[JobPosting]:
    """
    Convert one DDGS.text() result dict to a JobPosting.

    DDG result keys: ``title``, ``href``, ``body``
    """
    url = result.get("href", "").strip()
    title = result.get("title", "").strip()
    body = result.get("body", "").strip()

    if not url or not title:
        return None

    # Skip results that are clearly not job postings or are generic career hub pages
    lower_title = title.lower()
    skip_title_phrases = [
        "login", "sign in", "search results", "home page", "about us",
        "search jobs", "search careers", "job search", "explore careers",
        "join our team", "careers at ", "elevate your career", "welcome to careers",
        "join quantiphi", "life at ",
    ]
    if any(skip in lower_title for skip in skip_title_phrases):
        return None

    # Skip generic career portal landing pages and career blogs
    path_only = re.sub(r"^https?://[^/]+", "", url.split("?")[0]).strip("/").lower()
    if path_only in ("", "careers", "jobs", "en/careers", "en/jobs", "en-us/careers"):
        return None
    if "/blog" in path_only or "careers/blog" in url.lower() or "/article" in path_only:
        return None

    # Validate that the URL strictly belongs to the target company's domain
    inferred_company = company_from_url(url)
    if inferred_company != company:
        return None  # Skip if URL does not belong to the target company's ATS/career portal

    # Strict location verification if target is India
    combined_context = f"{title} {body} {url}"
    extracted_loc = extract_india_location(combined_context)
    if target_location and target_location.strip().lower() in ("india", "ind"):
        if not is_india_location(extracted_loc or "", combined_context):
            return None

    # Gen-AI keyword check
    if not matches_genai(title, body):
        return None

    exp_min, exp_max = parse_experience(title + " " + body, title=title)
    skills = detect_skills(title, body)

    return JobPosting(
        company=company,
        title=title,
        location=extracted_loc or ("India" if target_location and target_location.strip().lower() in ("india", "ind") else ""),
        date_posted=None,
        url=url,
        source="dork/ddg",
        description_snippet=truncate(body),
        exp_min=exp_min,
        exp_max=exp_max,
        skills=skills,
    )


# ─── Public API ──────────────────────────────────────────────────────────────

def fetch_via_dork(
    companies: list[str],
    location: str = "India",
    days: int = DEFAULT_DAYS,
    max_results: int = DEFAULT_MAX_RESULTS,
    progress_callback=None,
) -> list[JobPosting]:
    """
    For each company, build a DuckDuckGo ATS-dork query and parse the results
    into JobPosting objects.

    Parameters
    ----------
    companies         : canonical company names
    location          : forwarded into the DDG query string
    days              : unused (DDG has no native date filter; kept for API symmetry)
    max_results       : number of DDG results to request per company
    progress_callback : optional callable(company, query_str) for UI updates

    Returns
    -------
    De-duplicated list of JobPosting objects.
    """
    seen_keys: set[str] = set()
    all_jobs: list[JobPosting] = []

    # Map days parameter to DDGS timelimit ('d'=day, 'w'=week, 'm'=month)
    timelimit = None
    if days:
        if days <= 1:
            timelimit = "d"
        elif days <= 7:
            timelimit = "w"
        elif days <= 30:
            timelimit = "m"

    unlimited = not max_results or max_results <= 0
    ddg_limit = 30 if unlimited else max_results

    rl_state = {"streak": 0, "tripped": False, "lock": threading.Lock()}

    def _query_one(company: str) -> list[JobPosting]:
        query = _build_dork_query(company, location)
        if progress_callback:
            progress_callback(company, query)

        if rl_state["tripped"]:
            return []

        try:
            raw_results = _ddg_search(query, max_results=ddg_limit, timelimit=timelimit)
            with rl_state["lock"]:
                rl_state["streak"] = 0
        except Exception as exc:
            logger.debug("DDG failed/rate-limited for company=%r: %s", company, exc)
            with rl_state["lock"]:
                rl_state["streak"] += 1
                if rl_state["streak"] >= 4:
                    rl_state["tripped"] = True
            return []

        co_jobs: list[JobPosting] = []
        for result in raw_results:
            job = _parse_ddg_result(result, company, target_location=location)
            if job:
                co_jobs.append(job)
                if not unlimited and len(co_jobs) >= max_results:
                    break

        apply_jitter_delay(_DDG_INTER_QUERY_SLEEP)
        return co_jobs

    if not companies:
        return []

    with ThreadPoolExecutor(max_workers=min(3, len(companies))) as executor:
        futures = [executor.submit(_query_one, co) for co in companies]
        for fut in as_completed(futures):
            try:
                for job in fut.result() or []:
                    if job.dedup_key not in seen_keys:
                        seen_keys.add(job.dedup_key)
                        all_jobs.append(job)
            except Exception as exc:
                logger.debug("DDG worker crashed: %s", exc)

    return all_jobs
