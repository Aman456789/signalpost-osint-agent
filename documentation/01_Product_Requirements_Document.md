*Mermaid diagrams are shown as source code. They are not rendered in this file. The Markdown file holds the same source.*

# 01 — Product Requirements Document (PRD)

| **Field**       | **Value**                                                                              |
|-----------------|----------------------------------------------------------------------------------------|
| Project         | Signalpost OSINT Agent                                                                 |
| Document        | 01 — Product Requirements Document                                                     |
| Version         | 1.1 (alignment patch: redirect-chain timeout, date terminology, traceability) |
| Date            | 17 October 2026 |
| Status          | Draft for approval — no requirement is implemented by this document                    |
| Authoring role  | Principal Product Manager (with Principal Software Architect review)                   |
| Audience        | Product owner, engineering leads, QA, evaluators, challenge judges                     |
| Source of truth | Signalpost_OSINT_Agent_Execution_Manual.pdf (cited as "Manual p.N")                    |
| Related         | 02 TRD, 03 Application Flow, 04 UI/UX, 05 Backend Schema, 06 Plan, 07 RTM, 09 Register |

## Contents

1\. Executive summary

2\. Product vision

3\. Problem statement

4\. Existing workflow and limitations

5\. Proposed solution

6\. Product objectives

7\. Stakeholders

8\. User personas

9\. Jobs to be done

10\. User journeys

11\. Business requirements

12\. Functional requirements

13\. Non-functional requirements

14\. Product scope

15\. MVP and later-release scope

16\. Explicit exclusions

17\. External dependencies

18\. Success metrics

19\. Acceptance criteria

20\. Product risks

21\. Assumptions and open questions

22\. Release criteria

23\. Requirements traceability summary

## 1. Executive summary

Signalpost OSINT Agent turns a Norwegian company registration number (organisasjonsnummer, "orgnr") into a fact-checked, source-linked company profile. The product combines an official registry, a financial-data path, a company's own website, and AI-assisted extraction, and then passes every AI-proposed fact through deterministic code before publication.

The defining principle, stated in the manual, is **"MONEY BY CODE, WORDS BY AI."** Official structured data and permitted deterministic readers supply every financial value. The language model proposes descriptive facts; application code decides whether they may be published (Manual p.1, p.8, p.16).

The product must deliver at least 1,000 company profiles in a baseline run, and must pass a daily 100-company test under fixed limits of 45 minutes, 2,000 outbound requests and a declared API cost of \$10 (Manual p.4). Evaluation is scored on coverage, evidence match, update correctness, explanations and ease of use (Manual p.4).

## 2. Product vision

Every company profile the agent publishes should be something a reviewer can trust without redoing the research: each fact has a receipt (source, exact quotation, retrieval time, hash, confidence), wrong-company mixes are structurally prevented, and facts the system cannot prove are left blank rather than guessed (Manual p.1, p.8).

## 3. Problem statement

Know-Your-Customer (KYC) and open-source intelligence (OSINT) checks on companies are slow and error-prone (Manual p.4):

- Facts are spread across an official registry, company websites, annual accounts and news.

- Company names are often near-identical, so facts are copied to the wrong company.

- Facts go stale when boards, addresses or accounts change.

- A manual check takes 30–60 minutes per company (Manual p.4).

Language models add a further risk: they can produce confident but invented figures, and they answer from memory without a source link (Manual p.5, p.24).

## 4. Existing workflow and limitations

| **Current practice (as described by the manual)**   | **Limitation**                                            |
|-----------------------------------------------------|-----------------------------------------------------------|
| Analyst visits several offices/sites per company    | 30–60 minutes per company; inconsistent records           |
| Synchronous single-company loop (beginner approach) | Misses the 45-minute limit (Manual p.5)                   |
| Free-form LLM answers                               | No proof link; invented numbers (Manual p.5, p.24)        |
| Single-pass scraping with no request accounting     | Request bursts produce HTTP 429 and crashes (Manual p.5)  |
| No dates on facts                                   | Old facts appear current; changes are missed (Manual p.5) |

## 5. Proposed solution

A two-pass autonomous pipeline (Manual p.6, p.13):

1\. **Pass 1 — Registry spine.** For every eligible company, fetch the official registry record, roles, financial data (Plan A, with Plan B and Plan C fallbacks) and produce a safe base profile.

2\. **Pass 2 — Enrichment.** For companies with a registry-listed website, fetch and save pages, extract candidate facts with an LLM, validate them with deterministic locks, and publish only facts that pass the Confidence Engine.

The system runs under a shared Budget Governor, a request emergency brake, a time-based kill switch, evidence vaulting, change tracking and a dashboard with live progress (Manual p.8, p.23).

## 6. Product objectives

| **ID** | **Objective**                                       | **Measure (see Section 18)**                                                              |
|--------|-----------------------------------------------------|-------------------------------------------------------------------------------------------|
| OBJ-01 | Produce correct, identity-verified company profiles | Zero wrong-company publications in the Trap Set and test runs                             |
| OBJ-02 | Publish only evidence-backed facts                  | 100% of published facts have a verifiable quotation and source                            |
| OBJ-03 | Preserve financial-data integrity                   | Zero AI-originated monetary values in published output                                    |
| OBJ-04 | Stay inside all declared limits                     | No run exceeds 45 min, 2,000 requests or \$10 (daily); 14,000 requests and \$5 (baseline) |
| OBJ-05 | Deliver a reliable base for every company           | Every processed company has a Pass 1 profile or an explicit status                        |
| OBJ-06 | Keep profiles current                               | Change Radar re-checks changed companies only (Manual p.8)                                |
| OBJ-07 | Be easy to evaluate                                 | One command runs the pipeline; Lite mode needs no database (Manual p.7)                   |

## 7. Stakeholders

| **Stakeholder**                                            | **Interest**                                        | **Influence**         |
|------------------------------------------------------------|-----------------------------------------------------|-----------------------|
| Product owner / team lead (Team Hack Hive)                 | Scope, schedule, scoring                            | High                  |
| Engineering team (backend, frontend, validators, governor) | Buildability, testability                           | High                  |
| Challenge judges / evaluators                              | One-command run, scored outputs, reproducibility    | High                  |
| Brreg (Brønnøysundregistrene)                              | Lawful, rate-respecting use of open data (external) | External constraint   |
| Company websites                                           | Respect for robots.txt and access restrictions      | External constraint   |
| Compliance / data-protection reviewer (to be named)        | Personal-data minimisation (Manual p.18)            | Approval gate (OQ-12) |

## 8. User personas

