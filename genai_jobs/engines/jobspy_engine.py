"""
genai_jobs/engines/jobspy_engine.py
─────────────────────────────────────────────────────────────────────────────
Primary Aggregator Engine — wraps python-jobspy (`scrape_jobs`) to query
Indeed, Naukri, LinkedIn (and any other configured sites in settings.json).

Two-Phase High-Speed Architecture
─────────────────────────────────
1. Consolidated Boolean OR Search:
   Collapses configured search terms into a single focused boolean OR query per
   company (eliminating 11× sequential scrapes per company).
2. Split Board Pacing & Bounded Pagination:
   * Fast boards (Indeed / Naukri) run concurrently (`max_workers=2`,
     `results_wanted=25`, `fetch_description=False` — Indeed already returns full
     descriptions in its GraphQL search payload in ~0.4s/company).
   * LinkedIn runs cleanly with bounded single-page `results_wanted=10` and
     `max_workers=2` (`linkedin_fetch_description=False`) to prevent 429 stalls.
3. Targeted Phase-2 Hydration:
   Discards non-target companies, old jobs, non-India locations, and senior
   titles (`≥ 4` yrs) FIRST, then hydrates descriptions ONLY for surviving
   candidate LinkedIn postings via LinkedIn's lightweight guest jobPosting
   endpoint (`jobs-guest/jobs/api/jobPosting/{id}`). Also parses Naukri
   `experience_range` / URL year slugs directly without extra HTTP fetches.
"""
from __future__ import annotations

import html
import logging
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from typing import Optional

import httpx
import pandas as pd
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
)

from genai_jobs.constants import (
    DEFAULT_DAYS,
    DEFAULT_MAX_RESULTS,
    SEARCH_TERMS,
)
from genai_jobs.models import JobPosting
from genai_jobs.utils.filters import (
    detect_skills,
    extract_india_location,
    infer_seniority_from_title,
    is_india_location,
    matches_genai,
    parse_experience,
    resolve_company,
    truncate,
)
from genai_jobs.utils.security import apply_jitter_delay, get_random_user_agent, get_stealth_headers

logger = logging.getLogger(__name__)

_HYDRATE_TIMEOUT = httpx.Timeout(5.0, connect=3.0)
_NAUKRI_URL_EXP_RE = re.compile(r"(\d+)-to-(\d+)-years?", re.I)
_NAUKRI_RANGE_RE = re.compile(r"(\d+)\s*[-–to]+\s*(\d+)", re.I)


# ─── Query consolidation ─────────────────────────────────────────────────────

def _build_consolidated_queries(terms: list[str], chunk_size: int = 12) -> list[str]:
    """
    Merge search terms into compact boolean OR query groups so each company
    requires 1 query instead of 11 sequential calls.
    Also extracts high-signal single keywords when pairs look overly rigid.
    """
    cleaned: list[str] = []
    seen_lower: set[str] = set()
    for t in terms:
        item = t.strip()
        if not item:
            continue
        low = item.lower()
        if low not in seen_lower:
            seen_lower.add(low)
            cleaned.append(item)

    if not cleaned:
        cleaned = ["Generative AI", "Agentic AI", "Artificial Intelligence", "LLM", "RAG"]

    groups: list[str] = []
    for i in range(0, len(cleaned), chunk_size):
        chunk = cleaned[i : i + chunk_size]
        inner = " OR ".join(f'"{t}"' for t in chunk)
        groups.append(f"({inner})")
    return groups


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _safe_str(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val).strip()


def _safe_date(val) -> Optional[date]:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (date, datetime)):
        return val.date() if isinstance(val, datetime) else val
    try:
        return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _strip_html(raw: str) -> str:
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", text).strip()


