# 🤖 genai-jobs

> **Lightweight Python CLI tool** that fetches the latest **Generative AI, Agentic AI, LLM, and RAG job openings** directly from the official **career portals of 34 top-tier tech companies** and prints matching jobs with their clickable URLs straight to your terminal.

Built specifically for software and AI engineers (e.g., with ~2 years of experience) who want a fast, zero-bloat terminal tool instead of manually browsing dozens of career portals or noisy third-party job boards.

---

## ✨ Features & Architecture

| Capability | Details |
|---|---|
| **34 Target Companies** | Pre-configured for Google, Microsoft, Apple, Amazon, Salesforce, Disney, IBM Labs, Deloitte, Quantiphi, JP Morgan Chase, Goldman Sachs, Wells Fargo, DBS, Micron, Synopsys, Samsung, Berkadia, Barclays, Invesco, Tiger Analytics, Verisk Analytics, ADP, Coforge, CHUBB, ICICI Bank, Axis Bank, Adobe, HPE, eBay, Flipkart, JODO, Honeywell, HCL, and Cyient. |
| **Strict India Location** | **Strictly searches and filters for jobs within India only**. Accepts any location within India (Bengaluru, Hyderabad, Pune, Mumbai, Gurugram, Noida, Chennai, Delhi NCR, Kolkata, Pan-India Remote), while automatically filtering out international/foreign roles (USA, UK, Singapore, Europe, etc.). |
| **Strict Experience Filtering** | Profile-matched for **< 4 years (or 2–4 years)** experience. Eliminates senior positions (≥ 4 yrs, 5+ yrs, 11–15 yrs, Senior, Lead, Manager, Architect, Principal, Staff, Engineer III, MTS 3+). |
| **Weekly Timeframe** | Defaults to active jobs posted in the **last 7 days** (`default_days: 7`). |
| **Fetch All Openings (No Capping)** | Defaults to fetching **all** matching job openings without artificial caps (`default_max_results: 0`). You can optionally pass `-m <N>` to cap results. |
| **Focused Search Terms** | Strictly searches and matches only **Generative AI / GenAI, Agentic AI, LLM, and RAG** across all engines for fast, high-signal execution. |
| **Career-Portal-Only Fetching** | Runs 3 concurrent career-portal engines: **Amazon JSON API**, **Direct ATS Portals Engine** (`-s ats` supporting 18 direct company career portals: Amazon, Google, Salesforce, Adobe, Goldman Sachs, Deloitte, JP Morgan Chase, Micron, Disney, Wells Fargo, Honeywell, CHUBB, Invesco, Quantiphi, Berkadia, Synopsys, eBay, HPE), and **Parallel DuckDuckGo ATS Dorking** (`-s dork` restricted strictly to configured company career domains). Third-party job boards are excluded. |
| **Anti-Bot & Stealth Security** | Rotates modern desktop browser User-Agents (Chrome 131, Safari 18, Firefox 133), Client Hints (`sec-ch-ua`), and `Sec-Fetch-*` directives with randomized jitter pacing. |
| **Terminal-Only Output** | Renders a clean Rich summary table followed by full, untruncated, clickable **Job URLs** directly in the terminal—no generated files or UI bloat. |
| **100% Loose Coupling** | All companies, aliases, career portal domains, search terms, and runtime settings are configured externally in `config/*.json`. |

---

## 🚀 Setup & Installation

### 1. Clone and Navigate to the Repository
```bash
git clone https://github.com/dineshlalam15/job-tool.git
cd job-tool
```

### 2. Create and Activate Virtual Environment
```bash
python3 -m venv .venv
source .venv/bin/activate        # On Windows: .venv\Scripts\activate
```

### 3. Install the CLI & Dependencies
```bash
pip install -e .
```
*(Reads runtime dependencies from `pyproject.toml` and registers the `genai-jobs` command inside your virtual environment.)*

---

## 🖥️ How to Run the Application

### 1. Default Run (Recommended)
Fetches all matching jobs across all 34 companies in India posted in the **last 7 days**, strictly filtered for **< 4 years experience**, and displays the table + clickable job URLs in your terminal:
```bash
genai-jobs
```
*(Alternatively, without activating the venv: `./genai-jobs`, `.venv/bin/genai-jobs`, or `python -m genai_jobs`.)*

---