| **Persona**                                  | **Goal**                                                         | **Typical actions**                                                         |
|----------------------------------------------|------------------------------------------------------------------|-----------------------------------------------------------------------------|
| **P1 — Evaluator**                           | Run the agent on a company list and judge quality in minutes     | Uploads CSV/TXT; starts job; reads run report; opens Evidence Viewer        |
| **P2 — Compliance analyst** (representative) | Confirm that a company is real, correctly identified and healthy | Searches Dossier Explorer; reads facts and sources; checks status and roles |
| **P3 — Engineer / maintainer**               | Run, replay and extend the pipeline                              | Runs make run, make replay; inspects rejections and checkpoints             |
| **P4 — Reviewer / auditor**                  | Verify evidence and budget compliance                            | Reviews Rejection Log, Change Feed and run_report.json                      |

## 9. Jobs to be done

| **\#**  | **Job**                                                                                                                                              | **Persona** |
|---------|------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|
| JTBD-01 | When I give the agent a list of company numbers, I want invalid numbers rejected before any spending, so that no budget is wasted on typos.          | P1          |
| JTBD-02 | When a profile is shown, I want to click any fact and see the exact sentence it came from, so that I can trust it without redoing the research.      | P2, P4      |
| JTBD-03 | When money is mentioned, I want to know it came from an official source and not from a language model, so that I am not exposed to invented figures. | P2, P4      |
| JTBD-04 | When a run is slow or expensive, I want clear meters and automatic limits, so that I am not surprised by overruns.                                   | P1, P3      |
| JTBD-05 | When company data changes, I want to see what changed and when, so that my profile stays current.                                                    | P2          |
| JTBD-06 | When I rerun the pipeline offline, I want identical results from saved evidence, so that the work is reproducible.                                   | P3, P4      |

## 10. User journeys

**J-01 Evaluator daily run (happy path).**

1\. Opens Command Center; uploads a 100-company list (TXT or CSV).

2\. Input is validated (9 digits, MOD-11). Invalid entries are listed and excluded.

3\. Job starts. Meters show companies done, requests, cost, LLM rate and elapsed time.

4\. Live Agent Terminal shows registry, scraper, LLM and validator events.

5\. Run completes; Run Report shows counts, request usage, cost and stop reason.

6\. Evaluator opens Dossier Explorer, selects a company, and clicks a fact to open the Evidence Viewer.

**J-02 Trap verification.** The evaluator runs the Trap Set. Poisoned pages' false figures appear in the Rejection Log with reasons; the harmless "12 countries" line publishes; look-alike companies keep only their own facts.

**J-03 Budget stress.** Meters approach the soft cap (1,700). Optional pages are skipped. If the brake (1,950) is reached, no new outbound calls start and remaining companies finish as registry-only profiles with a stated reason.

**J-04 Day-two update.** A second run loads yesterday's store, consults the Brreg updates feed, re-checks only changed companies, and the Change Feed shows before and after values with dates.

**J-05 Offline replay.** The evaluator runs replay mode without network access and obtains the same outputs as the saved run (subject to the determinism rules in TRD Section 15).

## 11. Business requirements

| **ID** | **Requirement**                                                                                      | **Class** | **Source**       | **Priority**              |
|--------|------------------------------------------------------------------------------------------------------|-----------|------------------|---------------------------|
| BR-01  | Deliver at least 1,000 company profiles produced by the agent                                        | SR        | Manual p.4       | Must                      |
| BR-02  | Provide a 100-company daily test run under 45 minutes, 2,000 requests and \$10 declared API cost     | SR        | Manual p.1, p.4  | Must                      |
| BR-03  | Provide the code repository link and exact commit hash                                               | SR        | Manual p.4       | Must                      |
| BR-04  | Provide one command to run the system                                                                | SR        | Manual p.4, p.20 | Must                      |
| BR-05  | Provide model/API details and expected run costs                                                     | SR        | Manual p.4       | Must                      |
| BR-06  | Do not publish a wrong-company fact or a fabricated financial value (instant fail)                   | SR        | Manual p.4       | Must                      |
| BR-07  | Qualify threshold: 65/100 overall and 21/35 on coverage, plus accuracy, evidence and execution rules | SR        | Manual p.4       | Must (external criterion) |
| BR-08  | Adopt the "money by code, words by AI" principle                                                     | SR        | Manual p.1, p.8  | Must                      |
| BR-09  | Keep the baseline job separate from the daily test                                                   | SR        | Manual p.4, p.5  | Must                      |
| BR-10  | Use only permitted public sources (no access-control evasion)                                        | SR        | Manual p.7, p.17 | Must                      |
| BR-11  | Do not collect personal identifiers or birth dates                                                   | SR        | Manual p.18      | Must                      |

## 12. Functional requirements

Requirement IDs use the family prefixes requested in the brief. Each row lists the requirement, its class (see Section 0 legend below), source and priority. Acceptance criteria are given in Section 19 and in the RTM (07).

**Legend:** SR = Source Requirement; DR = Derived Requirement; TR = Technical Recommendation; AS = Assumption; OQ = Open Question; SC = Source Conflict; EV = External fact requiring verification.

### 12.1 Input

| **ID**       | **Requirement**                                                                                                        | **Class** | **Source**                                     | **Priority**   |
|--------------|------------------------------------------------------------------------------------------------------------------------|-----------|------------------------------------------------|----------------|
| FR-INPUT-001 | The system accepts organisation numbers entered by the user, as text, on the dashboard or by CLI (make run INPUT=...). | SR        | Manual p.13                                    | Must           |
| FR-INPUT-002 | The system accepts .txt and .csv uploads containing organisation numbers.                                              | SR        | Manual p.13                                    | Must           |
| FR-INPUT-003 | Each number must be exactly 9 digits and pass the MOD-11 check; failures are rejected before any outbound request.     | SR        | Manual p.13                                    | Must           |
| FR-INPUT-004 | The system reports each rejected input with a reason and line/row reference.                                           | DR        | Manual p.13 (derived)                          | Must           |
| FR-INPUT-005 | Leading zeros are preserved; numbers are handled as strings.                                                           | DR        | Manual p.13 (derived from 9-digit requirement) | Must           |
| FR-INPUT-006 | CSV column selection rules are defined; default is the first column containing 9-digit values.                         | AS        | Not specified in manual                        | Should (OQ-03) |
| FR-INPUT-007 | Duplicate numbers within one input are processed once and reported.                                                    | AS        | Not specified in manual                        | Should         |

### 12.2 Registry

