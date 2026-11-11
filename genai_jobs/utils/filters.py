"""
genai_jobs/utils/filters.py
─────────────────────────────────────────────────────────────────────────────
Company normalisation, skill detection, Gen-AI keyword matching, and
experience-level filtering helpers. All rules dynamically adhere to the
external configuration in `config/`.
"""
from __future__ import annotations

import re
from typing import Optional

from genai_jobs.config import (
    get_alias_to_canonical,
    get_canonical_companies,
    get_company_ats_domains,
    get_match_keywords,
    get_skills_detection_map,
)


# ─── Company Resolution ───────────────────────────────────────────────────────

def resolve_company(raw_name: str) -> Optional[str]:
    """
    Resolve a raw company name or shorthand alias into its canonical company name
    from ``config/companies.json``, using exact matching first and longest-first
    word-boundary regex matching (>= 3 chars) to prevent short-acronym collisions.

    Args:
        raw_name (str): Raw company name or alias string supplied by CLI or scraper.

    Returns:
        Optional[str]: Canonical company name if matched, or ``None`` otherwise.
    """
    if not raw_name:
        return None
    normalised = raw_name.lower().strip()
    alias_map = get_alias_to_canonical()

    # Exact alias lookup
    if normalised in alias_map:
        return alias_map[normalised]

    # Word-boundary alias lookup sorted longest-first (never reverse-substring)
    for alias in sorted(alias_map.keys(), key=len, reverse=True):
        if len(alias) < 3:
            continue
        pattern = r"(?<![a-z0-9])" + re.escape(alias) + r"(?![a-z0-9])"
        if re.search(pattern, normalised):
            return alias_map[alias]
    return None


# ─── Gen-AI Keyword Matching ─────────────────────────────────────────────────

# Non-technical or pure hardware job titles that should never be matched
_NON_TECH_TITLE_PATTERNS = re.compile(
    r"\b(graphic\s+designer|visual\s+designer|art\s+director|copywriter|content\s+writer|"
    r"recruiter|talent\s+acquisition|hr\s+specialist|human\s+resources|finance\s+analyst|"
    r"legal\s+counsel|attorney|paralegal|sales\s+representative|account\s+executive|"
    r"mechanical|facilities|technician|analog\s+layout|hardware|electrical\s+eng|"
    r"ic\s+package|package\s+development)\b",
    re.I,
)

# Corporate PR banners, HR AI-recruiting disclaimers, and non-engineering productivity blurbs
# that appear identically across unrelated roles (e.g. Program Management, Pricing Ops BA)
_CORPORATE_BOILERPLATE_PATTERNS = [
    # Salesforce universal Workday header/footer blurbs
    re.compile(r"Ready\s+to\s+(?:grow|level[\s-]+up)\s+your\s+career\s+at\s+the\s+company\s+leading\s+workforce\s+transformation\s+in\s+the\s+agentic\s+era\??[^.?!]*(?:[.?!]|$)", re.I),
    re.compile(r"Agentforce\s+is\s+the\s+future\s+of\s+AI[^.?!]*(?:[.?!]|$)", re.I),
    re.compile(r"[^.?!]*\band\s+our\s+AI\s+agents\s+accelerate\s+your\s+impact\b[^.?!]*(?:[.?!]|$)", re.I),
    re.compile(r"[^.?!]*\bbacked\s+by\s+automation\s+and\s+AI\s+agents\b[^.?!]*(?:[.?!]|$)", re.I),
    # Micron universal "About Micron" footer blurb & generic IT Copilot productivity text
    re.compile(r"Micron\s+Technology\s+is\s+a\s+world\s+leader\s+in\s+innovating\s+memory[^.]*?(?:\.|$)", re.I),
    re.compile(r"[^.?!]*\benabling\s+advances\s+in\s+artificial\s+intelligence\s+and\s+5G\b[^.?!]*(?:[.?!]|$)", re.I),
    re.compile(r"[^.?!]*\bAI-enabled\s+(?:ways\s+of\s+working|productivity\s+and\s+engineering\s+tools),\s+including\s+Microsoft\s+Copilot,\s+Generative\s+AI\b[^.?!]*(?:[.?!]|$)", re.I),
    # Generic recruiting AI screening disclaimers (EEO / candidate assessment)
    re.compile(r"[^.?!]*\b(?:uses?|utilizes?)\s+artificial\s+intelligence(?:\s*\(\s*AI\s*\))?\s*(?:tools?)?\s+to\s+(?:help\s+(?:our\s+)?)?(?:recruiters|assess|screen|evaluate|review)\b[^.?!]*(?:[.?!]|$)", re.I),
    # Casual end-user office productivity mention (using AI assistants for daily emails/docs)
    re.compile(r"\(\s*e\.g\.?,?\s*generative\s+AI\s+assistants\s*\)", re.I),
]


