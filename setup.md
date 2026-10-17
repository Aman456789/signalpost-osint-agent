# Signalpost OSINT Agent — Setup & Run Guide

This guide provides end-to-end instructions for developers, evaluators, and judges to set up and run the **Signalpost OSINT Agent** locally from scratch on Windows, macOS, or Linux.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Project Setup](#2-project-setup)
   - [Clone the Repository](#21-clone-the-repository)
   - [Backend Environment Setup (Python)](#22-backend-environment-setup-python)
   - [Frontend Environment Setup (Node.js)](#23-frontend-environment-setup-nodejs)
3. [Environment Configuration](#3-environment-configuration)
   - [Configuring the Backend (.env)](#31-configuring-the-backend-env)
   - [Configuring the Frontend (.env.local)](#32-configuring-the-frontend-envlocal)
4. [Running the System](#4-running-the-system)
   - [Option A: Running via CLI Tool (Autonomous Pipeline)](#option-a-running-via-cli-tool-autonomous-pipeline)
   - [Option B: Running the Full Stack (API + Dashboard)](#option-b-running-the-full-stack-api--dashboard)
5. [Step-by-Step Interactive Evaluation Walkthrough](#5-step-by-step-interactive-evaluation-walkthrough)
6. [Running the Test Suites](#6-running-the-test-suites)
7. [Troubleshooting & Common Issues](#7-troubleshooting--common-issues)

---

## 1. Prerequisites

Before starting, ensure you have the following installed:

| Tool | Minimum Version | Check Command | Download Link |
|---|---|---|---|
| **Python** | `3.12` or newer | `python --version` | [python.org](https://www.python.org/downloads/) |
| **Node.js** | `20.9.0` or newer | `node --version` | [nodejs.org](https://nodejs.org/) |
| **npm** | `10.0.0` or newer | `npm --version` | Bundled with Node.js |
| **Git** | `2.x` | `git --version` | [git-scm.com](https://git-scm.com/) |

*(Optional)* `make` utility is supported on macOS/Linux. On Windows, you can run the direct Python/npm commands provided below.

---

## 2. Project Setup

### 2.1 Clone the Repository

```bash
git clone https://github.com/Aman456789/signalpost-osint-agent.git
cd signalpost-osint-agent
```

### 2.2 Backend Environment Setup (Python)

Create and activate a virtual environment, then install Python dependencies.

#### On macOS / Linux:
```bash
# 1. Create a Python 3.12 virtual environment
python3 -m venv .venv

# 2. Activate the virtual environment
source .venv/bin/activate

# 3. Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

#### On Windows (PowerShell):
```powershell
# 1. Create a virtual environment
python -m venv .venv

# 2. If PowerShell restricts script execution, allow the current process:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 3. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Upgrade pip and install dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

*(Optional shortcut on Linux/macOS)*: You can run `make install` to configure both backend and frontend automatically.

### 2.3 Frontend Environment Setup (Node.js)

The frontend is a modern Next.js 15 application located in the `frontend/` directory.

```bash
# Navigate to frontend and install npm packages
cd frontend
npm install
cd ..
```

---

## 3. Environment Configuration

### 3.1 Configuring the Backend (`.env`)

In the project root directory, copy `.env.example` to create your local `.env`:

#### On macOS / Linux:
```bash
cp .env.example .env
```

#### On Windows (PowerShell):
```powershell
Copy-Item .env.example .env
```

Open `.env` in your text editor. Here is an explanation of the core parameters:

```ini
# Core Configuration
MODE=lite                        # Lite mode runs locally without Docker or external DBs
WORKERS=8                        # Concurrency (1 to 8 async company workers)

# Budget Governor
SOFT_CAP_REQUESTS=1700           # Skips optional web pages above 1,700 outbound requests
BRAKE_REQUESTS=1950              # Emergency brake: halts outbound requests at 1,950
PER_COMPANY_CAP=14               # Max 14 requests per company

# Language Model (Pass 2 Enrichment)
# Any OpenAI-compatible provider is supported (OpenAI, Groq, Ollama, vLLM, OpenRouter)
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_API_KEY=your_actual_api_key_here
LLM_RPM=30                       # Rate limiter: max 30 requests per minute

# Deterministic Validation Thresholds
CONF_THRESHOLD=0.80              # Minimum composite confidence score to publish
Q_THRESHOLD=0.95                 # Verbatim quote match score (Levenshtein similarity)
IDENTITY_THRESHOLD=0.6           # Official registry to website identity match score
```

> **Note on LLM Keys:**
> - If you want to run **Pass 1 only** (Official Brreg registry, financial balance metrics, executive roles, and base profiles), **NO LLM API key is required!** Simply use the `--pass1-only` flag or run `make demo`.
> - If you want full Pass 2 enrichment (AI fact extraction from company websites), supply an OpenAI-compatible API key in `.env`.

### 3.2 Configuring the Frontend (`frontend/.env.local`)

Copy the frontend example file:

#### On macOS / Linux:
```bash
cp frontend/.env.local.example frontend/.env.local
```

#### On Windows (PowerShell):
```powershell
Copy-Item frontend/.env.local.example frontend/.env.local
```

The default values point to the local FastAPI server:
```ini
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

---

## 4. Running the System

You can run Signalpost in two modes:
1. **CLI Pipeline Tool**: Fast autonomous execution directly from the terminal.
2. **Full Stack (API + Dashboard)**: Real-time graphical command center, live terminal streaming, and interactive evidence viewer.

---

### Option A: Running via CLI Tool (Autonomous Pipeline)

Ensure your `.venv` is activated:

#### 1. Full Dual-Pass Execution (Pass 1 + Pass 2):
Processes default companies in `data/input/companies.txt`:
```bash
# Using make (Linux/macOS)
make run

# Direct Python command (All platforms)
python -m agent_engine.cli run data/input/companies.txt
```

#### 2. Pass 1 Only (Zero AI / Registry Baseline):
Builds official profiles directly from the Brønnøysund Register Centre (`data.brreg.no`) without calling external websites or LLMs:
```bash
# Using make (Linux/macOS)
make demo

# Direct Python command (All platforms)
python -m agent_engine.cli run data/input/companies.txt --pass1-only
```

#### 3. Custom Input File:
```bash
# Using make
make run INPUT=path/to/my_companies.txt

# Direct Python command
python -m agent_engine.cli run path/to/my_companies.txt
```

#### 4. Resuming an Interrupted Run:
Signalpost automatically checkpoints state. To resume a run from the last finished company:
```bash
python -m agent_engine.cli run data/input/companies.txt --resume
```

#### Outputs Generated:
All results are atomically written to the `output/` directory:
- `output/dossiers.jsonl`: Successfully compiled company profiles and verified facts.
- `output/rejections.jsonl`: Audit log of all rejected candidate facts with exact failure codes.
- `output/run_report.json`: Execution scorecard with request counts, tokens, and duration.
- `data/snapshots/{sha256}.txt`: Cryptographic text snapshots of every fetched webpage.

---

### Option B: Running the Full Stack (API + Dashboard)

To use the Next.js Glassmorphism Dashboard, run the FastAPI backend and Next.js frontend in separate terminal windows.

#### Terminal 1 — Start the FastAPI Backend:

```bash
# Ensure virtual environment is active
source .venv/bin/activate        # On Windows: .\.venv\Scripts\Activate.ps1

# Using make (Linux/macOS)
make api

# OR direct uvicorn command (All platforms)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

The backend server is now running at:
- API Root: `http://localhost:8000/api`
- Interactive OpenAPI Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/health`

#### Terminal 2 — Start the Next.js Dashboard:

```bash
# Using make from root (Linux/macOS)
make web

# OR navigate to frontend (All platforms)
cd frontend
npm run dev
```

The frontend dashboard is now live at:
- **`http://localhost:3000`**

---

## 5. Step-by-Step Interactive Evaluation Walkthrough

Follow these steps in your browser to evaluate the end-to-end functionality:

### Step 1: Open the Command Center
1. Open your browser and navigate to `http://localhost:3000`.
2. You will be redirected to the **Command Center** (`/command-center`).
3. Notice the top navigation bar displaying real-time system status:
   - Outbound request budget gauge (`0 / 1,700` soft cap)
   - Connection status badge (`Connected`)
   - LLM rate limiter (`0 / 30 RPM`)

### Step 2: Input Pre-Flight Validation
1. In the input text box, paste one or more 9-digit Norwegian organisation numbers. For example:
   ```text
   923456789
   987654321
   812345672
   ```
2. Click **Validate numbers** (or upload a text file).
3. The client calls endpoint `POST /api/inputs/validate` (E1).
4. Notice the pre-flight summary:
   - Valid checksums (MOD-11 algorithm)
   - Duplicate entries removed
   - Detailed rejection list for any malformed or non-digit lines

### Step 3: Dispatch Job & Watch the Live Terminal
1. Click **Start job**.
2. You are automatically transitioned to the **Live Terminal** (`/jobs/[jobId]/terminal`).
3. Watch real-time Server-Sent Events (SSE) stream into the terminal:
   - `[JOB]` Job initialized
   - `[REGISTRY]` Fetching Brreg entity record, roles, and financial accounts
   - `[SCRAPER]` Fetching official website and checking identity lock
   - `[VALIDATOR]` Fact candidate validation through $Q$, $V$, $G$, and Money Filter gates
   - `[BUDGET]` Budget ledger updates

### Step 4: Explore Company Dossiers
1. Click **Dossiers** in the sidebar (`/dossiers`).
2. Search, filter by status (`published`, `registry_only`, `not_found`), or sort by revenue.
3. Click on any company (e.g. `EQUINOR ASA`) to view its comprehensive dossier:
   - Official Brreg identifiers, NACE industry classification, registered address
   - Executive leadership and Board of Directors
   - Multi-year statutory balance sheet and revenue (with exact NOK decimal precision)
   - Verified qualitative facts list

### Step 5: Verify Evidence with Character-Level Highlighting
1. From a company dossier, click on any verified fact or navigate to its evidence page (`/dossiers/[orgnr]/facts/[factId]`).
2. The **Interactive Split-Pane Evidence Viewer** opens:
   - **Left Pane**: Displays the published fact property, value, verbatim quote, $Q$-score, and SHA-256 hash.
   - **Right Pane**: Displays the immutable raw text snapshot fetched from the company's website.
3. Notice that the page **automatically scrolls to and highlights** the exact character range (`[char_start, char_end]`) in luminous amber, proving zero hallucination.

### Step 6: Inspect Rejection Audit Log
1. Click **Rejections** in the sidebar (`/rejections`).
2. Review every candidate fact that was rejected by deterministic code.
3. Filter by stage ($M$ for Money Filter, $G$ for Identity Lock, $Q$ for Quote Matcher, $V$ for Value Checker, $C$ for Confidence Score).
4. Inspect the diagnostic explanation for each rejection.

### Step 7: View the Run Report Scorecard
1. In the sidebar, click on **Run Report** for the completed job (`/jobs/[jobId]/report`).
2. Review the comprehensive visual scorecard:
   - Total runtime duration and stop reason
   - Outcome distribution (`published`, `registry_only`, with `of which flagged no_website` subline)
   - Outbound HTTP requests breakdown and remaining budget to soft cap/brake
   - LLM token consumption and estimated dollar costs
   - System flags and `plan_b_used_count` display

---

## 6. Running the Test Suites

Signalpost includes comprehensive automated test suites for both backend and frontend.

### 6.1 Backend Python Tests (pytest)

The backend test suite uses recorded HTTP fixtures and HTML traps. It runs **completely offline without live network dependencies**.

```bash
# Ensure virtual environment is active
source .venv/bin/activate        # On Windows: .\.venv\Scripts\Activate.ps1

# Run the complete test suite
pytest tests -v

# Run with quiet summary
pytest tests -q

# Run a specific test module (e.g., deterministic validators)
pytest tests/test_validators.py -v
```

### 6.2 Frontend Component Tests (Vitest)

```bash
cd frontend

# Run all component and view tests
npm test

# Verify production build compilation
npm run build
```

---

## 7. Troubleshooting & Common Issues

### 1. Browser CORS Error on Dashboard
- **Symptom**: Red error banner in the dashboard stating `Failed to fetch` or CORS rejection.
- **Cause**: The FastAPI backend strictly enforces CORS to the exact origin `http://localhost:3000`.
- **Solution**: Access the dashboard only via `http://localhost:3000` (not `http://127.0.0.1:3000` or a local IP). Ensure the backend is running on port 8000.

### 2. Windows PowerShell Execution Policy Error
- **Symptom**: `cannot be loaded because running scripts is disabled on this system` when activating `.venv`.
- **Solution**: Run this in PowerShell before activating:
  ```powershell
  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
  .\.venv\Scripts\Activate.ps1
  ```

### 3. Missing LLM Keys / 400 Config Error
- **Symptom**: Startup error stating `Missing LLM settings: LLM_API_KEY`.
- **Solution**:
  - For dual-pass runs with web enrichment, set `LLM_API_KEY=your_key` in `.env`.
  - If you do not have an API key, run in **Pass 1 Mode** using `make demo` or `python -m agent_engine.cli run data/input/companies.txt --pass1-only`.

### 4. Port 8000 or Port 3000 Already in Use
- **Symptom**: `Address already in use` or `EADDRINUSE`.
- **Solution**:
  - Stop the process occupying the port:
    - On Linux/macOS: `lsof -i :8000` and `kill -9 <PID>`
    - On Windows: `netstat -ano | findstr :8000` and `taskkill /PID <PID> /F`

### 5. Emergency Brake Tripped
- **Symptom**: Terminal displays `[BUDGET] Emergency brake tripped at 1,950 requests`.
- **Cause**: The process hit the safety ceiling of 1,950 requests.
- **Expected Behaviour**: This is an intended safety feature. The system will halt outbound network calls, finalize companies in progress with their existing registry profiles, and mark remaining companies as `not_processed_budget`.