| **ID**     | **Requirement**                                                                                                                         | **Class** | **Source**                                          | **Priority** |
|------------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------|-----------------------------------------------------|--------------|
| FR-REG-001 | Fetch the main company record from Brreg for each valid number; if not found, try the sub-unit endpoint.                                | SR        | Manual p.13, p.18                                   | Must         |
| FR-REG-002 | Fetch roles (board, CEO and other role-holders) from Brreg; store names and roles only.                                                 | SR        | Manual p.13, p.18                                   | Must         |
| FR-REG-003 | Registry facts are copied from the API response byte-for-byte and store the JSON path that supplies them.                               | SR        | Manual p.16                                         | Must         |
| FR-REG-004 | Deleted and bankrupt statuses are recorded as valid facts.                                                                              | SR        | Manual p.18                                         | Must         |
| FR-REG-005 | The registry website field supplies the official domain for Entity Lock. If absent, the website stays empty; no search-engine guessing. | SR        | Manual p.8, p.17                                    | Must         |
| FR-REG-006 | A registry record that is "not found" is distinguished from a service outage.                                                           | SR        | Manual p.18                                         | Must         |
| FR-REG-007 | Registry data is consumed through documented Brreg endpoints, with the endpoint list verified before build.                             | EV        | Manual p.3 (endpoints stated as checked by authors) | Must         |

### 12.3 Financial data

| **ID**     | **Requirement**                                                                                                                                      | **Class** | **Source**                                  | **Priority** |
|------------|------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|---------------------------------------------|--------------|
| FR-FIN-001 | Plan A: obtain annual accounts from the Brreg accounts API for each company.                                                                         | SR        | Manual p.7, p.13                            | Must         |
| FR-FIN-002 | Plan B: if Plan A is in outage, read fixed fields from Proff.no using deterministic code, and only after the robots.txt and terms check is complete. | SR        | Manual p.3, p.7                             | Must (gated) |
| FR-FIN-003 | Plan C: if Plan A and Plan B fail, financial fields are blank with flag financials_unavailable.                                                      | SR        | Manual p.7                                  | Must         |
| FR-FIN-004 | Each financial value carries: org number match, reporting year, explicit unit, currency, source, retrieval timestamp and method.                     | SR        | Manual p.7, p.16 (derived for completeness) | Must         |
| FR-FIN-005 | Plan B values are abstained when the unit is not clearly shown or when the organisation number does not match.                                       | SR        | Manual p.7, p.18                            | Must         |
| FR-FIN-006 | No language-model output may originate a monetary value.                                                                                             | SR        | Manual p.8, p.10, p.16                      | Must         |
| FR-FIN-007 | Only the latest fiscal year is published for each financial metric.                                                                                  | SR        | Manual p.7                                  | Must         |
| FR-FIN-008 | Plan A "not found" does not trigger Plan B.                                                                                                          | SR        | Manual p.18                                 | Must         |
| FR-FIN-009 | Plan A is re-tested every 5 minutes after the switch to Plan B.                                                                                      | SR        | Manual p.18                                 | Should       |

### 12.4 Website extraction

| **ID**         | **Requirement**                                                                                                                                                                  | **Class**        | **Source**       | **Priority**      |
|----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------|------------------|-------------------|
| FR-EXTRACT-001 | Fetch the registry-listed homepage and up to two linked About/Contact pages found from homepage links.                                                                           | SR               | Manual p.13      | Must              |
| FR-EXTRACT-002 | Use httpx first. Use Playwright only as a capped fallback (see FR-EXTRACT-006).                                                                                                  | SR               | Manual p.6, p.9  | Must              |
| FR-EXTRACT-003 | Clean HTML to plain text; strip menus, footers and hidden content; keep about 6,000 characters of About/Home text.                                                               | SR               | Manual p.11      | Must              |
| FR-EXTRACT-004 | Apply an 8-second timeout as an ABSOLUTE CUMULATIVE limit per fetch attempt, covering the entire redirect chain (DNS resolution, connection, TLS, every redirect hop and the response transfer). The limit is not per hop and is not restarted at any hop; each hop may use only the time remaining on the single chain deadline, and the whole chain is aborted when it reaches zero. Allow 2 retries per URL (3 attempts in total); each retry is a new attempt with a new reservation and a new 8-second deadline. After failure, publish the registry-only profile with flag website_unreachable. | SR (8 s, 2 retries); TR (cumulative semantics) | Manual p.17; TRD §14, §19.3 | Must |
| FR-EXTRACT-005 | HTTP 403 is not evaded (no fake identities, no proxy tricks); robots.txt is respected.                                                                                           | SR               | Manual p.17      | Must              |
| FR-EXTRACT-006 | Playwright: capped at 3 concurrent browser pages and 12 seconds per page; images, fonts and video blocked; counts as 5 requests per page. Playwright network interception must abort any request/response exceeding 5 MB to prevent worker memory exhaustion (OOM) on JS-heavy sites. Trigger condition is subject to SC-01. | SR (trigger: SC) | Manual p.9, p.17 | Must (trigger OQ) |
| FR-EXTRACT-007 | Every redirect hop is counted as one request and is checked against the same URL rules. All hops of one attempt share the single 8-second chain deadline defined in FR-EXTRACT-004 (maximum 5 hops [TR]). | SR; TR (hop limit) | Manual p.9; TRD §19.3 | Must |
| FR-EXTRACT-008 | Each saved page is stored as text with SHA-256 hash, retrieval timestamp, final URL and HTTP status.                                                                             | SR               | Manual p.9       | Must              |

### 12.5 AI extraction

| **ID**         | **Requirement**                                                                                                                                       | **Class** | **Source**       | **Priority** |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|------------------|--------------|
| FR-EXTRACT-101 | Extract facts through a configurable OpenAI-compatible endpoint, with model name set by environment configuration.                                    | SR        | Manual p.6, p.11 | Must         |
| FR-EXTRACT-102 | Output must conform to the Pydantic schema Extraction { facts: list\[Fact\] } where Fact has the five fields key, value, value_no, quote, source_url. | SR        | Manual p.10      | Must         |
| FR-EXTRACT-103 | key is one of the 8 fixed values: products, mission, customers, markets, scale, history, leadership, other_key_fact.                                  | SR        | Manual p.10      | Must         |
| FR-EXTRACT-104 | An empty facts list is a valid answer.                                                                                                                | SR        | Manual p.10      | Must         |
| FR-EXTRACT-105 | Temperature is 0 for extraction calls.                                                                                                                | SR        | Manual p.10      | Must         |
| FR-EXTRACT-106 | Quotations are copied without translation; a translated quotation fails.                                                                              | SR        | Manual p.11      | Must         |
| FR-EXTRACT-107 | Upon quote failure, one repair attempt is made with the reminder to copy the sentence exactly. The repair counts toward the budget.                   | SR        | Manual p.11      | Must         |
| FR-EXTRACT-108 | The model may not output money amounts (revenue, profit, tax, prices, salaries).                                                                      | SR        | Manual p.8, p.10 | Must         |
| FR-EXTRACT-109 | If no API key is configured, the system runs in registry-only mode and still produces valid profiles.                                                 | SR        | Manual p.11      | Must         |

