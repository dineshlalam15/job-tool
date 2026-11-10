# 🤖 genai-jobs

> **Production-grade Python CLI tool** that fetches the latest **Generative AI, Agentic AI, and Machine Learning job openings** across **34 top-tier tech companies** and delivers direct, clickable application links straight to your terminal.

Built specifically for software and AI engineers (e.g., with ~2 years of experience) who want to skip manually browsing dozens of individual company career portals and aggregators.

---

## ✨ Features & Architecture

| Capability | Details |
|---|---|
| **34 Target Companies** | Pre-configured for Google, Microsoft, Apple, Amazon, Salesforce, Disney, IBM Labs, Deloitte, Quantiphi, JP Morgan Chase, Goldman Sachs, Wells Fargo, DBS, Micron, Synopsys, Samsung, Berkadia, Barclays, Invesco, Tiger Analytics, Verisk Analytics, ADP, Coforge, CHUBB, ICICI Bank, Axis Bank, Adobe, HPE, eBay, Flipkart, JODO, Honeywell, HCL, and Cyient. |
| **Strict India Location** | **Strictly searches and filters for jobs within India only**. Accepts any location within India (Bengaluru, Hyderabad, Pune, Mumbai, Gurugram, Noida, Chennai, Delhi NCR, Kolkata, Pan-India Remote), while automatically and strictly filtering out any international/foreign roles (USA, UK, Singapore, Europe, etc.). |
| **Strict Experience Filtering** | Profile-matched for **< 4 years (or 2–4 years)** experience. Eliminates senior positions ($\ge 4$ yrs, $5+$ yrs, $11–15$ yrs, Senior, Lead, Manager, Architect, Principal, Staff, Engineer III, MTS 3+). |
| **Weekly Timeframe** | Defaults to active jobs posted in the **last 7 days** (`default_days: 7`). |
| **Fetch All Openings (No Capping)** | Defaults to fetching **all** matching job openings without artificial caps (`default_max_results: 0`). You can optionally pass `-m <N>` to cap results. |
| **Tech Stack Focus** | Targets roles requiring **Generative AI, Agentic AI, RAG, Python, FastAPI, LLMs, LangChain, LangGraph, Prompt Engineering, AWS Cloud, and Azure AI**. |
| **Multi-Source Fetching** | Runs 4 concurrent engines: **Amazon JSON API**, **Direct ATS Portals Engine** (`-s ats` supporting 18 direct company career portals: Amazon, Google, Salesforce, Adobe, Goldman Sachs, Deloitte, JP Morgan Chase, Micron, Disney, Wells Fargo, Honeywell, CHUBB, Invesco, Quantiphi, Berkadia, Synopsys, eBay, HPE), **Fast Two-Phase JobSpy** (Indeed, Naukri, LinkedIn), and **Parallel DuckDuckGo ATS Dorking**. |
| **Anti-Bot & Stealth Security** | Rotates modern desktop browser User-Agents (Chrome 131, Safari 18, Firefox 133), Client Hints (`sec-ch-ua`), and Sec-Fetch directives with randomized jitter pacing to bypass Cloudflare/Akamai bot detection. |
| **Pure CLI & Auto Reports** | Clean Rich terminal table with clickable URLs, plus auto-generated reports: `genai_jobs_report.md` (Markdown), `genai_jobs_report.csv` (Spreadsheet), and `genai_jobs_report.json` (Structured JSON). No web frontend bloat. |
| **100% Loose Coupling** | All companies, aliases, career portal domains, skills, keywords, and runtime settings are configured externally in `config/*.json`. Zero code changes needed to add companies or tweak skills. |

---

## 🚀 Setup & Installation