def _clean_description_for_matching(description: str) -> str:
    """
    Remove universal corporate PR banners, agentic-branding taglines, and
    automated HR recruiting disclaimers from job text prior to keyword matching.

    Args:
        description (str): Raw job description or qualification text.

    Returns:
        str: Sanitized text with configured corporate boilerplate phrases removed,
            or ``""`` if ``description`` is empty.
    """
    if not description:
        return ""
    cleaned = description
    for pat in _CORPORATE_BOILERPLATE_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    return cleaned


def _has_keyword(kw: str, text: str) -> bool:
    """
    Test whether a keyword appears as a standalone token or phrase in ``text``
    using case-insensitive regex word boundaries so acronyms like ``llm`` or ``rag``
    never match substrings inside unrelated words.

    Args:
        kw (str): Keyword or phrase to search for.
        text (str): Target text (job title or cleaned description).

    Returns:
        bool: True if ``kw`` occurs on word boundaries in ``text``, else False.
    """
    if not kw or not text:
        return False
    pattern = r"\b" + re.escape(kw.strip()) + r"\b"
    return bool(re.search(pattern, text, re.I))


def matches_genai(title: str, description: str = "") -> bool:
    """
    Determine whether a job posting matches the configured Gen-AI terms
    (Generative AI / GenAI, Agentic AI, LLM, RAG) while rejecting non-technical
    or pure hardware roles based on title exclusion patterns.

    Args:
        title (str): Job posting title.
        description (str): Optional job description or snippet text.

    Returns:
        bool: True when the role is technical and matches at least one configured
            Gen-AI keyword in either ``title`` or sanitized ``description``.
    """
    if _NON_TECH_TITLE_PATTERNS.search(title):
        return False

    clean_desc = _clean_description_for_matching(description)
    for kw in get_match_keywords():
        if _has_keyword(kw, title) or _has_keyword(kw, clean_desc):
            return True

    return False


# ─── URL-based Company Inference ─────────────────────────────────────────────

_SHARED_ATS_HOSTS = {
    "jobs.lever.co",
    "boards.greenhouse.io",
    "job-boards.greenhouse.io",
    "jobs.ashbyhq.com",
    "smartrecruiters.com",
    "wd1.myworkdaysite.com",
    "apply.workable.com",
}


def company_from_url(url: str) -> Optional[str]:
    """
    Infer a canonical company name from a career or ATS posting URL by matching
    full configured ``domain/path`` strings longest-first, falling back to
    host-only matching strictly for non-shared company-owned career domains.

    Args:
        url (str): Full career portal or ATS job URL.

    Returns:
        Optional[str]: Canonical company name if matched, or ``None`` otherwise.
    """
    if not url:
        return None
    url_lower = url.lower()
    ats_map = get_company_ats_domains()

    candidates: list[tuple[str, str]] = []
    for canonical, domains in ats_map.items():
        for d in domains:
            clean_d = d.lower().strip().rstrip("/")
            if clean_d:
                candidates.append((clean_d, canonical))

    # 1. Longest/most-specific configured domain(+path) match first
    for clean_d, canonical in sorted(candidates, key=lambda item: len(item[0]), reverse=True):
        if clean_d in url_lower:
            return canonical

    # 2. Host-only fallback only for dedicated company-owned domains
    for clean_d, canonical in candidates:
        domain_root = clean_d.split("/")[0]
        if domain_root and domain_root not in _SHARED_ATS_HOSTS and domain_root in url_lower:
            return canonical

    return None


