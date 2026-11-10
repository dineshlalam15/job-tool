# 🤖 genai-jobs

> **Production-grade Python CLI tool** that fetches the latest **Generative AI, Agentic AI, and Machine Learning job openings** across **34 top-tier tech companies** and delivers direct, clickable application links straight to your terminal.

Built specifically for software and AI engineers (e.g., with ~2 years of experience) who want to skip manually browsing dozens of individual company career portals and aggregators.

---

## ✨ Features & Architecture

| Capability | Details |
|---|---|
| **34 Target Companies** | Pre-configured for Google, Microsoft, Apple, Amazon, Salesforce, Disney, IBM Labs, Deloitte, Quantiphi, JP Morgan Chase, Goldman Sachs, Wells Fargo, DBS, Micron, Synopsys, Samsung, Berkadia, Barclays, Invesco, Tiger Analytics, Verisk Analytics, ADP, Coforge, CHUBB, ICICI Bank, Axis Bank, Adobe, HPE, eBay, Flipkart, JODO, Honeywell, HCL, and Cyient. |
| **Strict India Location** | **Strictly searches and filters for jobs within India only**. Accepts any location within India (Bengaluru, Hyderabad, Pune, Mumbai, Gurugram, Noida, Chennai, Delhi NCR, Kolkata, Pan-India Remote), while automatically and strictly filtering out any international/foreign roles (USA, UK, Singapore, Europe, etc.). |
| **Strict Experience Filtering** | Profile-matched for **< 4 years (or 2–4 years)** experience. Eliminates senior positions (≥ 4 yrs, 5+ yrs, 11–15 yrs, Senior, Lead, Manager, Architect, Principal, Staff, Engineer III, MTS 3+). |
| **Weekly Timeframe** | Defaults to active jobs posted in the **last 7 days** (`default_days: 7`). |
| **Fetch All Openings (No Capping)** | Defaults to fetching **all** matching job openings without artificial caps (`default_max_results: 0`). You can optionally pass `-m <N>` to cap results. |
| **Tech Stack Focus** | Targets roles requiring **Generative AI, Agentic AI, RAG, Python, FastAPI, LLMs, LangChain, LangGraph, Prompt Engineering, AWS Cloud, and Azure AI**. |
| **Multi-Source Fetching** | Runs 4 concurrent engines: **Amazon JSON API**, **Direct ATS Portals Engine** (`-s ats` supporting 18 direct company career portals: Amazon, Google, Salesforce, Adobe, Goldman Sachs, Deloitte, JP Morgan Chase, Micron, Disney, Wells Fargo, Honeywell, CHUBB, Invesco, Quantiphi, Berkadia, Synopsys, eBay, HPE), **Fast Two-Phase JobSpy** (Indeed, Naukri, LinkedIn), and **Parallel DuckDuckGo ATS Dorking**. |
| **Anti-Bot & Stealth Security** | Rotates modern desktop browser User-Agents (Chrome 131, Safari 18, Firefox 133), Client Hints (`sec-ch-ua`), and Sec-Fetch directives with randomized jitter pacing to bypass Cloudflare/Akamai bot detection. |
| **Pure CLI & Auto Reports** | Clean Rich terminal table with clickable URLs, plus auto-generated reports: `genai_jobs_report.md` (Markdown), `genai_jobs_report.csv` (Spreadsheet), and `genai_jobs_report.json` (Structured JSON). No web frontend bloat. |
| **100% Loose Coupling** | All companies, aliases, career portal domains, skills, keywords, and runtime settings are configured externally in `config/*.json`. Zero code changes needed to add companies or tweak skills. |

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

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install the CLI in Editable Mode
```bash
pip install -e .
```
*(This makes the `genai-jobs` command available anywhere in your active virtual environment.)*

---

## 🖥️ How to Run the Application

### 1. Default Run (Recommended)
Fetches all matching jobs across all 34 companies in India posted in the **last 7 days**, strictly filtered for **< 4 years / 2–4 years experience**:
```bash
genai-jobs
```
*(Alternatively, without activating the venv: `./genai-jobs`, `.venv/bin/genai-jobs`, or `python -m genai_jobs`.)*