def _extract_naukri_exp(row: pd.Series, url: str) -> tuple[int, int]:
    """Extract (exp_min, exp_max) from Naukri experience_range column or job URL slug."""
    exp_range = _safe_str(row.get("experience_range", ""))
    if exp_range:
        m = _NAUKRI_RANGE_RE.search(exp_range)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            return (min(lo, hi), max(lo, hi))
    m_url = _NAUKRI_URL_EXP_RE.search(url)
    if m_url:
        lo, hi = int(m_url.group(1)), int(m_url.group(2))
        return (min(lo, hi), max(lo, hi))
    return (-1, -1)


def _extract_linkedin_job_id(url: str) -> Optional[str]:
    m = re.search(r"/jobs/view/(?:[^/?]*-)?(\d{6,})", url)
    return m.group(1) if m else None


def _fetch_linkedin_guest_description(
    url: str,
    client: httpx.Client,
    rate_limit_state: dict,
) -> str:
    """
    Fetch full description text for a single surviving LinkedIn candidate URL
    using LinkedIn's public guest jobPosting endpoint. Stops immediately on 429.
    """
    if rate_limit_state.get("blocked"):
        return ""
    job_id = _extract_linkedin_job_id(url)
    if not job_id:
        return ""
    guest_url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        resp = client.get(guest_url)
        if resp.status_code == 429:
            with rate_limit_state["lock"]:
                rate_limit_state["429_count"] += 1
                if rate_limit_state["429_count"] >= 3:
                    rate_limit_state["blocked"] = True
            return ""
        if resp.status_code != 200:
            return ""
        # Extract job description markup block
        m = re.search(
            r'class="show-more-less-html__markup[^"]*"[^>]*>(.*?)</div>',
            resp.text,
            re.S | re.I,
        )
        return _strip_html(m.group(1) if m else resp.text[:15000])
    except Exception as exc:
        logger.debug("LinkedIn guest hydration failed for %s: %s", job_id, exc)
        return ""


def _build_job_from_candidate(
    cand: dict,
    target_location: str = "India",
) -> Optional[JobPosting]:
    """Finalize GenAI, experience, and skills checks on a hydrated candidate."""
    title = cand["title"]
    description = cand["description"]
    location = cand["location"]
    source_site = cand["source_site"]
    row = cand["row"]
    url = cand["url"]

    extra_skills = _safe_str(row.get("skills", ""))
    combined_text = f"{description} {extra_skills}".strip()

    # Re-verify India location with hydrated description if original location was generic
    if target_location and target_location.strip().lower() in ("india", "ind"):
        if not is_india_location(location, f"{title} {combined_text}"):
            return None
        normalized_loc = extract_india_location(f"{location} {title} {combined_text}")
        if normalized_loc:
            location = normalized_loc

    if not matches_genai(title, combined_text):
        return None

    exp_min, exp_max = parse_experience(f"{title} {combined_text}", title=title)
    if exp_min == -1 and exp_max == -1 and source_site == "naukri":
        n_lo, n_hi = _extract_naukri_exp(row, url)
        if n_lo != -1 or n_hi != -1:
            exp_min, exp_max = n_lo, n_hi

    skills = detect_skills(title, combined_text)

    return JobPosting(
        company=cand["company"],
        title=title,
        location=location,
        date_posted=cand["date_posted"],
        url=url,
        source=f"jobspy/{source_site}",
        description_snippet=truncate(combined_text or title),
        exp_min=exp_min,
        exp_max=exp_max,
        skills=skills,
    )