# ─── Location & India Verification ──────────────────────────────────────────

_INDIA_CITIES = {
    "bengaluru", "bangalore", "hyderabad", "secunderabad", "pune", "mumbai",
    "navi mumbai", "thane", "gurugram", "gurgaon", "noida", "greater noida",
    "delhi", "new delhi", "ncr", "chennai", "madras", "kolkata", "calcutta",
    "ahmedabad", "gandhinagar", "kochi", "cochin", "trivandrum", "thiruvananthapuram",
    "coimbatore", "chandigarh", "mohali", "jaipur", "indore", "bhubaneswar",
    "nagpur", "vadodara", "visakhapatnam", "vizag", "mysore", "mysuru", "mangaluru", "mangalore"
}

_INDIA_STATES = {
    "karnataka", "ka", "telangana", "ts", "tg", "maharashtra", "mh",
    "haryana", "hr", "uttar pradesh", "up", "tamil nadu", "tn",
    "west bengal", "wb", "delhi", "dl", "gujarat", "gj", "kerala", "kl",
    "andhra pradesh", "ap", "punjab", "pb", "rajasthan", "rj",
    "madhya pradesh", "mp", "odisha"
}

_FOREIGN_LOCATIONS = {
    "united states", "usa", "u.s.", "seattle", "redmond", "california",
    "san francisco", "sunnyvale", "austin", "new york", "boston", "texas",
    "chicago", "washington", "united kingdom", "london", "canada",
    "toronto", "vancouver", "singapore", "germany", "berlin", "munich",
    "poland", "warsaw", "krakow", "ireland", "dublin", "australia",
    "sydney", "melbourne", "japan", "tokyo", "france", "paris",
    "netherlands", "amsterdam", "israel", "tel aviv", "switzerland", "zurich"
}


_CITY_DISPLAY_NAMES = {
    "bengaluru": "Bengaluru, India",
    "bangalore": "Bengaluru, India",
    "hyderabad": "Hyderabad, India",
    "secunderabad": "Hyderabad, India",
    "pune": "Pune, India",
    "mumbai": "Mumbai, India",
    "navi mumbai": "Mumbai, India",
    "thane": "Mumbai, India",
    "gurugram": "Gurugram, India",
    "gurgaon": "Gurugram, India",
    "noida": "Noida, India",
    "greater noida": "Noida, India",
    "delhi": "Delhi NCR, India",
    "new delhi": "New Delhi, India",
    "ncr": "Delhi NCR, India",
    "chennai": "Chennai, India",
    "madras": "Chennai, India",
    "kolkata": "Kolkata, India",
    "calcutta": "Kolkata, India",
    "ahmedabad": "Ahmedabad, India",
    "gandhinagar": "Gandhinagar, India",
    "kochi": "Kochi, India",
    "cochin": "Kochi, India",
    "trivandrum": "Thiruvananthapuram, India",
    "thiruvananthapuram": "Thiruvananthapuram, India",
    "coimbatore": "Coimbatore, India",
    "chandigarh": "Chandigarh, India",
    "mohali": "Chandigarh, India",
    "jaipur": "Jaipur, India",
    "indore": "Indore, India",
    "bhubaneswar": "Bhubaneswar, India",
    "nagpur": "Nagpur, India",
    "vadodara": "Vadodara, India",
    "visakhapatnam": "Visakhapatnam, India",
    "vizag": "Visakhapatnam, India",
    "mysuru": "Mysuru, India",
    "mysore": "Mysuru, India",
    "mangalore": "Mangaluru, India",
    "mangaluru": "Mangaluru, India",
}


def extract_india_location(text: str) -> Optional[str]:
    """
    Extract and normalize an Indian city/hub display label (for example mapping
    ``"Bangalore"`` to ``"Bengaluru, India"``) or generic ``"India"`` from free text.

    Args:
        text (str): Combined job location, title, snippet, or URL text.

    Returns:
        Optional[str]: Standardized ``"<City>, India"`` or ``"India"`` string if
            an Indian location indicator is present, else ``None``.
    """
    if not text:
        return None
    lower = text.lower()
    for key, display in _CITY_DISPLAY_NAMES.items():
        if re.search(r"\b" + re.escape(key) + r"\b", lower):
            return display
    if re.search(r"\b(india|ind)\b", lower) or re.search(r",\s*IN\b", text):
        return "India"
    return None