---

### 2. Filter by Specific Companies
You can specify one or more target companies using `-c` or `--company` (accepts full names or aliases like `JPMC`, `HCL`, `MSFT`, `Google`):
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
By default, the application **strictly searches across all of India** (any city, tech hub, or pan-India remote role). You can also narrow your search to specific Indian hubs using `-l` or `--location`:
```bash
# Default: all Indian tech hubs and remote roles
genai-jobs

# Narrow to Bengaluru
genai-jobs -l Bengaluru

# Narrow to Hyderabad
genai-jobs -l Hyderabad

# Narrow to Pune
genai-jobs -l Pune

# Narrow to Gurugram / Delhi NCR
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
The tool defaults to `<4` years with strict verification enabled. You can pass custom experience criteria using `-x` or `--experience`:
```bash
# Strictly less than 4 years (default)
genai-jobs -x "<4"

# Target specifically 2 to 4 years
genai-jobs -x "2-4"

# Freshers & entry level only
genai-jobs -x fresher

# Show unstated experience roles as well
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

### 7. Choose Specific Fetching Engines
By default, `genai-jobs` runs all 4 engines concurrently (`all`). You can restrict to specific sources using `-s` or `--sources`:
```bash
# Run Direct Official Career Portal APIs only (ultra-fast ~15s across 18 company portals)
genai-jobs -s ats

# Run JobSpy only (Indeed, Naukri, LinkedIn)
genai-jobs -s jobspy

# Run DDG ATS Dorking only
genai-jobs -s dork

# Run all 4 engines concurrently (default)
genai-jobs -s all
```

---

### 8. View All CLI Options
```bash
genai-jobs --help
```

---

## 📂 Output Files

After every run, 3 report files are automatically saved in the output directory (default: current directory, customizable with `-o` / `--output-dir`):

| File | Purpose |
|---|---|
| **`genai_jobs_report.md`** | Clean Markdown report formatted as a table with run metadata, clickable `[Apply ↗]` links, and a company-wise job count breakdown. |
| **`genai_jobs_report.csv`** | Full UTF-8 spreadsheet export with all columns (`#`, `company`, `title`, `location`, `date_posted`, `experience`, `skills`, `source`, `url`). |
| **`genai_jobs_report.json`** | Structured JSON dataset with `generated_at`, `total_jobs`, and `jobs` items for programmatic use. |

*(These report files, along with `.venv/`, caches, and `.env` secrets, are excluded from Git tracking via `.gitignore`.)*

---

## ⚙️ Loose Coupling & External Configuration

All configuration lives in the `config/` directory:

| File | What it Controls |
|---|---|
| [`config/companies.json`](config/companies.json) | The 34 target companies, their regional aliases, direct ATS career domains (Workday, Oracle Cloud, Taleo, Lever, SmartRecruiters, etc.), and API adapter flags. |
| [`config/skills.json`](config/skills.json) | Primary search terms, Tier-1 & Tier-2 GenAI/AI/ML keywords, and skills detection rules (GenAI, Agentic AI, RAG & Vector DB, Python & FastAPI, LLM & Prompt Eng, LangChain & LangGraph, Cloud AWS/Azure, AI/ML). |
| [`config/settings.json`](config/settings.json) | Runtime defaults: `default_days` (7), `default_experience` ("<4"), `strict_experience` (true), `default_location` ("India"), `default_max_results` (0 = all), `default_sources` ("all"), `jobspy_sites`, `inter_request_delay` (0.4s), timeouts, retry settings, `amazon_api_url`, and optional `proxies`. |

> **Custom Config Directory**: You can pass `--config-dir <path>` or set the `GENAI_JOBS_CONFIG_DIR` environment variable to point to a custom configuration folder without modifying the project files.

---

## 🛡️ Anti-Bot & Rate-Limit Protections