### 2. Filter by Specific Companies
Specify one or more target companies using `-c` or `--company` (accepts full names or aliases like `JPMC`, `HCL`, `MSFT`, `Google`):
```bash
# Query Big Tech / FAANG
genai-jobs -c Google -c Microsoft -c Apple -c Amazon

# Query Financial Services & Banks
genai-jobs -c "JP Morgan Chase" -c "Goldman Sachs" -c "Wells Fargo" -c DBS -c Barclays

# Query AI, Data & Product Companies
genai-jobs -c Salesforce -c Adobe -c Quantiphi -c "Tiger Analytics" -c Flipkart -c JODO
```

---

### 3. Filter by Location (India Focus)
By default, the tool **strictly searches across all of India** (any city, tech hub, or pan-India remote role). Narrow to specific cities with `-l` or `--location`:
```bash
# Default: all Indian tech hubs and remote roles
genai-jobs

# Narrow to Bengaluru, Hyderabad, Pune, or Gurugram
genai-jobs -l Bengaluru
genai-jobs -l Hyderabad
genai-jobs -l Pune
genai-jobs -l Gurugram
```

---

### 4. Customise Posting Recency (Days)
```bash
# Last 3 days only
genai-jobs -d 3

# Last 14 days
genai-jobs -d 14
```

---

### 5. Experience Filter Controls
Defaults to `<4` years with strict verification enabled. Override with `-x` / `--experience`:
```bash
# Strictly less than 4 years (default)
genai-jobs -x "<4"

# Target specifically 2 to 4 years
genai-jobs -x "2-4"

# Freshers & entry level only
genai-jobs -x fresher

# Include unstated-experience roles as well
genai-jobs --allow-unstated

# Disable experience filter entirely
genai-jobs -x all
```

---

### 6. List All 34 Configured Companies
```bash
genai-jobs --list-companies
```

---

### 7. Choose Specific Career-Portal Engines
By default, `genai-jobs` runs all career-portal engines concurrently (`all`). Restrict with `-s` or `--sources`:
```bash
# Run Direct Official Career Portal APIs only (ultra-fast across 18 company portals)
genai-jobs -s ats

# Run DDG Career-Portal ATS Dorking only
genai-jobs -s dork

# Run all company career-portal engines concurrently (default)
genai-jobs -s all
```

---

### 8. View All CLI Options
```bash
genai-jobs --help
```

---

## 📺 Terminal Output

Every run prints two sections directly in your terminal without creating any extra files on disk:

1. **Summary Table** — Numbered rows showing `Company`, clickable `Job Title`, `Location`, `Posted`, `Exp`, `Skills`, and `Source`.
2. **Job URLs** — Clean, indexed list (`[1] Company — Title · Location`) with each full, untruncated career-portal URL on its own line so you can either Cmd/Ctrl+Click (OSC-8 hyperlink) or copy-paste cleanly in any terminal.

---

## ⚙️ Loose Coupling & External Configuration

All configuration lives in the `config/` directory:

| File | What it Controls |
|---|---|
| [`config/companies.json`](config/companies.json) | The 34 target companies, optional CLI shorthand aliases, and their official ATS career domains. |
| [`config/skills.json`](config/skills.json) | Core search terms (`Generative AI`, `Agentic AI`, `LLM`, `RAG`) and skills matching/tagging rules. |
| [`config/settings.json`](config/settings.json) | Minimal runtime defaults: `default_days` (7), `default_experience` ("<4"), `strict_experience` (true), `default_location` ("India"), `default_max_results` (0 = all), and `default_sources` ("all"). |

> **Custom Config Directory**: Pass `--config-dir <path>` or set `GENAI_JOBS_CONFIG_DIR` to point to a custom configuration folder without modifying project files.

---

## 🛡️ Anti-Bot & Rate-Limit Protections

* **Stealth Headers**: Dynamic emulation of modern Chrome/Safari/Firefox desktop browsers with Client Hints (`sec-ch-ua`, `sec-fetch-*`).
* **Jitter Delay**: Paces search requests with randomized delays to avoid tripping WAF burst rate limits.
* **Resilient Multi-Engine Failover**: Uses direct JSON/GraphQL/SSR endpoints alongside parallel ATS dorking with rate-limit backoff and circuit breaking.

---

## 🏗️ Project Structure