def is_india_location(location_str: str, text: str = "") -> bool:
    """
    Verify strictly whether a job posting is located in India by checking both
    explicit Indian cities/states/country markers and rejecting postings anchored
    in foreign cities/countries without an India match.

    Args:
        location_str (str): Structured location field from the portal or scraper.
        text (str): Optional supplementary text (title, description snippet, URL).

    Returns:
        bool: True when confirmed to be an India role, False if foreign or unverified.
    """
    if not location_str and not text:
        return False

    loc_lower = (location_str or "").strip().lower()
    text_lower = (text or "").strip().lower()
    combined = f"{loc_lower} {text_lower}"

    # 1. Check if location_str explicitly specifies a foreign location without India
    if loc_lower:
        for f in _FOREIGN_LOCATIONS:
            if re.search(r"\b" + re.escape(f) + r"\b", loc_lower):
                if not re.search(r"\b(india|ind)\b", loc_lower):
                    return False

        # If location_str mentions India or an Indian city/state
        if re.search(r"\b(india|ind)\b", loc_lower) or re.search(r",\s*IN\b", location_str):
            return True
        for city in _INDIA_CITIES:
            if re.search(r"\b" + re.escape(city) + r"\b", loc_lower):
                return True
        for state in _INDIA_STATES:
            if re.search(r"\b" + re.escape(state) + r"\b", loc_lower):
                return True

    # 2. If location_str was empty or generic (e.g. "Remote", "Hybrid"), inspect text:
    # If text is dominated by foreign locations with no India mention, reject
    has_foreign = any(
        re.search(r"\b" + re.escape(f) + r"\b", text_lower)
        for f in _FOREIGN_LOCATIONS
    )
    has_india = bool(
        re.search(r"\b(india|ind)\b", combined)
        or re.search(r",\s*IN\b", text)
        or any(re.search(r"\b" + re.escape(c) + r"\b", combined) for c in _INDIA_CITIES)
    )

    if has_foreign and not has_india:
        return False

    if has_india:
        return True

    return False


# ─── Misc helpers ─────────────────────────────────────────────────────────────

def truncate(text: str, max_chars: int = 300) -> str:
    """
    Trim whitespace from ``text`` and shorten it to at most ``max_chars``
    characters, appending ``"…"`` when truncated.

    Args:
        text (str): Input text string to shorten.
        max_chars (int): Maximum number of base characters to retain (default: 300).

    Returns:
        str: Trimmed (and optionally ellipsized) string, or ``""`` when empty.
    """
    if not text:
        return ""
    text = text.strip()
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def validate_company_names(names: list[str]) -> list[str]:
    """
    Resolve and validate CLI-provided company names/aliases against configured
    target companies, deduplicating resolved canonical names while preserving order.

    Args:
        names (list[str]): Raw company names or aliases supplied via CLI options.

    Returns:
        list[str]: Ordered deduplicated list of canonical company names.

    Raises:
        ValueError: If one or more inputs cannot be resolved to a valid company.
    """
    resolved: list[str] = []
    bad: list[str] = []
    for n in names:
        c = resolve_company(n)
        if c:
            resolved.append(c)
        else:
            bad.append(n)
    if bad:
        raise ValueError(
            f"Unknown company name(s): {bad}. "
            f"Valid companies: {get_canonical_companies()}"
        )
    return list(dict.fromkeys(resolved))  # deduplicate while preserving order


# ─── Experience Parsing & Filtering ──────────────────────────────────────────

# Sentinel returned when no experience requirement is found in the text.
EXPERIENCE_UNKNOWN: int = -1

