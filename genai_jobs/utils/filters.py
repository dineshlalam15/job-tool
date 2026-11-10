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
    get_company_aliases,
    get_company_ats_domains,
    get_skills_detection_map,
    get_tier1_keywords,
    get_tier2_keywords,
)


# ─── Company Resolution ───────────────────────────────────────────────────────

def resolve_company(raw_name: str) -> Optional[str]:
    """
    Map a raw company name string (from any scraper) to one of the canonical
    names loaded from config/companies.json. Returns None if no match is found.
    Uses exact lookup first, then word-boundary matching (len >= 3) so short
    acronyms or substrings like 'EY' in 'Honeywell' or 'gs' in 'GSPANN' never collide.
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


def is_target_company(raw_name: str, allowed: Optional[list[str]] = None) -> bool:
    """
    Return True when raw_name resolves to one of the configured target companies
    (or to a specific subset if ``allowed`` is provided).
    """
    canonical = resolve_company(raw_name)
    if canonical is None:
        return False
    targets = allowed if allowed else get_canonical_companies()
    return canonical in targets


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
    re.compile(r"Ready\s+to\s+grow\s+your\s+career\s+at\s+the\s+company\s+leading\s+workforce\s+transformation\s+in\s+the\s+agentic\s+era\??[^.?!]*(?:[.?!]|$)", re.I),
    re.compile(r"Agentforce\s+is\s+the\s+future\s+of\s+AI[^.?!]*(?:[.?!]|$)", re.I),
    re.compile(r"[^.?!]*\band\s+our\s+AI\s+agents\s+accelerate\s+your\s+impact\b[^.?!]*(?:[.?!]|$)", re.I),
    re.compile(r"[^.?!]*\bbacked\s+by\s+automation\s+and\s+AI\s+agents\b[^.?!]*(?:[.?!]|$)", re.I),
    # Micron universal "About Micron" footer blurb
    re.compile(r"Micron\s+Technology\s+is\s+a\s+world\s+leader\s+in\s+innovating\s+memory[^.]*?(?:\.|$)", re.I),
    re.compile(r"[^.?!]*\benabling\s+advances\s+in\s+artificial\s+intelligence\s+and\s+5G\b[^.?!]*(?:[.?!]|$)", re.I),
    # Generic recruiting AI screening disclaimers (EEO / candidate assessment)
    re.compile(r"[^.?!]*\b(?:uses?|utilizes?)\s+artificial\s+intelligence(?:\s*\(\s*AI\s*\))?\s*(?:tools?)?\s+to\s+(?:help\s+(?:our\s+)?)?(?:recruiters|assess|screen|evaluate|review)\b[^.?!]*(?:[.?!]|$)", re.I),
    # Casual end-user office productivity mention (using AI assistants for daily emails/docs)
    re.compile(r"\(\s*e\.g\.?,?\s*generative\s+AI\s+assistants\s*\)", re.I),
]


def _clean_description_for_matching(description: str) -> str:
    """Strip universal corporate PR banners and recruiting disclaimers before keyword matching."""
    if not description:
        return ""
    cleaned = description
    for pat in _CORPORATE_BOILERPLATE_PATTERNS:
        cleaned = pat.sub(" ", cleaned)
    return cleaned


def _has_keyword(kw: str, text: str) -> bool:
    """
    Check if a keyword appears in text using regex word boundaries.
    Prevents short acronyms like 'rag', 'llm', 'ai' from matching substrings
    in words like 'storage', 'leverage', 'coverage', 'garage', etc.
    """
    if not kw or not text:
        return False
    pattern = r"\b" + re.escape(kw.strip()) + r"\b"
    return bool(re.search(pattern, text, re.I))


def matches_genai(title: str, description: str = "") -> bool:
    """
    Return True when the job is in the Gen-AI / targeted skillset domain.
    Dynamically adheres to keywords defined in config/skills.json.
    """
    if _NON_TECH_TITLE_PATTERNS.search(title):
        return False

    clean_desc = _clean_description_for_matching(description)
    tier1 = get_tier1_keywords()
    tier2 = get_tier2_keywords()

    # Tier-1 hit in title or cleaned description with word boundary enforcement
    for kw in tier1:
        if _has_keyword(kw, title) or _has_keyword(kw, clean_desc):
            return True

    # Tier-2 (e.g. Python Developer / Engineer) in title + Tier-1 in cleaned description
    tier2_in_title = any(_has_keyword(kw, title) for kw in tier2)
    if tier2_in_title:
        for kw in tier1:
            if _has_keyword(kw, clean_desc):
                return True

    return False


# ─── URL-based Company Inference ─────────────────────────────────────────────

def company_from_url(url: str) -> Optional[str]:
    """
    Infer canonical company name from career/ATS URL using domains from
    config/companies.json.
    """
    if not url:
        return None
    url_lower = url.lower()
    ats_map = get_company_ats_domains()

    for canonical, domains in ats_map.items():
        for d in domains:
            domain_root = d.split("/")[0].lower().strip()
            if domain_root and domain_root in url_lower:
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
    Extract a normalized India location name (e.g. 'Bengaluru, India')
    from text snippets, location fields, titles, or URLs.
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
    Strictly verify whether a job's location or context is within India.
    Accepts any city, state, or pan-India remote location, while strictly
    rejecting international locations (USA, UK, Singapore, Europe, etc.).
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
    """Return at most `max_chars` characters with an ellipsis if trimmed."""
    if not text:
        return ""
    text = text.strip()
    return text[:max_chars] + ("…" if len(text) > max_chars else "")


def validate_company_names(names: list[str]) -> list[str]:
    """
    Validate a list of company names supplied via CLI against the canonical list.
    Returns the matched canonical names; raises ValueError listing bad inputs.
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
    Infer experience bounds from explicit seniority keywords in the job title.
    Enforces realistic minimums for Senior/Lead/Manager/Principal/Specialist/Advanced roles,
    and maps mid-level tiers (e.g. SDE II, Engineer II) to 2-4 years.
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
        r"(?:sde|software|dev(?:eloper)?|eng(?:ineer|r)?|data\s+scientist|scientist|mts|consultant|analyst|qa|tester)\s*(?:3|iii|4|iv|5|v)\b|"
        r"(?:level|lvl|grade|band|l)\s*(?:3|iii|4|iv|5|v|6|vi|7|vii|8|viii|9|ix|10|x|63|64|65|66)\b"
        r")\b",
        t,
    ):
        return (5, -1)

    # 5. Junior / Associate / Graduate / Level 1 (e.g. 'Advanced Data Science Associate')
    if re.search(
        r"\b("
        r"associate|junior|jr\.?|graduate|"
        r"(?:sde|software|dev(?:eloper)?|eng(?:ineer|r)?|data\s+scientist|scientist|mts|consultant|analyst)\s*(?:1|i\b)|"
        r"(?:level|lvl|grade|band|l)\s*(?:1|i\b)"
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
        r"(?:sde|software|dev(?:eloper)?|eng(?:ineer|r)?|data\s+scientist|scientist|mts|consultant|analyst)\s*(?:2|ii\b)|"
        r"(?:level|lvl|grade|band|l)\s*(?:2|ii\b|61|62)|"
        r"ict\s*(?:2|ii|3|iii)|ba\s*4|"
        r"mid[\s-]level|intermediate"
        r")\b",
        t,
    ):
        return (2, 4)

    return (EXPERIENCE_UNKNOWN, EXPERIENCE_UNKNOWN)