### 12.6 Validation

| **ID**          | **Requirement**                                                                                                                                                | **Class**      | **Source**        | **Priority** |
|-----------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------|-------------------|--------------|
| FR-VALIDATE-001 | Q (quote match): fuzzy match of the quotation against the saved page after normalisation; score below 0.95 becomes 0.                                          | SR             | Manual p.15       | Must         |
| FR-VALIDATE-002 | V (value support): key words of value_no appear in the quote; every digit in value appears in the quote; every capitalised name in value appears in the quote. | SR             | Manual p.15       | Must         |
| FR-VALIDATE-003 | G (identity gate): Identity Score ≥ 0.6 passes. Score components: official domain +0.6, org number on page +0.25, legal name and town +0.15.                   | SR (see SC-05) | Manual p.15       | Must         |
| FR-VALIDATE-004 | Money Filter: numbers adjacent to currency tokens or within 6 words of money terms are blocked unless from registry or Plan B.                                 | SR             | Manual p.15–16    | Must         |
| FR-VALIDATE-005 | Harmless numbers pass when the same digits appear in the quote.                                                                                                | SR             | Manual p.16       | Must         |
| FR-VALIDATE-006 | Registry clash: the registry value is kept; the conflicting page value is dropped and flagged conflicts_with_registry.                                         | SR             | Manual p.16       | Must         |
| FR-VALIDATE-007 | Relative time expressions are saved with tag time_relative.                                                                                                    | SR             | Manual p.16       | Must         |
| FR-VALIDATE-008 | Marketing superlatives are published only as "the company says..." with tag self_reported.                                                                     | SR             | Manual p.16       | Must         |
| FR-VALIDATE-009 | Rejected facts are written to the Rejection Log with reason code and diagnostic.                                                                               | SR             | Manual p.11, p.14 | Must         |
| FR-VALIDATE-010 | Registry facts skip Q and V; Plan B facts do not skip Q and V.                                                                                                 | SR             | Manual p.16       | Must         |
| FR-VALIDATE-011 | Confidence = Q × V × G × (0.6 × S + 0.4 × F); publish only if ≥ 0.80.                                                                                          | SR             | Manual p.15       | Must         |

### 12.7 Confidence

| **ID**      | **Requirement**                                                                                                                      | **Class**         | **Source**        | **Priority** |
|-------------|--------------------------------------------------------------------------------------------------------------------------------------|-------------------|-------------------|--------------|
| FR-CONF-001 | Source trust S: registry 1.0; company's own site 0.8; Plan B reader 0.7; anything else 0.5.                                          | SR                | Manual p.15       | Must         |
| FR-CONF-002 | Freshness F: latest fiscal year 1.0; one year older 0.7; older 0.4; pages fetched the same day 1.0. Rule for other web facts: OQ-06. | SR (rule gap: OQ) | Manual p.15       | Must         |
| FR-CONF-003 | Every published fact stores all components (Q, V, G, S, F) and the final score.                                                      | DR                | Manual p.15, p.16 | Must         |
| FR-CONF-004 | Honest null: when any lock fails, the fact is not saved; the field is left empty.                                                    | SR                | Manual p.8, p.16  | Must         |

### 12.8 Budget

| **ID**        | **Requirement**                                                                                                                                                                                                                      | **Class** | **Source**       | **Priority** |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------|------------------|--------------|
| FR-BUDGET-001 | A single ledger counts every outbound request, LLM call, token and dollar. Counter total_outbound_requests increments before each request is sent.                                                                                   | SR        | Manual p.9, p.17 | Must         |
| FR-BUDGET-002 | Per-company cap of 14 requests.                                                                                                                                                                                                      | SR        | Manual p.8, p.13 | Must         |
| FR-BUDGET-003 | Soft cap at 1,700 total requests: optional pages skipped; cheap steps still finish.                                                                                                                                                  | SR        | Manual p.8, p.18 | Must         |
| FR-BUDGET-004 | Emergency brake at 1,950 total requests: no new outbound scraping or AI calls; queued companies go to registry-only with reason request_brake.                                                                                       | SR        | Manual p.9, p.17 | Must         |
| FR-BUDGET-005 | LLM rate limiter at 30 requests per minute (internal target below the 40 RPM stated limit).                                                                                                                                          | SR        | Manual p.8, p.9  | Must         |
| FR-BUDGET-006 | Kill switch (FR-BUDGET-007) and brake are separate mechanisms.                                                                                                                                                                       | DR        | Manual p.9       | Must         |
| FR-BUDGET-007 | Time kill switch: projected finish \> 38 minutes trips the switch; Playwright disabled for the rest of the run; open browser pages cancelled; waiting companies keep their registry-only profile with flag time_limit_registry_only. | SR        | Manual p.9, p.17 | Must         |
| FR-BUDGET-008 | Baseline (1,000 profiles) runs as ten batches; each batch has its own checks; a global 14,000-request and \$5 hard stop applies to the whole baseline.                                                                               | SR        | Manual p.12      | Must         |
| FR-BUDGET-009 | Stop reasons are written to run_report.json.                                                                                                                                                                                         | SR        | Manual p.12      | Must         |
| FR-BUDGET-010 | Retries count toward the budget; redirect hops count individually; a Playwright page counts as 5 requests.                                                                                                                           | SR        | Manual p.9, p.11 | Must         |

### 12.9 Jobs

| **ID**     | **Requirement**                                                                                                                              | **Class**                    | **Source**                   | **Priority** |
|------------|----------------------------------------------------------------------------------------------------------------------------------------------|------------------------------|------------------------------|--------------|
| FR-JOB-001 | A job is created on submission and receives a unique identifier.                                                                             | DR                           | Manual p.19 (POST /api/jobs) | Must         |
| FR-JOB-002 | Eight workers take companies from the queue concurrently.                                                                                    | SR                           | Manual p.13                  | Must         |
| FR-JOB-003 | Pass 1 completes for all companies before Pass 2 begins.                                                                                     | SR                           | Manual p.8, p.13             | Must         |
| FR-JOB-004 | Pass 2 can be stopped at any time without losing Pass 1 profiles.                                                                            | SR                           | Manual p.8, p.13             | Must         |
| FR-JOB-005 | Checkpoints are written after each finished batch (and after each completed company in the baseline or in Lite mode, as recommended in TRD). | SR (batch); TR (per-company) | Manual p.12, p.20            | Must         |
| FR-JOB-006 | Duplicate job submission is detected and handled as defined in TRD Section 17 (idempotency).                                                 | AS                           | Not specified in manual      | Should       |
| FR-JOB-007 | The live event stream (SSE) reports progress for the job.                                                                                    | SR                           | Manual p.19                  | Must         |

