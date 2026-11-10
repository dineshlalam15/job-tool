"""
genai_jobs/engines/ats_engine.py
─────────────────────────────────────────────────────────────────────────────
Direct Career Portal API Engine — queries official ATS JSON/GraphQL endpoints
and structured SSR career pages directly without relying solely on aggregators.

Supported Direct Career Portal Adapters (17 portals + Amazon API = 18/34)
─────────────────────────────────────────────────────────────────────────
* Google Careers       (`www.google.com/about/careers/applications/jobs/results/`)
* Workday CXS API      (`*.myworkdayjobs.com` / `myworkdaysite.com`)
                       Salesforce, Adobe, Micron, Berkadia, Disney,
                       Invesco, Quantiphi, Wells Fargo
* Oracle Cloud HCM API (`*.fa.oraclecloud.com/hcmRestApi/...`)
                       JP Morgan Chase, CHUBB, Honeywell
* Goldman Sachs API    (`api-higher.gs.com/gateway/api/v1/graphql`)
* Deloitte South Asia  (`southasiacareers.deloitte.com`)
* Synopsys Career Site (`careers.synopsys.com`)
* Phenom People SSR    (`phApp.ddo`): eBay, HPE
"""
from __future__ import annotations

import html
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote_plus

import httpx

from genai_jobs.config import get_search_terms
from genai_jobs.constants import DEFAULT_DAYS, DEFAULT_MAX_RESULTS
from genai_jobs.models import JobPosting
from genai_jobs.utils.filters import (
    detect_skills,
    extract_india_location,
    infer_seniority_from_title,
    is_india_location,
    matches_genai,
    parse_experience,
    truncate,
)
from genai_jobs.utils.security import apply_jitter_delay, get_stealth_headers

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = httpx.Timeout(9.0, connect=4.5)
_HTTP_LIMITS = httpx.Limits(max_connections=12, max_keepalive_connections=8)
_DEFAULT_ATS_SEARCH_TERMS = ["Generative AI", "Agentic AI", "LLM", "RAG"]


def _get_ats_search_terms() -> list[str]:
    """
    Retrieve search query terms for direct career-portal APIs from external
    configuration, falling back to ``["Generative AI", "Agentic AI", "LLM", "RAG"]``.

    Args:
        None.

    Returns:
        list[str]: Active search query terms.
    """
    return get_search_terms() or list(_DEFAULT_ATS_SEARCH_TERMS)


def _strip_html(raw: str) -> str:
    """
    Decode HTML entities, strip HTML tags, and collapse whitespace into a single
    plain-text string.

    Args:
        raw (str): Raw HTML or HTML-escaped string.

    Returns:
        str: Normalized plain text, or ``""`` when input is empty.
    """
    if not raw:
        return ""
    unescaped = html.unescape(raw)
    text = re.sub(r"<[^>]+>", " ", unescaped)
    return re.sub(r"\s+", " ", text).strip()


def _parse_relative_date(raw: str) -> Optional[date]:
    """
    Parse relative or calendar date strings emitted by career portals (such as
    ``"Posted Today"``, ``"Posted 3 Days Ago"``, ISO timestamps, or ``"Nov 3, 2026"``).

    Args:
        raw (str): Raw date text from a career portal response.

    Returns:
        Optional[date]: Parsed calendar ``date`` object, or ``None`` if unrecognized.
    """
    if not raw:
        return None
    cleaned = re.sub(r"\s+", " ", raw.strip())
    s = cleaned.lower()
    today = datetime.now().date()
    if "today" in s:
        return today
    if "yesterday" in s:
        return today - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*day", s)
    if m:
        return today - timedelta(days=int(m.group(1)))
    m_iso = re.match(r"(\d{4}-\d{2}-\d{2})", cleaned)
    if m_iso:
        try:
            return datetime.strptime(m_iso.group(1), "%Y-%m-%d").date()
        except ValueError:
            pass
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _is_senior_title(title: str) -> bool:
    """
    Quickly detect whether a job title explicitly indicates >= 4 years seniority
    (e.g., Senior, Lead, Manager, Principal, Director) via ``infer_seniority_from_title()``.

    Args:
        title (str): Raw job posting title.

    Returns:
        bool: True when inferred minimum experience floor is >= 4 years, else False.
    """
    if not title:
        return False
    t_lo, _ = infer_seniority_from_title(title)
    return t_lo >= 4


# ─── Google Careers Direct Fetcher ────────────────────────────────────────────