### 1. Clone / Navigate to Project Directory
```bash
cd /Users/dineshlalam15/job-tool
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
*(This makes the `genai-jobs` command available anywhere in your active virtual environment).*

---

## 🖥️ How to Run the Application

### 1. Default Run (Recommended)
Fetches all matching jobs across all 34 companies in India posted in the **last 7 days**, strictly filtered for **< 4 years / 2–4 years experience**:
```bash
genai-jobs
```
*(Alternatively, without activating the venv: `.venv/bin/genai-jobs` or `python -m genai_jobs`)*

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

After every run, 3 report files are automatically saved in the current directory:

| File | Purpose |
|---|---|
| **`genai_jobs_report.md`** | Clean Markdown report formatted as a table with clickable `[Apply ↗]` application links. |
| **`genai_jobs_report.csv`** | Full spreadsheet export with all columns (Company, Title, Location, Date Posted, Experience, Skills, Source, URL). |
| **`genai_jobs_report.json`** | Structured JSON dataset with metadata and job items for programmatic use. |

---

## ⚙️ Loose Coupling & External Configuration

All configuration lives in the `config/` directory:

| File | What it Controls |
|---|---|
| [`config/companies.json`](file:///Users/dineshlalam15/job-tool/config/companies.json) | The 34 target companies, their regional aliases, and their direct ATS career domains (Workday, Oracle Cloud, Taleo, Lever, SmartRecruiters, etc.). |
| [`config/skills.json`](file:///Users/dineshlalam15/job-tool/config/skills.json) | Primary search terms, Tier-1 & Tier-2 keywords, and skills detection rules (GenAI, Agentic AI, RAG, Python, FastAPI, LLM, LangChain, LangGraph, AWS, Azure). |
| [`config/settings.json`](file:///Users/dineshlalam15/job-tool/config/settings.json) | Runtime defaults: `default_days` (7), `default_experience` ("<4"), `default_max_results` (0 = all), `strict_experience` (true), `inter_request_delay` (0.4s), and optional `proxies`. |

> **Custom Config Directory**: You can pass `--config-dir <path>` or set the `GENAI_JOBS_CONFIG_DIR` environment variable to point to a custom configuration folder without modifying the project files.

---

## 🛡️ Anti-Bot & Rate-Limit Protections

* **Stealth Headers**: Dynamic emulation of modern Chrome/Safari desktop browsers with Client Hints (`sec-ch-ua`, `sec-fetch-*`).
* **Jitter Delay**: Paces search requests with randomized delays (`inter_request_delay: 0.4` ± jitter) to avoid tripping WAF burst rate limits.
* **Resilient Multi-Engine Failover**: If an aggregator throttles requests, the tool automatically relies on the other engines (Amazon Direct API, Indeed, Naukri, and ATS dorking), ensuring a resilient run.

---

## 🏗️ Project Structure

```
job-tool/
├── pyproject.toml              # Build & dependency metadata
├── requirements.txt            # Pinned requirements
├── README.md                   # Complete application guide
├── config/                     # External Configuration (Loose Coupling)
│   ├── companies.json          # 34 Target companies, aliases & ATS domains
│   ├── skills.json             # Search queries & skills detection taxonomy
│   └── settings.json           # Default days (7), experience (<4), timeouts
└── genai_jobs/                 # Application Package
    ├── __init__.py
    ├── __main__.py             # Entry point for python -m genai_jobs
    ├── cli.py                  # Typer CLI definition & command handling
    ├── config.py               # Dynamic config loader & Pydantic models
    ├── constants.py            # Dynamic configuration bridge
    ├── models.py               # JobPosting Pydantic data model
    ├── pipeline.py             # Orchestrator & Rich live progress UI
    ├── engines/                # Fetching Engines
    │   ├── amazon_api.py       # Amazon native search JSON API fetcher
    │   ├── ats_engine.py       # Direct official ATS career portal APIs (Google, Workday, Oracle, GS, Deloitte, Synopsys, Phenom)
    │   ├── dork_engine.py      # Parallel DuckDuckGo ATS career portal dorker
    │   └── jobspy_engine.py    # Fast two-phase Indeed, Naukri & LinkedIn scraper
    ├── output/                 # Exporters
    │   └── formatters.py       # Terminal Rich table, Markdown, CSV, JSON
    └── utils/                  # Core Utilities
        ├── filters.py          # Strict experience parser & keyword matcher
        └── security.py         # Stealth headers, user-agents & anti-bot jitter
```
