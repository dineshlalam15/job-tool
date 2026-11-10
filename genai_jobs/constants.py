"""
genai_jobs/constants.py
─────────────────────────────────────────────────────────────────────────────
Configuration bridge providing loose coupling across the application.

All values are dynamically loaded from external JSON files in `config/`:
  - `config/companies.json`: Company list, aliases, ATS career domains
  - `config/skills.json`: Core search terms and skills detection / match rules
  - `config/settings.json`: Default days, experience, location, max results, sources

Changes in config/ take effect immediately without requiring code changes.
"""
from __future__ import annotations

from genai_jobs.config import (
    get_config,
    get_canonical_companies,
    get_company_aliases,
    get_alias_to_canonical,
    get_company_ats_domains,
    get_search_terms,
    get_match_keywords,
    get_skills_detection_map,
)

# Initial load from configuration files
_cfg = get_config()

CANONICAL_COMPANIES: list[str] = get_canonical_companies()
COMPANY_ALIASES: dict[str, set[str]] = get_company_aliases()
ALIAS_TO_CANONICAL: dict[str, str] = get_alias_to_canonical()
COMPANY_ATS_DOMAINS: dict[str, list[str]] = get_company_ats_domains()

SEARCH_TERMS: list[str] = get_search_terms()
MATCH_KEYWORDS: list[str] = get_match_keywords()
SKILLS_DETECTION_MAP: dict[str, list[str]] = get_skills_detection_map()

DEFAULT_LOCATION: str = _cfg.settings.default_location
DEFAULT_DAYS: int = _cfg.settings.default_days
DEFAULT_EXPERIENCE: str = _cfg.settings.default_experience
DEFAULT_MAX_RESULTS: int = _cfg.settings.default_max_results
DEFAULT_SOURCES: str = _cfg.settings.default_sources
MAX_RETRY_ATTEMPTS: int = _cfg.settings.max_retry_attempts
AMAZON_JOBS_API: str = _cfg.settings.amazon_api_url


def refresh_constants() -> None:
    """
    Re-read values from the active configuration singleton and overwrite all
    module-level constants so custom ``--config-dir`` reloads take effect immediately.

    Args:
        None.

    Returns:
        None: Updates module global constant bindings in place.
    """
    global CANONICAL_COMPANIES, COMPANY_ALIASES, ALIAS_TO_CANONICAL
    global COMPANY_ATS_DOMAINS, SEARCH_TERMS, MATCH_KEYWORDS
    global SKILLS_DETECTION_MAP, DEFAULT_LOCATION
    global DEFAULT_DAYS, DEFAULT_EXPERIENCE, DEFAULT_MAX_RESULTS, DEFAULT_SOURCES
    global MAX_RETRY_ATTEMPTS, AMAZON_JOBS_API

    cfg = get_config()
    CANONICAL_COMPANIES = get_canonical_companies()
    COMPANY_ALIASES = get_company_aliases()
    ALIAS_TO_CANONICAL = get_alias_to_canonical()
    COMPANY_ATS_DOMAINS = get_company_ats_domains()
    SEARCH_TERMS = get_search_terms()
    MATCH_KEYWORDS = get_match_keywords()
    SKILLS_DETECTION_MAP = get_skills_detection_map()
    DEFAULT_LOCATION = cfg.settings.default_location
    DEFAULT_DAYS = cfg.settings.default_days
    DEFAULT_EXPERIENCE = cfg.settings.default_experience
    DEFAULT_MAX_RESULTS = cfg.settings.default_max_results
    DEFAULT_SOURCES = cfg.settings.default_sources
    MAX_RETRY_ATTEMPTS = cfg.settings.max_retry_attempts
    AMAZON_JOBS_API = cfg.settings.amazon_api_url


def __getattr__(name: str):
    """
    Dynamically resolve supported configuration attribute names from active
    config when accessed via module lookup.

    Args:
        name (str): Name of the attribute requested from ``genai_jobs.constants``.

    Returns:
        Any: Live configuration value corresponding to ``name``.

    Raises:
        AttributeError: If ``name`` is not a recognized configuration constant.
    """
    cfg = get_config()
    if name == "CANONICAL_COMPANIES":
        return get_canonical_companies()
    if name == "COMPANY_ALIASES":
        return get_company_aliases()
    if name == "ALIAS_TO_CANONICAL":
        return get_alias_to_canonical()
    if name == "COMPANY_ATS_DOMAINS":
        return get_company_ats_domains()
    if name == "SEARCH_TERMS":
        return get_search_terms()
    if name == "MATCH_KEYWORDS":
        return get_match_keywords()
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
    if name == "DEFAULT_SOURCES":
        return cfg.settings.default_sources
    if name == "MAX_RETRY_ATTEMPTS":
        return cfg.settings.max_retry_attempts
    if name == "AMAZON_JOBS_API":
        return cfg.settings.amazon_api_url
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