### 12.10 Evidence

| **ID**          | **Requirement**                                                                                                | **Class** | **Source**       | **Priority** |
|-----------------|----------------------------------------------------------------------------------------------------------------|-----------|------------------|--------------|
| FR-EVIDENCE-001 | Save each fetched page as text with SHA-256, retrieval timestamp (UTC), source URL, final URL and HTTP status. | SR        | Manual p.8, p.9  | Must         |
| FR-EVIDENCE-002 | Every published AI fact has its exact quotation and a reference to the saved page.                             | SR        | Manual p.8, p.14 | Must         |
| FR-EVIDENCE-003 | Evidence Viewer highlights the quotation in the saved text.                                                    | SR        | Manual p.19      | Must         |
| FR-EVIDENCE-004 | Hashes detect any change in saved text; a changed hash is recorded as a change.                                | SR        | Manual p.8       | Must         |
| FR-EVIDENCE-005 | Saved snapshots are stored outside git; only dossiers ship with the repository.                                | SR        | Manual p.12      | Must         |

### 12.11 Change tracking

| **ID**        | **Requirement**                                                                                    | **Class** | **Source**       | **Priority**           |
|---------------|----------------------------------------------------------------------------------------------------|-----------|------------------|------------------------|
| FR-CHANGE-001 | Use the Brreg updates feed to identify changed companies.                                          | SR        | Manual p.8, p.20 | Should (later release) |
| FR-CHANGE-002 | Keep the previous profile and its evidence hashes; re-check only changed companies.                | SR        | Manual p.8       | Should                 |
| FR-CHANGE-003 | Each change records field, previous value, new value, source, change time and evidence references. | SR        | Manual p.19      | Should                 |
| FR-CHANGE-004 | Every published fact carries a Fact As-Of Date and a changelog line. The Fact As-Of Date (`as_of`) is the date the fact is stated to apply to and provides historical context. It is distinct from the Retrieval Date (`retrieved_at` per source; `data_freshness` per dossier), which is the system fetch time of the source. The two dates are stored separately, shown separately (Fact As-Of Date on each fact; Retrieval Date per source and per dossier) and never merged, interchanged or abbreviated to "freshness" in product or UI wording. | SR (as-of date and changelog); TR (terminology) | Manual p.8; 04 Screen 3, §10 | Must |

**Terminology note (FR-CHANGE-004).** "Retrieval Date" means when the system fetched the source (system fetch time, evidence of when the data was seen). "Fact As-Of Date" means the period or date to which the fact itself applies (historical context). A fact retrieved today may be as of an earlier date. The confidence component Freshness F (FR-CONF-002) is a separate scoring input and is not a display label for either date.

### 12.12 Rejection logging

| **ID**        | **Requirement**                                                                                                                                        | **Class**               | **Source**             | **Priority** |
|---------------|--------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------|------------------------|--------------|
| FR-REJECT-001 | Each rejected candidate fact is recorded with company, source, validation stage, reason code, timestamp and diagnostic.                                | SR                      | Manual p.8, p.11, p.19 | Must         |
| FR-REJECT-002 | Reason codes include at least quote_translated, quote_not_found, value_unsupported, money_blocked, identity_failed and request_brake-related statuses. | SR (codes partly named) | Manual p.11, p.17      | Must         |

### 12.13 Replay

| **ID**        | **Requirement**                                                                                            | **Class** | **Source**           | **Priority**           |
|---------------|------------------------------------------------------------------------------------------------------------|-----------|----------------------|------------------------|
| FR-REPLAY-001 | Replay mode re-runs the pipeline from saved evidence with no internet access and produces the same output. | SR        | Manual p.8, p.21     | Should (later release) |
| FR-REPLAY-002 | Replay records any external dependency it cannot reproduce (see TRD Section 15).                           | DR        | Manual p.8 (derived) | Should                 |

### 12.14 Reporting

| **ID**        | **Requirement**                                                                                                                        | **Class** | **Source**        | **Priority** |
|---------------|----------------------------------------------------------------------------------------------------------------------------------------|-----------|-------------------|--------------|
| FR-REPORT-001 | Each run writes run_report.json with requests used, LLM calls, tokens, estimated cost, duration, stop reason and per-company statuses. | SR        | Manual p.12, p.14 | Must         |
| FR-REPORT-002 | The pilot run projects full-run requests, tokens, cost and duration (20 companies × 50).                                               | SR        | Manual p.12       | Must         |

### 12.15 Dashboard

| **ID**    | **Requirement**                                                                                                                | **Class** | **Source**                    | **Priority**                               |
|-----------|--------------------------------------------------------------------------------------------------------------------------------|-----------|-------------------------------|--------------------------------------------|
| FR-UI-001 | Command Center: input, upload, validation, Start, meters (companies done, requests, cost, LLM calls per minute, elapsed time). | SR        | Manual p.19                   | Must                                       |
| FR-UI-002 | Live Agent Terminal: auto-scrolling colour-coded log fed by SSE.                                                               | SR        | Manual p.19                   | Must                                       |
| FR-UI-003 | Dossier Explorer: searchable table; side panel on row click; fact \[Source\] badges with URL, time, SHA-256 and confidence.    | SR        | Manual p.19                   | Must                                       |
| FR-UI-004 | Evidence Viewer: split view with saved page on the right, quotation highlighted, extracted fact on the left.                   | SR        | Manual p.19                   | Must                                       |
| FR-UI-005 | Rejection Log and Change Feed screens.                                                                                         | SR        | Manual p.19                   | Must (Rejection Log); Should (Change Feed) |
| FR-UI-006 | Run Report screen.                                                                                                             | DR        | Manual p.14 (run_report.json) | Should                                     |

## 13. Non-functional requirements

Targets marked **\[Recommendation\]** are proposed by this document and are not stated in the manual. The manual sets the constraints listed as **\[Source\]**.