```
job-tool/
├── .gitignore                  # Git ignore rules (.venv, caches, .env, OS/IDE files)
├── pyproject.toml              # Build system, metadata, dependencies & CLI script entry
├── genai-jobs                  # Executable Bash wrapper invoking .venv/bin/genai-jobs
├── README.md                   # Documentation, usage guide & codebase reference
├── config/                     # External Configuration (Loose Coupling)
│   ├── companies.json          # 34 target companies, optional shorthand aliases & ATS domains
│   ├── skills.json             # Core search terms & GenAI/Agentic/LLM/RAG matching rules
│   └── settings.json           # Minimal CLI runtime defaults (days, exp, location, sources)
└── genai_jobs/                 # Core Application Package
    ├── __init__.py             # Package version export (__version__)
    ├── __main__.py             # Module entry point for `python -m genai_jobs`
    ├── cli.py                  # Typer CLI interface, flags, validation & logging setup
    ├── config.py               # Pydantic config schemas, directory discovery & JSON loader
    ├── constants.py            # Dynamic configuration bridge & runtime reload support
    ├── models.py               # JobPosting Pydantic data model, dedup key & display helpers
    ├── pipeline.py             # Concurrent orchestrator, post-filtering & Rich terminal output
    ├── engines/                # Career-Portal Job Fetching Engines
    │   ├── __init__.py         # Re-exports Direct ATS, Dork & Amazon API fetchers
    │   ├── amazon_api.py       # Amazon Jobs public JSON API fetcher
    │   ├── ats_engine.py       # 17 direct career portal APIs (Google, Workday, Oracle, GS, Deloitte, Synopsys, Phenom)
    │   └── dork_engine.py      # Parallel DuckDuckGo site-restricted career-portal dorking engine
    └── utils/                  # Shared Domain Filtering & Anti-Bot Utilities
        ├── __init__.py         # Re-exports filter, location & experience helpers
        ├── filters.py          # Company resolution, GenAI matching, India location & exp parser
        └── security.py         # Browser fingerprinting, stealth headers & jitter delays
```

---

## 📖 Codebase Guide: What Each File Contains

### Execution Flow at a Glance

```text
genai_jobs/cli.py (or __main__.py)
   ├── loads external config via genai_jobs/config.py & genai_jobs/constants.py
   └── calls genai_jobs/pipeline.py :: run_pipeline()
         ├── runs active career-portal engines concurrently (ThreadPoolExecutor):
         │     ├── genai_jobs/engines/amazon_api.py     (Amazon JSON API)
         │     ├── genai_jobs/engines/ats_engine.py     (17 direct career portal APIs/SSR)
         │     └── genai_jobs/engines/dork_engine.py    (DuckDuckGo site-restricted ATS dorking)
         ├── engines normalize hits into genai_jobs/models.py :: JobPosting
         │     └── using genai_jobs/utils/filters.py (company, GenAI, location, exp, skills)
         │     └── and genai_jobs/utils/security.py (stealth headers, jitter delays)
         └── merges, deduplicates, filters, sorts, and renders table + URLs in terminal via:
               └── genai_jobs/pipeline.py :: render_rich_table()
```

---

### 1. Root & Packaging Files

| File | Responsibility & Key Contents |
|---|---|
| [`.gitignore`](.gitignore) | Prevents committing local virtual environments (`.venv/`, `venv/`, `env/`), `.env` secrets, Python caches & build artifacts (`__pycache__/`, `*.egg-info/`, `dist/`, `build/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`), logs, and OS/IDE files (`.DS_Store`, `.vscode/`, `.idea/`). |
| [`pyproject.toml`](pyproject.toml) | PEP 517/621 build specification (`setuptools.build_meta`), package metadata (`genai-jobs` v1.0.0, Python `>=3.10`), runtime dependencies (`ddgs`, `typer`, `rich`, `httpx`, `tenacity`, `pydantic`), and `[project.scripts]` entry point (`genai-jobs = "genai_jobs.cli:app"`). |
| [`genai-jobs`](genai-jobs) | Executable Bash wrapper script that delegates directly to `.venv/bin/genai-jobs` so the CLI can be run with `./genai-jobs` without manually activating the virtual environment. |
| [`README.md`](README.md) | Project overview, installation instructions, CLI usage examples, configuration reference, and this file-by-file architecture guide. |

---

### 2. External Configuration (`config/`)

