# 🤖 genai-jobs

> **Lightweight, 100% deterministic Python CLI tool** that fetches active **Generative AI, Agentic AI, LLM, and RAG job openings** directly from the official **career portals of 38 top-tier tech and financial companies** and prints matching roles with clickable URLs straight to your terminal.

> **No LLM / AI Model Required:** `genai-jobs` runs completely locally using official career-portal APIs, DuckDuckGo site-restricted search (`ddgs`), and deterministic regex/keyword filtering. **No OpenAI/Gemini/Anthropic API keys, no local LLMs, no GPU, and zero token costs.**

Built for software and AI engineers who want a fast, zero-bloat terminal tool instead of manually browsing dozens of career portals or noisy third-party job boards.

---

## ✨ Key Capabilities

| Capability | Details |
|---|---|
| **Zero LLM / No API Keys** | Pure Python (`httpx`, `ddgs`, `pydantic`, `typer`, `rich`). Requires **no LLM model**, no paid API keys, and no external database. |
| **38 Pre-Configured Companies** | Covers Big Tech, FinTech, Payments, Enterprise AI, and Consulting portals (full table below). |
| **Amazon SDE-1 Only Rule** | For Amazon, automatically filters down to **SDE-1** roles (`Software Development Engineer I` / `SDE I`, or unnumbered `Software Development Engineer` with `< 3 yr` experience), excluding SDE II+, Data Engineer, Applied/Data Scientist, SDET, Intern, and Manager postings. |
| **Strict India Location** | Defaults to **India only** (Bengaluru, Hyderabad, Pune, Mumbai, Gurugram, Noida, Chennai, Delhi NCR, Kolkata, Pan-India hubs), rejecting foreign-only roles unless overridden with `-l`. |
| **Strict Experience Filtering** | Defaults to **`< 4` years** minimum required experience (`strict_experience: true`). Ranges like `3–5 yr` qualify (`3 < 4`), while `4+ yr`, Senior, Lead, Manager, Staff, and Principal roles are excluded. |
| **Weekly Lookback & No Cap** | Defaults to postings from the **last 7 days** (`default_days: 7`) with no artificial result cap (`default_max_results: 0`). |
| **Career-Portal-Only Fetching** | Runs 3 concurrent engines: **Amazon JSON API**, **Direct ATS Portals Engine** (23 official portals), and **Parallel DuckDuckGo ATS Dorking** (`site:` restricted strictly to official company career domains; in default `-s all` mode automatically targets the remaining 14 portals). |
| **100% Loose Coupling** | Customize your preferred companies, aliases, career domains, keywords, and default filters in `config/*.json` (or via `--config-dir`) without touching Python code. |

---

## 🏢 Supported Companies (38)

You can query any company by its canonical name or any listed CLI alias (`-c <name_or_alias>`).