# Patterns ordered from most-specific to least-specific.
# Each pattern must yield at least one numeric capture group (lo, or lo + hi).
_EXP_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Prefix range: "Years of Experience: 11 - 15", "Experience: 10 - 15", "Total Exp: 8 to 12"
    (
        re.compile(
            r"(?:years?\s+of\s+experience|total\s+experience|relevant\s+experience|work\s+experience|experience|exp)\s*[:\-–]\s*(\d+)\s*(?:[-–to]+|and|&)\s*(\d+)",
            re.I,
        ),
        "prefix_range",
    ),
    # Prefix min: "Years of Experience: 11+", "Experience: 10+"
    (
        re.compile(
            r"(?:years?\s+of\s+experience|total\s+experience|relevant\s+experience|work\s+experience|experience|exp)\s*[:\-–]\s*(\d+)\+?",
            re.I,
        ),
        "prefix_min",
    ),
    # "0 - 3 years", "2-4 yrs", "1 to 3 years", "between 2 and 4 years", "2–4 years"
    (
        re.compile(
            r"(?:between\s+)?(\d+)\s*(?:[-–to]+|and|&)\s*(\d+)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)?",
            re.I,
        ),
        "range",
    ),
    # "at least 5 years", "more than 4 years", "> 3 years"
    (
        re.compile(
            r"(?:at\s+least|more\s+than|greater\s+than|>)\s*(\d+)\s*(?:years?|yrs?)",
            re.I,
        ),
        "min_plus",
    ),
    # "less than 4 years", "fewer than 3 years", "under 5 years"
    (
        re.compile(
            r"(?:less\s+than|fewer\s+than|under|below|<)\s*(\d+)\s*(?:years?|yrs?)",
            re.I,
        ),
        "less_than",
    ),
    # "up to 3 years", "upto 4 years"
    (
        re.compile(r"up\s*to\s+(\d+)\s*(?:years?|yrs?)", re.I),
        "up_to",
    ),
    # "at most 3 years"
    (
        re.compile(r"at\s+most\s+(\d+)\s*(?:years?|yrs?)", re.I),
        "up_to",
    ),
    # "0+ years", "3+ years experience"  (minimum-only patterns)
    (
        re.compile(r"(\d+)\+\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)?", re.I),
        "min_plus",
    ),
    # "minimum 2 years", "min. 3 years", "minimum of 2 years"
    (
        re.compile(r"(?:minimum|min\.?)\s+(?:of\s+)?(\d+)\s*(?:years?|yrs?)", re.I),
        "min_plus",
    ),
    # "X years of experience" (bare single number, must NOT follow -, –, to, and, or, +)
    (
        re.compile(r"(?<![-–\dto\w\+&])(\d+)\s*(?:years?|yrs?)\s*(?:of\s+)?(?:experience|exp)", re.I),
        "exact",
    ),
    # Fresher / entry-level keywords → treat as 0 years required
    (
        re.compile(r"\b(?:fresher|fresh\s+graduate|entry[\s-]level|no\s+experience)\b", re.I),
        "fresher",
    ),
]