def _fetch_google_careers(
    location: str,
    cutoff_date: Optional[date],
    max_results: int,
) -> list[JobPosting]:
    """
    Fetch active Gen-AI job postings directly from Google Careers HTML search
    pages by extracting embedded ``AF_initDataCallback`` JSON payloads and
    filtering by seniority, location, date cutoff, and Gen-AI relevance.

    Args:
        location (str): Target search location string (default normalized to ``"India"``).
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        max_results (int): Maximum jobs to return (<= 0 means unlimited).

    Returns:
        list[JobPosting]: Matching Google ``JobPosting`` records.
    """
    queries = _get_ats_search_terms()
    loc_param = "India" if (not location or "india" in location.lower()) else location
    headers = get_stealth_headers("text/html,application/xhtml+xml")

    seen_ids: set[str] = set()
    jobs: list[JobPosting] = []
    unlimited = not max_results or max_results <= 0

    with httpx.Client(headers=headers, timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        for q in queries:
            if not unlimited and len(jobs) >= max_results:
                break
            url = (
                "https://www.google.com/about/careers/applications/jobs/results/"
                f"?q={quote_plus(q)}&location={quote_plus(loc_param)}&sort_by=date"
            )
            try:
                resp = client.get(url)
                if resp.status_code != 200:
                    logger.debug("Google Careers HTTP %d for query=%r", resp.status_code, q)
                    continue
            except Exception as exc:
                logger.debug("Google Careers request failed for query=%r: %s", q, exc)
                continue

            blocks = re.findall(
                r"AF_initDataCallback\(\{key:\s*'ds:1'[^}]*?data:(.*?), sideChannel:",
                resp.text,
                re.S,
            )
            if not blocks:
                continue

            try:
                payload = json.loads(blocks[0])
                raw_items = payload[0] if isinstance(payload, list) and payload else []
            except Exception as exc:
                logger.debug("Google Careers JSON parse error: %s", exc)
                continue

            for item in raw_items:
                if not isinstance(item, list) or len(item) < 10:
                    continue
                job_id = str(item[0] or "").strip()
                if not job_id or job_id in seen_ids:
                    continue
                seen_ids.add(job_id)

                title = str(item[1] or "").strip()
                if not title or _is_senior_title(title):
                    continue

                raw_locs = item[9] if isinstance(item[9], list) else []
                loc_names = [
                    str(loc_entry[0]).strip()
                    for loc_entry in raw_locs
                    if isinstance(loc_entry, list) and loc_entry and loc_entry[0]
                ]
                loc_str = "; ".join(loc_names[:3])

                if location and location.strip().lower() in ("india", "ind"):
                    if not is_india_location(loc_str, title):
                        continue
                    extracted = extract_india_location(loc_str)
                    if extracted:
                        loc_str = extracted

                date_posted: Optional[date] = None
                for ts_idx in (12, 13, 14):
                    if len(item) > ts_idx and isinstance(item[ts_idx], list) and item[ts_idx]:
                        ts_val = item[ts_idx][0]
                        if isinstance(ts_val, (int, float)) and ts_val > 1_000_000_000:
                            date_posted = datetime.fromtimestamp(ts_val, tz=timezone.utc).date()
                            break

                if cutoff_date and date_posted and date_posted < cutoff_date:
                    continue

                resp_html = item[3][1] if len(item) > 3 and isinstance(item[3], list) and len(item[3]) > 1 else ""
                qual_html = item[4][1] if len(item) > 4 and isinstance(item[4], list) and len(item[4]) > 1 else ""
                desc_html = item[10][1] if len(item) > 10 and isinstance(item[10], list) and len(item[10]) > 1 else ""
                pref_html = item[19][1] if len(item) > 19 and isinstance(item[19], list) and len(item[19]) > 1 else ""
                full_text = _strip_html(f"{qual_html} {pref_html} {resp_html} {desc_html}")

                if not matches_genai(title, full_text):
                    continue

                exp_min, exp_max = parse_experience(full_text, title=title)
                skills = detect_skills(title, full_text)
                job_url = f"https://www.google.com/about/careers/applications/jobs/results/{job_id}"

                jobs.append(
                    JobPosting(
                        company="Google",
                        title=title,
                        location=loc_str or "India",
                        date_posted=date_posted,
                        url=job_url,
                        source="ats/google",
                        description_snippet=truncate(full_text),
                        exp_min=exp_min,
                        exp_max=exp_max,
                        skills=skills,
                    )
                )
                if not unlimited and len(jobs) >= max_results:
                    break

    return jobs


# ─── Workday CXS JSON API Fetcher ─────────────────────────────────────────────

_WORKDAY_PORTALS: dict[str, dict[str, str]] = {
    "Salesforce": {
        "host": "salesforce.wd12.myworkdayjobs.com",
        "tenant": "salesforce",
        "site": "External_Career_Site",
    },
    "Adobe": {
        "host": "adobe.wd5.myworkdayjobs.com",
        "tenant": "adobe",
        "site": "external_experienced",
    },
    "Micron": {
        "host": "micron.wd1.myworkdayjobs.com",
        "tenant": "micron",
        "site": "External",
    },
    "Berkadia": {
        "host": "berkadia.wd1.myworkdayjobs.com",
        "tenant": "berkadia",
        "site": "Berkadia",
    },
    "Disney": {
        "host": "disney.wd5.myworkdayjobs.com",
        "tenant": "disney",
        "site": "disneycareer",
    },
    "Invesco": {
        "host": "invesco.wd1.myworkdayjobs.com",
        "tenant": "invesco",
        "site": "IVZ",
    },
    "Quantiphi": {
        "host": "quantiphi.wd1.myworkdayjobs.com",
        "tenant": "quantiphi",
        "site": "Careers_at_Quantiphi",
    },
    "Wells Fargo": {
        "host": "wd1.myworkdaysite.com",
        "tenant": "wf",
        "site": "WellsFargoJobs",
        "url_prefix": "/recruiting/wf/WellsFargoJobs",
    },
}


def _fetch_workday_company(
    company: str,
    cfg: dict[str, str],
    location: str,
    cutoff_date: Optional[date],
    max_results: int,
) -> list[JobPosting]:
    """
    Query a company's Workday CXS JSON endpoint across configured search terms,
    pre-filter candidates by date, India location, and title seniority, then
    concurrently fetch full descriptions to verify Gen-AI match and experience.

    Args:
        company (str): Canonical company name.
        cfg (dict[str, str]): Workday configuration containing ``host``, ``tenant``,
            ``site``, and optional ``url_prefix``.
        location (str): Target location filter string.
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        max_results (int): Maximum jobs to return (<= 0 means unlimited).

    Returns:
        list[JobPosting]: Matching ``JobPosting`` records from the company's Workday portal.
    """
    host = cfg["host"]
    tenant = cfg["tenant"]
    site = cfg["site"]
    url_prefix = cfg.get("url_prefix") or f"/en-US/{site}"
    list_url = f"https://{host}/wday/cxs/{tenant}/{site}/jobs"

    headers = get_stealth_headers(
        accept_type="application/json",
        referer=f"https://{host}/{site}",
    )
    headers["Content-Type"] = "application/json"

    is_india_target = not location or location.strip().lower() in ("india", "ind")
    loc_suffix = " India" if is_india_target else f" {location}"
    search_terms = [f"{term}{loc_suffix}" for term in _get_ats_search_terms()]

    seen_paths: set[str] = set()
    candidates: list[dict] = []
    jobs: list[JobPosting] = []
    unlimited = not max_results or max_results <= 0

    with httpx.Client(
        headers=headers,
        timeout=_HTTP_TIMEOUT,
        limits=_HTTP_LIMITS,
        follow_redirects=True,
    ) as client:
        for term in search_terms:
            # Paginate up to 2 pages (40 hits) per search term when total > 20
            for offset in (0, 20):
                try:
                    resp = client.post(
                        list_url,
                        json={
                            "appliedFacets": {},
                            "limit": 20,
                            "offset": offset,
                            "searchText": term,
                        },
                    )
                    if resp.status_code != 200:
                        logger.debug("Workday %s HTTP %d for %r", company, resp.status_code, term)
                        break
                    data = resp.json()
                except Exception as exc:
                    logger.debug("Workday %s list failed for %r: %s", company, term, exc)
                    break

                postings = data.get("jobPostings", [])
                if not postings:
                    break

                recent_hits = 0
                for item in postings:
                    ext_path = (item.get("externalPath") or "").strip()
                    title = (item.get("title") or "").strip()
                    if not ext_path or not title or ext_path in seen_paths:
                        continue
                    seen_paths.add(ext_path)

                    posted_on = _parse_relative_date(item.get("postedOn") or "")
                    if cutoff_date and posted_on and posted_on < cutoff_date:
                        continue
                    recent_hits += 1

                    raw_loc = (item.get("locationsText") or "").strip()
                    combined_loc_ctx = f"{raw_loc} {ext_path.replace('-', ' ').replace('/', ' ')}"
                    if is_india_target and not is_india_location(raw_loc, combined_loc_ctx):
                        continue

                    if _is_senior_title(title):
                        continue

                    candidates.append(
                        {
                            "title": title,
                            "ext_path": ext_path,
                            "raw_loc": raw_loc,
                            "posted_on": posted_on,
                        }
                    )

                total = data.get("total") or 0
                if (offset + len(postings)) >= total or recent_hits == 0:
                    break

        if not candidates:
            return []

        def _hydrate(cand: dict) -> Optional[JobPosting]:
            """
            Fetch detailed job description and location for one Workday candidate
            posting and construct a filtered ``JobPosting`` if valid.

            Args:
                cand (dict): Pre-filtered candidate metadata with ``title``,
                    ``ext_path``, ``raw_loc``, and ``posted_on``.

            Returns:
                Optional[JobPosting]: Hydrated ``JobPosting`` or ``None`` if filtered out.
            """
            detail_url = f"https://{host}/wday/cxs/{tenant}/{site}{cand['ext_path']}"
            full_text = ""
            final_loc = cand["raw_loc"]
            try:
                dr = client.get(detail_url)
                if dr.status_code == 200:
                    info = dr.json().get("jobPostingInfo", {})
                    full_text = _strip_html(info.get("jobDescription") or "")
                    detail_loc = (info.get("location") or "").strip()
                    if detail_loc:
                        final_loc = detail_loc
            except Exception as exc:
                logger.debug("Workday detail fetch failed for %s: %s", detail_url, exc)

            if is_india_target:
                combined_ctx = f"{final_loc} {cand['ext_path'].replace('-', ' ')}"
                if not is_india_location(final_loc, combined_ctx):
                    return None
                extracted = extract_india_location(combined_ctx)
                if extracted:
                    final_loc = extracted

            if not matches_genai(cand["title"], full_text):
                return None

            exp_min, exp_max = parse_experience(full_text or cand["title"], title=cand["title"])
            skills = detect_skills(cand["title"], full_text)
            apply_url = f"https://{host}{url_prefix}{cand['ext_path']}"

            return JobPosting(
                company=company,
                title=cand["title"],
                location=final_loc or "India",
                date_posted=cand["posted_on"],
                url=apply_url,
                source="ats/workday",
                description_snippet=truncate(full_text or cand["title"]),
                exp_min=exp_min,
                exp_max=exp_max,
                skills=skills,
            )

        with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as pool:
            for job in pool.map(_hydrate, candidates):
                if job:
                    jobs.append(job)
                    if not unlimited and len(jobs) >= max_results:
                        break

    return jobs


# ─── Oracle Cloud HCM JSON API (JPMC, CHUBB, Honeywell) ───────────────────────

_ORACLE_PORTALS: dict[str, dict[str, str]] = {
    "JP Morgan Chase": {
        "host": "jpmc.fa.oraclecloud.com",
        "site": "CX_1001",
    },
    "CHUBB": {
        "host": "fa-ewgu-saasfaprod1.fa.ocs.oraclecloud.com",
        "site": "CX_2001",
    },
    "Honeywell": {
        "host": "ibqbjb.fa.ocs.oraclecloud.com",
        "site": "CX_1001",
    },
}


def _fetch_oracle_company(
    company: str,
    cfg: dict[str, str],
    location: str,
    cutoff_date: Optional[date],
    max_results: int,
) -> list[JobPosting]:
    """
    Fetch Gen-AI job requisitions from an Oracle Cloud HCM Recruiting API
    using configured search keywords, pre-filter candidate metadata, and
    concurrently hydrate requisition details.

    Args:
        company (str): Canonical company name.
        cfg (dict[str, str]): Oracle portal configuration with ``host`` and ``site``.
        location (str): Target search location string.
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        max_results (int): Maximum jobs to return (<= 0 means unlimited).

    Returns:
        list[JobPosting]: Matching ``JobPosting`` objects from the Oracle HCM portal.
    """
    host = cfg["host"]
    site = cfg["site"]
    base_api = f"https://{host}/hcmRestApi/resources/latest"
    headers = get_stealth_headers("application/json")
    is_india_target = not location or location.strip().lower() in ("india", "ind")

    seen_ids: set[str] = set()
    candidates: list[dict] = []
    jobs: list[JobPosting] = []
    unlimited = not max_results or max_results <= 0

    keywords = _get_ats_search_terms()
    with httpx.Client(
        headers=headers,
        timeout=_HTTP_TIMEOUT,
        limits=_HTTP_LIMITS,
        follow_redirects=True,
    ) as client:
        for kw in keywords:
            list_url = (
                f"{base_api}/recruitingCEJobRequisitions"
                f"?onlyData=true&expand=requisitionList.secondaryLocations"
                f"&finder=findReqs;siteNumber={site},keyword={quote_plus(kw)},limit=25"
            )
            try:
                r = client.get(list_url)
                if r.status_code != 200:
                    continue
                items = r.json().get("items", [])
                reqs = items[0].get("requisitionList", []) if items else []
            except Exception as exc:
                logger.debug("Oracle %s list failed for %r: %s", company, kw, exc)
                continue

            for req in reqs:
                req_id = str(req.get("Id") or "").strip()
                title = (req.get("Title") or "").strip()
                if not req_id or not title or req_id in seen_ids:
                    continue
                seen_ids.add(req_id)

                primary_loc = (req.get("PrimaryLocation") or "").strip()
                if is_india_target and not is_india_location(primary_loc, title):
                    continue

                posted_on = _parse_relative_date(req.get("PostedDate") or "")
                if cutoff_date and posted_on and posted_on < cutoff_date:
                    continue

                if _is_senior_title(title):
                    continue

                candidates.append(
                    {
                        "id": req_id,
                        "title": title,
                        "location": extract_india_location(primary_loc) or primary_loc or "India",
                        "posted_on": posted_on,
                        "short_desc": req.get("ShortDescriptionStr") or "",
                    }
                )

        if not candidates:
            return []

        def _hydrate(cand: dict) -> Optional[JobPosting]:
            """
            Retrieve full qualifications and responsibilities for a single Oracle
            HCM job requisition and convert it into a filtered ``JobPosting``.

            Args:
                cand (dict): Pre-filtered requisition dict containing ``id``,
                    ``title``, ``location``, ``posted_on``, and ``short_desc``.

            Returns:
                Optional[JobPosting]: Normalized ``JobPosting`` if matched, else ``None``.
            """
            detail_url = (
                f"{base_api}/recruitingCEJobRequisitionDetails"
                f"?onlyData=true&finder=ById;Id=%22{cand['id']}%22,siteNumber={site}"
            )
            full_text = cand["short_desc"]
            try:
                dr = client.get(detail_url)
                if dr.status_code == 200:
                    d_items = dr.json().get("items", [])
                    if d_items:
                        d0 = d_items[0]
                        raw_html = " ".join(
                            str(d0.get(k) or "")
                            for k in (
                                "ExternalQualificationsStr",
                                "ExternalResponsibilitiesStr",
                                "ExternalDescriptionStr",
                                "ShortDescriptionStr",
                            )
                        )
                        stripped = _strip_html(raw_html)
                        if stripped:
                            full_text = stripped
            except Exception as exc:
                logger.debug("Oracle %s detail failed for %s: %s", company, cand["id"], exc)

            if not matches_genai(cand["title"], full_text):
                return None

            exp_min, exp_max = parse_experience(full_text or cand["title"], title=cand["title"])
            skills = detect_skills(cand["title"], full_text)
            apply_url = f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{cand['id']}"
            return JobPosting(
                company=company,
                title=cand["title"],
                location=cand["location"],
                date_posted=cand["posted_on"],
                url=apply_url,
                source="ats/oracle",
                description_snippet=truncate(full_text or cand["title"]),
                exp_min=exp_min,
                exp_max=exp_max,
                skills=skills,
            )

        with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as pool:
            for job in pool.map(_hydrate, candidates):
                if job:
                    jobs.append(job)
                    if not unlimited and len(jobs) >= max_results:
                        break

    return jobs


# ─── Goldman Sachs GraphQL API ───────────────────────────────────────────────

def _fetch_goldman_sachs(
    location: str,
    cutoff_date: Optional[date],
    max_results: int,
) -> list[JobPosting]:
    """
    Query Goldman Sachs' Higher GraphQL API (``GetRoles``) for early-career
    and professional openings matching ``location``, then filter results by
    seniority, recency cutoff, India verification, and Gen-AI keywords.

    Args:
        location (str): Target search location string.
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        max_results (int): Maximum jobs to return (<= 0 means unlimited).

    Returns:
        list[JobPosting]: Matching Goldman Sachs ``JobPosting`` objects.
    """
    api_url = "https://api-higher.gs.com/gateway/api/v1/graphql"
    headers = get_stealth_headers("application/json", referer="https://higher.gs.com/")
    headers["Content-Type"] = "application/json"

    is_india_target = not location or location.strip().lower() in ("india", "ind")
    search_term = "India" if is_india_target else location

    query_gql = """
    query GetRoles($searchQueryInput: RoleSearchQueryInput!) {
      roleSearch(searchQueryInput: $searchQueryInput) {
        totalCount
        items {
          roleId
          corporateTitle
          jobTitle
          division
          jobFunction
          lastPostedDate
          shortDescription
          descriptionHtml
          skills
          locations {
            city
            state
            country
            primary
          }
          externalSource {
            sourceId
          }
        }
      }
    }
    """

    seen_ids: set[str] = set()
    jobs: list[JobPosting] = []
    unlimited = not max_results or max_results <= 0

    with httpx.Client(headers=headers, timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        for page_num in (0, 1):
            try:
                resp = client.post(
                    api_url,
                    json={
                        "operationName": "GetRoles",
                        "variables": {
                            "searchQueryInput": {
                                "page": {"pageSize": 100, "pageNumber": page_num},
                                "sort": {"sortStrategy": "RELEVANCE", "sortOrder": "DESC"},
                                "filters": [],
                                "experiences": ["PROFESSIONAL", "EARLY_CAREER"],
                                "searchTerm": search_term,
                            }
                        },
                        "query": query_gql,
                    },
                )
                if resp.status_code != 200:
                    break
                role_search = (resp.json().get("data") or {}).get("roleSearch") or {}
                items = role_search.get("items") or []
                total_count = role_search.get("totalCount") or 0
            except Exception as exc:
                logger.debug("Goldman Sachs GraphQL failed: %s", exc)
                break

            if not items:
                break

            for item in items:
                sid = str((item.get("externalSource") or {}).get("sourceId") or item.get("roleId") or "").strip()
                title = (item.get("jobTitle") or "").strip()
                if not sid or not title or sid in seen_ids:
                    continue
                seen_ids.add(sid)

                corp_title = (item.get("corporateTitle") or "").strip()
                combined_title = f"{title} {corp_title}".strip()
                if _is_senior_title(combined_title):
                    continue

                posted_on = _parse_relative_date(item.get("lastPostedDate") or "")
                if cutoff_date and posted_on and posted_on < cutoff_date:
                    continue

                locs = item.get("locations") or []
                loc_parts = [
                    ", ".join(p for p in [l.get("city"), l.get("state"), l.get("country")] if p)
                    for l in locs
                    if isinstance(l, dict)
                ]
                loc_str = "; ".join(loc_parts[:2])
                if is_india_target:
                    if not is_india_location(loc_str, combined_title):
                        continue
                    extracted = extract_india_location(loc_str)
                    if extracted:
                        loc_str = extracted

                skills_txt = " ".join(item.get("skills") or []) if isinstance(item.get("skills"), list) else str(item.get("skills") or "")
                full_text = _strip_html(
                    f"{item.get('shortDescription') or ''} {item.get('descriptionHtml') or ''} {skills_txt}"
                )
                if not matches_genai(title, full_text):
                    continue

                exp_min, exp_max = parse_experience(full_text, title=combined_title)
                skills = detect_skills(title, full_text)
                jobs.append(
                    JobPosting(
                        company="Goldman Sachs",
                        title=title,
                        location=loc_str or "India",
                        date_posted=posted_on,
                        url=f"https://higher.gs.com/roles/{sid}",
                        source="ats/goldman",
                        description_snippet=truncate(full_text or title),
                        exp_min=exp_min,
                        exp_max=exp_max,
                        skills=skills,
                    )
                )
                if not unlimited and len(jobs) >= max_results:
                    return jobs

            if (page_num + 1) * 100 >= total_count:
                break

    return jobs


# ─── Deloitte South Asia Career Portal ────────────────────────────────────────

def _fetch_deloitte_portal(
    location: str,
    cutoff_date: Optional[date],
    max_results: int,
) -> list[JobPosting]:
    """
    Search Deloitte South Asia's career portal across configured search terms,
    parse HTML result rows, pre-filter by date, location, and title seniority,
    and concurrently fetch individual job detail pages.

    Args:
        location (str): Target search location string.
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        max_results (int): Maximum jobs to return (<= 0 means unlimited).

    Returns:
        list[JobPosting]: Matching Deloitte ``JobPosting`` records.
    """
    base_url = "https://southasiacareers.deloitte.com"
    headers = get_stealth_headers("text/html,application/xhtml+xml")
    is_india_target = not location or location.strip().lower() in ("india", "ind")
    loc_q = "India" if is_india_target else location

    seen_hrefs: set[str] = set()
    candidates: list[dict] = []
    jobs: list[JobPosting] = []
    unlimited = not max_results or max_results <= 0

    with httpx.Client(
        headers=headers,
        timeout=_HTTP_TIMEOUT,
        limits=_HTTP_LIMITS,
        follow_redirects=True,
    ) as client:
        for q in _get_ats_search_terms():
            url = f"{base_url}/search/?q={quote_plus(q)}&locationsearch={quote_plus(loc_q)}"
            try:
                r = client.get(url)
                if r.status_code != 200:
                    continue
            except Exception as exc:
                logger.debug("Deloitte portal failed for %r: %s", q, exc)
                continue

            rows = re.findall(r'<tr class="data-row">(.*?)</tr>', r.text, re.S)
            for row_html in rows:
                m_link = re.search(
                    r'<a[^>]+href="([^"]+)"[^>]*class="jobTitle-link"[^>]*>([^<]+)</a>',
                    row_html,
                ) or re.search(
                    r'<a[^>]+class="jobTitle-link"[^>]*href="([^"]+)"[^>]*>([^<]+)</a>',
                    row_html,
                )
                if not m_link:
                    continue
                href = m_link.group(1).strip()
                title = html.unescape(m_link.group(2)).strip()
                if not href or not title or href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                m_date = re.search(r'class="jobDate"[^>]*>([^<]+)', row_html)
                posted_on = _parse_relative_date(m_date.group(1) if m_date else "")
                if cutoff_date and posted_on and posted_on < cutoff_date:
                    continue

                m_loc = re.search(r'<span class="jobLocation">\s*([^<]+)', row_html)
                raw_loc = (m_loc.group(1) if m_loc else "").strip()
                if is_india_target:
                    if not is_india_location(raw_loc, title):
                        continue
                    extracted = extract_india_location(f"{raw_loc} {title}")
                    if extracted:
                        raw_loc = extracted

                if _is_senior_title(title):
                    continue

                candidates.append(
                    {
                        "title": title,
                        "url": href if href.startswith("http") else f"{base_url}{href}",
                        "location": raw_loc or "India",
                        "posted_on": posted_on,
                    }
                )

        if not candidates:
            return []

        def _hydrate(cand: dict) -> Optional[JobPosting]:
            """
            Fetch a Deloitte job detail page, extract its description HTML, verify
            Gen-AI keyword relevance, and return a normalized ``JobPosting``.

            Args:
                cand (dict): Pre-filtered candidate dict with ``title``, ``url``,
                    ``location``, and ``posted_on``.

            Returns:
                Optional[JobPosting]: Hydrated ``JobPosting`` if valid, else ``None``.
            """
            full_text = ""
            try:
                dr = client.get(cand["url"])
                if dr.status_code == 200:
                    m_desc = re.search(
                        r'class="jobdescription"[^>]*>(.*?)</span>\s*</div>',
                        dr.text,
                        re.S | re.I,
                    )
                    full_text = _strip_html(m_desc.group(1) if m_desc else dr.text[:15000])
            except Exception as exc:
                logger.debug("Deloitte detail failed for %s: %s", cand["url"], exc)

            if not matches_genai(cand["title"], full_text):
                return None

            exp_min, exp_max = parse_experience(full_text or cand["title"], title=cand["title"])
            skills = detect_skills(cand["title"], full_text)
            return JobPosting(
                company="Deloitte",
                title=cand["title"],
                location=cand["location"],
                date_posted=cand["posted_on"],
                url=cand["url"],
                source="ats/deloitte",
                description_snippet=truncate(full_text or cand["title"]),
                exp_min=exp_min,
                exp_max=exp_max,
                skills=skills,
            )

        with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as pool:
            for job in pool.map(_hydrate, candidates):
                if job:
                    jobs.append(job)
                    if not unlimited and len(jobs) >= max_results:
                        break

    return jobs


# ─── Synopsys TalentBrew Career Portal ────────────────────────────────────────

def _fetch_synopsys_portal(
    location: str,
    cutoff_date: Optional[date],
    max_results: int,
) -> list[JobPosting]:
    """
    Query Synopsys' TalentBrew search endpoint across configured Gen-AI search
    terms, parse job cards from HTML/JSON results, and concurrently hydrate
    candidate detail pages to verify keywords and experience bounds.

    Args:
        location (str): Target search location string.
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        max_results (int): Maximum jobs to return (<= 0 means unlimited).

    Returns:
        list[JobPosting]: Matching Synopsys ``JobPosting`` records.
    """
    base_url = "https://careers.synopsys.com"
    headers = get_stealth_headers("application/json, text/html")
    is_india_target = not location or location.strip().lower() in ("india", "ind")

    seen_hrefs: set[str] = set()
    candidates: list[dict] = []
    jobs: list[JobPosting] = []
    unlimited = not max_results or max_results <= 0

    with httpx.Client(
        headers=headers,
        timeout=_HTTP_TIMEOUT,
        limits=_HTTP_LIMITS,
        follow_redirects=True,
    ) as client:
        for kw in _get_ats_search_terms():
            search_url = (
                f"{base_url}/search-jobs/results"
                f"?ActiveFacetID=0&CurrentPage=1&RecordsPerPage=30"
                f"&Keywords={quote_plus(kw)}&Location=India&LocationType=2&LocationPath=1269750"
                f"&OrganizationIds=44408&SortCriteria=7&SortDirection=0&SearchType=1"
            )
            try:
                r = client.get(search_url)
                if r.status_code != 200:
                    continue
                ctype = r.headers.get("content-type", "")
                html_block = r.json().get("results", "") if "application/json" in ctype else r.text
            except Exception as exc:
                logger.debug("Synopsys portal failed for %r: %s", kw, exc)
                continue

            items = re.findall(r'<li[^>]*class="search-results-list__list-item"[^>]*>(.*?)</li>', html_block, re.S)
            for li_html in items:
                m_href = re.search(r'<a[^>]+href="([^"]+)"[^>]*data-job-id="\d+"', li_html)
                m_title = re.search(r'<h2>([^<]+)', li_html)
                if not m_href or not m_title:
                    continue
                href = m_href.group(1).strip()
                title = html.unescape(m_title.group(1)).strip()
                if not href or not title or href in seen_hrefs:
                    continue
                seen_hrefs.add(href)

                m_date = re.search(r'Posted:\s*</strong>\s*([\d/]+)', li_html)
                posted_on = _parse_relative_date(m_date.group(1) if m_date else "")
                if cutoff_date and posted_on and posted_on < cutoff_date:
                    continue

                m_loc = re.search(r'class="job-location"[^>]*>.*?/>([^<]+)', li_html, re.S)
                raw_loc = (m_loc.group(1) if m_loc else "").strip()
                if is_india_target:
                    if not is_india_location(raw_loc, title):
                        continue
                    extracted = extract_india_location(raw_loc)
                    if extracted:
                        raw_loc = extracted

                if _is_senior_title(title):
                    continue

                candidates.append(
                    {
                        "title": title,
                        "url": href if href.startswith("http") else f"{base_url}{href}",
                        "location": raw_loc or "India",
                        "posted_on": posted_on,
                    }
                )

        if not candidates:
            return []

        def _hydrate(cand: dict) -> Optional[JobPosting]:
            """
            Fetch a Synopsys job detail page, extract its ``ats-description`` HTML
            block, verify Gen-AI keyword relevance, and build a ``JobPosting``.

            Args:
                cand (dict): Pre-filtered candidate dict with ``title``, ``url``,
                    ``location``, and ``posted_on``.

            Returns:
                Optional[JobPosting]: Hydrated ``JobPosting`` if valid, else ``None``.
            """
            full_text = ""
            try:
                dr = client.get(cand["url"])
                if dr.status_code == 200:
                    m_desc = re.search(
                        r'class="ats-description"[^>]*>(.*?)</section>',
                        dr.text,
                        re.S | re.I,
                    )
                    full_text = _strip_html(m_desc.group(1) if m_desc else dr.text[:15000])
            except Exception as exc:
                logger.debug("Synopsys detail failed for %s: %s", cand["url"], exc)

            if not matches_genai(cand["title"], full_text):
                return None

            exp_min, exp_max = parse_experience(full_text or cand["title"], title=cand["title"])
            skills = detect_skills(cand["title"], full_text)
            return JobPosting(
                company="Synopsys",
                title=cand["title"],
                location=cand["location"],
                date_posted=cand["posted_on"],
                url=cand["url"],
                source="ats/synopsys",
                description_snippet=truncate(full_text or cand["title"]),
                exp_min=exp_min,
                exp_max=exp_max,
                skills=skills,
            )

        with ThreadPoolExecutor(max_workers=min(4, len(candidates))) as pool:
            for job in pool.map(_hydrate, candidates):
                if job:
                    jobs.append(job)
                    if not unlimited and len(jobs) >= max_results:
                        break

    return jobs


# ─── Phenom People Direct Fetcher (eBay, HPE) ─────────────────────────────────

_PHENOM_PORTALS: dict[str, str] = {
    "eBay": "https://jobs.ebayinc.com/us/en/search-results",
    "HPE": "https://careers.hpe.com/us/en/search-results",
}


def _fetch_phenom_company(
    company: str,
    base_url: str,
    location: str,
    cutoff_date: Optional[date],
    max_results: int,
) -> list[JobPosting]:
    """
    Fetch Gen-AI job openings from Phenom People-powered career portals (eBay, HPE)
    by extracting server-rendered ``phApp.ddo`` JSON payloads and applying
    seniority, location, date cutoff, and Gen-AI keyword filters.

    Args:
        company (str): Canonical company name.
        base_url (str): Search-results base URL of the Phenom career portal.
        location (str): Target search location string.
        cutoff_date (Optional[date]): Oldest allowed posting date (inclusive).
        max_results (int): Maximum jobs to return (<= 0 means unlimited).

    Returns:
        list[JobPosting]: Matching ``JobPosting`` records from the Phenom portal.
    """
    headers = get_stealth_headers("text/html,application/xhtml+xml")
    is_india_target = not location or location.strip().lower() in ("india", "ind")
    seen_ids: set[str] = set()
    jobs: list[JobPosting] = []
    unlimited = not max_results or max_results <= 0

    with httpx.Client(headers=headers, timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        for kw in _get_ats_search_terms():
            if not unlimited and len(jobs) >= max_results:
                break
            url = f"{base_url}?keywords={kw}&location={'India' if is_india_target else location}"
            try:
                r = client.get(url)
                if r.status_code != 200:
                    continue
            except Exception as exc:
                logger.debug("Phenom %s failed: %s", company, exc)
                continue

            m = re.search(r"phApp\.ddo\s*=\s*(\{.*?\});\s*</script>", r.text, re.S)
            if not m:
                continue
            try:
                ddo = json.loads(m.group(1))
                raw_jobs = ddo.get("eagerLoadRefineSearch", {}).get("data", {}).get("jobs", [])
            except Exception:
                continue

            for item in raw_jobs:
                job_id = str(item.get("jobId") or item.get("reqId") or "").strip()
                title = (item.get("title") or "").strip()
                if not title or (job_id and job_id in seen_ids):
                    continue
                if job_id:
                    seen_ids.add(job_id)

                if _is_senior_title(title):
                    continue

                loc_raw = (
                    item.get("cityStateCountry")
                    or item.get("location")
                    or f"{item.get('city', '')}, {item.get('country', '')}"
                ).strip()
                if is_india_target and not is_india_location(loc_raw, title):
                    continue

                posted_on = _parse_relative_date(item.get("postedDate") or "")
                if cutoff_date and posted_on and posted_on < cutoff_date:
                    continue

                desc = _strip_html(item.get("descriptionTeaser") or item.get("description") or "")
                if not matches_genai(title, desc):
                    continue

                apply_url = (item.get("applyUrl") or "").strip()
                if not apply_url:
                    continue
                exp_min, exp_max = parse_experience(desc or title, title=title)
                skills = detect_skills(title, desc)
                norm_loc = extract_india_location(loc_raw) or loc_raw or "India"

                jobs.append(
                    JobPosting(
                        company=company,
                        title=title,
                        location=norm_loc,
                        date_posted=posted_on,
                        url=apply_url,
                        source="ats/phenom",
                        description_snippet=truncate(desc or title),
                        exp_min=exp_min,
                        exp_max=exp_max,
                        skills=skills,
                    )
                )
                if not unlimited and len(jobs) >= max_results:
                    break

    return jobs


# ─── Public Dispatcher ────────────────────────────────────────────────────────

def get_supported_ats_companies() -> set[str]:
    """
    Build the set of all canonical company names that have direct JSON, GraphQL,
    or SSR career portal adapters implemented in this module.

    Args:
        None.

    Returns:
        set[str]: Supported canonical company names (Google, Goldman Sachs,
            Deloitte, Synopsys, plus all Workday, Oracle, and Phenom portals).
    """
    supported = {"Google", "Goldman Sachs", "Deloitte", "Synopsys"}
    supported.update(_WORKDAY_PORTALS.keys())
    supported.update(_ORACLE_PORTALS.keys())
    supported.update(_PHENOM_PORTALS.keys())
    return supported


def fetch_via_ats_apis(
    companies: list[str],
    location: str = "India",
    days: int = DEFAULT_DAYS,
    max_results: int = DEFAULT_MAX_RESULTS,
    progress_callback=None,
) -> list[JobPosting]:
    """
    Concurrently execute all applicable direct ATS career-portal fetchers for
    the requested companies, invoking ``progress_callback`` upon each portal
    completion and returning deduplicated ``JobPosting`` records.

    Args:
        companies (list[str]): Canonical company names requested for fetching.
        location (str): Target search location string (default: ``"India"``).
        days (int): Recency cutoff window in days; 0 disables cutoff.
        max_results (int): Maximum jobs kept per portal fetcher (<= 0 means unlimited).
        progress_callback (Optional[Callable[[str, str], None]]): Optional callback
            invoked as ``progress_callback(company, "direct-api")``.

    Returns:
        list[JobPosting]: Deduplicated list of matching ``JobPosting`` objects across
            all executed direct career-portal adapters.
    """
    cutoff_date = (
        datetime.now().date() - timedelta(days=days)
        if days else None
    )

    target_set = set(companies)
    tasks = []

    if "Google" in target_set:
        tasks.append(("Google", lambda: _fetch_google_careers(location, cutoff_date, max_results)))
    if "Goldman Sachs" in target_set:
        tasks.append(("Goldman Sachs", lambda: _fetch_goldman_sachs(location, cutoff_date, max_results)))
    if "Deloitte" in target_set:
        tasks.append(("Deloitte", lambda: _fetch_deloitte_portal(location, cutoff_date, max_results)))
    if "Synopsys" in target_set:
        tasks.append(("Synopsys", lambda: _fetch_synopsys_portal(location, cutoff_date, max_results)))
    for co, cfg in _WORKDAY_PORTALS.items():
        if co in target_set:
            tasks.append((co, lambda c=co, conf=cfg: _fetch_workday_company(c, conf, location, cutoff_date, max_results)))
    for co, cfg in _ORACLE_PORTALS.items():
        if co in target_set:
            tasks.append((co, lambda c=co, conf=cfg: _fetch_oracle_company(c, conf, location, cutoff_date, max_results)))
    for co, base_url in _PHENOM_PORTALS.items():
        if co in target_set:
            tasks.append((co, lambda c=co, u=base_url: _fetch_phenom_company(c, u, location, cutoff_date, max_results)))

    if not tasks:
        return []

    seen_keys: set[str] = set()
    all_jobs: list[JobPosting] = []

    with ThreadPoolExecutor(max_workers=min(8, len(tasks))) as executor:
        future_map = {executor.submit(fn): co for co, fn in tasks}
        for future in as_completed(future_map):
            co = future_map[future]
            if progress_callback:
                progress_callback(co, "direct-api")
            try:
                res = future.result()
                for job in res:
                    if job.dedup_key not in seen_keys:
                        seen_keys.add(job.dedup_key)
                        all_jobs.append(job)
            except Exception as exc:
                logger.warning("Direct ATS fetcher failed for %s: %s", co, exc)

    return all_jobs