| # | Company | CLI Aliases | Fetching Engine | Official Career / ATS Domains |
|---:|---|---|---|---|
| 1 | **Google** | `alphabet` | Direct ATS API | `careers.google.com`, `google.com/about/careers` |
| 2 | **Microsoft** | `msft` | DDG ATS Dork | `careers.microsoft.com`, `jobs.careers.microsoft.com` |
| 3 | **Apple** | — | DDG ATS Dork | `jobs.apple.com` |
| 4 | **Amazon** *(SDE-1 only)* | `aws` | Amazon JSON API | `amazon.jobs` |
| 5 | **IBM Labs** | `ibm` | DDG ATS Dork | `ibm.com/careers`, `ibm.biz` |
| 6 | **EY** | `ernst & young`, `ernst and young`, `ey india`, `ey gds` | Direct ATS API | `careers.ey.com`, `ey.com/en_in/careers`, `ey.com/en_gl/careers` |
| 7 | **ZS Associates** | `zs`, `zs associates india` | Direct ATS API | `jobs.zs.com`, `careers-zs.icims.com`, `incareers-zs.icims.com`, `zs.com/careers` |
| 8 | **Quantiphi** | — | Direct ATS API | `quantiphi.com/careers`, `quantiphi.wd1.myworkdayjobs.com`, `jobs.lever.co/quantiphi` |
| 9 | **JP Morgan Chase** | `jpmc`, `jpmorgan` | Direct ATS API | `jpmc.fa.oraclecloud.com`, `careers.jpmorgan.com` |
| 10 | **Goldman Sachs** | `gs`, `goldman` | Direct ATS API | `goldmansachs.com/careers`, `goldmansachs.tal.net`, `higher.gs.com` |
| 11 | **Wells Fargo** | — | Direct ATS API | `wellsfargo.com/about/careers`, `wd1.myworkdaysite.com/recruiting/wf/WellsFargoJobs`, `wellsfargojobs.com` |
| 12 | **DBS** | `dbs bank` | DDG ATS Dork | `dbs.com/careers`, `dbs.taleo.net` |
| 13 | **Micron** | — | Direct ATS API | `micron.wd1.myworkdayjobs.com`, `micron.com/careers` |
| 14 | **Synopsys** | — | Direct ATS API | `synopsys.wd1.myworkdayjobs.com`, `synopsys.com/careers`, `careers.synopsys.com` |
| 15 | **Samsung** | — | DDG ATS Dork | `samsung.com/careers`, `sec.taleo.net`, `sri.taleo.net` |
| 16 | **Berkadia** | — | Direct ATS API | `berkadia.wd1.myworkdayjobs.com`, `berkadia.com/careers` |
| 17 | **Invesco** | — | Direct ATS API | `careers.invesco.com`, `invesco.wd1.myworkdayjobs.com/IVZ` |
| 18 | **Verisk Analytics** | `verisk` | DDG ATS Dork | `careers.verisk.com`, `verisk.wd1.myworkdayjobs.com`, `smartrecruiters.com/Verisk` |
| 19 | **ADP** | — | DDG ATS Dork | `jobs.adp.com` |
| 20 | **Coforge** | — | DDG ATS Dork | `careers.coforge.com` |
| 21 | **CHUBB** | — | Direct ATS API | `fa-ewgu-saasfaprod1.fa.ocs.oraclecloud.com`, `careers.chubb.com`, `chubb.com/careers` |
| 22 | **ICICI Lombard** | `icici` | DDG ATS Dork | `icicilombard.peoplestrong.com`, `icicilombard.com/careers` |
| 23 | **Axis Bank** | `axis` | DDG ATS Dork | `axisbank.com/careers`, `axisbank.taleo.net` |
| 24 | **Adobe** | — | Direct ATS API | `adobe.wd5.myworkdayjobs.com`, `careers.adobe.com` |
| 25 | **HPE** | `hewlett packard enterprise` | Direct ATS API | `careers.hpe.com` |
| 26 | **eBay** | — | Direct ATS API | `ebayinc.com/careers`, `jobs.ebayinc.com` |
| 27 | **Flipkart** | — | DDG ATS Dork | `flipkartcareers.com` |
| 28 | **JODO** | — | DDG ATS Dork | `jodo.in/careers`, `jobs.lever.co/jodo` |
| 29 | **Honeywell** | — | Direct ATS API | `ibqbjb.fa.ocs.oraclecloud.com`, `careers.honeywell.com` |
| 30 | **HCL** | `hcltech` | DDG ATS Dork | `hcltech.com/careers` |
| 31 | **Cyient** | — | DDG ATS Dork | `cyient.wd3.myworkdayjobs.com`, `cyient.com/careers` |
| 32 | **Disney** | `hotstar` | Direct ATS API | `disneycareers.com`, `jobs.disneycareers.com`, `join.disneycareers.com`, `disney.wd5.myworkdayjobs.com`, `careers.hotstar.com` |
| 33 | **Caterpillar** | `cat` | Direct ATS API | `cat.wd5.myworkdayjobs.com`, `careers.caterpillar.com` |
| 34 | **Ericsson** | `ericson` | Direct ATS API | `jobs.ericsson.com` |
| 35 | **Visa** | — | Direct ATS API | `visa.wd5.myworkdayjobs.com`, `usa.visa.com/careers`, `visa.com/careers`, `smartrecruiters.com/Visa` |
| 36 | **Mastercard** | `master card` | Direct ATS API | `mastercard.wd1.myworkdayjobs.com`, `careers.mastercard.com` |
| 37 | **American Express** | `amex` | Direct ATS API | `egug.fa.us2.oraclecloud.com`, `careers.americanexpress.com`, `americanexpress.com/en-us/careers`, `aexp.eightfold.ai` |
| 38 | **BNY Mellon** | `bny`, `bank of new york mellon` | Direct ATS API | `eofe.fa.us2.oraclecloud.com`, `bny.com/careers`, `jobs.bnymellon.com` |

> Run `genai-jobs --list-companies` anytime to print the active company list from your configuration.

---

## 🚀 Local Installation (macOS & Windows)

### Prerequisites
* **Python 3.10+** (`python3 --version` on macOS, `python --version` on Windows)
* **Git** (`git --version`)
* Internet connection (for installing Python packages and querying career portals)

---

### Option A: macOS (Terminal / zsh / bash)