def infer_seniority_from_title(title: str) -> tuple[int, int]:
    """
    Infer minimum and maximum required experience bounds solely from seniority
    or career-level markers inside a job title (e.g., Intern -> 0–2 yr,
    Associate/Junior -> 0–2 yr, SDE II -> 2–4 yr, Senior/Lead -> 5+ yr, Principal -> 8+ yr).

    Args:
        title (str): Job title string.

    Returns:
        tuple[int, int]: Tuple ``(min_years, max_years)`` where ``-1`` denotes
            an open-ended ceiling or ``(EXPERIENCE_UNKNOWN, EXPERIENCE_UNKNOWN)`` if unstated.
    """
    if not title:
        return (EXPERIENCE_UNKNOWN, EXPERIENCE_UNKNOWN)
    t = title.lower()

    # 1. Intern / Trainee / Fresher / Entry-level ALWAYS take precedence
    if re.search(
        r"\b(intern|internship|trainee|fresher|campus|entry[\s-]level)\b",
        t,
    ):
        return (0, 2)

    # 2. Executive / Director / Leadership / AVP / VP
    if re.search(r"\b(director|vp|vice\s+president|avp|assistant\s+vice\s+president|head\s+of|chief|cxo|partner)\b", t):
        return (7, -1)

    # 3. Principal / Distinguished / Staff / Fellow / PMTS / LMTS
    if re.search(r"\b(principal|distinguished|fellow|staff|pmts|lmts)\b", t):
        return (8, -1)

    # 4. Explicit Senior / Lead / Manager / Architect / Level 3+ tiers
    # (checked before 'associate' so 'Senior Associate' and 'Associate Renewals Manager' are caught as senior)
    if re.search(
        r"\b("
        r"senior|sr\.?|lead|tech\s+lead|team\s+lead|project\s+lead|manager|architect|architecture|"
        r"managing\s+consultant|principal\s+consultant|advisory\s+consultant|smts|ict\s*(?:4|iv|5|v)|"
        r"(?:sde|software|dev(?:eloper)?|eng(?:ineer|r)?|data\s+scientist|scientist|mts|consultant|analyst|qa|tester)[\s-]*(?:3|iii|4|iv|5|v)\b|"
        r"(?:level|lvl|grade|band|l)[\s-]*(?:3|iii|4|iv|5|v|6|vi|7|vii|8|viii|9|ix|10|x|63|64|65|66)\b"
        r")\b",
        t,
    ):
        return (5, -1)

    # 5. Junior / Associate / Graduate / Level 1 (e.g. 'Advanced Data Science Associate')
    if re.search(
        r"\b("
        r"associate|junior|jr\.?|graduate|"
        r"(?:sde|software|dev(?:eloper)?|eng(?:ineer|r)?|data\s+scientist|scientist|mts|consultant|analyst)[\s-]*(?:1|i\b)|"
        r"(?:level|lvl|grade|band|l)[\s-]*(?:1|i\b)"
        r")\b",
        t,
    ):
        return (0, 2)

    # 6. Domain/track senior tiers when not paired with Associate/Junior (e.g. 'AI Specialist')
    if re.search(
        r"\b(advanced|specialist|expert|sme|technical\s+consultant)\b",
        t,
    ):
        return (5, -1)

    # 7. Mid-level: SDE II, Engineer II, Data Scientist II -> 2 to 4 years (ideal for ~2 years experience)
    if re.search(
        r"\b("
        r"(?:sde|software|dev(?:eloper)?|eng(?:ineer|r)?|data\s+scientist|scientist|mts|consultant|analyst)[\s-]*(?:2|ii\b)|"
        r"(?:level|lvl|grade|band|l)[\s-]*(?:2|ii\b|61|62)|"
        r"ict\s*(?:2|ii|3|iii)|ba\s*4|"
        r"mid[\s-]level|intermediate"
        r")\b",
        t,
    ):
        return (2, 4)

    return (EXPERIENCE_UNKNOWN, EXPERIENCE_UNKNOWN)


def parse_experience(text: str, title: str = "") -> tuple[int, int]:
    """
    Extract required years of experience from job description text using ordered
    regex rules, taking the highest overall qualification floor and correlating it
    against title seniority via ``infer_seniority_from_title()``.

    Args:
        text (str): Job description or qualifications text to scan.
        title (str): Optional job title used to enforce seniority floors.

    Returns:
        tuple[int, int]: Normalized ``(min_years, max_years)`` bounds, where ``-1``
            indicates an open-ended ceiling or unknown value.
    """
    if not text and not title:
        return (EXPERIENCE_UNKNOWN, EXPERIENCE_UNKNOWN)

    found_bounds: list[tuple[int, int]] = []

    for pattern, kind in _EXP_PATTERNS:
        for m in pattern.finditer(text):
            if kind == "fresher":
                found_bounds.append((0, 0))
            elif kind in ("prefix_range", "range"):
                lo, hi = int(m.group(1)), int(m.group(2))
                found_bounds.append((min(lo, hi), max(lo, hi)))
            elif kind == "less_than":
                hi = int(m.group(1)) - 1
                found_bounds.append((0, max(hi, 0)))
            elif kind == "up_to":
                hi = int(m.group(1))
                found_bounds.append((0, hi))
            elif kind in ("prefix_min", "min_plus"):
                lo = int(m.group(1))
                found_bounds.append((lo, EXPERIENCE_UNKNOWN))
            elif kind == "exact":
                val = int(m.group(1))
                found_bounds.append((val, val))

    if found_bounds:
        max_lo = max(b[0] for b in found_bounds)
        matching_his = [b[1] for b in found_bounds if b[0] == max_lo and b[1] != EXPERIENCE_UNKNOWN]
        max_hi = max(matching_his) if matching_his else EXPERIENCE_UNKNOWN
        parsed_lo, parsed_hi = max_lo, max_hi
    else:
        parsed_lo, parsed_hi = EXPERIENCE_UNKNOWN, EXPERIENCE_UNKNOWN

    # If title is provided, correlate with title seniority
    if title:
        t_lo, t_hi = infer_seniority_from_title(title)
        if t_lo != EXPERIENCE_UNKNOWN:
            if parsed_lo == EXPERIENCE_UNKNOWN:
                return (t_lo, t_hi)
            # A Senior/Lead/Manager/Specialist role requires at least the title floor
            parsed_lo = max(parsed_lo, t_lo)
            if parsed_hi != EXPERIENCE_UNKNOWN and parsed_hi < parsed_lo:
                parsed_hi = EXPERIENCE_UNKNOWN

    return (parsed_lo, parsed_hi)


