# Signalpost OSINT Agent

[![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js 15](https://img.shields.io/badge/Next.js-15.0-black?style=flat&logo=next.js&logoColor=white)](https://nextjs.org/)
[![Pydantic v2](https://img.shields.io/badge/Pydantic-v2-E92063?style=flat&logo=pydantic&logoColor=white)](https://docs.pydantic.dev/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Architecture: Dual--Pass](https://img.shields.io/badge/Architecture-Dual--Pass%20OSINT-orange.svg)](#dual-pass-architecture)

**Signalpost** is an industrial-grade, zero-hallucination OSINT (Open Source Intelligence) pipeline and automated verification agent for Norwegian commercial entities. It turns lists of 9-digit Norwegian organisation numbers (*organisasjonsnummer*) into source-linked corporate dossiers. 

Every monetary figure is extracted deterministically from official government statutory filings with exact decimal precision. Every descriptive fact is retrieved from corporate web presences, bounded by Instructor schemas, and validated against verbatim text quotations with cryptographic SHA-256 evidence receipts.

> ### The Signalpost Axiom:
> **Money by code, words by AI.**  
> *Every financial figure is extracted and calculated deterministically with exact decimal precision from statutory filings. Every qualitative fact is published only when verbatim quotations, character-level offsets, cryptographic SHA-256 hashes, and identity locks corroborate the claim.*

---

## Contents

1. [Executive Summary & Design Philosophy](#executive-summary--design-philosophy)
2. [Dual-Pass Architecture & Workflow](#dual-pass-architecture--workflow)
3. [Full Technology Stack](#full-technology-stack)
4. [Complete File Directory Tree](#complete-file-directory-tree)
5. [Key Subsystems & Core Mechanics](#key-subsystems--core-mechanics)
   - [Budget Governor & Resilience](#1-budget-governor--resilience)
   - [Deterministic Validators & Gates](#2-deterministic-validators--rejection-pipeline)
   - [Cryptographic Evidence Vault](#3-cryptographic-evidence-vault)
   - [FastAPI Backend & SSE Event Bus](#4-fastapi-backend--sse-event-bus)
   - [Next.js 15 Command Center Dashboard](#5-nextjs-15-command-center--dashboard)
6. [Hard Limits & Safety Thresholds](#hard-limits--safety-thresholds)
7. [API Contract Reference (E1 – E12)](#api-contract-reference-e1--e12)
8. [Quick Start & One-Command Run](#quick-start--one-command-run)
9. [Configuration Reference](#configuration-reference)
10. [Testing & Trap Suites](#testing--trap-suites)
11. [Output Deliverables & Audit Schemas](#output-deliverables--audit-schemas)
12. [Documentation Index](#documentation-index)

---

## Executive Summary & Design Philosophy

Corporate intelligence pipelines frequently suffer from two fatal vulnerabilities:
1. **Financial Hallucination**: Large Language Models (LLMs) guessing or inventing financial metrics, mixing currencies, or confusing operating margins with gross revenue.
2. **Citation Drift & Source Ghosting**: Generating corporate narratives without verifiable provenance, quoting outdated web copies, or analyzing scrapers caught in honeypots or lookalike domains.

Signalpost eliminates these failure modes at the architectural level through five immutable guarantees:

* **Money by Code**: Revenue, operating profit, and balance metrics are parsed directly from official statutory accounting filings (*Regnskapsregisteret*) using Python's arbitrary-precision `Decimal`. No model output may write a monetary value; a deterministic `MoneyFilter` rejects any candidate fact containing currency symbols, ISO codes, or numeric amounts.
* **Words by AI**: The language model proposes short descriptive facts from website text. It never decides what gets published.
* **Publish Only What Can Be Proven**: A candidate fact is published only when deterministic code finds its quotation verbatim in the saved page text ($Q \ge 0.95$), the value is supported by that quote ($V = 1.0$), the page passed an identity check against the registry record ($G \ge 0.60$), and the confidence score clears the threshold ($C \ge 0.80$). Everything else is logged to `output/rejections.jsonl` with its exact failure stage and diagnostic reason.
* **Page Text is Data, Never Instructions**: Scraped website content is treated as untrusted binary/textual input. Text is stripped of scripts, style sheets, hidden CSS elements, navigation bars, and length-capped before being injected as quoted data into constrained prompt schemas.
* **Strict Temporal Decoupling**: Two distinct dates are tracked and never conflated:
  * **Retrieval Timestamp** (`retrieved_at`, `data_freshness`): The exact UTC moment the crawler captured the page.
  * **Fact As-Of Date** (`as_of`): The temporal assertion made within the source text.

---

## Dual-Pass Architecture & Workflow

```
       Raw 9-digit Organisation Numbers (companies.txt / API E1)
                                  |
                                  v
      +-------------------------------------------------------+
      |  INPUT PROCESSOR: MOD-11 Checksum, Strip, De-duplicate |
      +-------------------------------------------------------+
                                  |
                                  v
      +-------------------------------------------------------+
      |   BUDGET GOVERNOR: 8 Async Workers, Request Ledger,   |
      |   Soft Cap (1,700), Brake (1,950), Kill Switch (38m)  |
      +-------------------------------------------------------+
                                  |
          +-----------------------+-----------------------+
          |                                               |
          v                                               v
+-----------------------------------+   +------------------------------------+
|   PASS 1: REGISTRY SPINE (NO AI)  |   |  PASS 2: WEBSITE ENRICHMENT (AI)   |
|                                   |   |                                    |
| 1. Brreg Enhetsregisteret API     |   | 1. URL Guard & Domain Discovery    |
| 2. Executive Roles API (/roller)  |   | 2. Async Web Scraper (8s timeout)  |
| 3. Regnskapsregisteret Accounts   |   | 3. Trafilatura / Selectolax Clean  |
| 4. Deterministic Financial Summary|   | 4. Identity Lock (G-Score >= 0.60) |
|                                   |   | 5. Instructor LLM Extraction       |
| Output: Base profile guaranteed   |   | 6. Q/V/G/Money Deterministic Gates |
|         as `registry_only`        |   | 7. SHA-256 Evidence Vaulting       |
+-----------------------------------+   +------------------------------------+
          \                                               /
           \                                             /
            v                                           v
      +-------------------------------------------------------+
      |               STORAGE & AUDIT PERSISTENCE             |
      |   output/dossiers.jsonl    output/rejections.jsonl     |
      |   output/run_report.json   output/checkpoints/        |
      |   data/snapshots/{sha256}.txt                         |
      +-------------------------------------------------------+
                                  |
                                  v
      +-------------------------------------------------------+
      |              FASTAPI BACKEND & EVENT STREAM           |
      |   REST Endpoints (E1-E12) | SSE Event Bus (/events)   |
      |   RFC 9457 Problem Details | Safe 300-char Truncation |
      +-------------------------------------------------------+
                                  |
                                  v
      +-------------------------------------------------------+
      |          NEXT.JS 15 GLASSMORPHISM DASHBOARD           |
      |   Command Center | Live Terminal | Dossier Explorer   |
      |   Interactive Split-Pane Evidence Viewer | Run Report |
      +-------------------------------------------------------+
```

### Company Lifecycle State Machine

Every organisation number processed transitions through an unambiguous, deterministic state machine:

| Final Status | Description |
|---|---|
| `published` | Company passed Pass 1 and published one or more verified Pass 2 AI facts. |
| `registry_only` | Company passed Pass 1; Pass 2 was skipped (no website, soft cap reached) or yielded no validated facts. (Sub-line indicates `of which flagged no_website`). |
| `not_found` | Organisation number does not exist in Brreg (404 response). |
| `registry_unavailable` | Brreg returned 503 / 500 errors after exhausting exponential backoff retries. |
| `not_processed_budget` | Run reached the emergency brake (1,950 requests) or the time kill switch before company execution began. |
| `failed` | Unrecoverable error occurred during execution. |

---

## Full Technology Stack

| Layer | Technology | Version / Specification | Role in Signalpost |
|---|---|---|---|
| **Language & Runtime** | Python | `3.12+` | Asynchronous core engine (`asyncio`), high-performance I/O concurrency |
| **HTTP Client** | `httpx` | `^0.27.0` | Async HTTP/2 client for Brreg API and web crawling with connection pooling |
| **Data Validation** | `pydantic` & `pydantic-settings` | `^2.7.0` | Immutable strict models, custom validators, and runtime environment validation |
| **HTML Cleaning** | `selectolax` & `trafilatura` | `^0.3.21` / `^1.12.0` | Ultra-fast C-based DOM pruning, boilerplate removal, and hidden-text stripping |
| **Fuzzy Matching** | `rapidfuzz` | `^3.9.0` | Levenshtein and token-set ratio scoring for $Q$-Score quotation matching |
| **Structured AI Extraction** | `instructor` & `openai` | `^1.3.0` / `^1.30.0` | Pydantic-enforced LLM candidate fact extraction with structured JSON schemas |
| **Arbitrary Precision** | `decimal.Decimal` | Built-in | Zero-floating-point calculations for statutory NOK revenues, assets, and profits |
| **API Framework** | `fastapi` & `uvicorn` | `^0.110.0` / `^0.29.0` | REST API, Server-Sent Events (SSE), and RFC 9457 `application/problem+json` error handling |
| **Frontend Framework** | `Next.js` (App Router) | `15.0.0` | Glassmorphism dashboard, React Server Components, client-side streaming |
| **Frontend UI Library** | `React` | `19.0.0` | Responsive declarative UI components and hooks |
| **Testing & Quality** | `pytest`, `pytest-asyncio`, `ruff` | Latest | Deterministic unit, integration, and trap testing; linting |
| **Frontend Testing** | `vitest`, `@testing-library/react` | Latest | Component testing for dashboard, tables, and evidence highlighting |

---

## Complete File Directory Tree

```text
signalpost-agent/
├── .env.example                               # Annotated template of environment variables
├── .gitignore                                  # Git exclusion rules (Python, Next.js, checkpoints)
├── Makefile                                    # Orchestration targets: run, demo, test, api, web
├── README.md                                   # Master enterprise project documentation
├── setup.md                                    # Detailed local installation and run guide
├── pytest.ini                                  # Pytest configuration and asyncio modes
├── requirements.txt                            # Pinned Python backend dependencies
├── agent_engine/                               # Core pipeline execution package
│   ├── __init__.py
│   ├── cli.py                                  # Unified CLI runner (run, demo, replay)
│   ├── config.py                               # Validated runtime settings via Pydantic
│   ├── enrichment.py                           # Pass 2 enrichment orchestrator
│   ├── errors.py                               # Domain exception hierarchy
│   ├── financials.py                           # Deterministic accounting & financial extractor
│   ├── html_clean.py                           # Selectolax & Trafilatura DOM sanitizer
│   ├── input_processor.py                      # MOD-11 checksum validator & de-duplicator
│   ├── language.py                             # Language detection (Norwegian / English)
│   ├── llm_client.py                           # Instructor LLM client with retry & rate limiter
│   ├── logging_setup.py                        # Structured JSON & console logging
│   ├── orchestrator.py                         # Dual-pass state machine & worker pool
│   ├── profile.py                              # Pass 1 base profile builder
│   ├── prompts.py                              # System & user prompt templates for extraction
│   ├── registry_client.py                      # Asynchronous Brreg API client
│   ├── report.py                               # Run report aggregator & JSON exporter
│   ├── schemas.py                              # Canonical Pydantic schemas, enums & models
│   ├── scraper.py                              # Async website crawler & redirect manager
│   └── url_guard.py                            # SSRF protection, port & private IP firewall
├── api/                                        # FastAPI REST service & SSE bus
│   ├── __init__.py
│   ├── main.py                                 # FastAPI application instance & CORS middleware
│   ├── problems.py                             # RFC 9457 application/problem+json error handler
│   ├── records.py                              # Shared API schemas & response models
│   ├── request_body.py                         # Request parsers, size limits & input validators
│   ├── routes_dossiers.py                      # Endpoints E5 (list) & E6 (detail)
│   ├── routes_inputs.py                        # Endpoint E1 (input pre-flight validation)
│   ├── routes_jobs.py                          # Endpoints E2 (create) & E3 (status)
│   ├── routes_records.py                       # Endpoints E7 (evidence), E8 (rejections), E9 (changes)
│   ├── routes_stream.py                        # Endpoint E4 (resumable SSE event stream)
│   ├── routes_system.py                        # Endpoints E10 (report), E11 (budget), E12 (health)
│   └── state.py                                # In-memory job state & event broadcast bus
├── governor/                                   # Budget and resilience governance
│   ├── __init__.py
│   ├── backoff.py                              # Jittered exponential backoff algorithm
│   ├── budget_ledger.py                        # Request reservation & accounting ledger
│   ├── rate_limiter.py                         # Token-bucket LLM rate limiter (30 RPM)
│   ├── request_brake.py                        # Emergency brake trigger (1,950 requests)
│   └── time_kill_switch.py                     # Predictive linear-regression time kill switch
├── validators/                                 # Deterministic fact verification gates
│   ├── __init__.py
│   ├── confidence.py                           # Composite confidence scoring (C >= 0.80)
│   ├── identity_lock.py                        # Company identity lock (G >= 0.60)
│   ├── money_filter.py                         # Currency token & financial value filter
│   ├── orgnr_checksum.py                       # MOD-11 algorithm implementation
│   ├── quote_matcher.py                        # Verbatim quotation finder (Q >= 0.95)
│   └── value_checker.py                        # Claim-to-quotation consistency check (V = 1.0)
├── storage/                                    # Persistence & cryptographic vault
│   ├── __init__.py
│   ├── evidence_vault.py                       # Content-addressed snapshot storage (SHA-256)
│   └── store.py                                # JSONL atomic append & checkpoint engine
├── data/                                       # Data directory
│   ├── input/
│   │   └── companies.txt                       # Default test batch of organisation numbers
│   └── snapshots/                              # Cryptographic page snapshots ({sha256}.txt)
├── output/                                     # Output audit directory
│   ├── dossiers.jsonl                          # Published company dossiers
│   ├── rejections.jsonl                        # Audit log of rejected candidate facts
│   ├── run_report.json                         # Telemetry & execution scorecard
│   └── checkpoints/                            # Resumable execution state snapshots
├── scripts/                                    # Shell wrappers
│   ├── run_one.sh                              # Single-command production entry point
│   ├── run_pilot.sh                            # Pilot batch runner (20 companies)
│   └── run_baseline.sh                         # Baseline batch runner (1,000 companies)
├── documentation/                              # Complete engineering specifications
│   ├── 01_Product_Requirements_Document.md
│   ├── 02_Technical_Requirements_Document.md
│   ├── 03_Application_Flow_Specification.md
│   ├── 04_UI_UX_Design_Specification.md
│   └── 05_Backend_Architecture_and_Database_Schema.md
├── frontend/                                   # Next.js 15 Command Center & Dashboard
│   ├── package.json                            # Frontend npm scripts & dependencies
│   ├── next.config.mjs                         # Next.js build & proxy configuration
│   ├── jsconfig.json                           # Absolute import alias mappings (@/*)
│   ├── vitest.config.js                        # Vitest test runner configuration
│   ├── .eslintrc.json                          # ESLint rules
│   ├── .env.local.example                      # Frontend environment template
│   ├── app/                                    # App Router pages
│   │   ├── layout.jsx                          # Root layout, JobProvider & AppShell
│   │   ├── page.jsx                            # Home page redirect to /command-center
│   │   ├── globals.css                         # Dark-mode Glassmorphism design system
│   │   ├── command-center/page.jsx             # Input dispatcher & live telemetry
│   │   ├── changes/page.jsx                    # Cross-run change audit feed
│   │   ├── rejections/page.jsx                 # Filterable rejection audit log
│   │   ├── dossiers/                           # Dossier explorer & fact detail
│   │   │   ├── page.jsx                        # Paginated dossier data table
│   │   │   └── [orgnr]/
│   │   │       ├── page.jsx                    # Company dossier detail view
│   │   │       └── facts/[factId]/page.jsx     # Side-by-side evidence viewer
│   │   └── jobs/[jobId]/
│   │       ├── terminal/page.jsx               # Live streaming SSE terminal emulator
│   │       └── report/page.jsx                 # Comprehensive run scorecard
│   ├── components/                             # Reusable UI component library
│   │   ├── AppShell.jsx                        # Navigation sidebar & header telemetry
│   │   ├── Banners.jsx                         # Soft cap, brake & kill-switch alert banners
│   │   ├── BudgetBar.jsx                       # Visual request meter with soft/brake markers
│   │   ├── ConnectionIndicator.jsx             # SSE live connection status badge
│   │   ├── DataTable.jsx                       # Generic sortable, paginated table
│   │   ├── EmptyState.jsx                      # Friendly empty condition placeholder
│   │   ├── ErrorBanner.jsx                     # Dismissible error notification
│   │   ├── EvidenceViewer.jsx                  # Split-pane snapshot viewer with highlights
│   │   ├── FactList.jsx                        # Grouped list of published company facts
│   │   ├── FlagChip.jsx                        # Visual chips for company status flags
│   │   ├── HashText.jsx                        # Monospace truncated hash with copy button
│   │   ├── HighlightedText.jsx                 # Automatic character-offset text highlighter
│   │   ├── MeterCard.jsx                       # Card wrapper for telemetry gauges
│   │   ├── OutcomesTable.jsx                   # Status counts with no_website sub-line
│   │   ├── SidePanel.jsx                       # Slide-out drawer for fact audit preview
│   │   ├── SourceBadge.jsx                     # Source provenance indicator (Registry vs Web)
│   │   └── StatusBadge.jsx                     # Color-coded status chip
│   ├── lib/                                    # Frontend utility functions & state
│   │   ├── api.js                              # Fetch wrappers for API endpoints E1-E12
│   │   ├── format.js                           # Currency, date, and number formatters
│   │   ├── hooks.js                            # SSE subscriber & debounce hooks
│   │   └── job-context.jsx                     # React context for active job tracking
│   └── tests/                                  # Vitest frontend component tests
│       ├── banners.test.jsx
│       ├── budget-bar.test.jsx
│       ├── command-center.test.jsx
│       ├── data-table.test.jsx
│       ├── evidence-viewer.test.jsx
│       ├── highlighted-text.test.jsx
│       ├── outcomes-table.test.jsx
│       └── setup.js
└── tests/                                      # Python test suite & verification traps
    ├── helpers.py                              # Mock registries, generators & fixtures
    ├── helpers_run.py                          # Mock run & store helpers
    ├── helpers_web.py                          # Mock web server & HTTP trap handlers
    ├── test_api_contract.py                    # Contract tests for endpoints E1-E12
    ├── test_backoff.py                         # Backoff calculation & jitter tests
    ├── test_checksum.py                        # MOD-11 valid, invalid & corner cases
    ├── test_config.py                          # Pydantic configuration validation tests
    ├── test_decimal_policy.py                  # Exact Decimal precision tests
    ├── test_event_and_browser_limits.py        # 300-char event & 5MB Playwright limit tests
    ├── test_evidence_vault.py                  # Snapshot hashing & offset tests
    ├── test_financials.py                      # Annual accounts extraction tests
    ├── test_html_clean.py                      # Selectolax & Trafilatura cleaning tests
    ├── test_input_processor.py                 # Orgnr parser & deduplication tests
    ├── test_kill_switch.py                     # Linear regression projection tests
    ├── test_language.py                        # Bokmål, Nynorsk, English detection tests
    ├── test_ledger.py                          # Budget ledger reservations & caps
    ├── test_one_command.py                     # End-to-end CLI execution tests
    ├── test_orchestrator.py                    # Dual-pass state machine tests
    ├── test_pass1_budget.py                    # Pass 1 request accounting tests
    ├── test_registry_client.py                 # Brreg client 200, 404, 410, 503 handling
    ├── test_report.py                          # Run report compilation & hash tests
    ├── test_schemas.py                         # Pydantic models & RejectionReason tests
    ├── test_scraper.py                         # Web crawler, redirect & timeout tests
    ├── test_store_contract.py                  # JSONL store & checkpoint resumption tests
    ├── test_url_guard.py                       # SSRF firewall & domain restriction tests
    ├── test_validators.py                     # Q, V, G, and MoneyFilter gate tests
    └── fixtures/                               # Offline recorded fixtures
        ├── registry/                           # Recorded Brreg JSON & error files
        └── trap_pages/                         # Lookalikes, hidden CSS & JS-only HTML
```

---

## Key Subsystems & Core Mechanics

### 1. Budget Governor & Resilience

The Budget Governor is an asynchronous sentinel that guarantees the system never breaches infrastructure caps, registry fair-use policies, or LLM financial limits.

* **Soft Cap (1,700 requests)**: Optional secondary pages (About, Contact) are skipped; only homepages are scraped.
* **Emergency Brake (1,950 requests)**: Outbound network activity immediately ceases. In-flight companies gracefully degrade to `registry_only` with base profiles intact. Unstarted companies are set to `not_processed_budget`.
* **Per-Company Cap (14 requests)**: Maximum total requests allocated to a single entity across Brreg and web crawling.
* **Predictive Kill Switch (38 minutes)**: Employs a sliding-window linear velocity algorithm over the last 10 finished companies. If the projected finish time exceeds the 45-minute daily limit, the kill switch trips at $T \ge 38\text{ min}$, halting Pass 2 and finalizing registry profiles.
* **Token-Bucket Rate Limiter (30 RPM)**: Enforces an internal ceiling of 30 LLM requests per minute, comfortably under the 40 RPM provider ceiling.

### 2. Deterministic Validators & Rejection Pipeline

Before an AI-extracted candidate fact can be merged into a published dossier, it must pass a battery of deterministic validators. Failure at any stage causes immediate rejection, logging the candidate to `output/rejections.jsonl` with its exact rejection stage, failure code, and diagnostic context:

```
  Candidate Fact (property, value, quotation, as_of)
                       |
                       v
     [ Gate 1: Money Filter (AST / Regex) ]
      -> Contains monetary tokens or amounts?
         YES: REJECT (Stage: M, Code: money_blocked)
         NO : Proceed
                       |
                       v
     [ Gate 2: Identity Lock (G-Score >= 0.60) ]
      -> Does the web page match official Brreg records?
         G < 0.60: REJECT (Stage: G, Code: identity_failed)
         G >= 0.60: Proceed
                       |
                       v
     [ Gate 3: Quote Matcher (Q-Score >= 0.95) ]
      -> Is the quotation found verbatim in page text?
         Q < 0.95: REJECT (Stage: Q, Code: quote_not_found)
         Q >= 0.95: Proceed (stores character range [char_start, char_end])
                       |
                       v
     [ Gate 4: Value Checker (V-Score = 1.0) ]
      -> Does the quote directly substantiate the claim?
         V != 1.0: REJECT (Stage: V, Code: value_unsupported)
         V == 1.0: Proceed
                       |
                       v
     [ Gate 5: Confidence Threshold (C >= 0.80) ]
      -> C = f(Q, V, G, source_type, page_depth)
         C < 0.80: REJECT (Stage: C, Code: below_threshold)
         C >= 0.80: PUBLISH TO DOSSIER
```

The system enforces exactly **12 explicit RejectionReason codes**:
`schema_invalid`, `identity_failed`, `quote_not_found`, `quote_translated`, `value_unsupported`, `digit_unsupported`, `name_unsupported`, `money_blocked`, `below_threshold`, `llm_invalid_json`, `fetch_failed`, `conflicts_with_registry`.

### 3. Cryptographic Evidence Vault

All web content processed by Signalpost is stored immutably to guarantee 100% reproducible auditing:
1. Raw HTML is cleaned, removing scripts, hidden CSS (`display: none`, `opacity: 0`), and navigation.
2. Cleaned text is hashed using SHA-256:
   $$\text{Hash} = \text{SHA-256}(\text{CleanText})$$
3. Snapshot text is saved under `data/snapshots/{sha256}.txt`.
4. Character-level offsets (`char_start`, `char_end`) within this exact snapshot file are stored alongside the fact in `output/dossiers.jsonl`.
5. The frontend Evidence Viewer retrieves the snapshot via endpoint E7 and highlights the exact verbatim quote in split-pane view.

### 4. FastAPI Backend & SSE Event Bus

The backend server exposes 12 standardized REST endpoints and a real-time Server-Sent Events stream:
* **RFC 9457 Problem Details**: Errors return standard `application/problem+json` bodies. Validation errors on endpoint E1 return status 422 with a structured nested `rejected` array detailing failing lines and reason codes.
* **Safe Event Message Truncation**: Any event message string exceeding 300 characters is safely auto-truncated with `...` before validation and storage to prevent database and buffer crashes.
* **Idempotency**: Job creation (E2) accepts an `Idempotency-Key` header, preventing duplicate batch runs.
* **CORS Security**: Restricted strictly to `http://localhost:3000`.

### 5. Next.js 15 Command Center & Dashboard

A purpose-built corporate intelligence console featuring a **Glassmorphism dark mode** design system:
* **Command Center (`/command-center`)**: Input text area and drag-and-drop file upload for organisation lists. Client-side MOD-11 validation, pre-flight analysis, and job dispatch.
* **Live Terminal (`/jobs/[jobId]/terminal`)**: High-performance SSE terminal emulator streaming company progress events, stage completions, and governor alerts.
* **Dossier Explorer (`/dossiers`)**: Searchable data table with status filters, NACE industry tags, and sorting by revenue.
* **Interactive Evidence Viewer (`/dossiers/[orgnr]/facts/[factId]`)**: Side-by-side audit panel showing extracted facts alongside raw page snapshots, auto-scrolling to and highlighting verbatim quotations.
* **Rejection Audit Log (`/rejections`)**: Filterable ledger of rejected candidate facts by stage ($M, G, Q, V, C$) and failure reason.
* **Run Report Scorecard (`/jobs/[jobId]/report`)**: Comprehensive execution summary displaying duration, token costs, request breakdowns, and outcome tables with `no_website` rendered cleanly as a sub-line under `registry_only`.

---

## Hard Limits & Safety Thresholds

| Limit Parameter | Threshold | Operational Behaviour |
|---|---|---|
| **Max Requests per Run** | `2,000` | Absolute ceiling for entire daily test run. |
| **Emergency Brake** | `1,950` | Outbound network calls halted. In-flight jobs degrade to `registry_only`. |
| **Soft Cap** | `1,700` | Secondary pages skipped; homepage-only crawling. |
| **Per-Company Cap** | `14` | Max outbound HTTP requests per company. |
| **LLM Call Rate** | `30 RPM` | Token-bucket rate limiter pauses calls when rate exceeds 30/min. |
| **Website Fetch Timeout** | `8 seconds` | Cumulative limit covering entire redirect chain; 2 retries max. |
| **Playwright Resource Limit** | `5 MB` | Aborts any request/response > 5 MB to prevent worker memory exhaustion (OOM). |
| **Daily Run Time Limit** | `45 minutes` | Hard stop. Linear kill switch trips at $T \ge 38\text{ min}$ if projected finish > 45m. |
| **Max Event Message Length**| `300 chars` | Auto-truncated with `...` before storage to ensure stability. |

---

## API Contract Reference (E1 – E12)

All endpoints reside under the `/api` prefix:

| Endpoint ID | HTTP Method & Path | Description |
|---|---|---|
| **E1** | `POST /api/inputs/validate` | Validates raw organisation numbers via MOD-11. Returns 422 Problem Details if no valid numbers exist. |
| **E2** | `POST /api/jobs` | Dispatches an agent execution job. Idempotent via `Idempotency-Key`. |
| **E3** | `GET /api/jobs/{id}` | Retrieves execution status (`queued`, `pass1_running`, `completed`, `stopped_budget`). |
| **E4** | `GET /api/jobs/{id}/events` | Resumable Server-Sent Events (SSE) stream using `Last-Event-ID`. |
| **E5** | `GET /api/dossiers` | Paginated search of published company dossiers with search and status filters. |
| **E6** | `GET /api/dossiers/{orgnr}` | Retrieves a complete company dossier with all verified facts and financials. |
| **E7** | `GET /api/dossiers/{orgnr}/facts/{id}/evidence` | Returns verbatim quotation, full snapshot text, SHA-256 hash, and `[char_start, char_end]` offsets. |
| **E8** | `GET /api/rejections` | Paginated audit log of rejected candidate facts filterable by stage and reason code. |
| **E9** | `GET /api/changes` | Audit feed of historical changes and updates across consecutive runs. |
| **E10** | `GET /api/jobs/{id}/report` | Retrieves the detailed execution scorecard (`run_report.json`). |
| **E11** | `GET /api/budget` | Real-time budget telemetry: outbound requests, soft cap status, LLM RPM, elapsed time. |
| **E12** | `GET /api/health` | Comprehensive health check: uptime, storage read/write status, and configuration health. |

---

## Quick Start & One-Command Run

For step-by-step installation instructions on Windows, macOS, and Linux, refer to [setup.md](setup.md).

### 1. Prerequisites
- **Python 3.12+**
- **Node.js 20.9+** (required for dashboard only)

### 2. Quick Setup
```bash
# Clone the repository
git clone https://github.com/Aman456789/signalpost-osint-agent.git
cd signalpost-osint-agent

# Create virtual environment and install dependencies
python3.12 -m venv .venv
source .venv/bin/activate       # On Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Configure environment
cp .env.example .env
```

### 3. Primary Make Targets

| Make Target | Command Executed | Purpose |
|---|---|---|
| `make run` | `bash scripts/run_one.sh data/input/companies.txt` | Complete dual-pass pipeline over default input. |
| `make demo` | `bash scripts/run_one.sh data/input/companies.txt --pass1-only` | Pass 1 only. Builds official Brreg profile with zero AI. |
| `make test` | `pytest tests -q` | Runs complete backend test suite. |
| `make api` | `uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload` | Starts FastAPI service on http://localhost:8000. |
| `make web` | `cd frontend && npm run dev` | Starts Next.js dashboard on http://localhost:3000. |
| `make install` | `python -m pip install -r requirements.txt && cd frontend && npm install` | Installs both backend and frontend dependencies. |

### Running with Custom Options
```bash
# Process a custom input file
make run INPUT=path/to/custom_orgs.txt

# Resume an interrupted batch from the last checkpoint
bash scripts/run_one.sh data/input/companies.txt --resume

# Direct CLI invocation with custom worker count
python -m agent_engine.cli run data/input/companies.txt --workers 4
```

---

## Configuration Reference

All settings are configured via environment variables or a `.env` file validated in `agent_engine/config.py`:

| Variable | Default | Valid Range | Meaning |
|---|---|---|---|
| `MODE` | `lite` | `lite` | Execution mode (`lite` requires no external databases). |
| `WORKERS` | `8` | `1` to `8` | Concurrent company worker tasks. |
| `SOFT_CAP_REQUESTS` | `1700` | $\ge 1, < \text{BRAKE}$ | Request threshold to skip secondary web pages. |
| `BRAKE_REQUESTS` | `1950` | $\ge 1, \le 2000$ | Emergency brake. Halts all outbound network calls. |
| `PER_COMPANY_CAP` | `14` | `1` to `14` | Max outbound HTTP requests per company. |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | URL | OpenAI-compatible API endpoint. |
| `LLM_MODEL` | `gpt-4o-mini` | String | Model identifier for extraction. |
| `LLM_API_KEY` | `None` | Secret string | API key for the model endpoint. |
| `LLM_RPM` | `30` | `1` to `40` | Maximum LLM requests per minute rate limit. |
| `WEBSITE_TIMEOUT_S` | `8` | $0.1$ to $8.0$ | Cumulative HTTP timeout per page across redirect chains. |
| `WEBSITE_RETRIES` | `2` | `0` to `2` | Max HTTP retry attempts on 5xx or connection drops. |
| `WEBSITE_MAX_PAGES` | `3` | `1` to `3` | Maximum distinct web pages scraped per company. |
| `WEBSITE_TEXT_CHARS` | `6000` | `500` to `20000` | Maximum cleaned characters sent to LLM per company. |
| `CONF_THRESHOLD` | `0.80` | `0.80` to `1.00` | Minimum confidence score ($C$) required to publish fact. |
| `Q_THRESHOLD` | `0.95` | `0.01` to `1.00` | Minimum quote verbatim matching threshold ($Q$). |
| `IDENTITY_THRESHOLD`| `0.6` | `0.00` to `1.00` | Minimum identity lock score ($G$) required for website. |
| `STORE_MODE` | `jsonl` | `jsonl`, `mongo` | Storage backend driver. |
| `DATA_DIR` | `data` | Path | Directory containing input files and snapshots. |
| `OUTPUT_DIR` | `output` | Path | Destination directory for dossiers, rejections, reports. |

---

## Testing & Trap Suites

Signalpost includes an exhaustive offline testing suite that validates every failure mode, security boundary, and limit without requiring live network access.

```bash
# Run backend test suite
pytest tests -v

# Run frontend test suite
cd frontend && npm test

# Verify production frontend build
cd frontend && npm run build
```

### Deterministic Test Traps
* **Lookalike Domain Traps (`tests/fixtures/trap_pages/lookalike_*.html`)**: Validates that companies sharing similar names but different organisation numbers fail the Identity Lock ($G < 0.60$).
* **Hidden Text Traps (`tests/fixtures/trap_pages/hidden_text.html`)**: Verifies that text concealed via CSS (`display: none;`, `visibility: hidden;`, `opacity: 0;`, `font-size: 0px;`) is stripped before quote verification.
* **JavaScript-Only Pages (`tests/fixtures/trap_pages/js_only.html`)**: Verifies graceful degradation to `registry_only` without crashing.
* **Browser Size Guard (`tests/test_event_and_browser_limits.py`)**: Tests that requests or responses $> 5\text{ MB}$ are aborted immediately.
* **Event Message Truncation (`tests/test_event_and_browser_limits.py`)**: Verifies that event strings $> 300\text{ chars}$ are auto-truncated with `...`.
* **HTTP Error Simulations (`tests/fixtures/registry/`)**: Tests 404 Not Found, 410 Gone, and 503 Service Unavailable handling with exponential backoff.

---

## Output Deliverables & Audit Schemas

Running Signalpost produces three primary audit deliverables in the `output/` directory:

### 1. `output/dossiers.jsonl`
Each line contains an immutable JSON entity dossier:
```json
{
  "orgnr": "923456789",
  "status": "published",
  "name": "NORDIC ENERGY SYSTEMS AS",
  "organization_form": "AS",
  "registered_date": "2018-04-12",
  "nace_code": "35.110",
  "nace_description": "Produksjon av elektrisitet",
  "address": {
    "street": "Havnegata 12",
    "postal_code": "0150",
    "city": "OSLO",
    "country": "Norge"
  },
  "financials": {
    "currency": "NOK",
    "year": 2023,
    "revenue_nok": "184500000.00",
    "operating_profit_nok": "24100000.00"
  },
  "roles": [
    {"role": "Daglig leder", "name": "Hansen, Ola"},
    {"role": "Styrets leder", "name": "Berg, Kari"}
  ],
  "facts": [
    {
      "fact_id": "f-9a1c3e",
      "property": "company_mission",
      "value": "Developing offshore floating wind turbine substructures.",
      "quotation": "developing offshore floating wind turbine substructures for deep water",
      "char_start": 340,
      "char_end": 409,
      "page_url": "https://nordicenergy.no/about",
      "snapshot_sha256": "8f4a3b1c...",
      "retrieved_at": "2026-10-17T12:00:00Z",
      "confidence": "0.95"
    }
  ]
}
```

### 2. `output/rejections.jsonl`
Audit record of every rejected candidate fact:
```json
{
  "orgnr": "923456789",
  "stage": "M",
  "reason_code": "money_blocked",
  "candidate_property": "seed_funding",
  "candidate_value": "Raised 50 million NOK in Series A",
  "diagnostic": "Value violated MoneyFilter policy by declaring currency token 'NOK'."
}
```

### 3. `output/run_report.json`
Comprehensive batch scorecard:
```json
{
  "report_version": "1.0",
  "mode": "daily_test",
  "duration_seconds": 184,
  "stop_reason": "completed",
  "company_count": 25,
  "outcomes": {
    "published": 18,
    "registry_only": 5,
    "not_found": 1,
    "not_processed_budget": 0,
    "failed": 1
  },
  "requests": {
    "total": 142,
    "by_kind": {"registry": 75, "website": 67}
  },
  "llm_calls": 22,
  "input_tokens": 14850,
  "output_tokens": 1840,
  "estimated_cost_usd": "0.04",
  "cost_limit_usd": "10.00",
  "time_limit_min": 45,
  "flags": {
    "soft_cap_reached": false,
    "brake_tripped": false,
    "kill_switch_tripped": false,
    "plan_a_outage_detected": false
  },
  "plan_b_used_count": 0,
  "rejections_by_reason": {
    "quote_not_found": 3,
    "money_blocked": 1
  }
}
```

---

## Documentation Index

The full system engineering specifications and architectural decisions are maintained in the [`documentation/`](documentation/) directory:

1. [**01 — Product Requirements Document (PRD)**](documentation/01_Product_Requirements_Document.md): Scope, user personas, success criteria, and governance objectives.
2. [**02 — Technical Requirements Document (TRD)**](documentation/02_Technical_Requirements_Document.md): System architecture, failure recovery, security posture, and traceability matrices.
3. [**03 — Application Flow Specification**](documentation/03_Application_Flow_Specification.md): State diagrams, transition matrices, step-by-step algorithms, and edge-case flows.
4. [**04 — UI / UX Design Specification**](documentation/04_UI_UX_Design_Specification.md): Glassmorphism tokens, component hierarchies, responsive layouts, and interactive states.
5. [**05 — Backend Architecture and Database Schema**](documentation/05_Backend_Architecture_and_Database_Schema.md): Data dictionaries, Pydantic model definitions, storage formats, and REST/SSE contracts.

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