1. **Clone and enter the repository:**
   ```bash
   git clone https://github.com/dineshlalam15/job-tool.git
   cd job-tool
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install the CLI in editable mode:**
   ```bash
   pip install -e .
   ```

4. **Verify installation:**
   ```bash
   genai-jobs --help
   ```

---

### Option B: Windows (PowerShell or Command Prompt)

1. **Clone and enter the repository:**
   ```powershell
   git clone https://github.com/dineshlalam15/job-tool.git
   cd job-tool
   ```

2. **Create and activate a virtual environment:**
   * **PowerShell:**
     ```powershell
     python -m venv .venv
     .venv\Scripts\Activate.ps1
     ```
     *(If PowerShell blocks script execution, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, or activate using Command Prompt below.)*
   * **Command Prompt (`cmd.exe`):**
     ```bat
     python -m venv .venv
     .venv\Scripts\activate.bat
     ```

3. **Install the CLI in editable mode:**
   ```powershell
   pip install -e .
   ```

4. **Verify installation:**
   ```powershell
   genai-jobs --help
   ```

---

## 🖥️ How to Run the Application

### On macOS

* **With virtual environment activated** (`source .venv/bin/activate`):
  ```bash
  genai-jobs
  ```
* **Without activating the virtual environment** (run from project root):
  ```bash
  ./genai-jobs
  # or:
  .venv/bin/genai-jobs
  # or:
  .venv/bin/python -m genai_jobs
  ```

### On Windows

* **With virtual environment activated** (`.venv\Scripts\Activate.ps1` or `.venv\Scripts\activate.bat`):
  ```powershell
  genai-jobs
  ```
* **Without activating the virtual environment** (run from project root):
  ```powershell
  .venv\Scripts\genai-jobs.exe
  # or:
  .venv\Scripts\python.exe -m genai_jobs
  ```

---

## 🔍 CLI Usage & Filter Examples

All examples below work identically on **macOS** and **Windows** (using `genai-jobs` when the venv is active, or `./genai-jobs` on macOS / `.venv\Scripts\genai-jobs.exe` on Windows).

### 1. Default Run (Recommended)
Searches all configured companies in **India**, posted in the **last 7 days**, strictly filtered for **`< 4` years** experience (and SDE-1 only for Amazon):
```bash
genai-jobs
```

### 2. Filter by Specific Companies
Pass `-c` / `--company` multiple times using full names or aliases:
```bash
genai-jobs -c Google -c Amazon -c Microsoft -c Apple
genai-jobs -c jpmc -c gs -c "Wells Fargo" -c amex -c Visa -c Mastercard
genai-jobs -c Adobe -c ey -c zs -c Quantiphi -c Flipkart
```

### 3. Filter by Location
```bash
genai-jobs -l Bengaluru
genai-jobs -l Hyderabad
genai-jobs -l Pune
genai-jobs -l Gurugram
genai-jobs -l Global
```

### 4. Filter by Posting Age & Max Results
```bash
# Last 3 days only
genai-jobs -d 3

# Last 14 days, capped at 20 jobs per company per engine
genai-jobs -d 14 -m 20
```

### 5. Experience Filter Controls
```bash
# Less than 4 years (default)
genai-jobs -x "<4"

# Specific range (2 to 4 years)
genai-jobs -x "2-4"

# Freshers / entry-level only
genai-jobs -x fresher

# Include jobs where experience is not explicitly mentioned
genai-jobs --allow-unstated

# Disable experience filtering completely
genai-jobs -x all
```

### 6. Select Fetching Engine (`-s` / `--sources`)
```bash
# Direct career-portal APIs only (Amazon + 23 direct ATS portals — fastest)
genai-jobs -s ats

# DuckDuckGo site-restricted career-portal dorking only
genai-jobs -s dork