# ─── Experience Range & Expression Filter ────────────────────────────────────

def parse_experience_filter(filter_val: str | int) -> tuple[int, int]:
    """
    Parse a user-supplied CLI experience filter expression (such as ``"<4"``,
    ``"2-4"``, ``"4"``, ``"fresher"``, or ``"all"``) into numeric target bounds.

    Args:
        filter_val (str | int): Experience expression string or integer cap.

    Returns:
        tuple[int, int]: Inclusive target bounds ``(target_lo, target_hi)``, or
            ``(-1, -1)`` when the experience filter is disabled.
    """
    if not filter_val:
        return (-1, -1)
    s = str(filter_val).strip().lower()
    if s in ("0", "all", "any", "none", "off", "false", "-1"):
        return (-1, -1)

    # "< 4", "less than 4", "under 4", "below 4"
    m_lt = re.search(r"(?:less\s+than|under|below|<)\s*(\d+)", s)
    if m_lt:
        hi = max(int(m_lt.group(1)) - 1, 0)
        return (0, hi)

    # "2-4", "2 to 4", "2–4"
    m_range = re.search(r"(\d+)\s*[-–to]+\s*(\d+)", s)
    if m_range:
        lo, hi = int(m_range.group(1)), int(m_range.group(2))
        return (min(lo, hi), max(lo, hi))

    # Single integer "4" -> up to 4 years
    m_int = re.search(r"^\s*(\d+)\s*$", s)
    if m_int:
        val = int(m_int.group(1))
        return (0, val) if val > 0 else (-1, -1)

    if "fresh" in s or "entry" in s:
        return (0, 0)

    return (-1, -1)


def job_matches_experience(
    job_lo: int,
    job_hi: int,
    target_lo: int,
    target_hi: int,
    strict_mode: bool = False,
) -> bool:
    """
    Evaluate whether a job posting's required experience meets the user's filter
    bounds ``(target_lo, target_hi)`` by checking the posting's minimum required
    years of experience (so ranges such as ``3–5 yr`` satisfy ``< 4 yr``
    because ``3 <= 3``).

    Args:
        job_lo (int): Minimum required years for the job (``-1`` if unstated).
        job_hi (int): Maximum required years for the job (``-1`` if open-ended/unstated).
        target_lo (int): Lower bound of user experience filter (``-1`` disables filter).
        target_hi (int): Upper bound of user experience filter (``-1`` if unbounded).
        strict_mode (bool): When True, rejects jobs with both ``job_lo == -1`` and
            ``job_hi == -1``.

    Returns:
        bool: True if the posting's minimum experience satisfies the filter criteria,
            else False.
    """
    if target_lo == -1 and target_hi == -1:
        return True  # filter disabled

    if job_lo == -1 and job_hi == -1:
        return not strict_mode  # in strict mode, reject unverified roles

    # Check the minimum required years against target_hi (treating unstated floor <= 0 as 0)
    min_required = max(job_lo, 0)
    if target_hi != -1 and min_required > target_hi:
        return False

    # When user specifies an explicit positive lower bound (e.g. "2-4"), exclude lower ceilings
    if target_lo > 0 and job_hi != -1 and job_hi < target_lo:
        return False

    return True