* **Stealth Headers**: Dynamic emulation of modern Chrome/Safari/Firefox desktop browsers with Client Hints (`sec-ch-ua`, `sec-fetch-*`).
* **Jitter Delay**: Paces search requests with randomized delays (`inter_request_delay: 0.4` ± jitter) to avoid tripping WAF burst rate limits.
* **Resilient Multi-Engine Failover**: If an aggregator throttles requests, the tool automatically relies on the other engines (Amazon Direct API, Direct ATS Portals, Indeed, Naukri, and ATS dorking), ensuring a resilient run.

---

## 🏗️ Project Structure

```
job-tool/
├── .gitignore                  # Git ignore rules (.venv, caches, .env, generated reports)
├── pyproject.toml              # Build system, metadata, dependencies & console script entry
├── requirements.txt            # Runtime pip dependencies
├── genai-jobs                  # Executable Bash wrapper invoking .venv/bin/genai-jobs
├── README.md                   # Documentation, usage guide & codebase reference
├── config/                     # External Configuration (Loose Coupling)
│   ├── companies.json          # 34 target companies, aliases, ATS domains & API adapter flags
│   ├── skills.json             # Search queries, Tier-1/Tier-2 keywords & skill detection map
│   └── settings.json           # Runtime defaults, JobSpy boards, HTTP timeouts & retry config
└── genai_jobs/                 # Core Application Package
    ├── __init__.py             # Package version export (__version__)
    ├── __main__.py             # Module entry point for `python -m genai_jobs`
    ├── cli.py                  # Typer CLI interface, flags, validation & logging setup
    ├── config.py               # Pydantic config schemas, directory discovery & JSON loader
    ├── constants.py            # Dynamic configuration bridge & runtime reload support
    ├── models.py               # JobPosting Pydantic data model, dedup key & display helpers
    ├── pipeline.py             # Concurrent orchestrator, post-filtering, Rich progress & export
    ├── engines/                # Multi-Source Job Fetching Engines
    │   ├── __init__.py         # Re-exports JobSpy, Dork & Amazon API fetchers
    │   ├── amazon_api.py       # Amazon Jobs public JSON API fetcher
    │   ├── ats_engine.py       # Direct career portal APIs (Google, Workday, Oracle, GS, Deloitte, Synopsys, Phenom)
    │   ├── dork_engine.py      # Parallel DuckDuckGo site-restricted ATS dorking engine
    │   └── jobspy_engine.py    # Fast two-phase Indeed, Naukri & LinkedIn aggregator scraper
    ├── output/                 # Terminal Rendering & File Exporters
    │   ├── __init__.py         # Re-exports render_rich_table and export
    │   └── formatters.py       # Rich terminal table + CSV, JSON & Markdown report writers
    └── utils/                  # Shared Domain Filtering & Anti-Bot Utilities
        ├── __init__.py         # Re-exports filter, location & experience helpers
        ├── filters.py          # Company resolution, GenAI matching, India location & exp parser
        └── security.py         # Browser fingerprinting, stealth headers, jitter & WAF detection
```

---

## 📖 Codebase Guide: What Each File Contains

### Execution Flow at a Glance

```text
genai_jobs/cli.py (or __main__.py)
   ├── loads external config via genai_jobs/config.py & genai_jobs/constants.py
   └── calls genai_jobs/pipeline.py :: run_pipeline()
         ├── runs enabled engines concurrently (ThreadPoolExecutor):
         │     ├── genai_jobs/engines/amazon_api.py     (Amazon JSON API)
         │     ├── genai_jobs/engines/ats_engine.py     (17 direct career portal APIs/SSR)
         │     ├── genai_jobs/engines/jobspy_engine.py  (Indeed, Naukri, LinkedIn)
         │     └── genai_jobs/engines/dork_engine.py    (DuckDuckGo ATS dorking)
         ├── engines normalize hits into genai_jobs/models.py :: JobPosting
         │     └── using genai_jobs/utils/filters.py (company, GenAI, location, exp, skills)
         │     └── and genai_jobs/utils/security.py (stealth headers, jitter delays)
         └── merges, deduplicates, sorts, and renders/saves reports via:
               └── genai_jobs/output/formatters.py (Rich table + CSV / JSON / MD)
```

---

### 1. Root & Packaging Files