| **ID**         | **Category**        | **Requirement**                                                                                              | **Class**                                        |
|----------------|---------------------|--------------------------------------------------------------------------------------------------------------|--------------------------------------------------|
| NFR-REL-001    | Reliability         | No single company failure stops the job.                                                                     | SR (partial results, p.8, p.18)                  |
| NFR-REL-002    | Reliability         | A registry-only profile remains valid when website extraction or AI fails.                                   | SR (p.8)                                         |
| NFR-REL-003    | Reliability         | Interrupted runs resume from the last checkpoint without repeating finished work.                            | SR (p.12)                                        |
| NFR-ACC-001    | Accuracy            | Zero wrong-company publications in the Trap Set and in pilot output.                                         | SR (instant fail, p.4)                           |
| NFR-ACC-002    | Accuracy            | Zero fabricated financial values; ambiguous values are rejected.                                             | SR (p.4, p.18)                                   |
| NFR-PERF-001   | Performance         | Daily test completes within 45 minutes; kill switch targets 40 minutes and trips at projected \> 38 minutes. | SR (p.4, p.9)                                    |
| NFR-PERF-002   | Performance         | Pass 1 for 100 companies completes in about 2–3 minutes.                                                     | SR (p.8)                                         |
| NFR-PERF-003   | Performance         | Full daily test about 12–15 minutes.                                                                         | SR (p.12)                                        |
| NFR-PERF-004   | Performance         | Website fetch timeout: 8 seconds as an absolute cumulative limit per attempt for the entire redirect chain (not per hop); 2 retries. Worst case per URL is 3 attempts of 8 seconds (24 seconds) before any retry delay, so a 5-hop chain cannot hold a worker for 40 seconds. | SR (p.17); TR (cumulative semantics, TRD §14) |
| NFR-PERF-005   | Performance         | Dashboard live event latency: \[Recommendation\] under 2 seconds from event to display.                      | TR                                               |
| NFR-SEC-001    | Security            | No secrets committed; keys only in environment configuration.                                                | SR (p.20 .env.example, "never commit real keys") |
| NFR-SEC-002    | Security            | Untrusted page text is treated as data; prompt injection cannot change rules.                                | SR (p.16)                                        |
| NFR-SEC-003    | Security            | Only permitted sources are accessed; robots.txt respected; no access-control evasion.                        | SR (p.3, p.7, p.17)                              |
| NFR-SEC-004    | Security            | Input validation before any outbound request.                                                                | SR (p.13)                                        |
| NFR-AUD-001    | Auditability        | Every fact traceable to quotation, saved page, hash and timestamp.                                           | SR (p.8, p.14)                                   |
| NFR-AUD-002    | Auditability        | Every rejected fact logged with reason.                                                                      | SR (p.8)                                         |
| NFR-REPRO-001  | Reproducibility     | One command produces outputs; replay produces identical output from saved evidence.                          | SR (p.7, p.21)                                   |
| NFR-REPRO-002  | Reproducibility     | Environment setup verified on a clean machine.                                                               | SR (p.22)                                        |
| NFR-MAINT-001  | Maintainability     | Modules separated as in repository tree (p.20); each AI-written function tested by its author.               | SR (p.12, p.20)                                  |
| NFR-ACC-UI-001 | Accessibility       | \[Recommendation\] WCAG 2.2 AA contrast, keyboard operation and screen-reader labels for dashboard.          | TR                                               |
| NFR-USE-001    | Usability           | Dark, calm corporate dashboard with clear numbers (p.19).                                                    | SR                                               |
| NFR-RES-001    | Resource efficiency | Snapshots total about 100–200 MB for baseline; text only.                                                    | SR (p.12)                                        |
| NFR-RES-002    | Resource efficiency | Playwright network interception must abort any request/response exceeding 5 MB to prevent worker memory exhaustion (OOM) on JS-heavy sites. | TR                                               |
| NFR-COST-001   | Cost                | Daily test ≤ \$10 declared; baseline hard stop \$5.                                                          | SR (p.4, p.5)                                    |

## 14. Product scope

**In scope:** Norwegian organisation numbers; Brreg registry, roles and accounts; Plan B reader after gating; company websites (httpx, optional Playwright); AI fact extraction with fixed menu; deterministic validators; evidence vault; budget governor; kill switch; brake; rejection log; dossier output (JSONL); run report; dashboard (Command Center, Live Terminal, Dossier Explorer, Evidence Viewer, Rejection Log); Lite and Full modes; baseline and pilot scripts.

**Out of scope for MVP:** see Section 16.

## 15. MVP and later-release scope

Source priority (p.21, MVD list). The MVP is:

| **\#** | **MVP item**                                                            | **Maps to**                              |
|--------|-------------------------------------------------------------------------|------------------------------------------|
| 1      | Registry client, MOD-11 check, asynchronous workers                     | FR-INPUT-003, FR-REG-001–003, FR-JOB-002 |
| 2      | Scraper and LLM extraction with quotations                              | FR-EXTRACT-001–003, FR-EXTRACT-101–108   |
| 3      | Validators (Q, V, G) and Rejection Log                                  | FR-VALIDATE-001–003, FR-VALIDATE-009     |
| 4      | One command writing dossiers.jsonl                                      | BR-04, FR-REPORT-001                     |
| 5      | Basic dashboard: upload, progress, request/cost meters, Evidence Viewer | FR-UI-001–002, FR-UI-004                 |

**Later additions (source p.21 "Add later if time remains"):** Change Radar diffs (FR-CHANGE-*), Replay mode (FR-REPLAY-*), Playwright fallback (FR-EXTRACT-006).

**Conflict:** The Killer Demo (p.21) uses Playwright, Kill Switch and Replay. See SC-08. The Kill Switch is also part of the budget requirements that the brief marks as required, so this document treats the **Kill Switch and the request brake as MVP-required** (they protect the daily limits) and Playwright as a conditional fallback. Approval required (OQ-01).

## 16. Explicit exclusions

| **Exclusion**                                                             | **Basis**                                     |
|---------------------------------------------------------------------------|-----------------------------------------------|
| Kafka or other heavy message brokers                                      | Manual p.7                                    |
| Language-model generation of any monetary value                           | Manual p.8, p.10                              |
| Search-engine guessing of company websites                                | Manual p.17                                   |
| Fake identities, proxy tricks or other access-control evasion             | Manual p.17                                   |
| Personal identifiers, birth dates or personal data beyond names and roles | Manual p.18                                   |
| Captcha solving or anti-bot circumvention                                 | Derived from p.17 "we do not dodge the block" |
| Autonomous re-training of models                                          | Not in source; excluded to avoid scope creep  |
| Multi-tenant authentication and user accounts                             | Not in source; assumed out of scope (AS-08)   |
| Commercial pricing or subscription features                               | Not in source                                 |