# ─── Skillset Detection ──────────────────────────────────────────────────────

def detect_skills(title: str, description: str = "") -> list[str]:
    """
    Detect matching skill tags configured in ``config/skills.json`` from the
    combined job title and boilerplate-cleaned description using word-boundary regex.

    Args:
        title (str): Job posting title.
        description (str): Optional job description text.

    Returns:
        list[str]: Matched canonical skill names (e.g. ``["Generative AI", "LLM"]``),
            defaulting to ``["GenAI"]`` if no specific tag matches.
    """
    text = f"{title} {_clean_description_for_matching(description)}"
    skills_map = get_skills_detection_map()
    if not skills_map:
        return ["GenAI"]

    matched: list[str] = []
    for skill_name, keywords in skills_map.items():
        if any(_has_keyword(k, text) for k in keywords):
            matched.append(skill_name)

    return matched if matched else ["GenAI"]


# ─── Amazon SDE-1 Filtering ──────────────────────────────────────────────────

_AMAZON_SDE_TITLE_RE = re.compile(
    r"\b(?:sde(?:[\s-]*(?:i|1))?|software\s+(?:dev(?:elopment)?\s+)?engineer)\b",
    re.I,
)

_AMAZON_EXPLICIT_SDE1_RE = re.compile(
    r"(?:"
    r"\bsde[\s-]*(?:i|1)\b"
    r"|\bsoftware\s+(?:dev(?:elopment)?\s+)?engineer[\s-]*(?:i|1)\b"
    r")",
    re.I,
)

_AMAZON_NON_SDE1_TITLE_RE = re.compile(
    r"(?:"
    r"\b(?:ii|iii|iv)\b"
    r"|\b(?:sde|software\s+(?:dev(?:elopment)?\s+)?engineer|engineer|eng)[\s-]*(?:v|2|3|4|5)\b"
    r"|\bsde(?:2|3|4|ii|iii)\b"
    r"|\b(?:l|level)[\s-]*(?:5|6|7|8)\b"
    r"|\b(?:senior|sr\.?|lead|principal|staff|distinguished|fellow|manager|director|architect|head|vp)\b"
    r"|\b(?:intern|internship|co-?op)\b"
    r"|\b(?:in\s+test|sdet|qa|qae|quality\s+assurance|test\s+engineer|"
    r"support\s+engineer|cloud\s+support|application\s+support|technical\s+support|production\s+support|it\s+support|"
    r"systems?\s+dev(?:elopment)?|sysde|"
    r"data\s+engineer|data\s+scientist|applied\s+scientist|research\s+scientist|scientist|"
    r"analyst|business\s+intelligence|bie|consultant|program\s+manager|product\s+manager|tpm|sdm)\b"
    r")",
    re.I,
)


def is_amazon_sde1(title: str, exp_min: int = -1, exp_max: int = -1) -> bool:
    """
    Determine whether an Amazon job posting represents an SDE-1 role.

    Accepts explicit SDE-1 titles (e.g. ``Software Development Engineer I``,
    ``SDE I``, ``SDE-1``) as well as unnumbered ``Software Development Engineer``
    (or ``Software Engineer`` / ``SDE``) titles when parsed minimum experience is
    strictly verified to be ``< 3`` years, while rejecting SDE II+, Senior/Lead,
    Intern, SDET/QA, Data Engineer, Data/Applied Scientist, and Manager roles.

    Args:
        title (str): Amazon job posting title.
        exp_min (int): Parsed minimum required years of experience (``-1`` if unstated).
        exp_max (int): Parsed maximum required years of experience (``-1`` if unstated).

    Returns:
        bool: True if the posting qualifies as an Amazon SDE-1 role, else False.
    """
    if not title or not _AMAZON_SDE_TITLE_RE.search(title):
        return False
    if _AMAZON_NON_SDE1_TITLE_RE.search(title):
        return False

    if exp_min >= 3:
        return False

    if exp_min == -1:
        if exp_max != -1:
            return exp_max < 3
        # Unstated experience is allowed only when the title explicitly says SDE I / 1
        return bool(_AMAZON_EXPLICIT_SDE1_RE.search(title))

    return True