# All engines concurrently (default)
genai-jobs -s all
```

### 7. Utility & Debug Flags
```bash
genai-jobs --list-companies   # Print all configured companies and exit
genai-jobs -v                 # Enable debug logging
genai-jobs --help             # Show full CLI reference
```

---

## ⚙️ Keeping Your Preferred Companies, Keywords & Default Filters

You do **not** need to edit any Python code to customize the tool for your own job hunt. Every company, search keyword, and default filter lives in JSON under `config/`.

### 1. Customize Your Preferred Company List (`config/companies.json`)
Keep only the companies you care about, or add new companies:
```json
{
  "companies": [
    {
      "name": "Google",
      "aliases": ["alphabet"],
      "ats_domains": ["careers.google.com", "google.com/about/careers"]
    },
    {
      "name": "Your Preferred Company",
      "aliases": ["ypc"],
      "ats_domains": ["careers.example.com", "boards.greenhouse.io/example"]
    }
  ]
}
```
* **Remove companies** you don't want by deleting their JSON object from `"companies"`.
* **Add any new company** with its career portal URL in `"ats_domains"`—the DDG ATS Dork engine will automatically search it without needing code changes.

### 2. Customize Default Filters (`config/settings.json`)
Edit `config/settings.json` to change the defaults whenever you run `genai-jobs` without flags:
```json
{
  "default_days": 7,
  "default_experience": "<4",
  "strict_experience": true,
  "default_location": "India",
  "default_max_results": 0,
  "default_sources": "all"
}
```
* `default_days`: Lookback window (`1`–`90`)
* `default_experience`: Default `-x` filter (`"<4"`, `"2-4"`, `"fresher"`, `"all"`)
* `strict_experience`: `true` rejects jobs with unstated experience; `false` allows them
* `default_location`: Default city/country (`"India"`, `"Bengaluru"`, `"Hyderabad"`, `"USA"`, `"Global"`, etc.)
* `default_max_results`: `0` = unlimited results per company per engine
* `default_sources`: `"all"`, `"ats"`, or `"dork"`

### 3. Customize Skills & Search Terms (`config/skills.json`)
Modify `search_terms` (sent to career portals) and `skills_detection` (used for matching & table tags):
```json
{
  "search_terms": ["Generative AI", "Agentic AI", "LLM", "RAG"],
  "skills_detection": {
    "Generative AI": ["generative ai", "genai", "gen ai"],
    "Agentic AI": ["agentic ai", "agentic", "ai agent", "ai agents", "multi-agent", "multiagent"],
    "LLM": ["llm", "llms", "large language model", "large language models"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented"]
  }
}
```

### 4. Keep a Separate Personal Config Folder (`--config-dir`)
To avoid merge conflicts when pulling repository updates, copy `config/` to a personal folder (e.g., `~/my-job-config/` or `C:\Users\<you>\my-job-config\`), edit your preferred companies and filters there, and either pass `--config-dir` or set `GENAI_JOBS_CONFIG_DIR`:

* **CLI flag (macOS & Windows):**
  ```bash
  genai-jobs --config-dir /path/to/my-job-config
  ```
* **Environment variable (macOS):**
  ```bash
  export GENAI_JOBS_CONFIG_DIR="$HOME/my-job-config"
  genai-jobs
  ```
* **Environment variable (Windows PowerShell):**
  ```powershell
  $env:GENAI_JOBS_CONFIG_DIR = "$HOME\my-job-config"
  genai-jobs
  ```

Config discovery priority: `--config-dir` → `GENAI_JOBS_CONFIG_DIR` → `./config` → package `config/`.

---

## 📺 Terminal Output

Every run prints directly to your terminal without creating output files on disk:

1. **Summary Table** — Numbered rows with `Company`, clickable `Job Title`, `Location`, `Posted`, `Exp`, `Skills`, and `Source`.
2. **Job URLs** — Indexed list (`[1] Company — Title · Location`) with full, untruncated career-portal URLs ready for Cmd/Ctrl+Click or copy-paste.

---

## 🏗️ Project Structure

```
job-tool/
├── .gitignore                  # Git ignore rules (.venv, caches, .env, OS/IDE files)
├── pyproject.toml              # Build config, dependencies & `genai-jobs` CLI entry point
├── genai-jobs                  # Executable Bash wrapper for macOS/Linux (.venv/bin/genai-jobs)
├── README.md                   # Documentation, setup, cross-platform commands & config guide
├── config/                     # External JSON Configuration (Loose Coupling)
│   ├── companies.json          # Target companies, CLI aliases & official ATS domains
│   ├── skills.json             # Search terms & skill matching/tagging rules
│   └── settings.json           # Default CLI filters (days, experience, location, sources)
└── genai_jobs/                 # Core Python Package
    ├── __init__.py             # Package version export (__version__)
    ├── __main__.py             # Enables `python -m genai_jobs`
    ├── cli.py                  # Typer CLI interface, flags, validation & logging
    ├── config.py               # Pydantic config schemas, discovery & JSON loader
    ├── constants.py            # Dynamic config bridge & runtime reload support
    ├── models.py               # JobPosting Pydantic model, dedup key & display helpers
    ├── pipeline.py             # Concurrent orchestrator, post-filtering & Rich output
    ├── engines/                # Career-Portal Job Fetching Engines
    │   ├── __init__.py         # Exports Direct ATS, Dork & Amazon API fetchers
    │   ├── amazon_api.py       # Amazon Jobs JSON API fetcher (enforces SDE-1 only)
    │   ├── ats_engine.py       # 23 direct career-portal APIs (Google, Workday, Oracle, GS, EY, ZS, Synopsys, Phenom, Eightfold)
    │   └── dork_engine.py      # Parallel DuckDuckGo site-restricted ATS dorking engine
    └── utils/                  # Filtering & Anti-Bot Utilities
        ├── __init__.py         # Re-exports filter, location, Amazon SDE-1 & exp helpers
        ├── filters.py          # Company resolution, GenAI matching, India location, exp parser & is_amazon_sde1
        └── security.py         # Browser User-Agent rotation, stealth headers & jitter delays
```