| File | Responsibility & Key Contents |
|---|---|
| [`config/companies.json`](config/companies.json) | Holds the `companies` array of 34 target organizations. Each entry specifies canonical `name`, optional CLI shorthand `aliases`, and official `ats_domains` (career portal hostnames/paths for ATS dorking and URL matching). |
| [`config/skills.json`](config/skills.json) | Holds `search_terms` (`Generative AI`, `Agentic AI`, `LLM`, `RAG` — shared as the single source of truth across all engines) and `skills_detection` (keyword variants used for matching and tagging `Generative AI`, `Agentic AI`, `LLM`, and `RAG`). |
| [`config/settings.json`](config/settings.json) | Holds lightweight CLI runtime defaults: `default_days` (`7`), `default_experience` (`"<4"`), `strict_experience` (`true`), `default_location` (`"India"`), `default_max_results` (`0`), and `default_sources` (`"all"`). |

---

### 3. Core Application & Entry Points (`genai_jobs/`)

| File | Responsibility & Key Contents |
|---|---|
| [`genai_jobs/__init__.py`](genai_jobs/__init__.py) | Package initializer; defines and exports `__version__` (`"1.0.0"`). |
| [`genai_jobs/__main__.py`](genai_jobs/__main__.py) | Module execution entry point enabling `python -m genai_jobs`; imports and invokes `app()` from `genai_jobs.cli`. |
| [`genai_jobs/cli.py`](genai_jobs/cli.py) | Typer CLI definition (`app` and `main()`). Parses and validates CLI flags (`--company`/`-c`, `--location`/`-l`, `--days`/`-d`, `--max-results`/`-m`, `--experience`/`-x`, `--strict-exp`/`--allow-unstated`, `--sources`/`-s`, `--config-dir`, `--list-companies`, `--verbose`/`-v`), configures logging (`_configure_logging()`), handles `--config-dir` reloads, resolves target companies, and invokes `run_pipeline()`. |
| [`genai_jobs/config.py`](genai_jobs/config.py) | Pydantic config schemas (`CompanyItem`, `CompaniesConfig`, `SkillsConfig`, `SettingsConfig`, `AppConfig`), config directory discovery (`discover_config_dir()` checking `--config-dir` → `GENAI_JOBS_CONFIG_DIR` → `./config` → repo `config/`), singleton loader (`load_config()`, `get_config()`), and dynamic accessors (`get_canonical_companies()`, `get_alias_to_canonical()`, `get_company_ats_domains()`, `get_search_terms()`, `get_match_keywords()`, `get_skills_detection_map()`). |
| [`genai_jobs/constants.py`](genai_jobs/constants.py) | Loose-coupling configuration bridge exposing module-level constants (`CANONICAL_COMPANIES`, `COMPANY_ALIASES`, `ALIAS_TO_CANONICAL`, `COMPANY_ATS_DOMAINS`, `SEARCH_TERMS`, `MATCH_KEYWORDS`, `SKILLS_DETECTION_MAP`, `DEFAULT_*`, `MAX_RETRY_ATTEMPTS`, `AMAZON_JOBS_API`) along with `refresh_constants()` and `__getattr__()` for live reloads. |
| [`genai_jobs/models.py`](genai_jobs/models.py) | Shared Pydantic `JobPosting` model returned by all engines. Stores `company`, `title`, `location`, `date_posted`, `url`, `source`, `description_snippet`, `exp_min`, `exp_max`, and `skills`; provides field validators (`_clean_url`, `_strip_strings`), `dedup_key` for cross-engine deduplication, and display properties (`date_str`, `experience_label`, `skills_label`). |
| [`genai_jobs/pipeline.py`](genai_jobs/pipeline.py) | Pipeline orchestrator (`run_pipeline()`) and terminal renderer (`render_rich_table()`). Determines active career-portal engines based on `--sources` (`ats` / `dork` / `all`) and target companies, runs up to 3 engines concurrently (`amazon`, `ats`, `dork`) via `ThreadPoolExecutor` with thread-safe Rich progress bars (`_make_progress()`), merges/deduplicates (`_deduplicate()`), sorts (`_sort_jobs()` by company name ↑ and posting date ↓), enforces strict India location and experience rules (`_filter_by_experience()`), and prints the Rich table + full clickable Job URLs in the terminal. |

---

### 4. Job Fetching Engines (`genai_jobs/engines/`)