def parse_experience(text: str, title: str = "") -> tuple[int, int]:
    """
    Parse the experience requirement from a job description or text, cross-referencing
    the job title to prevent senior titles from masquerading as entry-level.

    Scans for all stated experience requirements and determines the overall role
    requirement (e.g. if a role requires '11-15 years total' and '2+ years in Python',
    the role's true qualification floor is 11-15 years).

    Returns
    -------
    (min_years, max_years)
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


def matches_experience(
    title: str,
    description: str,
    max_exp: int,
) -> bool:
    """
    Return True when the job's stated experience **requirement** is at most
    ``max_exp`` years — i.e., the posting is reachable for someone with up to
    that many years of experience.

    Semantics (from the job's perspective)
    ───────────────────────────────────────
    The user passes ``-x N`` meaning "show me roles that require ≤ N years."

    | Job says              | Parsed as     | Keep when cap=N?           |
    |-----------------------|---------------|----------------------------|
    | "2–4 years"           | (min=2, max=4)| max(4) ≤ N                 |
    | "less than 4 years"   | (min=0, max=3)| max(3) ≤ N                 |
    | "up to 2 years"       | (min=0, max=2)| max(2) ≤ N                 |
    | "5 years experience"  | (min=5, max=5)| 5 ≤ N                      |
    | "3+ years"            | (min=3, max=-1)| min(3) ≤ N (open ceiling) |
    | "fresher"             | (min=0, max=0)| always keep               |
    | (not found)           | (-1, -1)      | always keep               |

    Parameters
    ----------
    title       : job title string
    description : job description / snippet string
    max_exp     : maximum years of experience the job should require (inclusive)
    """
    for text in (title, description):
        min_yrs, max_yrs = parse_experience(text, title=title)
        if min_yrs == EXPERIENCE_UNKNOWN and max_yrs == EXPERIENCE_UNKNOWN:
            continue   # nothing found in this text, try next

        if max_yrs != EXPERIENCE_UNKNOWN:
            # We know the job's ceiling — keep only if ceiling ≤ user cap
            return max_yrs <= max_exp

        # Only min_yrs known (open-ended "X+") — keep if floor ≤ user cap
        return min_yrs <= max_exp

    # No experience data anywhere → let the job through
    return True


# ─── Experience Range & Expression Filter ────────────────────────────────────

def parse_experience_filter(filter_val: str | int) -> tuple[int, int]:
    """
    Parse an experience filter expression into (target_lo, target_hi).

    Supported formats:
      - "4" or 4           -> (0, 4)   (<= 4 years / freshers to 4 years)
      - "2-4" or "2 to 4"  -> (2, 4)   (roles between 2 and 4 years)
      - "<4" or "under 4"  -> (0, 3)   (strictly less than 4 years)
      - "fresher" / "0"    -> (0, 0)
      - "all" / "0" / None -> (-1, -1) (disabled)
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
    Check whether a job with bounds (job_lo, job_hi) satisfies target (target_lo, target_hi).

    In strict_mode:
      Jobs with unstated/unverified experience (job_lo == -1 and job_hi == -1) are REJECTED,
      guaranteeing that 100% of returned jobs have confirmed experience matching the criteria.
    """
    if target_lo == -1 and target_hi == -1:
        return True  # filter disabled

    if job_lo == -1 and job_hi == -1:
        return not strict_mode  # in strict mode, reject unverified roles

    # Job has ceiling only (e.g. up to 2 yrs)
    if job_lo <= 0 and job_hi != -1:
        max_allowed = target_hi + 1 if target_hi != -1 else -1
        if max_allowed != -1 and job_hi > max_allowed:
            return False
        if target_lo > 0 and job_hi < target_lo:
            return False
        return True

    # Job has floor only (e.g. 3+ yrs, 5+ yrs)
    if job_hi == -1:
        if target_hi != -1 and job_lo > target_hi:
            return False
        return True

    # Job has both bounds [job_lo, job_hi] (e.g. 2-4 yrs, 3-6 yrs, 11-15 yrs)
    if target_hi != -1 and job_lo > target_hi:
        return False

    max_allowed = target_hi + 1 if target_hi != -1 else -1
    if max_allowed != -1 and job_hi > max_allowed:
        return False

    if target_lo > 0 and job_hi < target_lo:
        return False

    return True


# ─── Skillset Detection ──────────────────────────────────────────────────────

def detect_skills(title: str, description: str = "") -> list[str]:
    """
    Extract skillset tags dynamically from external configuration in config/skills.json.
    Uses regex word boundaries so short tags like 'RAG' never match inside 'storage'.
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