## 17. External dependencies

| **Dependency**                                                               | **Use**                                          | **Status**                                                                             | **Class** |
|------------------------------------------------------------------------------|--------------------------------------------------|----------------------------------------------------------------------------------------|-----------|
| Brønnøysundregistrene — enhetsregisteret, roles, updates feed, bulk download | Registry identity, roles, change radar, seed IDs | Endpoints stated as checked in manual (p.3)                                            | EV        |
| Regnskapsregisteret accounts API                                             | Plan A financials                                | Described as a "temporary research API that can be shut down without notice" (p.3)     | EV        |
| Proff.no                                                                     | Plan B financial reader                          | Terms and robots.txt **not yet checked** (p.3, p.7); must be checked before enablement | EV, gated |
| Company websites                                                             | Pass 2 evidence                                  | Variable availability and access rules                                                 | External  |
| OpenAI-compatible LLM endpoint (NVIDIA NIM, Groq, Together, etc.)            | Structured extraction                            | Model names and free limits change (p.3)                                               | EV        |
| Redis, MongoDB (Full mode only)                                              | Queue and store                                  | Optional in Lite                                                                       | Internal  |
| Playwright and Chromium                                                      | Fallback rendering                               | Conditional                                                                            | Internal  |

## 18. Success metrics

### 18.1 Challenge scoring framework (source)

| **Dimension**      | **Points** | **Source** |
|--------------------|------------|------------|
| Coverage           | 35         | p.4        |
| Evidence match     | 30         | p.4        |
| Update correctness | 20         | p.4        |
| Explanations       | 10         | p.4        |
| Ease of use        | 5          | p.4        |
| **Total**          | **100**    | p.4        |

**Qualification (source):** 65/100 overall, 21/35 on coverage, plus accuracy, evidence and execution rules (p.4). The manual does not define the accuracy, evidence and execution sub-rules numerically; they are listed as OQ-02.

**Important:** Meeting these targets is not implied by this documentation. Qualification is determined by the evaluator, and the documentation does not claim that the product qualifies.

### 18.2 Product operating metrics (recommended)

| **Metric**                  | **Definition**                                                                       | **Target**                  | **Class**         |
|-----------------------------|--------------------------------------------------------------------------------------|-----------------------------|-------------------|
| Wrong-company publications  | Count of published facts whose company identity is wrong in Trap Set or pilot review | 0                           | SR (instant fail) |
| Fabricated financial values | Count of published monetary values not traceable to registry or Plan B evidence      | 0                           | SR                |
| Evidence coverage           | Share of published AI facts with verifiable quote and saved page                     | 100%                        | SR (derived)      |
| Budget overrun              | Runs exceeding 45 min, 2,000 requests or \$10                                        | 0                           | SR                |
| Registry-only validity      | Share of processed companies with a valid base profile                               | 100% of processed companies | DR                |
| Pilot projection accuracy   | Projected vs actual full-run requests                                                | Within ±20%                 | TR                |

## 19. Acceptance criteria

Each functional requirement carries testable criteria in the RTM (07). The following product-level criteria apply to release.

| **ID** | **Criterion**                                                                                                                                                                        |
|--------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| AC-01  | A list of 100 valid numbers produces 100 company outcomes (profile, registry-only, or explicit failure status), each with a status.                                                  |
| AC-02  | An invalid number (wrong length, non-digit, failed MOD-11) produces zero outbound requests.                                                                                          |
| AC-03  | For the Trap Set, the poisoned page stating "Revenue: 5 billion" and the hidden "ignore your rules" text are rejected; "We operate in 12 countries" is published with its quotation. |
| AC-04  | Two look-alike companies produce profiles that contain only their own facts.                                                                                                         |
| AC-05  | A translated quotation is rejected with quote_translated.                                                                                                                            |
| AC-06  | Run report shows total requests ≤ 1,950 in every run and ≤ 2,000 in every run.                                                                                                       |
| AC-07  | Forcing the kill switch produces the flag time_limit_registry_only for waiting companies and no Playwright requests after trip.                                                      |
| AC-08  | Pass 2 interruption leaves all Pass 1 profiles intact.                                                                                                                               |
| AC-09  | Each published fact in the Evidence Viewer shows quote, URL, retrieval time, SHA-256 and confidence.                                                                                 |
| AC-10  | The one-command run produces dossiers.jsonl, rejections.jsonl and run_report.json.                                                                                                   |

## 20. Product risks

| **ID** | **Risk**                                                       | **Likelihood**   | **Impact** | **Mitigation**                                          | **Reference** |
|--------|----------------------------------------------------------------|------------------|------------|---------------------------------------------------------|---------------|
| PR-01  | Brreg accounts API withdrawn or changed                        | Medium           | High       | Plan B after gating; Plan C; retest every 5 min         | p.3, p.18     |
| PR-02  | Plan B not permitted or data format unstable                   | Medium           | Medium     | Gate; abstain on unclear units                          | p.3, p.7      |
| PR-03  | Model availability or free-credit exhaustion                   | Medium           | High       | Config switch; run registry-only; ledger tracks credits | p.12          |
| PR-04  | Wrong-company facts                                            | Low (with locks) | Critical   | Entity Lock; Trap Set; tests                            | p.4, p.8      |
| PR-05  | Scoring rules differ from the pasted copy                      | Medium           | High       | Verify official rules (EV)                              | p.3           |
| PR-06  | Schedule overrun (Oct 15–19)                                   | High             | High       | Scope priority; revised schedule (06)                   | p.22          |
| PR-07  | Judges' environment blocks database                            | Medium           | High       | Lite mode default                                       | p.7           |
| PR-08  | Playwright makes run too slow                                  | Medium           | Medium     | Kill switch; caps                                       | p.9           |
| PR-09  | Brake and per-batch limits conflict with the global 14,000 cap | Low              | High       | Global ledger (SC-09)                                   | p.12          |
| PR-10  | Personal data collected inadvertently from pages               | Low              | High       | Names and roles only; redaction rules                   | p.18          |

## 21. Assumptions and open questions

### 21.1 Assumptions

| **ID** | **Assumption**                                                                                                  |
|--------|-----------------------------------------------------------------------------------------------------------------|
| AS-01  | The Brreg endpoints named in the manual exist and are available without an API key (manual states this; EV-01). |
| AS-02  | The judges' environment will allow Python 3.12 and local file writes.                                           |
| AS-03  | Free-tier or paid LLM access is available to the team; prices are planning figures (p.3).                       |
| AS-04  | The daily test list is supplied as a file of 100 numbers.                                                       |
| AS-05  | Web pages fetched on the day of the run have freshness F = 1.0.                                                 |
| AS-06  | Users are trusted internal evaluators; authentication is not required in Lite mode.                             |
| AS-07  | Duplicate numbers in one submission are merged.                                                                 |
| AS-08  | No multi-tenant access control is needed for the MVP.                                                           |