| File | Responsibility & Key Contents |
|---|---|
| [`genai_jobs/engines/__init__.py`](genai_jobs/engines/__init__.py) | Package exports for `fetch_via_ats_apis`, `fetch_via_dork`, and `fetch_amazon_jobs`. |
| [`genai_jobs/engines/amazon_api.py`](genai_jobs/engines/amazon_api.py) | **Amazon JSON API Engine** (`fetch_amazon_jobs()`, `get_amazon_search_terms()`). Queries `amazon.jobs/en/search.json` (`_get_amazon_page()` with Tenacity retries and stealth headers) across the configured `search_terms` (`Generative AI`, `Agentic AI`, `LLM`, `RAG`), handles offset pagination (`_MAX_OFFSET_PER_TERM`), cutoff dates (`_parse_date()`), location verification (`_location_matches()`), and converts hits into `JobPosting` objects (`_build_job()`). |
| [`genai_jobs/engines/ats_engine.py`](genai_jobs/engines/ats_engine.py) | **Direct Career Portal API Engine** (`fetch_via_ats_apis()`, `get_supported_ats_companies()`). Concurrently queries 17 official ATS endpoints/SSR pages directly using the configured `search_terms` (`Generative AI`, `Agentic AI`, `LLM`, `RAG`): <br>• **Google Careers** (`_fetch_google_careers()`): extracts `AF_initDataCallback` JSON payloads.<br>• **Workday CXS** (`_fetch_workday_company()`, `_WORKDAY_PORTALS`): Salesforce, Adobe, Micron, Berkadia, Disney, Invesco, Quantiphi, Wells Fargo with concurrent job-detail hydration.<br>• **Oracle Cloud HCM** (`_fetch_oracle_company()`, `_ORACLE_PORTALS`): JP Morgan Chase, CHUBB, Honeywell REST APIs + requisition detail hydration.<br>• **Goldman Sachs** (`_fetch_goldman_sachs()`): Higher GraphQL API (`GetRoles`).<br>• **Deloitte South Asia** (`_fetch_deloitte_portal()`): `southasiacareers.deloitte.com` search & detail scraping.<br>• **Synopsys** (`_fetch_synopsys_portal()`): TalentBrew endpoint on `careers.synopsys.com`.<br>• **Phenom People SSR** (`_fetch_phenom_company()`, `_PHENOM_PORTALS`): eBay and HPE `phApp.ddo` payloads. |
| [`genai_jobs/engines/dork_engine.py`](genai_jobs/engines/dork_engine.py) | **DuckDuckGo Career-Portal ATS Dorking Engine** (`fetch_via_dork()`). Builds `site:`-restricted queries exclusively from configured `ats_domains` + dynamic `search_terms` (`_build_genai_ddg_clause()`) + location clauses (`_build_dork_query()`), skips companies without configured career domains, executes searches via `ddgs` (`_ddg_search()`) in parallel with rate-limit retry and circuit breaking (`rl_state`), filters out career landing/blog pages, verifies exact domain ownership (`company_from_url()`), enforces India location & GenAI matching, and parses snippets into `JobPosting` objects (`_parse_ddg_result()`). |

---

### 5. Shared Utilities (`genai_jobs/utils/`)

| File | Responsibility & Key Contents |
|---|---|
| [`genai_jobs/utils/__init__.py`](genai_jobs/utils/__init__.py) | Re-exports company, GenAI, location, and experience utilities from `filters.py`. |
| [`genai_jobs/utils/filters.py`](genai_jobs/utils/filters.py) | Central filtering and normalization logic driven by `config/*.json`: <br>• **Company normalization**: `resolve_company()`, `validate_company_names()`, `company_from_url()`.<br>• **GenAI & skill matching**: `_clean_description_for_matching()` (strips corporate PR/HR boilerplate), `_has_keyword()` (word-boundary regex), `matches_genai()`, `detect_skills()`, `truncate()`.<br>• **India location verification**: `is_india_location()` (strictly accepts Indian cities/states/pan-India while rejecting foreign-only roles) and `extract_india_location()` (normalizes city names e.g. `Bangalore` → `Bengaluru, India`).<br>• **Experience parsing & filtering**: `infer_seniority_from_title()`, `parse_experience()`, `parse_experience_filter()`, `job_matches_experience()`. |
| [`genai_jobs/utils/security.py`](genai_jobs/utils/security.py) | Anti-bot and HTTP stealth helpers: `get_stealth_headers()` (rotates Chrome/Safari/Firefox User-Agents, `sec-ch-ua`, and `Sec-Fetch-*` headers) and `apply_jitter_delay()` (randomized request pacing). |