# ─── Single-query scraper (with fast retry) ──────────────────────────────────

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=2.0),
    before_sleep=before_sleep_log(logger, logging.DEBUG),
    reraise=False,
)
def _scrape_once(
    company: str,
    search_term: str,
    location: str,
    days: int,
    max_results: int,
    sites: list[str],
    proxies: Optional[list[str]] = None,
) -> list[dict]:
    """
    Phase-1 scrape via jobspy.scrape_jobs returning pre-filtered candidate dicts
    (company match + date cutoff + India location + non-senior title < 4 yrs).
    """
    try:
        from jobspy import scrape_jobs  # lazy import — avoids slow startup
    except ImportError:
        logger.error("python-jobspy is not installed. Run: pip install python-jobspy")
        return []

    query = f'"{company}" {search_term}'
    try:
        scrape_kwargs = {
            "site_name": sites,
            "search_term": query,
            "location": location,
            "results_wanted": max_results,
            "hours_old": days * 24,
            "country_indeed": "India" if "india" in location.lower() else "USA",
            "linkedin_fetch_description": False,
            "fetch_description": False,
            "user_agent": get_random_user_agent(),
            "verbose": None,
        }
        if proxies:
            scrape_kwargs["proxies"] = proxies

        df: pd.DataFrame = scrape_jobs(**scrape_kwargs)
    except Exception as exc:
        logger.debug(
            "jobspy scrape failed for company=%r sites=%r: %s", company, sites, exc
        )
        raise  # let tenacity retry once

    if df is None or df.empty:
        return []

    cutoff_date = (
        datetime.now().date() - timedelta(days=days)
        if days else None
    )
    is_india_target = (location or "").strip().lower() in ("india", "ind")

    candidates: list[dict] = []
    for _, row in df.iterrows():
        raw_co = _safe_str(row.get("company", ""))
        canonical = resolve_company(raw_co)
        if canonical is None or canonical != company:
            continue

        url = _safe_str(row.get("job_url", "")) or _safe_str(row.get("job_url_direct", ""))
        if not url:
            continue

        title = _safe_str(row.get("title", ""))
        if not title:
            continue

        # Fast seniority reject BEFORE hydration
        t_lo, _ = infer_seniority_from_title(title)
        if t_lo >= 4:
            continue

        date_posted = _safe_date(row.get("date_posted"))
        if cutoff_date and date_posted and date_posted < cutoff_date:
            continue

        loc_str = _safe_str(row.get("location", ""))
        desc = _safe_str(row.get("description", ""))
        if is_india_target and not is_india_location(loc_str, f"{title} {desc}"):
            continue

        site_name = _safe_str(row.get("site", "")) or _safe_str(row.get("source", "")) or "unknown"
        candidates.append(
            {
                "company": company,
                "title": title,
                "location": loc_str,
                "date_posted": date_posted,
                "url": url,
                "source_site": site_name,
                "description": desc,
                "row": row,
            }
        )

    return candidates


def _fetch_company_for_sites(
    company: str,
    query_groups: list[str],
    location: str,
    days: int,
    max_results: int,
    sites: list[str],
    proxies: Optional[list[str]],
    inter_delay: float,
    progress_callback=None,
) -> list[dict]:
    """Run consolidated queries for one company on a subset of boards."""
    all_cands: list[dict] = []
    for term in query_groups:
        if progress_callback:
            progress_callback(company, f"{','.join(sites)} · {term[:25]}")
        try:
            cands = _scrape_once(
                company=company,
                search_term=term,
                location=location,
                days=days,
                max_results=max_results,
                sites=sites,
                proxies=proxies,
            ) or []
            all_cands.extend(cands)
        except Exception as exc:
            logger.error("jobspy permanently failed for company=%r sites=%r: %s", company, sites, exc)
        if inter_delay > 0:
            apply_jitter_delay(base_seconds=inter_delay)
    return all_cands


# ─── Public API ──────────────────────────────────────────────────────────────

