"""
genai_jobs/engines/amazon_api.py
─────────────────────────────────────────────────────────────────────────────
Bonus / Fast-Path Engine — Amazon's public JSON search endpoint.

Amazon exposes https://www.amazon.jobs/en/search.json which returns
structured JSON (no JS rendering required) with full job metadata including
title, location, posted date, job_path, and description_short.

This engine runs concurrently and fills the Amazon bucket rapidly alongside the other
engines querying the remaining target companies.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from genai_jobs.config import get_search_terms
from genai_jobs.constants import (
    AMAZON_JOBS_API,
    DEFAULT_DAYS,
    DEFAULT_MAX_RESULTS,
    MAX_RETRY_ATTEMPTS,
)
from genai_jobs.models import JobPosting
from genai_jobs.utils.filters import (
    detect_skills,
    matches_genai,
    parse_experience,
    truncate,
    extract_india_location,
    is_india_location,
)
from genai_jobs.utils.security import apply_jitter_delay, get_stealth_headers

logger = logging.getLogger(__name__)

_AMAZON_BASE_URL = "https://www.amazon.jobs"
_AMAZON_PAGE_SIZE = 100
_MAX_OFFSET_PER_TERM = 300

_DEFAULT_AMAZON_SEARCH_TERMS = [
    "Generative AI",
    "Agentic AI",
    "LLM",
    "RAG",
]


def get_amazon_search_terms() -> list[str]:
    """
    Retrieve search terms for Amazon Jobs queries from external configuration,
    falling back to the default Gen-AI keyword list if unconfigured.

    Args:
        None.

    Returns:
        list[str]: Search query strings (e.g. ``["Generative AI", "Agentic AI", "LLM", "RAG"]``).
    """
    return get_search_terms() or list(_DEFAULT_AMAZON_SEARCH_TERMS)


# ─── HTTP client helpers ──────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
    stop=stop_after_attempt(min(2, MAX_RETRY_ATTEMPTS)),
    wait=wait_exponential(multiplier=1, min=1.0, max=4.0),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=False,
)
def _get_amazon_page(params: dict, client: Optional[httpx.Client] = None) -> Optional[dict]:
    """
    Execute a single HTTP GET request against the Amazon Jobs JSON search API
    with Tenacity retry handling, reusing ``client`` when provided or opening a
    temporary stealth-header ``httpx.Client``.

    Args:
        params (dict): Query parameters for the ``search.json`` endpoint.
        client (Optional[httpx.Client]): Optional shared HTTP client for connection reuse.

    Returns:
        Optional[dict]: Deserialized JSON response dictionary, or ``None`` if retries fail.
    """
    if client is not None:
        resp = client.get(AMAZON_JOBS_API, params=params)
        resp.raise_for_status()
        return resp.json()

    headers = get_stealth_headers(
        accept_type="application/json, text/plain, */*",
        referer="https://www.amazon.jobs/en/search",
    )
    with httpx.Client(
        headers=headers,
        timeout=httpx.Timeout(12.0, connect=6.0),
        follow_redirects=True,
    ) as temp_client:
        resp = temp_client.get(AMAZON_JOBS_API, params=params)
        resp.raise_for_status()
        return resp.json()


# ─── Parsers ──────────────────────────────────────────────────────────────────

def _parse_date(raw: str) -> Optional[date]:
    """
    Parse Amazon's posted-date string (such as ``"November  6, 2026"`` or
    ``"2026-11-06"``) after normalizing extra whitespace.

    Args:
        raw (str): Raw ``posted_date`` string returned by the Amazon API.

    Returns:
        Optional[date]: Parsed calendar ``date`` object, or ``None`` if parsing fails.
    """
    cleaned = re.sub(r"\s+", " ", (raw or "").strip())
    for fmt in ("%B %d, %Y", "%Y-%m-%d", "%b %d, %Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _build_job(
    hit: dict,
    cutoff_date: Optional[date],
    target_location: str = "India",
) -> Optional[JobPosting]:
    """
    Validate and transform one raw Amazon JSON job hit into a normalized
    ``JobPosting``, enforcing recency cutoff, strict India location verification,
    Gen-AI relevance, experience extraction, and skill tagging.

    Args:
        hit (dict): Single job object from Amazon's JSON ``jobs`` array.
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        target_location (str): Requested target location string (default: ``"India"``).

    Returns:
        Optional[JobPosting]: Normalized ``JobPosting`` instance if valid and matching
            all filters, or ``None`` if discarded.
    """
    title = (hit.get("title") or "").strip()
    basic_quals = (hit.get("basic_qualifications") or "").strip()
    pref_quals = (hit.get("preferred_qualifications") or "").strip()
    desc_long = (hit.get("description") or "").strip()
    desc_short = (hit.get("description_short") or "").strip()
    full_text = f"{basic_quals} {pref_quals} {desc_long} {desc_short}"
    description = desc_short or desc_long or basic_quals
    location = (hit.get("normalized_location") or hit.get("city") or "").strip()
    job_path = (hit.get("job_path") or "").strip()
    url = (_build_url(job_path)) if job_path else ""
    posted_raw = (hit.get("posted_date") or "").strip()

    if not url or not title:
        return None

    date_posted = _parse_date(posted_raw)
    if cutoff_date and date_posted and date_posted < cutoff_date:
        return None  # too old

    # Strict India location verification
    if target_location and target_location.strip().lower() in ("india", "ind"):
        if not is_india_location(location, full_text):
            return None
        normalized_loc = extract_india_location(f"{location} {full_text}")
        if normalized_loc:
            location = normalized_loc

    if not matches_genai(title, full_text):
        return None

    exp_min, exp_max = parse_experience(full_text, title=title)
    skills = detect_skills(title, full_text)

    return JobPosting(
        company="Amazon",
        title=title,
        location=location,
        date_posted=date_posted,
        url=url,
        source="amazon-api",
        description_snippet=truncate(description),
        exp_min=exp_min,
        exp_max=exp_max,
        skills=skills,
    )


def _build_url(job_path: str) -> str:
    """
    Construct a full Amazon Careers URL from a relative or absolute ``job_path``.

    Args:
        job_path (str): Relative path (e.g. ``"/en/jobs/123"``) or full HTTP URL.

    Returns:
        str: Absolute URL pointing to the Amazon Jobs posting.
    """
    if job_path.startswith("http"):
        return job_path
    return _AMAZON_BASE_URL + (job_path if job_path.startswith("/") else f"/{job_path}")


def _location_matches(target_loc: str, hit: dict) -> bool:
    """
    Perform a fast location pre-check on raw Amazon hit metadata fields
    (``normalized_location``, ``city``, ``country_code``, ``state``) against
    the requested target location.

    Args:
        target_loc (str): User-requested location filter (e.g. ``"India"``, ``"USA"``, ``"Global"``).
        hit (dict): Raw job dictionary returned by Amazon's search endpoint.

    Returns:
        bool: True when the hit's location metadata matches ``target_loc`` or
            when location filtering is global/empty, else False.
    """
    if not target_loc or target_loc.strip().lower() in ("global", "any", "all", ""):
        return True

    loc_lower = target_loc.strip().lower()
    hit_text = " ".join([
        hit.get("normalized_location") or "",
        hit.get("city") or "",
        hit.get("country_code") or "",
        hit.get("state") or "",
    ]).lower()

    if loc_lower in ("india", "ind"):
        return "ind" in hit_text or "india" in hit_text or hit.get("country_code") == "IND"
    if loc_lower in ("usa", "us", "united states"):
        return "usa" in hit_text or "united states" in hit_text or hit.get("country_code") == "USA"
    if loc_lower in ("uk", "united kingdom", "gbr"):
        return "gbr" in hit_text or "united kingdom" in hit_text or "london" in hit_text

    return loc_lower in hit_text


# ─── Public API ──────────────────────────────────────────────────────────────

def fetch_amazon_jobs(
    location: str = "India",
    days: int = DEFAULT_DAYS,
    max_results: int = DEFAULT_MAX_RESULTS,
    progress_callback=None,
) -> list[JobPosting]:
    """
    Fetch and deduplicate Gen-AI job postings directly from Amazon's public
    ``search.json`` API by paginating across all configured search terms with
    recency cutoff and pagination guards.

    Args:
        location (str): Target search location (default: ``"India"``).
        days (int): Lookback window in days; 0 disables date cutoff.
        max_results (int): Maximum jobs to return; <= 0 disables result capping.
        progress_callback (Optional[Callable[[str, str], None]]): Optional callback
            invoked as ``progress_callback("Amazon", term)`` per search term.

    Returns:
        list[JobPosting]: Deduplicated list of matching Amazon ``JobPosting`` records.
    """
    cutoff_date = (
        datetime.now().date() - timedelta(days=days)
        if days else None
    )

    seen_keys: set[str] = set()
    all_jobs: list[JobPosting] = []

    country_code = ""
    loc_lower = (location or "").strip().lower()
    if loc_lower in ("india", "ind"):
        country_code = "IND"
    elif loc_lower in ("usa", "us", "united states"):
        country_code = "USA"
    elif loc_lower in ("uk", "united kingdom", "gbr"):
        country_code = "GBR"

    unlimited = not max_results or max_results <= 0

    headers = get_stealth_headers(
        accept_type="application/json, text/plain, */*",
        referer="https://www.amazon.jobs/en/search",
    )

    with httpx.Client(
        headers=headers,
        timeout=httpx.Timeout(12.0, connect=6.0),
        follow_redirects=True,
    ) as client:
        for term in get_amazon_search_terms():
            if not unlimited and len(all_jobs) >= max_results:
                break

            if progress_callback:
                progress_callback("Amazon", term)

            offset = 0
            page_size = _AMAZON_PAGE_SIZE if unlimited else min(_AMAZON_PAGE_SIZE, max_results)
            term_seen_paths: set[str] = set()

            while offset < _MAX_OFFSET_PER_TERM:
                if not unlimited and len(all_jobs) >= max_results:
                    break

                params: dict = {
                    "query": term,
                    "radius": "24km",
                    "facets[]": [],
                    "offset": offset,
                    "result_limit": page_size,
                    "sort": "recent",
                    "latitude": "",
                    "longitude": "",
                    "loc_group_id": "",
                    "loc_query": location if location else "",
                    "base_query": term,
                    "city": "",
                    "country": country_code,
                    "region": "",
                    "county": "",
                    "query_options": "",
                }
                try:
                    data = _get_amazon_page(params, client=client)
                except Exception as exc:
                    logger.debug("Amazon API error for term=%r offset=%d: %s", term, offset, exc)
                    break

                if not data or not isinstance(data, dict):
                    logger.debug("Amazon API returned empty/invalid response for term=%r offset=%d", term, offset)
                    break

                hits: list[dict] = data.get("jobs", [])
                if not hits:
                    break  # no more results for this term

                # Prevent infinite pagination if Amazon returns duplicate pages
                new_paths_on_page = 0
                recent_hits_on_page = 0
                for hit in hits:
                    jp = (hit.get("job_path") or hit.get("id_icims") or hit.get("title") or "").strip()
                    if jp and jp not in term_seen_paths:
                        term_seen_paths.add(jp)
                        new_paths_on_page += 1

                    # Track whether any hit on this page is within cutoff_date
                    posted_dt = _parse_date(hit.get("posted_date") or "")
                    if not cutoff_date or not posted_dt or posted_dt >= cutoff_date:
                        recent_hits_on_page += 1

                    if not _location_matches(location, hit):
                        continue
                    job = _build_job(hit, cutoff_date, target_location=location)
                    if job and job.dedup_key not in seen_keys:
                        seen_keys.add(job.dedup_key)
                        all_jobs.append(job)
                        if not unlimited and len(all_jobs) >= max_results:
                            break

                total_hits = data.get("hits") or 0
                if new_paths_on_page == 0 or len(hits) < page_size:
                    break  # last page or repeating page
                if total_hits and (offset + len(hits)) >= total_hits:
                    break  # fetched all hits
                if cutoff_date and recent_hits_on_page == 0:
                    break  # entire page is older than cutoff window

                offset += page_size
                apply_jitter_delay(base_seconds=0.25)

    return all_jobs