| File | Responsibility & Key Contents |
|---|---|
| [`.gitignore`](.gitignore) | Prevents committing local virtual environments (`.venv/`, `venv/`, `env/`), `.env` secrets, Python caches & build artifacts (`__pycache__/`, `*.egg-info/`, `dist/`, `build/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`), logs, OS/IDE files (`.DS_Store`, `.vscode/`, `.idea/`), and generated `genai_jobs_report.*` outputs. |
| [`pyproject.toml`](pyproject.toml) | PEP 517/621 build specification (`setuptools.build_meta`), package metadata (`genai-jobs` v1.0.0, Python `>=3.10`), runtime dependencies, and `[project.scripts]` entry point (`genai-jobs = "genai_jobs.cli:app"`). |
| [`requirements.txt`](requirements.txt) | Direct pip dependency specification (`python-jobspy`, `ddgs`, `duckduckgo-search`, `typer`, `rich`, `httpx`, `pandas`, `tenacity`, `pydantic`). |
| [`genai-jobs`](genai-jobs) | Executable Bash wrapper script that delegates directly to `.venv/bin/genai-jobs` so the CLI can be run with `./genai-jobs` without manually activating the virtual environment. |
| [`README.md`](README.md) | Project overview, installation instructions, CLI usage examples, configuration reference, and this file-by-file architecture guide. |

---

### 2. External Configuration (`config/`)

| File | Responsibility & Key Contents |
|---|---|
| [`config/companies.json`](config/companies.json) | Holds the `companies` array of 34 target organizations. Each entry specifies canonical `name`, `aliases` (used to resolve raw scraper names), `ats_domains` (career portal hostnames/paths for ATS dorking and URL matching), and optional `api_adapter` (e.g., `"amazon"`). |
| [`config/skills.json`](config/skills.json) | Holds `search_terms` (queries sent to JobSpy), `tier1_keywords` (high-signal GenAI/Agentic/RAG/LLM/FastAPI terms), `tier2_keywords` (supporting Python/ML/cloud keywords paired with Tier-1 in descriptions), and `skills_detection` (tag-to-keyword mapping for labeling matched jobs). |
| [`config/settings.json`](config/settings.json) | Holds runtime defaults and scraping parameters: `default_days` (`7`), `default_experience` (`"<4"`), `strict_experience` (`true`), `default_location` (`"India"`), `default_max_results` (`0`), `default_sources` (`"all"`), `jobspy_sites` (`["indeed", "naukri", "linkedin"]`), `inter_request_delay` (`0.4`), `proxies`, `request_timeout_seconds`, retry backoff parameters, and `amazon_api_url`. |

---

### 3. Core Application & Entry Points (`genai_jobs/`)