def fetch_via_jobspy(
    companies: list[str],
    location: str = "India",
    days: int = DEFAULT_DAYS,
    max_results: int = DEFAULT_MAX_RESULTS,
    sites: Optional[list[str]] = None,
    progress_callback=None,
) -> list[JobPosting]:
    """
    Fetch Gen-AI job postings for target companies via fast two-phase JobSpy.
    """
    from genai_jobs.config import get_config

    cfg = get_config()
    if sites is None:
        sites = cfg.settings.jobspy_sites

    if not companies or not sites:
        return []

    inter_delay = cfg.settings.inter_request_delay
    proxies = cfg.settings.proxies or None
    unlimited = not max_results or max_results <= 0

    query_groups = _build_consolidated_queries(SEARCH_TERMS, chunk_size=12)

    fast_sites = [s for s in sites if s.lower() != "linkedin"]
    has_linkedin = any(s.lower() == "linkedin" for s in sites)

    raw_candidates: list[dict] = []

    # ── Track A & B concurrently across dedicated fast (2) & LinkedIn (2) pools ─
    track_futures = []
    with (
        ThreadPoolExecutor(max_workers=max(1, min(2, len(companies)))) as fast_pool,
        ThreadPoolExecutor(max_workers=max(1, min(2, len(companies)))) as li_pool,
    ):
        if fast_sites:
            fast_req = 25 if unlimited else min(25, max_results)
            for co in companies:
                track_futures.append(
                    fast_pool.submit(
                        _fetch_company_for_sites,
                        co,
                        query_groups,
                        location,
                        days,
                        fast_req,
                        fast_sites,
                        proxies,
                        max(0.25, inter_delay * 0.6),
                        (lambda c, d, cb=progress_callback: cb(f"{c}:fast", d)) if progress_callback else None,
                    )
                )

        if has_linkedin:
            # Cap at 10 (LinkedIn's exact page size) to keep each query to 1 HTTP request
            # without triggering jobspy's internal 3-7s inter-page sleep or 429 blocks.
            li_req = 10 if unlimited else min(10, max_results)
            for co in companies:
                track_futures.append(
                    li_pool.submit(
                        _fetch_company_for_sites,
                        co,
                        query_groups,
                        location,
                        days,
                        li_req,
                        ["linkedin"],
                        proxies,
                        max(0.3, inter_delay * 0.75),
                        (lambda c, d, cb=progress_callback: cb(f"{c}:li", d)) if progress_callback else None,
                    )
                )

        for fut in as_completed(track_futures):
            try:
                raw_candidates.extend(fut.result() or [])
            except Exception as exc:
                logger.error("jobspy track worker error: %s", exc)

    if not raw_candidates:
        return []

    # Deduplicate candidates by URL before Phase-2 hydration
    dedup_cands: list[dict] = []
    seen_urls: set[str] = set()
    for c in raw_candidates:
        u = c["url"].rstrip("/")
        if u not in seen_urls:
            seen_urls.add(u)
            dedup_cands.append(c)

    # ── Phase-2: Targeted LinkedIn description hydration for survivors only ────
    need_li_hydration = [
        c for c in dedup_cands
        if not c["description"] and c["source_site"].lower() == "linkedin"
    ]
    if need_li_hydration:
        rate_state = {"blocked": False, "429_count": 0, "lock": threading.Lock()}
        headers = get_stealth_headers("text/html,application/xhtml+xml")
        with httpx.Client(headers=headers, timeout=_HYDRATE_TIMEOUT, follow_redirects=True) as client:
            with ThreadPoolExecutor(max_workers=4) as pool:
                fut_map = {
                    pool.submit(_fetch_linkedin_guest_description, c["url"], client, rate_state): c
                    for c in need_li_hydration
                }
                for fut in as_completed(fut_map):
                    cand = fut_map[fut]
                    try:
                        text = fut.result()
                        if text:
                            cand["description"] = text
                    except Exception:
                        pass

    # ── Final filter, experience extraction & per-company cap enforcement ─────
    seen_keys: set[str] = set()
    all_jobs: list[JobPosting] = []
    company_counts: dict[str, int] = {}

    for cand in dedup_cands:
        co = cand["company"]
        if not unlimited and company_counts.get(co, 0) >= max_results:
            continue
        job = _build_job_from_candidate(cand, target_location=location)
        if job and job.dedup_key not in seen_keys:
            seen_keys.add(job.dedup_key)
            all_jobs.append(job)
            company_counts[co] = company_counts.get(co, 0) + 1

    return all_jobs