### 21.2 Open questions

| **ID** | **Question**                                                                                                                           | **Owner**            | **Blocking?**           |
|--------|----------------------------------------------------------------------------------------------------------------------------------------|----------------------|-------------------------|
| OQ-01  | Confirm that the Kill Switch and request brake are MVP-required while Playwright, Replay and Change Radar are later additions (SC-08). | Product owner        | Yes for scope           |
| OQ-02  | Define the numeric values for accuracy, evidence and execution qualification rules (p.4 does not give them).                           | Challenge organisers | Yes for evaluation      |
| OQ-03  | Define CSV column rules.                                                                                                               | Product owner        | No                      |
| OQ-04  | Is the daily test list fixed ("Same 100 random companies each day", p.4) or replaced by judges (p.20)?                                 | Product owner        | Yes for daily test      |
| OQ-05  | Is Q binarised (≥ 0.95 → 1) or does the raw score (0.95–1.0) enter the product?                                                        | Architect            | Yes for confidence math |
| OQ-06  | What freshness value applies to web facts retrieved on an earlier day (for example, in replay)?                                        | Architect            | Yes for replay          |
| OQ-07  | Is the Playwright trigger "plain httpx gets an empty page" (p.9), the 403 case in "one polite Playwright load" (p.17), or both?        | Architect + legal    | Yes                     |
| OQ-08  | Is 40:00 a target or a hard stop (SC-02)?                                                                                              | Product owner        | Yes                     |
| OQ-09  | Is the baseline budget enforced globally (14,000 / \$5) in addition to per-batch brakes (SC-09)?                                       | Architect            | Yes                     |
| OQ-10  | How are the 1,000 seed IDs selected (random seed, stratification)?                                                                     | Product owner        | No                      |
| OQ-11  | Will Proff.no terms and robots.txt permit automated reading?                                                                           | Legal / team         | Yes for Plan B          |
| OQ-12  | Who approves personal-data handling of names and roles?                                                                                | Compliance           | Yes for release         |
| OQ-13  | Circuit-breaker failure threshold (not stated, p.17).                                                                                  | Architect            | No                      |
| OQ-14  | Does the Entity Lock require the org number on page or only domain (SC-05)?                                                            | Architect            | Yes                     |

## 22. Release criteria

A release is ready when all of the following are true, with evidence attached:

1\. All Must requirements in Section 12 have passing tests (07 RTM).

2\. The Trap Set produces zero wrong-company and zero fabricated financial publications.

3\. The daily test (100 companies) completes within limits and writes all three output files.

4\. The one-command run succeeds on a clean machine (BR-04, NFR-REPRO-002).

5\. The baseline checkpoint procedure has been exercised (interruption and resume).

6\. Open questions OQ-01, OQ-04, OQ-05, OQ-07, OQ-08, OQ-09, OQ-11, OQ-12 and OQ-14 are closed or formally accepted.

7\. Commit hash recorded and matches the tested build.

## 23. Requirements traceability summary

Full traceability is in 07 RTM. Summary:

| **PRD area** | **TRD section** | **Application flow** | **UI**            | **Data entity**                                 | **Plan task** |
|--------------|-----------------|----------------------|-------------------|-------------------------------------------------|---------------|
| INPUT        | 5, 7            | 03 §3–5              | Command Center    | ProcessingJob, JobCompany                       | P2            |
| REG          | 7               | 03 §9                | Dossier Explorer  | RegistryRecord, CompanyRole                     | P2            |
| FIN          | 8               | 03 §10               | Dossier, Evidence | FinancialRecord                                 | P2            |
| EXTRACT      | 9, 10, 14, 19.3 | 03 §11–12            | Live Terminal     | SourceDocument, EvidenceSnapshot, CandidateFact | P4–P5         |
| VALIDATE     | 11              | 03 §13–16            | Rejection Log     | ValidationResult, RejectionRecord               | P5            |
| BUDGET       | 13              | 03 §22–24            | Command Center    | BudgetLedger                                    | P3            |
| EVIDENCE     | 16              | 03 §19               | Evidence Viewer   | EvidenceSnapshot                                | P4, P6        |
| CHANGE       | 5, 16, 17       | 03 §18, §19, §21     | Change Feed, Dossier Explorer, Dossier Detail, Evidence Viewer | ChangeRecord, PublishedFact (`as_of`), Dossier (`data_freshness`), EvidenceSnapshot (`retrieved_at`) | P5-P6 (FR-CHANGE-004); P6 later (FR-CHANGE-001 to 003) |
| REPORT       | 17, 20          | 03 §27               | Run Report        | RunReport                                       | P6            |
| UI           | 17              | —                    | Section 04        | —                                               | P8            |

### 23.1 Traceability of the updated constraints

| **Requirement** | **Constraint** | **TRD section** | **Application flow (03)** | **UI (04)** | **Data entity (05)** | **Plan task** |
|---|---|---|---|---|---|---|
| FR-EXTRACT-004 | 8 s absolute cumulative limit for the whole redirect chain; 2 retries, each a new 8 s attempt | 9.2, 14 (timeout semantics), 19.3 | §11 (F12, F13, D6; E-07) | Live Terminal (company.scraper events); flag website_unreachable | SourceDocument, BudgetLedger | P4-02, P4-04 |
| FR-EXTRACT-007 | All hops share the single chain deadline; each hop counts 1 request; max 5 hops | 14, 19.3 | §11 (F13) | Command Center request meter | BudgetLedger | P4-02 |
| NFR-PERF-004 | Cumulative 8 s per attempt; worst case 24 s per URL | 14 | §11, failure matrix (website timeout) | Not applicable | Not applicable | P4-04 |
| FR-CHANGE-004 | Retrieval Date (system fetch time) and Fact As-Of Date (historical context) are separate fields and labels | 16, 17 (E5, E6) | §18 (F20, D12), §19 (F21) | Dossier Explorer (Retrieval Date column); side panel and Dossier Detail (Fact As-Of Date); Evidence Viewer (Retrieved) | Dossier `data_freshness`; PublishedFact `as_of`; EvidenceSnapshot `retrieved_at` | P5, P6-04 |

Notes: 03 section references use the flow numbers of the coverage check in 03. TRD references follow 02 §27 and the sections named above.