| File | Responsibility & Key Contents |
|---|---|
| [`genai_jobs/__init__.py`](genai_jobs/__init__.py) | Package initializer; defines and exports `__version__` (`"1.0.0"`). |
| [`genai_jobs/__main__.py`](genai_jobs/__main__.py) | Module execution entry point enabling `python -m genai_jobs`; imports and invokes `app()` from `genai_jobs.cli`. |
| [`genai_jobs/cli.py`](genai_jobs/cli.py) | Typer CLI definition (`app` and `main()`). Parses and validates CLI flags (`--company`/`-c`, `--location`/`-l`, `--days`/`-d`, `--max-results`/`-m`, `--experience`/`-x`, `--strict-exp`/`--allow-unstated`, `--sources`/`-s`, `--export`/`-e`, `--output-dir`/`-o`, `--config-dir`, `--list-companies`, `--verbose`/`-v`), configures logging (`_configure_logging()`), handles `--config-dir` reloads, resolves target companies, and invokes `run_pipeline()`. |
| [`genai_jobs/config.py`](genai_jobs/config.py) | Pydantic config schemas (`CompanyItem`, `CompaniesConfig`, `SkillsConfig`, `SettingsConfig`, `AppConfig`), config directory discovery (`discover_config_dir()` checking `--config-dir` → `GENAI_JOBS_CONFIG_DIR` → `./config` → repo `config/`), singleton loader (`load_config()`, `get_config()`), and dynamic accessor functions (`get_canonical_companies()`, `get_alias_to_canonical()`, `get_company_ats_domains()`, `get_search_terms()`, `get_tier1_keywords()`, `get_tier2_keywords()`, `get_skills_detection_map()`). |
| [`genai_jobs/constants.py`](genai_jobs/constants.py) | Loose-coupling configuration bridge exposing module-level constants (`CANONICAL_COMPANIES`, `COMPANY_ALIASES`, `ALIAS_TO_CANONICAL`, `COMPANY_ATS_DOMAINS`, `SEARCH_TERMS`, `GENAI_TIER1_KEYWORDS`, `GENAI_TIER2_KEYWORDS`, `SKILLS_DETECTION_MAP`, `DEFAULT_*`, `JOBSPY_SITES`, `AMAZON_JOBS_API`, etc.) along with `refresh_constants()` and `__getattr__()` for live reloads. |
| [`genai_jobs/models.py`](genai_jobs/models.py) | Shared Pydantic `JobPosting` model returned by all engines. Stores `company`, `title`, `location`, `date_posted`, `url`, `source`, `description_snippet`, `exp_min`, `exp_max`, and `skills`; provides field validators (`_clean_url`, `_strip_strings`), `dedup_key` for cross-engine deduplication, display properties (`date_str`, `experience_label`, `skills_label`), and `to_dict()`. |
| [`genai_jobs/pipeline.py`](genai_jobs/pipeline.py) | Pipeline orchestrator (`run_pipeline()`). Determines active engines based on `--sources` and target companies, runs up to 4 engines concurrently via `ThreadPoolExecutor` with thread-safe Rich progress bars (`_make_progress()`), merges/deduplicates (`_deduplicate()`), sorts (`_sort_jobs()` by company name ↑ and posting date ↓), enforces strict India location and experience rules (`_filter_by_experience()`), renders the terminal table, and triggers CSV/MD/JSON report export. |

---

### 4. Job Fetching Engines (`genai_jobs/engines/`)

| File | Responsibility & Key Contents |
|---|---|
| [`genai_jobs/engines/__init__.py`](genai_jobs/engines/__init__.py) | Package exports for `fetch_via_jobspy`, `fetch_via_dork`, and `fetch_amazon_jobs`. |
| [`genai_jobs/engines/amazon_api.py`](genai_jobs/engines/amazon_api.py) | **Amazon JSON API Engine** (`fetch_amazon_jobs()`). Queries `amazon.jobs/en/search.json` (`_get_amazon_page()` with Tenacity retries and stealth headers) across `_AMAZON_SEARCH_TERMS` (`Generative AI`, `Agentic AI`, `LLM`, `RAG`, `Machine Learning Python`, `FastAPI`), handles offset pagination (`_MAX_OFFSET_PER_TERM`), cutoff dates (`_parse_date()`), location verification (`_location_matches()`), and converts hits into `JobPosting` objects (`_build_job()`). |
| [`genai_jobs/engines/ats_engine.py`](genai_jobs/engines/ats_engine.py) | **Direct Career Portal API Engine** (`fetch_via_ats_apis()`, `get_supported_ats_companies()`). Concurrently queries 17 official ATS endpoints/SSR pages directly: <br>• **Google Careers** (`_fetch_google_careers()`): extracts `AF_initDataCallback` JSON payloads.<br>• **Workday CXS** (`_fetch_workday_company()`, `_WORKDAY_PORTALS`): Salesforce, Adobe, Micron, Berkadia, Disney, Invesco, Quantiphi, Wells Fargo with concurrent job-detail hydration.<br>• **Oracle Cloud HCM** (`_fetch_oracle_company()`, `_ORACLE_PORTALS`): JP Morgan Chase, CHUBB, Honeywell REST APIs + requisition detail hydration.<br>• **Goldman Sachs** (`_fetch_goldman_sachs()`): Higher GraphQL API (`GetRoles`).<br>• **Deloitte South Asia** (`_fetch_deloitte_portal()`): `southasiacareers.deloitte.com` search & detail scraping.<br>• **Synopsys** (`_fetch_synopsys_portal()`): TalentBrew endpoint on `careers.synopsys.com`.<br>• **Phenom People SSR** (`_fetch_phenom_company()`, `_PHENOM_PORTALS`): eBay and HPE `phApp.ddo` payloads. |
| [`genai_jobs/engines/jobspy_engine.py`](genai_jobs/engines/jobspy_engine.py) | **Two-Phase JobSpy Aggregator Engine** (`fetch_via_jobspy()`). Consolidates `SEARCH_TERMS` into boolean `OR` queries (`_build_consolidated_queries()`), splits scraping across concurrent fast-board (`indeed`, `naukri`) and bounded single-page `linkedin` worker pools (`_scrape_once()`, `_fetch_company_for_sites()`), performs fast pre-filtering (company resolution, cutoff date, India location, title seniority rejection), extracts Naukri experience ranges (`_extract_naukri_exp()`), hydrates surviving LinkedIn candidates via LinkedIn's guest `jobPosting` API (`_fetch_linkedin_guest_description()` with 429 circuit breaking), and emits validated `JobPosting` objects (`_build_job_from_candidate()`). |
| [`genai_jobs/engines/dork_engine.py`](genai_jobs/engines/dork_engine.py) | **DuckDuckGo ATS Dorking Engine** (`fetch_via_dork()`). Builds `site:`-restricted queries from `COMPANY_ATS_DOMAINS` + GenAI/location clauses (`_build_dork_query()`), executes searches via `ddgs` / `duckduckgo_search` (`_ddg_search()`) in parallel with a rate-limit circuit breaker (`rl_state`), filters out career landing/blog pages, verifies domain ownership (`company_from_url()`), enforces India location & GenAI matching, and parses snippets into `JobPosting` objects (`_parse_ddg_result()`). |

