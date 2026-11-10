"""
genai_jobs/config.py
─────────────────────────────────────────────────────────────────────────────
External configuration loader ensuring loose coupling across companies,
skillsets, and application settings.

Configuration files (JSON format) located in `config/`:
  - `companies.json`: Company names, CLI shorthand aliases, and official ATS career domains.
  - `skills.json`: Core search terms and skills detection / matching rules.
  - `settings.json`: Default days, experience bounds, location, max results, and sources.

To add/remove companies, target different skills (e.g., DevOps, Golang, Data),
or alter posting timeframes, simply update the JSON files without modifying code.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ─── Pydantic Models for Configuration ───────────────────────────────────────

class CompanyItem(BaseModel):
    name: str
    aliases: list[str] = Field(default_factory=list)
    ats_domains: list[str] = Field(default_factory=list)


class CompaniesConfig(BaseModel):
    companies: list[CompanyItem] = Field(default_factory=list)


class SkillsConfig(BaseModel):
    search_terms: list[str] = Field(default_factory=list)
    skills_detection: dict[str, list[str]] = Field(default_factory=dict)


class SettingsConfig(BaseModel):
    default_days: int = 7
    default_experience: str = "<4"
    strict_experience: bool = True
    default_location: str = "India"
    default_max_results: int = 0
    default_sources: str = "all"
    max_retry_attempts: int = 3
    amazon_api_url: str = "https://www.amazon.jobs/en/search.json"


class AppConfig(BaseModel):
    companies: CompaniesConfig = Field(default_factory=CompaniesConfig)
    skills: SkillsConfig = Field(default_factory=SkillsConfig)
    settings: SettingsConfig = Field(default_factory=SettingsConfig)
    config_dir: Optional[Path] = None


# ─── Config Directory Discovery ──────────────────────────────────────────────

def discover_config_dir(explicit_dir: Optional[str | Path] = None) -> Path:
    """
    Resolve the directory containing external JSON configuration files in priority order:
    explicit path -> ``GENAI_JOBS_CONFIG_DIR`` env var -> ``./config`` -> repo ``config/``.

    Args:
        explicit_dir (Optional[str | Path]): Optional custom directory path supplied via CLI.

    Returns:
        Path: First existing directory containing ``companies.json``, or the highest-priority
            fallback path if none exists yet.
    """
    candidates: list[Path] = []

    if explicit_dir:
        candidates.append(Path(explicit_dir).expanduser().resolve())

    env_dir = os.environ.get("GENAI_JOBS_CONFIG_DIR")
    if env_dir:
        candidates.append(Path(env_dir).expanduser().resolve())

    # Current working directory / config
    candidates.append(Path.cwd() / "config")

    # File parent tree (project root / config)
    pkg_dir = Path(__file__).resolve().parent
    candidates.append(pkg_dir.parent / "config")
    candidates.append(pkg_dir / "config")

    for p in candidates:
        if p.is_dir() and (p / "companies.json").exists():
            return p

    # Fallback to the first candidate or current dir / config
    return candidates[0] if candidates else Path.cwd() / "config"


# ─── Safe Loaders ────────────────────────────────────────────────────────────

def _load_json_file(file_path: Path) -> dict[str, Any]:
    """
    Safely read and deserialize a JSON configuration file from disk, returning an
    empty dictionary instead of raising if the file is missing or malformed.

    Args:
        file_path (Path): Filesystem path to the target JSON file.

    Returns:
        dict[str, Any]: Parsed JSON object, or ``{}`` when missing or invalid.
    """
    if not file_path.is_file():
        logger.warning("Config file not found: %s", file_path)
        return {}
    try:
        with file_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("Failed to parse config file %s: %s", file_path, exc)
        return {}


# ─── Singleton & Global Loader ───────────────────────────────────────────────

_ACTIVE_CONFIG: Optional[AppConfig] = None


def load_config(config_dir: Optional[str | Path] = None, reload: bool = False) -> AppConfig:
    """
    Load ``companies.json``, ``skills.json``, and ``settings.json`` into the singleton
    ``AppConfig`` model, returning the cached instance unless ``reload`` or a custom
    ``config_dir`` is provided.

    Args:
        config_dir (Optional[str | Path]): Optional directory overriding default discovery.
        reload (bool): When True, forces re-reading JSON files even if already cached.

    Returns:
        AppConfig: Active validated configuration instance.
    """
    global _ACTIVE_CONFIG
    if _ACTIVE_CONFIG is not None and not reload and config_dir is None:
        return _ACTIVE_CONFIG

    target_dir = discover_config_dir(config_dir)
    logger.debug("Loading genai-jobs config from: %s", target_dir)

    # 1. Companies
    companies_data = _load_json_file(target_dir / "companies.json")
    companies_cfg = CompaniesConfig(**companies_data) if companies_data else CompaniesConfig()

    # 2. Skills
    skills_data = _load_json_file(target_dir / "skills.json")
    skills_cfg = SkillsConfig(**skills_data) if skills_data else SkillsConfig()

    # 3. Settings
    settings_data = _load_json_file(target_dir / "settings.json")
    settings_cfg = SettingsConfig(**settings_data) if settings_data else SettingsConfig()

    _ACTIVE_CONFIG = AppConfig(
        companies=companies_cfg,
        skills=skills_cfg,
        settings=settings_cfg,
        config_dir=target_dir,
    )
    return _ACTIVE_CONFIG


def get_config() -> AppConfig:
    """
    Return the active ``AppConfig`` singleton, loading default configuration files
    on first access if it has not been initialized yet.

    Args:
        None.

    Returns:
        AppConfig: Currently active configuration object.
    """
    global _ACTIVE_CONFIG
    if _ACTIVE_CONFIG is None:
        return load_config()
    return _ACTIVE_CONFIG


# ─── Dynamic Accessors for Loose Coupling ────────────────────────────────────

def get_canonical_companies() -> list[str]:
    """
    Extract the ordered list of canonical company names from active configuration.

    Args:
        None.

    Returns:
        list[str]: Canonical company names configured in ``companies.json``.
    """
    cfg = get_config()
    return [c.name for c in cfg.companies.companies]


def get_company_aliases() -> dict[str, set[str]]:
    """
    Build a mapping from each canonical company name to its lowercase aliases
    (including the canonical name itself).

    Args:
        None.

    Returns:
        dict[str, set[str]]: Map of canonical company name to normalized alias strings.
    """
    cfg = get_config()
    result: dict[str, set[str]] = {}
    for c in cfg.companies.companies:
        aliases_set = {a.lower().strip() for a in c.aliases}
        aliases_set.add(c.name.lower().strip())
        result[c.name] = aliases_set
    return result


def get_alias_to_canonical() -> dict[str, str]:
    """
    Invert the company-aliases map for O(1) lookup from any lowercase alias
    or name to its canonical company name.

    Args:
        None.

    Returns:
        dict[str, str]: Reverse map of ``{lowercase_alias: canonical_company_name}``.
    """
    aliases = get_company_aliases()
    return {
        alias: canonical
        for canonical, alias_set in aliases.items()
        for alias in alias_set
    }


def get_company_ats_domains() -> dict[str, list[str]]:
    """
    Return configured official career portal / ATS domains per canonical company.

    Args:
        None.

    Returns:
        dict[str, list[str]]: Map of canonical company name to list of ATS domains/paths.
    """
    cfg = get_config()
    return {c.name: c.ats_domains for c in cfg.companies.companies}


def get_search_terms() -> list[str]:
    """
    Return active search query terms loaded from ``skills.json``, falling back to
    ``["Generative AI", "Agentic AI", "LLM", "RAG"]`` if empty.

    Args:
        None.

    Returns:
        list[str]: Search query strings used across all fetching engines.
    """
    cfg = get_config()
    return cfg.skills.search_terms or [
        "Generative AI",
        "Agentic AI",
        "LLM",
        "RAG",
    ]


def get_skills_detection_map() -> dict[str, list[str]]:
    """
    Return the mapping of canonical skill labels to their detection keyword variants.

    Args:
        None.

    Returns:
        dict[str, list[str]]: Map of ``{skill_label: [keyword_variants]}``.
    """
    cfg = get_config()
    return cfg.skills.skills_detection


def get_match_keywords() -> list[str]:
    """
    Build a deduplicated list of lowercase matching keywords combined from
    ``skills_detection`` and ``search_terms``, with built-in GenAI/Agentic/LLM/RAG fallback.

    Args:
        None.

    Returns:
        list[str]: Deduplicated lowercase keyword strings used by ``matches_genai()``.
    """
    seen: set[str] = set()
    keywords: list[str] = []
    for kws in get_skills_detection_map().values():
        for kw in kws:
            norm = kw.lower().strip()
            if norm and norm not in seen:
                seen.add(norm)
                keywords.append(norm)
    for term in get_search_terms():
        norm = term.lower().strip()
        if norm and norm not in seen:
            seen.add(norm)
            keywords.append(norm)
    return keywords or ["generative ai", "genai", "gen ai", "agentic ai", "llm", "rag"]

