"""
genai_jobs/constants.py
─────────────────────────────────────────────────────────────────────────────
Configuration bridge providing loose coupling across the application.

All values are dynamically loaded from external JSON files in `config/`:
  - `config/companies.json`: Company list, aliases, ATS career domains
  - `config/skills.json`: Search terms, GenAI/Agentic/RAG/Python keywords
  - `config/settings.json`: Default days, experience, location, sites, timeouts

Changes in config/ take effect immediately without requiring code changes.
"""
from __future__ import annotations

from genai_jobs.config import (
    get_config,
    get_canonical_companies,
    get_company_aliases,
    get_alias_to_canonical,
    get_company_ats_domains,
    get_company_linkedin_ids,
    get_search_terms,
    get_tier1_keywords,
    get_tier2_keywords,
    get_skills_detection_map,
)

# Initial load from configuration files
_cfg = get_config()

CANONICAL_COMPANIES: list[str] = get_canonical_companies()
COMPANY_ALIASES: dict[str, set[str]] = get_company_aliases()
ALIAS_TO_CANONICAL: dict[str, str] = get_alias_to_canonical()
COMPANY_ATS_DOMAINS: dict[str, list[str]] = get_company_ats_domains()
COMPANY_LINKEDIN_IDS: dict[str, list[str]] = get_company_linkedin_ids()

SEARCH_TERMS: list[str] = get_search_terms()
GENAI_TIER1_KEYWORDS: list[str] = get_tier1_keywords()
GENAI_TIER2_KEYWORDS: list[str] = get_tier2_keywords()
SKILLS_DETECTION_MAP: dict[str, list[str]] = get_skills_detection_map()

DEFAULT_LOCATION: str = _cfg.settings.default_location
DEFAULT_DAYS: int = _cfg.settings.default_days
DEFAULT_EXPERIENCE: str = _cfg.settings.default_experience
DEFAULT_MAX_RESULTS: int = _cfg.settings.default_max_results
JOBSPY_SITES: list[str] = _cfg.settings.jobspy_sites
REQUEST_TIMEOUT: int = _cfg.settings.request_timeout_seconds
MAX_RETRY_ATTEMPTS: int = _cfg.settings.max_retry_attempts
RETRY_WAIT_MIN: float = _cfg.settings.retry_wait_min
RETRY_WAIT_MAX: float = _cfg.settings.retry_wait_max
AMAZON_JOBS_API: str = _cfg.settings.amazon_api_url


def refresh_constants() -> None:
    """Reload all constants if configuration has changed at runtime."""
    global CANONICAL_COMPANIES, COMPANY_ALIASES, ALIAS_TO_CANONICAL
    global COMPANY_ATS_DOMAINS, COMPANY_LINKEDIN_IDS, SEARCH_TERMS, GENAI_TIER1_KEYWORDS
    global GENAI_TIER2_KEYWORDS, SKILLS_DETECTION_MAP, DEFAULT_LOCATION
    global DEFAULT_DAYS, DEFAULT_EXPERIENCE, DEFAULT_MAX_RESULTS
    global JOBSPY_SITES, REQUEST_TIMEOUT, MAX_RETRY_ATTEMPTS
    global RETRY_WAIT_MIN, RETRY_WAIT_MAX, AMAZON_JOBS_API

    cfg = get_config()
    CANONICAL_COMPANIES = get_canonical_companies()
    COMPANY_ALIASES = get_company_aliases()
    ALIAS_TO_CANONICAL = get_alias_to_canonical()
    COMPANY_ATS_DOMAINS = get_company_ats_domains()
    COMPANY_LINKEDIN_IDS = get_company_linkedin_ids()
    SEARCH_TERMS = get_search_terms()
    GENAI_TIER1_KEYWORDS = get_tier1_keywords()
    GENAI_TIER2_KEYWORDS = get_tier2_keywords()
    SKILLS_DETECTION_MAP = get_skills_detection_map()
    DEFAULT_LOCATION = cfg.settings.default_location
    DEFAULT_DAYS = cfg.settings.default_days
    DEFAULT_EXPERIENCE = cfg.settings.default_experience
    DEFAULT_MAX_RESULTS = cfg.settings.default_max_results
    JOBSPY_SITES = cfg.settings.jobspy_sites
    REQUEST_TIMEOUT = cfg.settings.request_timeout_seconds
    MAX_RETRY_ATTEMPTS = cfg.settings.max_retry_attempts
    RETRY_WAIT_MIN = cfg.settings.retry_wait_min
    RETRY_WAIT_MAX = cfg.settings.retry_wait_max
    AMAZON_JOBS_API = cfg.settings.amazon_api_url


def __getattr__(name: str):
    """Dynamic fallback allowing live updates without restarting."""
    cfg = get_config()
    if name == "CANONICAL_COMPANIES":
        return get_canonical_companies()
    if name == "COMPANY_ALIASES":
        return get_company_aliases()
    if name == "ALIAS_TO_CANONICAL":
        return get_alias_to_canonical()
    if name == "COMPANY_ATS_DOMAINS":
        return get_company_ats_domains()
    if name == "COMPANY_LINKEDIN_IDS":
        return get_company_linkedin_ids()
    if name == "SEARCH_TERMS":
        return get_search_terms()
    if name == "GENAI_TIER1_KEYWORDS":
        return get_tier1_keywords()
    if name == "GENAI_TIER2_KEYWORDS":
        return get_tier2_keywords()
    if name == "SKILLS_DETECTION_MAP":
        return get_skills_detection_map()
    if name == "DEFAULT_DAYS":
        return cfg.settings.default_days
    if name == "DEFAULT_EXPERIENCE":
        return cfg.settings.default_experience
    if name == "DEFAULT_LOCATION":
        return cfg.settings.default_location
    if name == "DEFAULT_MAX_RESULTS":
        return cfg.settings.default_max_results
    if name == "JOBSPY_SITES":
        return cfg.settings.jobspy_sites
    if name == "REQUEST_TIMEOUT":
        return cfg.settings.request_timeout_seconds
    if name == "MAX_RETRY_ATTEMPTS":
        return cfg.settings.max_retry_attempts
    if name == "RETRY_WAIT_MIN":
        return cfg.settings.retry_wait_min
    if name == "RETRY_WAIT_MAX":
        return cfg.settings.retry_wait_max
    if name == "AMAZON_JOBS_API":
        return cfg.settings.amazon_api_url
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