---

### 5. Output & Reporting (`genai_jobs/output/`)

| File | Responsibility & Key Contents |
|---|---|
| [`genai_jobs/output/__init__.py`](genai_jobs/output/__init__.py) | Package exports for `render_rich_table` and `export`. |
| [`genai_jobs/output/formatters.py`](genai_jobs/output/formatters.py) | Terminal display and file export logic: `render_rich_table()` (formatted Rich CLI table with clickable apply links), `export_csv()` (`genai_jobs_report.csv`), `export_json()` (`genai_jobs_report.json`), `export_markdown()` (`genai_jobs_report.md` with run metadata, clickable `[Apply ↗]` links, and per-company counts), and the `export()` dispatcher. |

---

### 6. Shared Utilities (`genai_jobs/utils/`)

| File | Responsibility & Key Contents |
|---|---|
| [`genai_jobs/utils/__init__.py`](genai_jobs/utils/__init__.py) | Re-exports company, GenAI, location, and experience utilities from `filters.py`. |
| [`genai_jobs/utils/filters.py`](genai_jobs/utils/filters.py) | Central filtering and normalization logic driven by `config/*.json`: <br>• **Company normalization**: `resolve_company()`, `is_target_company()`, `validate_company_names()`, `company_from_url()`.<br>• **GenAI & skill matching**: `_clean_description_for_matching()` (strips corporate PR/HR boilerplate), `_has_keyword()` (word-boundary regex), `matches_genai()`, `detect_skills()`, `truncate()`.<br>• **India location verification**: `is_india_location()` (strictly accepts Indian cities/states/pan-India while rejecting foreign-only roles) and `extract_india_location()` (normalizes city names e.g. `Bangalore` → `Bengaluru, India`).<br>• **Experience parsing & filtering**: `infer_seniority_from_title()`, `parse_experience()`, `matches_experience()`, `parse_experience_filter()`, `job_matches_experience()`. |
| [`genai_jobs/utils/security.py`](genai_jobs/utils/security.py) | Anti-bot and HTTP stealth helpers: `get_random_user_agent()`, `get_stealth_headers()` (rotates Chrome/Safari/Firefox User-Agents, `sec-ch-ua`, and `Sec-Fetch-*` headers), `apply_jitter_delay()` (randomized pacing to avoid WAF burst limits), and `is_bot_challenge_response()` (detects Cloudflare, Akamai, DataDome, and Incapsula challenge pages). |
