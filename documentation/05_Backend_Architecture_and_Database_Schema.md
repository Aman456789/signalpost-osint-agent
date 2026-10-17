*Mermaid diagrams are shown as source code. They are not rendered in this file. The Markdown file holds the same source.*

# 05 — Backend Architecture and Database Schema

| **Field**           | **Value**                                                                          |
|---------------------|------------------------------------------------------------------------------------|
| Document            | 05 — Backend Architecture and Database Schema                                      |
| Version             | 1.0 (documentation baseline)                                                       |
| Date                | 16 October 2026                                                                    |
| Status              | Draft. No database, migration or model code has been written.                      |
| Authoring role      | Senior Backend Engineer / Data Architect, reviewed by Principal Software Architect |
| Companion documents | 02 TRD (components and API), 03 Flows (state names), 04 UI (field names)           |
| Example data        | All orgnrs used here pass MOD-11. All company names are fictional placeholders.    |

## Contents

1\. Backend architecture summary

2\. Storage-mode differences (JSONL, SQLite not used, MongoDB)

3\. Logical entities (18)

4\. Entity dictionary (field-by-field)

5\. Enumerations

6\. Entity-relationship diagram

7\. JSON Schema definitions

8\. Pydantic model examples

9\. Example JSON records

10\. Indexing strategy

11\. Query strategy

12\. Uniqueness rules

13\. Concurrency and transaction boundaries

14\. Schema migration strategy

15\. Data lifecycle and retention

16\. Lite-mode mapping

17\. Full-mode mapping

18\. Consistency checks

## 1. Backend architecture summary

The backend has four layers:

1\. **API layer** (FastAPI): request validation, SSE, read models for the dashboard (TRD §17).

2\. **Application services**: orchestrator, Governor, validators, confidence engine (TRD §5).

3\. **Domain models** (Pydantic v2): the single source of field names, types and validation.

4\. **Storage adapter**: one interface, two implementations (JSONL for Lite, MongoDB for Full). The interface, not the storage technology, is what the services call.

Money, timestamps and identifiers follow the rules in §4.0.

### 4.0 Global field conventions

| **Concern**                 | **Convention**                                                                      | **Reason**                                         |
|-----------------------------|-------------------------------------------------------------------------------------|----------------------------------------------------|
| Organisation number (orgnr) | String, exactly 9 digits, leading zeros kept, MOD-11 valid                          | Preserves leading zeros; Norwegian identity (p.13) |
| Timestamps                  | ISO 8601 UTC, suffix Z, millisecond precision optional                              | Source example uses 2026-10-15T09:41:00Z (p.14)    |
| Identifiers                 | UUID v4 strings for jobs, reservations, events; SHA-256 hex (64 chars) for evidence | Stable, collision-safe                             |
| Money                       | Decimal string, never a JSON number; with currency, unit_scale, amount_as_printed   | Avoids floating-point loss (TRD §8.3)              |
| Confidence components       | Decimal strings with 2 decimal places in storage; computed in Decimal               | Repeatable comparison with 0.80                    |
| Text                        | UTF-8; Norwegian characters preserved (æ, ø, å)                                     | Quote matching (p.15)                              |
| Null vs absent              | Explicit null for unavailable values, plus a reason field                           | Honest-null policy (p.8)                           |
| Personal data               | Roles store name and role only                                                      | p.18                                               |

## 2. Storage-mode differences

The manual requires Lite and Full modes (p.7). The two backends do not offer the same guarantees. This section records the differences so that the service layer does not assume them.

| **Capability**            | **JSONL + JSON files (Lite)**                      | **MongoDB (Full)**                                                            | **Consequence for design**                                                                                                   |
|---------------------------|----------------------------------------------------|-------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------|
| Atomic multi-record write | No native transaction                              | Multi-document transactions require a replica set                             | All writes are written per company in one atomic unit: one JSON document per company (Lite) or one upsert per company (Full) |
| Unique constraint         | Enforced in application index, verified at startup | Unique index (server-enforced)                                                | Application must check before writing in Lite                                                                                |
| Concurrent writers        | One process; fcntl file lock                       | Many writers; upserts                                                         | Lite uses single-writer queue                                                                                                |
| Query and sort            | Full scan into memory                              | Index-backed                                                                  | Dashboard list endpoints must page; Lite limited to ≤ 1,000 dossiers (baseline) with in-memory index                         |
| Durability                | fsync at checkpoints and company completion        | Server journal                                                                | Replay must not depend on unflushed state                                                                                    |
| Schema enforcement        | Pydantic at read and write                         | Pydantic at application layer; optional JSON Schema validators on collections | Same Pydantic model in both modes                                                                                            |
| Ordering of events        | Append order in events.jsonl                       | Sequence field seq per job (allocated by the orchestrator)                    | seq is part of the model in both modes                                                                                       |
| Idempotent job submission | Key file per job                                   | Unique index on idempotency_key                                               | Same semantics                                                                                                               |

**SQLite:** The manual mentions "JSONL/SQLite" (p.7) but the repository tree lists only JSONL and MongoDB (p.20). This document does not use SQLite. The decision is recorded as ADR-02 and SC-03 (requires approval).

## 3. Logical entities (18)

| **\#** | **Entity**       | **Purpose**                                              | **Storage (Lite / Full)**                              | **Identifier**          |
|--------|------------------|----------------------------------------------------------|--------------------------------------------------------|-------------------------|
| 1      | Company          | Identity anchor for an orgnr                             | companies.jsonl / companies                            | orgnr                   |
| 2      | Dossier          | Assembled public profile for a company                   | dossiers.jsonl / dossiers                              | orgnr (one per company) |
| 3      | RegistryRecord   | Brreg main or sub-unit record (raw JSON fields)          | embedded in dossier + registry/ / registry_records     | registry_record_id      |
| 4      | CompanyRole      | Role-holder (name and role only)                         | embedded list / company_roles                          | role_id                 |
| 5      | FinancialRecord  | One financial metric for one fiscal year                 | embedded list / financial_records                      | financial_id            |
| 6      | SourceDocument   | A page or registry response as a source                  | sources.jsonl / source_documents                       | source_id               |
| 7      | EvidenceSnapshot | Saved text and hash of a source                          | data/snapshots/ + snapshots.jsonl / evidence_snapshots | sha256                  |
| 8      | CandidateFact    | AI-proposed fact before validation                       | candidates.jsonl / candidate_facts                     | candidate_id            |
| 9      | PublishedFact    | Fact that passed validation                              | embedded + facts.jsonl / published_facts               | fact_id                 |
| 10     | ValidationResult | Stage outcomes and confidence components for a candidate | embedded in candidate / validation_results             | validation_id           |
| 11     | RejectionRecord  | Rejected candidate with reason                           | rejections.jsonl / rejections                          | rejection_id            |
| 12     | ProcessingJob    | One submitted run                                        | output/jobs/{job_id}.json / processing_jobs            | job_id                  |
| 13     | JobCompany       | Per-company state within a job                           | embedded in job file / job_companies                   | (job_id, orgnr)         |
| 14     | ProcessingEvent  | Live and audit event                                     | events.jsonl / processing_events                       | (job_id, seq)           |
| 15     | BudgetLedger     | Shared counters for a job                                | ledger.json + ledger.jsonl / budget_ledgers            | job_id                  |
| 16     | Checkpoint       | Recovery point after a batch or company                  | checkpoints/\*.json / checkpoints                      | checkpoint_id           |
| 17     | ChangeRecord     | Field change between runs                                | changes.jsonl / change_records                         | change_id               |
| 18     | RunReport        | Final summary of a job                                   | run_report.json / run_reports                          | job_id                  |

**Merge and separation decisions** (required by the brief; ADR-11):

- *CandidateFact and ValidationResult* are separate in the model but ValidationResult is embedded in CandidateFact to keep one-to-one lookups cheap.

- *PublishedFact and CandidateFact* are separate so that rejected and published facts remain distinct (Audit C).

- *SourceDocument and EvidenceSnapshot* are separate: one source can have several snapshots over time (for example retrievals on different days).

- *RegistryRecord and Company* are separate: Company is identity; RegistryRecord is a versioned registry read.

- *FinancialRecord* is separate from Dossier so that Plan A, Plan B and Plan C provenance is kept per metric.

- *CompanyRole* is embedded in Dossier for display, but also stored as its own collection in Full mode for queries.

## 4. Entity dictionary (field by field)

Column legend: **R** = required; **O** = optional; **Rule** = validation or invariant. Types: str, int, dec (decimal string), bool, ts (UTC ISO timestamp), enum, json (object), list.

### 4.1 Company

| **Field**     | **Type**                   | **R/O** | **Rule**                                     |
|---------------|----------------------------|---------|----------------------------------------------|
| orgnr         | str(9)                     | R       | 9 digits; MOD-11 valid; unique               |
| is_subunit    | bool                       | R       | default false                                |
| parent_orgnr  | str(9)                     | O       | required if is_subunit true and parent known |
| first_seen_at | ts                         | R       | set on first job                             |
| last_seen_at  | ts                         | R       | updated on every job                         |
| active_status | enum CompanyStatusRegistry | O       | registry status (§5)                         |

Relationships: 1 Company → 0..1 Dossier; 1 Company → 0..n RegistryRecord; 1 Company → 0..n JobCompany. Uniqueness: orgnr. Indexes: unique(orgnr); index(parent_orgnr). Lifecycle: created by first accepted submission; never deleted by the system (only archived by operator, out of scope). Retention: indefinite (identity) — subject to operator policy (OQ-17).

### 4.2 Dossier

| **Field**               | **Type**                | **R/O** | **Rule**                                          |
|-------------------------|-------------------------|---------|---------------------------------------------------|
| dossier_id              | str                     | R       | equals orgnr (one per company)                    |
| orgnr                   | str(9)                  | R       | FK Company                                        |
| legal_name              | str                     | O       | from registry; null if not found                  |
| org_form                | str                     | O       | from registry                                     |
| registry_status         | enum                    | R       | CompanyStatusRegistry                             |
| website_url             | str                     | O       | registry-listed URL; null if absent               |
| website_official_domain | str                     | O       | derived domain; used by G                         |
| processing_status       | enum ProcessingStatus   | R       | §5                                                |
| flags                   | list\[enum Flag\]       | R       | may be empty; never null                          |
| verified_fact_count     | int                     | R       | count of PublishedFact with status published; ≥ 0 |
| registry_fields         | json                    | O       | selected Brreg fields with JSON paths             |
| roles                   | list\[CompanyRole\]     | O       | names and roles only                              |
| financial_summary       | list\[FinancialRecord\] | O       | latest year per metric                            |
| published_fact_ids      | list\[str\]             | O       | references                                        |
| data_freshness          | ts                      | R       | latest retrieval time of any input                |
| created_at              | ts                      | R       | first dossier creation                            |
| updated_at              | ts                      | R       | latest update                                     |
| job_id                  | str(uuid)               | R       | job that last updated the dossier                 |
| schema_version          | str                     | R       | "1.0"                                             |

Relationships: Dossier → 0..n PublishedFact; → 0..n FinancialRecord; → 0..n ChangeRecord. Uniqueness: orgnr. Indexes: unique(orgnr); index(processing_status); index(registry_status); text index on legal_name (Full); lowercase prefix index on legal_name (Lite in-memory). Lifecycle: created at Pass 1; updated after each company finishes; keeps previous version on change via ChangeRecord (not a full history copy). Retention: as Company.

### 4.3 RegistryRecord

| **Field**          | **Type**  | **R/O** | **Rule**                                      |
|--------------------|-----------|---------|-----------------------------------------------|
| registry_record_id | str(uuid) | R       |                                               |
| orgnr              | str(9)    | R       | FK Company                                    |
| endpoint           | str       | R       | endpoint name (no secret parameters)          |
| retrieved_at       | ts        | R       | UTC                                           |
| http_status        | int       | R       | 100–599                                       |
| raw_sha256         | str(64)   | R       | hash of raw body                              |
| raw_snapshot_ref   | str       | O       | path or id of stored raw body                 |
| fields             | json      | R       | selected fields as typed values               |
| field_paths        | json      | R       | map field name → JSON path (e.g. \$.navn)     |
| is_subunit         | bool      | R       |                                               |
| status_values      | json      | O       | status fields (deleted, bankrupt, etc.)       |
| schema_version     | str       | R       | verified schema version at build time (EV-02) |

Uniqueness: (orgnr, endpoint, raw_sha256). Indexes: index(orgnr, retrieved_at desc). Lifecycle: append-only. Newer reads add records; the dossier points to the latest. Retention: as evidence.

### 4.4 CompanyRole

| **Field**       | **Type**      | **R/O** | **Rule**                                                |
|-----------------|---------------|---------|---------------------------------------------------------|
| role_id         | str(uuid)     | R       |                                                         |
| orgnr           | str(9)        | R       | FK Company                                              |
| person_name     | str           | R       | name as published by registry; no identifiers           |
| role            | str           | R       | role label as published (for example board member, CEO) |
| role_normalised | enum RoleType | O       | mapped role category; unknown → other                   |
| from_date       | str(date)     | O       | ISO date if published; no birth dates ever stored       |
| source_ref      | str           | R       | RegistryRecord id                                       |
| retrieved_at    | ts            | R       |                                                         |

Forbidden fields (never stored): birth date, national identity number (fødselsnummer), address of private persons, any other personal identifier (p.18). Validation rejects such keys on write (extra="forbid"). Uniqueness: (orgnr, person_name, role, from_date). Indexes: index(orgnr); index(person_name) for search (Full). Lifecycle: replaced on change; prior values are in ChangeRecord.

### 4.5 FinancialRecord

| **Field**           | **Type**                        | **R/O**                      | **Rule**                                                   |
|---------------------|---------------------------------|------------------------------|------------------------------------------------------------|
| financial_id        | str(uuid)                       | R                            |                                                            |
| orgnr               | str(9)                          | R                            | FK Company; must equal the org number on the source        |
| metric              | enum FinancialMetric            | R                            | §5                                                         |
| fiscal_year         | int                             | R                            | 1900–2100; latest year only in publication                 |
| period_start        | str(date)                       | O                            |                                                            |
| period_end          | str(date)                       | O                            |                                                            |
| amount              | dec                             | O                            | null when unavailable; decimal string                      |
| currency            | str(3)                          | R when amount present        | ISO 4217 code, e.g. NOK                                    |
| unit_scale          | int                             | R when amount present        | 1 or 1000 or 1000000, as printed on source                 |
| amount_as_printed   | str                             | R when amount present        | exact printed text, e.g. 1 504 112                         |
| amount_base         | dec                             | R when amount present        | amount_as_printed scaled by unit_scale                     |
| method              | enum FinancialMethod            | R                            | registry, structured_fallback, unavailable                 |
| source_url          | str                             | R                            |                                                            |
| source_ref          | str                             | R                            | RegistryRecord or SourceDocument id                        |
| org_match           | bool                            | R                            | true required for publication                              |
| unit_verified       | bool                            | R                            | true required for Plan B publication                       |
| retrieved_at        | ts                              | R                            |                                                            |
| sha256              | str(64)                         | R when a source page is used | snapshot hash                                              |
| unavailable_reason  | enum FinancialUnavailableReason | R when amount null           | e.g. plan_b_not_permitted, unit_unclear, no_accounts_filed |
| verification_status | enum VerificationStatus         | R                            | verified, abstained, unavailable                           |

Rules:

- amount and amount_base are never floats. Arithmetic uses Decimal with precision 28.

- Money is never produced by the LLM. The method field must be registry or structured_fallback, and LLM-sourced financial rows are rejected on write.

- Plan B rows require unit_verified = true and org_match = true to publish.

Uniqueness: (orgnr, metric, fiscal_year, method). Indexes: index(orgnr, metric, fiscal_year desc). Lifecycle: new fiscal years add rows; old rows are kept with their as-of time.

### 4.6 SourceDocument

| **Field**               | **Type**        | **R/O** | **Rule**                                                  |
|-------------------------|-----------------|---------|-----------------------------------------------------------|
| source_id               | str(uuid)       | R       |                                                           |
| orgnr                   | str(9)          | R       | FK Company (the company the page was fetched for)         |
| source_kind             | enum SourceKind | R       | registry, company_website, plan_b_reader, other           |
| url                     | str             | R       | as requested (no query string stored in logs)             |
| final_url               | str             | R       | after permitted redirects                                 |
| redirect_hops           | int             | R       | ≥ 0                                                       |
| http_status             | int             | R       |                                                           |
| content_type            | str             | R       | MIME type                                                 |
| retrieved_at            | ts              | R       | UTC                                                       |
| sha256                  | str(64)         | R       | of saved text                                             |
| language                | str             | O       | no, en, or unknown (detected; used by V and Q)            |
| domain_on_official_list | bool            | R       | true if final domain matches the registry official domain |
| identity_score          | dec             | R       | G score, 0.00–1.00                                        |
| identity_signals        | json            | R       | {org_number_on_page, name_and_town_on_page} booleans      |
| snapshot_ref            | str             | R       | EvidenceSnapshot sha256                                   |

Uniqueness: (orgnr, url, sha256). Indexes: index(orgnr, retrieved_at desc); index(sha256). Lifecycle: append-only; new retrieval creates a new record.

### 4.7 EvidenceSnapshot

| **Field**              | **Type**    | **R/O** | **Rule**                                                             |
|------------------------|-------------|---------|----------------------------------------------------------------------|
| sha256                 | str(64)     | R       | primary key; hash of normalised text                                 |
| text_path              | str         | R       | data/snapshots/{sha256}.txt (Lite) or GridFS/volume reference (Full) |
| byte_size              | int         | R       | ≥ 0; soft limit per snapshot 2 MB (TRD §19.3)                        |
| char_count             | int         | R       |                                                                      |
| text_truncated_for_llm | bool        | R       | true if the model received only the first ~6,000 characters          |
| created_at             | ts          | R       | first write                                                          |
| raw_llm_responses      | list\[str\] | O       | sha256 of stored raw LLM responses that used this snapshot (replay)  |

Rules: the file content is immutable. If sha256 already exists, the existing file is reused. The hash is computed over UTF-8 bytes after normalisation (TRD §11.2 step 1). Retention: indefinite while any dossier references it; snapshots not referenced after a dossier change are kept for 30 days \[TR\].

### 4.8 CandidateFact

| **Field**        | **Type**         | **R/O** | **Rule**                                                   |
|------------------|------------------|---------|------------------------------------------------------------|
| candidate_id     | str(uuid)        | R       |                                                            |
| orgnr            | str(9)           | R       | FK Company                                                 |
| source_id        | str(uuid)        | R       | FK SourceDocument                                          |
| key              | enum FactKey     | R       | 8-value menu (§5)                                          |
| value            | str              | R       | English; ≤ 300 chars; no money                             |
| value_no         | str              | R       | Norwegian (or English if page English, AS-12); ≤ 300 chars |
| quote            | str              | R       | exact text; ≤ 600 chars; not translated                    |
| source_url       | str              | R       | equals the page URL processed                              |
| extraction_model | str              | R       | model identifier from configuration                        |
| prompt_hash      | str(64)          | R       | hash of prompt template and version                        |
| llm_call_ids     | list\[str\]      | R       | ids of LLM calls (≥ 1)                                     |
| extracted_at     | ts               | R       |                                                            |
| validation       | ValidationResult | R       | embedded (see 4.10)                                        |

Uniqueness: (orgnr, source_id, key, value_hash) where value_hash is SHA-256 of normalised value. Indexes: index(orgnr, key); index(source_id). Lifecycle: retained for audit with its ValidationResult; the published copy lives in PublishedFact.

### 4.9 PublishedFact

| **Field**          | **Type**               | **R/O** | **Rule**                                                          |
|--------------------|------------------------|---------|-------------------------------------------------------------------|
| fact_id            | str(uuid)              | R       |                                                                   |
| orgnr              | str(9)                 | R       | FK Company                                                        |
| key                | enum FactKey           | R       |                                                                   |
| value              | str                    | R       | English                                                           |
| value_no           | str                    | R       | Norwegian                                                         |
| quote              | str                    | O       | required for AI facts; null for registry facts                    |
| registry_json_path | str                    | O       | required for registry facts (e.g. \$.navn)                        |
| method             | enum FactMethod        | R       | registry, llm_verified, structured_fallback                       |
| source_id          | str(uuid)              | R       | FK SourceDocument or RegistryRecord                               |
| source_url         | str                    | R       |                                                                   |
| retrieved_at       | ts                     | R       |                                                                   |
| sha256             | str(64)                | R       | evidence hash                                                     |
| as_of              | ts                     | R       | as-of date for the statement (p.8: every fact has an as-of date)  |
| tags               | list\[enum FactTag\]   | R       | may be empty: time_relative, self_reported                        |
| flags              | list\[enum Flag\]      | R       | e.g. conflicts_with_registry (drop)                               |
| identity_score     | dec                    | R       | G score                                                           |
| q                  | dec                    | R       | 0.00 or 1.00 (or raw per OQ-05)                                   |
| v                  | dec                    | R       | 0 or 1                                                            |
| g                  | dec                    | R       | 0 or 1                                                            |
| s                  | dec                    | R       | 0.5, 0.7, 0.8, or 1.0                                             |
| f                  | dec                    | R       | 0.4, 0.7, or 1.0                                                  |
| confidence         | dec                    | R       | 2 decimals; = q × v × g × (0.6s + 0.4f); rounded only for display |
| publication_status | enum PublicationStatus | R       | published                                                         |
| validation_id      | str(uuid)              | R       | FK ValidationResult                                               |
| created_at         | ts                     | R       |                                                                   |

Invariants:

- confidence ≥ 0.80 for published.

- method = registry ⇒ q = v = g = 1 and quote is null.

- method = llm_verified ⇒ quote present and value contains no money (validated by Money Filter).

- method = structured_fallback ⇒ source proff.no and s = 0.7.

- value never contains a money number unless method = registry (registry values may include amounts).

- Dossier verified_fact_count counts only llm_verified facts with publication_status = published (AS-15). Registry fields are reported separately.

Uniqueness: (orgnr, key, value_hash, sha256). Indexes: index(orgnr, key); index(publication_status). Lifecycle: superseded by a newer PublishedFact on change; previous kept with publication_status = superseded \[TR\] and linked via ChangeRecord.

Note: publication_status values are published and superseded only; rejected facts never appear here (Audit C).

### 4.10 ValidationResult

| **Field**           | **Type**                | **R/O** | **Rule**                                             |
|---------------------|-------------------------|---------|------------------------------------------------------|
| validation_id       | str(uuid)               | R       |                                                      |
| candidate_id        | str(uuid)               | R       | FK CandidateFact                                     |
| schema_ok           | bool                    | R       | Pydantic pass                                        |
| g_identity_ok       | bool                    | R       |                                                      |
| q_raw               | dec                     | R       | raw fuzzy score 0.00–1.00                            |
| q                   | dec                     | R       | after threshold rule (OQ-05)                         |
| q_language_mismatch | bool                    | R       | used for quote_translated                            |
| quote_start         | int                     | O       | 0-based offset of the quote in the stored snapshot text (4.7); null if Q = 0 (E7 highlight) |
| quote_end           | int                     | O       | exclusive end offset; null exactly when quote_start is null |
| v                   | dec                     | R       | 0 or 1                                               |
| v_checks            | json                    | R       | {key_words_ok, digits_ok, names_ok}                  |
| money_filter        | enum MoneyDecision      | R       | not_money, harmless_passed, blocked, registry_source |
| registry_clash      | bool                    | R       |                                                      |
| confidence          | dec                     | R       |                                                      |
| decision            | enum ValidationDecision | R       | publish, reject, abstain                             |
| first_failed_stage  | enum ValidationStage    | O       | required for reject                                  |
| reason_code         | enum ReasonCode         | O       | required for reject                                  |
| repair_attempted    | bool                    | R       | true if the one repair call was used                 |
| decided_at          | ts                      | R       |                                                      |

### 4.11 RejectionRecord

| **Field**        | **Type**             | **R/O** | **Rule**                                                                       |
|------------------|----------------------|---------|--------------------------------------------------------------------------------|
| rejection_id     | str(uuid)            | R       |                                                                                |
| job_id           | str(uuid)            | R       | FK ProcessingJob                                                               |
| orgnr            | str(9)               | R       | FK Company                                                                     |
| candidate_id     | str(uuid)            | O       | null when rejected before candidate creation (for example page-level identity) |
| source_id        | str(uuid)            | O       |                                                                                |
| source_url       | str                  | O       |                                                                                |
| rejected_value   | str                  | O       | truncated to 300 chars; full value in candidate                                |
| validation_stage | enum ValidationStage | R       | schema, identity, quote, value, money, registry_clash, confidence, fetch       |
| reason_code      | enum ReasonCode      | R       | §5                                                                             |
| diagnostic       | json                 | R       | numeric and structural details, no page text beyond 200 chars                  |
| rejected_at      | ts                   | R       |                                                                                |

Rule: a rejection record never contains a PublishedFact id. Uniqueness: none (multiple rejections for the same candidate are not expected; if they occur, the first is authoritative). Indexes: index(job_id, rejected_at); index(orgnr); index(reason_code).

### 4.12 ProcessingJob

| **Field**            | **Type**        | **R/O** | **Rule**                                              |
|----------------------|-----------------|---------|-------------------------------------------------------|
| job_id               | str(uuid)       | R       |                                                       |
| idempotency_key      | str             | O       | unique when present (TRD §17.3)                       |
| request_hash         | str(64)         | R       | SHA-256 of the accepted orgnr list                    |
| mode                 | enum JobMode    | R       | daily_test, baseline_batch, pilot                     |
| status               | enum JobStatus  | R       | §5                                                    |
| current_pass         | int             | R       | 0, 1, or 2                                            |
| submitted_at         | ts              | R       |                                                       |
| started_at           | ts              | O       |                                                       |
| ended_at             | ts              | O       |                                                       |
| input_count          | int             | R       | accepted count                                        |
| rejected_input_count | int             | R       | count of input rejections                             |
| completed_count      | int             | R       | terminal companies                                    |
| failed_count         | int             | R       |                                                       |
| registry_only_count  | int             | R       |                                                       |
| stop_reason          | enum StopReason | O       | §5; set once                                          |
| config_hash          | str(64)         | R       | hash of effective configuration (replay precondition) |
| code_version         | str             | R       | commit hash                                           |
| checkpoint_ref       | str             | O       | latest checkpoint id                                  |
| batch_index          | int             | O       | 1–10 for baseline                                     |
| batch_count          | int             | O       | 10 for baseline                                       |
| label                | str             | O       | operator label                                        |

Relationships: ProcessingJob → n JobCompany; → 1 BudgetLedger; → 0..n ProcessingEvent; → 0..1 RunReport; → n Checkpoint. Indexes: unique(job_id); unique sparse(idempotency_key); index(status, submitted_at).

### 4.13 JobCompany

| **Field**      | **Type**              | **R/O** | **Rule**                                                                              |
|----------------|-----------------------|---------|---------------------------------------------------------------------------------------|
| job_id         | str(uuid)             | R       | FK ProcessingJob                                                                      |
| orgnr          | str(9)                | R       | FK Company                                                                            |
| status         | enum ProcessingStatus | R       | §5                                                                                    |
| pass1_status   | enum                  | R       | pending, complete, not_found, failed, not_processed_budget                            |
| pass2_status   | enum                  | R       | pending, complete, skipped_no_website, failed, time_limit, request_brake, not_started |
| flags          | list\[enum Flag\]     | R       |                                                                                       |
| requests_used  | int                   | R       | ≥ 0; ≤ 14 (per-company cap)                                                           |
| llm_calls_used | int                   | R       | ≥ 0                                                                                   |
| started_at     | ts                    | O       |                                                                                       |
| finished_at    | ts                    | O       |                                                                                       |
| error_class    | str                   | O       | exception class name only (no message text)                                           |

Uniqueness: (job_id, orgnr). Indexes: index(job_id, status). Invariant: requests_used ≤ 14. Every JobCompany ends with exactly one terminal status (published, registry_only, not_found, registry_unavailable, not_processed_budget, failed).

### 4.14 ProcessingEvent

| **Field** | **Type**       | **R/O** | **Rule**                                                                              |
|-----------|----------------|---------|---------------------------------------------------------------------------------------|
| job_id    | str(uuid)      | R       |                                                                                       |
| seq       | int            | R       | strictly increasing per job; allocated by orchestrator                                |
| ts        | ts             | R       |                                                                                       |
| type      | enum EventType | R       | TRD §17.3 E4                                                                          |
| orgnr     | str(9)         | O       |                                                                                       |
| message   | str            | R       | ≤ 300 chars; no page text                                                             |
| data      | json           | O       | counts and codes only                                                                 |
| tag       | enum           | R       | derived from type: REGISTRY, SCRAPER, LLM, VALIDATOR, BUDGET, KILL-SWITCH, JOB, ERROR |

Uniqueness: (job_id, seq). Indexes: index(job_id, seq). Retention: 30 days or per run \[TR\].

**Invariant rule:** Any event message string exceeding 300 characters MUST be safely auto-truncated with '...' before validation/storage to prevent database crashes.

### 4.15 BudgetLedger

| **Field**                  | **Type**  | **R/O** | **Rule**                                                                              |
|----------------------------|-----------|---------|---------------------------------------------------------------------------------------|
| job_id                     | str(uuid) | R       | one ledger per job; FK                                                                |
| total_outbound_requests    | int       | R       | ≥ 0; reservation check ≤ 1,950                                                        |
| requests_by_kind           | json      | R       | keys: registry, website, plan_b, llm, retry, redirect_hop, playwright_page_equivalent |
| soft_cap                   | int       | R       | 1,700 (config)                                                                        |
| brake                      | int       | R       | 1,950 (config)                                                                        |
| brake_tripped              | bool      | R       | never reset within run                                                                |
| soft_cap_reached           | bool      | R       |                                                                                       |
| per_company_requests       | json      | R       | orgnr → int ≤ 14                                                                      |
| plan_b_used_count          | int       | R       | ≥ 0; ≤ input_count; companies (not requests) where Plan B was invoked; copied to RunReport (TA-14) |
| llm_calls                  | int       | R       | ≥ 0                                                                                   |
| input_tokens               | int       | R       | ≥ 0                                                                                   |
| output_tokens              | int       | R       | ≥ 0                                                                                   |
| tokens_estimated           | bool      | R       | true when counts are estimates                                                        |
| estimated_cost_usd         | dec       | R       | 2 to 4 decimal places in storage                                                      |
| cost_limit_usd             | dec       | R       | 10 (daily) or 5 (baseline)                                                            |
| elapsed_seconds            | int       | R       | monotonic clock measure, recorded at checkpoint                                       |
| kill_switch_tripped        | bool      | R       | never reset within run                                                                |
| kill_switch_projection_min | dec       | O       | last projection                                                                       |
| version                    | int       | R       | optimistic-concurrency version (Full: Redis version key; Lite: in-process)            |
| updated_at                 | ts        | R       |                                                                                       |

Relationships: 1 BudgetLedger ↔ 1 ProcessingJob. Concurrency: see §13.

### 4.16 Checkpoint

| **Field**              | **Type**               | **R/O** | **Rule**                                |
|------------------------|------------------------|---------|-----------------------------------------|
| checkpoint_id          | str(uuid)              | R       |                                         |
| job_id                 | str(uuid)              | R       |                                         |
| created_at             | ts                     | R       |                                         |
| trigger                | enum CheckpointTrigger | R       | batch_end, company_end, stop, interval  |
| batch_index            | int                    | O       |                                         |
| terminal_orgnrs        | list\[str(9)\]         | R       | companies with terminal status          |
| pending_orgnrs         | list\[str(9)\]         | R       |                                         |
| ledger_snapshot        | json                   | R       | BudgetLedger values                     |
| file_hashes            | json                   | R       | path → sha256 of outputs written so far |
| job_status             | enum                   | R       | status at checkpoint                    |
| sequence               | int                    | R       | monotonic per job                       |
| previous_checkpoint_id | str                    | O       | chain                                   |

Rule: the checkpoint is written to a temporary file, fsynced, then renamed (Lite). A checkpoint whose file hashes do not match outputs triggers a verification warning at resume.

### 4.17 ChangeRecord

| **Field**        | **Type**        | **R/O** | **Rule**                                                                 |
|------------------|-----------------|---------|--------------------------------------------------------------------------|
| change_id        | str(uuid)       | R       |                                                                          |
| orgnr            | str(9)          | R       |                                                                          |
| job_id           | str(uuid)       | R       | job that detected the change                                             |
| field            | str             | R       | field name (for example roles, website_url, legal_name, fact:leadership) |
| previous_value   | json            | O       | null when new                                                            |
| new_value        | json            | O       | null when removed                                                        |
| previous_fact_id | str(uuid)       | O       |                                                                          |
| new_fact_id      | str(uuid)       | O       |                                                                          |
| source_id        | str(uuid)       | R       |                                                                          |
| detected_at      | ts              | R       |                                                                          |
| evidence_refs    | list\[str\]     | R       | snapshot sha256 values                                                   |
| kind             | enum ChangeKind | R       | added, removed, modified                                                 |

Rule: a change is recorded only when the newly validated value differs from the previous published value (after normalisation). Unchanged values produce no record.

### 4.18 RunReport

| **Field**            | **Type**        | **R/O** | **Rule**                                                                     |
|----------------------|-----------------|---------|------------------------------------------------------------------------------|
| job_id               | str(uuid)       | R       | PK                                                                           |
| report_version       | str             | R       | "1.0"                                                                        |
| mode                 | enum JobMode    | R       |                                                                              |
| started_at           | ts              | R       |                                                                              |
| ended_at             | ts              | R       |                                                                              |
| duration_seconds     | int             | R       | ≥ 0                                                                          |
| company_count        | int             | R       |                                                                              |
| outcomes             | json            | R       | counts per processing status                                                 |
| requests             | json            | R       | total and requests_by_kind                                                   |
| llm_calls            | int             | R       |                                                                              |
| input_tokens         | int             | R       |                                                                              |
| output_tokens        | int             | R       |                                                                              |
| tokens_estimated     | bool            | R       |                                                                              |
| estimated_cost_usd   | dec             | R       |                                                                              |
| cost_limit_usd       | dec             | R       |                                                                              |
| time_limit_min       | int or null     | R       | 45 for daily_test; int or null for baseline_batch and pilot (null = no fixed limit) |
| stop_reason          | enum StopReason | R       |                                                                              |
| flags                | json            | R       | soft_cap_reached, brake_tripped, kill_switch_tripped, plan_a_outage_detected |
| plan_b_used_count    | int             | R       |                                                                              |
| rejections_by_reason | json            | R       |                                                                              |
| checkpoint           | json            | O       | {checkpoint_id, sha256}                                                      |
| config_hash          | str(64)         | R       |                                                                              |
| code_version         | str             | R       |                                                                              |

Rule: values equal the BudgetLedger and JobCompany totals at the moment of report creation (TA-14).

## 5. Enumerations

### 5.1 FactKey (fixed menu, p.10)

products, mission, customers, markets, scale, history, leadership, other_key_fact.

Adding a key requires a documented change (brief Rule 5; ADR-12).

### 5.2 Job and company states

| **Enum**                   | **Values**                                                                                                                                                                                        |
|----------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| JobStatus                  | queued, pass1_running, pass1_complete, pass2_running, completed, stopped_budget, stopped_time, stopped_storage, failed, cancelled                                                                 |
| ProcessingStatus (company) | pending, pass1_running, pass1_complete, pass2_running, published, registry_only, not_found, registry_unavailable, not_processed_budget, failed                                                    |
| StopReason                 | none, completed, request_brake, soft_cap_only, time_hard_stop, kill_switch, daily_request_limit, daily_cost_limit, baseline_request_cap, baseline_cost_limit, operator_interrupt, storage_failure |

Note: none is used only while running. soft_cap_only is not a stop; it is recorded as a flag. It appears in the enum only so that a run that ends normally with the soft cap reached can be labelled accurately (ADR-13).

### 5.3 Flags

website_unreachable, blocked_403, no_website, time_limit_registry_only, request_brake, llm_skipped, financials_unavailable, not_processed_budget, conflicts_with_registry, plan_a_outage, no_accounts_filed, identity_failed (page-level), playwright_failed, llm_invalid_json, llm_rate_limited, interrupted_resumed.

### 5.4 ReasonCode (rejections and input)

Input: length_not_9, non_digit, mod11_checksum_failed. Fact: schema_invalid, identity_failed, quote_not_found, quote_translated, value_unsupported, digit_unsupported, name_unsupported, money_blocked, below_threshold, llm_invalid_json, fetch_failed, conflicts_with_registry (12 fact codes in total, matching §7.2 and §8).

### 5.5 Other enums

| **Enum**                   | **Values**                                                                                                                                                                                                                                    |
|----------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| FactMethod                 | registry, llm_verified, structured_fallback                                                                                                                                                                                                   |
| FinancialMethod            | registry, structured_fallback, unavailable                                                                                                                                                                                                    |
| FinancialMetric            | revenue, operating_result, net_result, total_assets, equity (exact list pending OQ-16)                                                                                                                                                        |
| FinancialUnavailableReason | plan_b_not_permitted, unit_unclear, org_mismatch, value_not_in_page, no_accounts_filed, plan_a_and_b_failed, plan_c_active                                                                                                                    |
| FactTag                    | time_relative, self_reported                                                                                                                                                                                                                  |
| SourceKind                 | registry, company_website, plan_b_reader, other                                                                                                                                                                                               |
| ValidationStage            | fetch, schema, identity, quote, value, money, registry_clash, confidence                                                                                                                                                                      |
| ValidationDecision         | publish, reject, abstain                                                                                                                                                                                                                      |
| MoneyDecision              | not_money, harmless_passed, blocked, registry_source                                                                                                                                                                                          |
| PublicationStatus          | published, superseded                                                                                                                                                                                                                         |
| JobMode                    | daily_test, baseline_batch, pilot                                                                                                                                                                                                             |
| CompanyStatusRegistry      | active, deleted, bankrupt, dissolved, unknown (exact registry values to be mapped after verification, EV-02)                                                                                                                                  |
| VerificationStatus         | verified, abstained, unavailable                                                                                                                                                                                                              |
| CheckpointTrigger          | batch_end, company_end, stop, interval                                                                                                                                                                                                        |
| ChangeKind                 | added, removed, modified                                                                                                                                                                                                                      |
| EventType                  | job.started, company.registry, company.scraper, company.llm, company.validator, company.rejected, company.finished, budget.update, budget.soft_cap, budget.brake, killswitch.projection, killswitch.tripped, job.finished, job.resumed, error |
| RoleType                   | board_member, chair, deputy_chair, ceo, other                                                                                                                                                                                                 |

## 6. Entity-relationship diagram

*\[Mermaid source (not rendered)\]*

```text
erDiagram
    COMPANY ||--o| DOSSIER : "has profile"
    COMPANY ||--o{ REGISTRY_RECORD : "registry reads"
    COMPANY ||--o{ JOB_COMPANY : "processed in"
    DOSSIER ||--o{ COMPANY_ROLE : "lists"
    DOSSIER ||--o{ FINANCIAL_RECORD : "summarises"
    DOSSIER ||--o{ PUBLISHED_FACT : "contains"
    DOSSIER ||--o{ CHANGE_RECORD : "changes"
    SOURCE_DOCUMENT ||--o{ CANDIDATE_FACT : "yields"
    SOURCE_DOCUMENT }o--|| EVIDENCE_SNAPSHOT : "stored as"
    CANDIDATE_FACT ||--|| VALIDATION_RESULT : "validated by"
    CANDIDATE_FACT ||--o| PUBLISHED_FACT : "publishes as"
    CANDIDATE_FACT ||--o| REJECTION_RECORD : "rejected as"
    PROCESSING_JOB ||--o{ JOB_COMPANY : "contains"
    PROCESSING_JOB ||--|| BUDGET_LEDGER : "governed by"
    PROCESSING_JOB ||--o{ PROCESSING_EVENT : "emits"
    PROCESSING_JOB ||--o{ CHECKPOINT : "recovers with"
    PROCESSING_JOB ||--o| RUN_REPORT : "summarised in"
    PROCESSING_JOB ||--o{ REJECTION_RECORD : "records"
    PUBLISHED_FACT }o--|| SOURCE_DOCUMENT : "cites"
    FINANCIAL_RECORD }o--|| REGISTRY_RECORD : "from"
```

Note: the diagram uses Mermaid erDiagram names in upper case with underscores (Mermaid requires them). Entity names match §3.

## 7. JSON Schema definitions

The schemas below use JSON Schema draft 2020-12. They are the wire and storage contracts; Pydantic models (§8) implement them. Each schema is valid JSON.

### 7.1 PublishedFact

*\[json\]*

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://signalpost.local/schemas/published_fact.json",
  "title": "PublishedFact",
  "type": "object",
  "additionalProperties": false,
  "required": [
    "fact_id", "orgnr", "key", "value", "value_no", "method", "source_id",
    "source_url", "retrieved_at", "sha256", "as_of", "tags", "flags",
    "identity_score", "q", "v", "g", "s", "f", "confidence",
    "publication_status", "validation_id", "created_at"
  ],
  "properties": {
    "fact_id": {"type": "string", "format": "uuid"},
    "orgnr": {"type": "string", "pattern": "^[0-9]{9}$"},
    "key": {"enum": ["products", "mission", "customers", "markets", "scale", "history", "leadership", "other_key_fact"]},
    "value": {"type": "string", "minLength": 1, "maxLength": 300},
    "value_no": {"type": "string", "minLength": 1, "maxLength": 300},
    "quote": {"type": ["string", "null"], "maxLength": 600},
    "registry_json_path": {"type": ["string", "null"]},
    "method": {"enum": ["registry", "llm_verified", "structured_fallback"]},
    "source_id": {"type": "string", "format": "uuid"},
    "source_url": {"type": "string", "format": "uri"},
    "retrieved_at": {"type": "string", "format": "date-time"},
    "sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "as_of": {"type": "string", "format": "date-time"},
    "tags": {"type": "array", "uniqueItems": true, "items": {"enum": ["time_relative", "self_reported"]}},
    "flags": {"type": "array", "uniqueItems": true, "items": {"type": "string"}},
    "identity_score": {"type": "string", "pattern": "^(0(\\.[0-9]{1,2})?|1(\\.00?)?)$"},
    "q": {"enum": ["0.00", "1.00"]},
    "v": {"enum": ["0", "1"]},
    "g": {"enum": ["0", "1"]},
    "s": {"enum": ["0.5", "0.7", "0.8", "1.0"]},
    "f": {"enum": ["0.4", "0.7", "1.0"]},
    "confidence": {"type": "string", "pattern": "^[01]\\.[0-9]{2}$"},
    "publication_status": {"enum": ["published", "superseded"]},
    "validation_id": {"type": "string", "format": "uuid"},
    "created_at": {"type": "string", "format": "date-time"}
  },
  "allOf": [
    {
      "if": {"properties": {"method": {"const": "registry"}}, "required": ["method"]},
      "then": {"properties": {"quote": {"type": "null"}}, "required": ["registry_json_path"]}
    },
    {
      "if": {"properties": {"method": {"const": "llm_verified"}}, "required": ["method"]},
      "then": {"properties": {"quote": {"type": "string", "minLength": 1}}}
    }
  ]
}
```

Note: confidence is stored as a string in JSON to preserve decimal representation. The pattern cannot test the ≥ 0.80 rule; that invariant is enforced by Pydantic and by test TA-13.

### 7.2 RejectionRecord

*\[json\]*

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://signalpost.local/schemas/rejection_record.json",
  "title": "RejectionRecord",
  "type": "object",
  "additionalProperties": false,
  "required": ["rejection_id", "job_id", "orgnr", "validation_stage", "reason_code", "diagnostic", "rejected_at"],
  "properties": {
    "rejection_id": {"type": "string", "format": "uuid"},
    "job_id": {"type": "string", "format": "uuid"},
    "orgnr": {"type": "string", "pattern": "^[0-9]{9}$"},
    "candidate_id": {"type": ["string", "null"], "format": "uuid"},
    "source_id": {"type": ["string", "null"], "format": "uuid"},
    "source_url": {"type": ["string", "null"], "format": "uri"},
    "rejected_value": {"type": ["string", "null"], "maxLength": 300},
    "validation_stage": {"enum": ["fetch", "schema", "identity", "quote", "value", "money", "registry_clash", "confidence"]},
    "reason_code": {"enum": ["schema_invalid", "identity_failed", "quote_not_found", "quote_translated", "value_unsupported", "digit_unsupported", "name_unsupported", "money_blocked", "below_threshold", "llm_invalid_json", "fetch_failed", "conflicts_with_registry"]},
    "diagnostic": {"type": "object", "additionalProperties": true},
    "rejected_at": {"type": "string", "format": "date-time"}
  }
}
```

### 7.3 FinancialRecord

*\[json\]*

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://signalpost.local/schemas/financial_record.json",
  "title": "FinancialRecord",
  "type": "object",
  "additionalProperties": false,
  "required": ["financial_id", "orgnr", "metric", "fiscal_year", "method", "source_url", "source_ref", "org_match", "unit_verified", "retrieved_at", "verification_status"],
  "properties": {
    "financial_id": {"type": "string", "format": "uuid"},
    "orgnr": {"type": "string", "pattern": "^[0-9]{9}$"},
    "metric": {"enum": ["revenue", "operating_result", "net_result", "total_assets", "equity"]},
    "fiscal_year": {"type": "integer", "minimum": 1900, "maximum": 2100},
    "period_start": {"type": ["string", "null"], "format": "date"},
    "period_end": {"type": ["string", "null"], "format": "date"},
    "amount": {"type": ["string", "null"], "pattern": "^-?[0-9]+(\\.[0-9]+)?$"},
    "currency": {"type": ["string", "null"], "pattern": "^[A-Z]{3}$"},
    "unit_scale": {"type": ["integer", "null"], "enum": [1, 1000, 1000000, null]},
    "amount_as_printed": {"type": ["string", "null"], "maxLength": 40},
    "amount_base": {"type": ["string", "null"], "pattern": "^-?[0-9]+(\\.[0-9]+)?$"},
    "method": {"enum": ["registry", "structured_fallback", "unavailable"]},
    "source_url": {"type": "string", "format": "uri"},
    "source_ref": {"type": "string"},
    "org_match": {"type": "boolean"},
    "unit_verified": {"type": "boolean"},
    "retrieved_at": {"type": "string", "format": "date-time"},
    "sha256": {"type": ["string", "null"], "pattern": "^[0-9a-f]{64}$"},
    "unavailable_reason": {"type": ["string", "null"]},
    "verification_status": {"enum": ["verified", "abstained", "unavailable"]}
  },
  "allOf": [
    {
      "if": {"properties": {"amount": {"type": "string"}}, "required": ["amount"]},
      "then": {"required": ["currency", "unit_scale", "amount_as_printed", "amount_base"]}
    },
    {
      "if": {"properties": {"method": {"const": "structured_fallback"}}, "required": ["method"]},
      "then": {"properties": {"unit_verified": {"const": true}, "org_match": {"const": true}}}
    }
  ]
}
```

### 7.4 ProcessingJob

*\[json\]*

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://signalpost.local/schemas/processing_job.json",
  "title": "ProcessingJob",
  "type": "object",
  "additionalProperties": false,
  "required": ["job_id", "request_hash", "mode", "status", "current_pass", "submitted_at", "input_count", "rejected_input_count", "completed_count", "failed_count", "registry_only_count", "config_hash", "code_version"],
  "properties": {
    "job_id": {"type": "string", "format": "uuid"},
    "idempotency_key": {"type": ["string", "null"], "maxLength": 128},
    "request_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "mode": {"enum": ["daily_test", "baseline_batch", "pilot"]},
    "status": {"enum": ["queued", "pass1_running", "pass1_complete", "pass2_running", "completed", "stopped_budget", "stopped_time", "stopped_storage", "failed", "cancelled"]},
    "current_pass": {"type": "integer", "enum": [0, 1, 2]},
    "submitted_at": {"type": "string", "format": "date-time"},
    "started_at": {"type": ["string", "null"], "format": "date-time"},
    "ended_at": {"type": ["string", "null"], "format": "date-time"},
    "input_count": {"type": "integer", "minimum": 0},
    "rejected_input_count": {"type": "integer", "minimum": 0},
    "completed_count": {"type": "integer", "minimum": 0},
    "failed_count": {"type": "integer", "minimum": 0},
    "registry_only_count": {"type": "integer", "minimum": 0},
    "stop_reason": {"type": ["string", "null"], "enum": ["none", "completed", "request_brake", "soft_cap_only", "time_hard_stop", "kill_switch", "daily_request_limit", "daily_cost_limit", "baseline_request_cap", "baseline_cost_limit", "operator_interrupt", "storage_failure", null]},
    "config_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "code_version": {"type": "string", "minLength": 7},
    "checkpoint_ref": {"type": ["string", "null"]},
    "batch_index": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
    "batch_count": {"type": ["integer", "null"], "minimum": 1, "maximum": 10},
    "label": {"type": ["string", "null"], "maxLength": 120}
  }
}
```

### 7.5 RunReport

*\[json\]*

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://signalpost.local/schemas/run_report.json",
  "title": "RunReport",
  "type": "object",
  "additionalProperties": false,
  "required": ["job_id", "report_version", "mode", "started_at", "ended_at", "duration_seconds", "company_count", "outcomes", "requests", "llm_calls", "input_tokens", "output_tokens", "tokens_estimated", "estimated_cost_usd", "cost_limit_usd", "time_limit_min", "stop_reason", "flags", "plan_b_used_count", "rejections_by_reason", "config_hash", "code_version"],
  "properties": {
    "job_id": {"type": "string", "format": "uuid"},
    "report_version": {"const": "1.0"},
    "mode": {"enum": ["daily_test", "baseline_batch", "pilot"]},
    "started_at": {"type": "string", "format": "date-time"},
    "ended_at": {"type": "string", "format": "date-time"},
    "duration_seconds": {"type": "integer", "minimum": 0},
    "company_count": {"type": "integer", "minimum": 0},
    "outcomes": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
    "requests": {
      "type": "object",
      "required": ["total", "by_kind"],
      "properties": {
        "total": {"type": "integer", "minimum": 0, "maximum": 2000},
        "by_kind": {
          "type": "object",
          "additionalProperties": {"type": "integer", "minimum": 0}
        }
      }
    },
    "llm_calls": {"type": "integer", "minimum": 0},
    "input_tokens": {"type": "integer", "minimum": 0},
    "output_tokens": {"type": "integer", "minimum": 0},
    "tokens_estimated": {"type": "boolean"},
    "estimated_cost_usd": {"type": "string", "pattern": "^[0-9]+\\.[0-9]{2,4}$"},
    "cost_limit_usd": {"type": "string", "pattern": "^[0-9]+(\\.[0-9]{1,2})?$"},
    "time_limit_min": {"type": ["integer", "null"]},
    "stop_reason": {"type": "string"},
    "flags": {
      "type": "object",
      "required": ["soft_cap_reached", "brake_tripped", "kill_switch_tripped", "plan_a_outage_detected"],
      "properties": {
        "soft_cap_reached": {"type": "boolean"},
        "brake_tripped": {"type": "boolean"},
        "kill_switch_tripped": {"type": "boolean"},
        "plan_a_outage_detected": {"type": "boolean"}
      }
    },
    "plan_b_used_count": {"type": "integer", "minimum": 0},
    "rejections_by_reason": {"type": "object", "additionalProperties": {"type": "integer", "minimum": 0}},
    "checkpoint": {"type": ["object", "null"]},
    "config_hash": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
    "code_version": {"type": "string", "minLength": 7}
  }
}
```

Note: requests.total maximum is 2,000 because it must never exceed the daily limit. In baseline mode the per-batch total is also ≤ 2,000 by the daily-batch rule (p.5); the baseline global total (14,000) is recorded in a separate baseline summary (see §9.10).

Note: time_limit_min accepts an integer or null. A daily test reports 45. Baseline and pilot reports are not tied to the 45-minute test window (the full baseline takes about 2.5 hours across its batches), so they may report null or another integer without failing schema validation.

## 8. Pydantic model examples

These examples show the intended implementation shape. They are not yet code. Field names and enums match §4–5.

*\[python\]*

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

FactKeyT = Literal["products", "mission", "customers", "markets",
                   "scale", "history", "leadership", "other_key_fact"]

class Method(str, Enum):
    REGISTRY = "registry"
    LLM_VERIFIED = "llm_verified"
    STRUCTURED_FALLBACK = "structured_fallback"

class Fact(BaseModel):
    """LLM output contract (manual p.10). Five fields only."""
    model_config = ConfigDict(extra="forbid")
    key: FactKeyT
    value: str = Field(min_length=1, max_length=300)
    value_no: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=600)
    source_url: str

class Extraction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    facts: list[Fact] = Field(max_length=20)   # [] is valid

class PublishedFactModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    fact_id: UUID
    orgnr: str
    key: FactKeyT
    value: str
    value_no: str
    quote: Optional[str] = None
    registry_json_path: Optional[str] = None
    method: Method
    source_id: UUID
    source_url: str
    retrieved_at: datetime
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    as_of: datetime
    tags: list[Literal["time_relative", "self_reported"]] = []
    flags: list[str] = []
    identity_score: Decimal
    q: Decimal
    v: Decimal
    g: Decimal
    s: Decimal
    f: Decimal
    confidence: Decimal
    publication_status: Literal["published", "superseded"]
    validation_id: UUID
    created_at: datetime

    @field_validator("orgnr")
    @classmethod
    def orgnr_9_digits(cls, v: str) -> str:
        if len(v) != 9 or not v.isdigit():
            raise ValueError("orgnr must be 9 digits")
        return v

    @model_validator(mode="after")
    def publication_rules(self):
        # Confidence threshold (manual p.15)
        if self.publication_status == "published" and self.confidence < Decimal("0.80"):
            raise ValueError("published facts require confidence >= 0.80")
        # Registry facts skip Q and V and carry no quote (manual p.16)
        if self.method is Method.REGISTRY:
            if self.quote is not None or self.registry_json_path is None:
                raise ValueError("registry facts need a JSON path and no quote")
        # AI facts need an exact quote
        if self.method is Method.LLM_VERIFIED and not self.quote:
            raise ValueError("AI facts require an exact quote")
        return self

class RejectionReason(str, Enum):
    """Fact-rejection reason codes (the same 12 values as the 7.2 reason_code enum)."""
    QUOTE_NOT_FOUND = "quote_not_found"
    QUOTE_TRANSLATED = "quote_translated"
    MONEY_BLOCKED = "money_blocked"
    IDENTITY_FAILED = "identity_failed"
    VALUE_UNSUPPORTED = "value_unsupported"
    BELOW_THRESHOLD = "below_threshold"
    SCHEMA_INVALID = "schema_invalid"
    DIGIT_UNSUPPORTED = "digit_unsupported"
    NAME_UNSUPPORTED = "name_unsupported"
    LLM_INVALID_JSON = "llm_invalid_json"
    FETCH_FAILED = "fetch_failed"
    CONFLICTS_WITH_REGISTRY = "conflicts_with_registry"

class RejectionRecordModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    rejection_id: UUID
    job_id: UUID
    orgnr: str
    candidate_id: Optional[UUID] = None
    source_id: Optional[UUID] = None
    source_url: Optional[str] = None
    rejected_value: Optional[str] = Field(default=None, max_length=300)
    validation_stage: Literal["fetch", "schema", "identity", "quote",
                              "value", "money", "registry_clash", "confidence"]
    reason_code: RejectionReason
    diagnostic: dict = {}
    rejected_at: datetime

class FinancialRecordModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    financial_id: UUID
    orgnr: str
    metric: Literal["revenue", "operating_result", "net_result", "total_assets", "equity"]
    fiscal_year: int = Field(ge=1900, le=2100)
    amount: Optional[Decimal] = None          # Decimal, never float
    currency: Optional[str] = Field(default=None, pattern=r"^[A-Z]{3}$")
    unit_scale: Optional[Literal[1, 1000, 1000000]] = None
    amount_as_printed: Optional[str] = None
    amount_base: Optional[Decimal] = None
    method: Literal["registry", "structured_fallback", "unavailable"]
    source_url: str
    source_ref: str
    org_match: bool
    unit_verified: bool
    retrieved_at: datetime
    sha256: Optional[str] = None
    unavailable_reason: Optional[str] = None
    verification_status: Literal["verified", "abstained", "unavailable"]

    @model_validator(mode="after")
    def money_rules(self):
        if self.amount is not None:
            if None in (self.currency, self.unit_scale, self.amount_as_printed, self.amount_base):
                raise ValueError("amount requires currency, unit_scale, printed text and base amount")
            if self.amount_base != self.amount * self.unit_scale:
                raise ValueError("amount_base must equal amount x unit_scale")
        if self.method is not None and self.method == "structured_fallback":
            if not (self.org_match and self.unit_verified):
                raise ValueError("Plan B values require org match and verified unit")
        return self
```

Note: amount_base != amount \* unit_scale compares Decimal to Decimal times int; Decimal \* int is exact. Equality test is exact.

## 9. Example JSON records

All examples are valid JSON. Company names are fictional. Orgnrs pass MOD-11.

### 9.1 Company dossier (illustrative)

*\[json\]*

```json
{
  "dossier_id": "923456783",
  "orgnr": "923456783",
  "legal_name": "Eksempel Fiskefôr AS",
  "org_form": "AS",
  "registry_status": "active",
  "website_url": "https://eksempel-fiskefor.no",
  "website_official_domain": "eksempel-fiskefor.no",
  "processing_status": "published",
  "flags": [],
  "verified_fact_count": 2,
  "registry_fields": {
    "municipality": {"value": "Eksempel kommune", "json_path": "$.forretningsadresse.kommune"},
    "employees": {"value": 12, "json_path": "$.antallAnsatte", "as_of": "2026-10-16T08:30:00Z"}
  },
  "roles": [
    {"person_name": "Ola Nordmann", "role": "Styreleder", "role_normalised": "chair"},
    {"person_name": "Kari Eksempel", "role": "Daglig leder", "role_normalised": "ceo"}
  ],
  "financial_summary": [
    {
      "metric": "revenue",
      "fiscal_year": 2025,
      "amount": "1504112",
      "currency": "NOK",
      "unit_scale": 1,
      "amount_as_printed": "1 504 112",
      "amount_base": "1504112",
      "method": "registry",
      "verification_status": "verified"
    }
  ],
  "published_fact_ids": [
    "0f6b2c1e-3a9d-4b8e-8c7f-1a2b3c4d5e6f",
    "7d9e1f2a-4b6c-4d8e-9f0a-b1c2d3e4f5a6"
  ],
  "data_freshness": "2026-10-16T08:33:50Z",
  "created_at": "2026-10-16T08:31:10Z",
  "updated_at": "2026-10-16T08:34:02Z",
  "job_id": "5f1c2a9e-7d3b-4c1e-9a8f-2b6d4e0c1a77",
  "schema_version": "1.0"
}
```

Note: the registry field names in registry_fields are illustrative. Real Brreg field names must be verified (EV-02).

### 9.2 Published fact (AI-verified, company website)

*\[json\]*

```json
{
  "fact_id": "0f6b2c1e-3a9d-4b8e-8c7f-1a2b3c4d5e6f",
  "orgnr": "923456783",
  "key": "products",
  "value": "Sells fish feed to salmon farms",
  "value_no": "Selger fôr til lakseoppdrett",
  "quote": "Vi leverer fôr til lakseoppdrett over hele Norge.",
  "registry_json_path": null,
  "method": "llm_verified",
  "source_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "source_url": "https://eksempel-fiskefor.no/om-oss",
  "retrieved_at": "2026-10-16T08:33:50Z",
  "sha256": "ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12",
  "as_of": "2026-10-16T08:33:50Z",
  "tags": [],
  "flags": [],
  "identity_score": "1.00",
  "q": "1.00",
  "v": "1",
  "g": "1",
  "s": "0.8",
  "f": "1.0",
  "confidence": "0.88",
  "publication_status": "published",
  "validation_id": "3c4d5e6f-7a8b-4c9d-8e0f-1a2b3c4d5e6f",
  "created_at": "2026-10-16T08:34:01Z"
}
```

The sha256 in this example is a placeholder value of the correct length and format. It is not the hash of any real page.

Check: 1.00 × 1 × 1 × (0.6 × 0.8 + 0.4 × 1.0) = 0.88 ✓ (manual p.16 example).

Note on the value and quote: the quote is Norwegian and the value is English. value_no uses words from the quote ("fôr", "lakseoppdrett") per p.11. The example is a valid form, not a real published fact.

### 9.3 Rejected fact (translated quotation)

*\[json\]*

```json
{
  "rejection_id": "5e6f7a8b-9c0d-4e1f-8a2b-3c4d5e6f7a8b",
  "job_id": "5f1c2a9e-7d3b-4c1e-9a8f-2b6d4e0c1a77",
  "orgnr": "923456783",
  "candidate_id": "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d",
  "source_id": "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d",
  "source_url": "https://eksempel-fiskefor.no/om-oss",
  "rejected_value": "Supplies feed across all of Norway",
  "validation_stage": "quote",
  "reason_code": "quote_translated",
  "diagnostic": {
    "q_raw": "0.00",
    "quote_language": "en",
    "page_language": "no",
    "repair_attempted": true,
    "repair_result": "failed"
  },
  "rejected_at": "2026-10-16T08:34:03Z"
}
```

### 9.4 Financial record (Plan A, registry)

*\[json\]*

```json
{
  "financial_id": "2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e",
  "orgnr": "923456783",
  "metric": "revenue",
  "fiscal_year": 2025,
  "period_start": "2025-01-01",
  "period_end": "2025-12-31",
  "amount": "1504112",
  "currency": "NOK",
  "unit_scale": 1,
  "amount_as_printed": "1 504 112",
  "amount_base": "1504112",
  "method": "registry",
  "source_url": "https://data.brreg.example/regnskap/923456783",
  "source_ref": "reg-rec-0001",
  "org_match": true,
  "unit_verified": true,
  "retrieved_at": "2026-10-16T08:30:05Z",
  "sha256": null,
  "unavailable_reason": null,
  "verification_status": "verified"
}
```

The source_url above is a placeholder. The real Plan A endpoint is EV-01 / EV-02.

### 9.5 Financial record (Plan B, abstained)

*\[json\]*

```json
{
  "financial_id": "3c4d5e6f-7a8b-4c9d-8e0f-2a3b4c5d6e7f",
  "orgnr": "984851006",
  "metric": "revenue",
  "fiscal_year": 2025,
  "period_start": null,
  "period_end": null,
  "amount": null,
  "currency": null,
  "unit_scale": null,
  "amount_as_printed": null,
  "amount_base": null,
  "method": "unavailable",
  "source_url": "https://www.proff.no/example-profile",
  "source_ref": "snap-0002",
  "org_match": true,
  "unit_verified": false,
  "retrieved_at": "2026-10-16T08:40:12Z",
  "sha256": "cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34",
  "unavailable_reason": "unit_unclear",
  "verification_status": "abstained"
}
```

Note: Plan B is disabled by default (ADR-06). This record illustrates the abstention path; it presupposes the gate has been opened and does not confirm that the source is permitted.

### 9.6 Processing job (daily test, in progress)

*\[json\]*

```json
{
  "job_id": "5f1c2a9e-7d3b-4c1e-9a8f-2b6d4e0c1a77",
  "idempotency_key": "daily-2026-10-16-a",
  "request_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "mode": "daily_test",
  "status": "pass2_running",
  "current_pass": 2,
  "submitted_at": "2026-10-16T08:30:00Z",
  "started_at": "2026-10-16T08:30:02Z",
  "ended_at": null,
  "input_count": 100,
  "rejected_input_count": 2,
  "completed_count": 74,
  "failed_count": 3,
  "registry_only_count": 21,
  "stop_reason": "none",
  "config_hash": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
  "code_version": "a1b2c3d",
  "checkpoint_ref": "ckpt-0001",
  "batch_index": null,
  "batch_count": null,
  "label": "daily-2026-10-16"
}
```

The request_hash and config_hash values are the SHA-256 of an empty string and of a placeholder, shown only to demonstrate format.

### 9.7 Run report (daily test, completed)

*\[json\]*

```json
{
  "job_id": "5f1c2a9e-7d3b-4c1e-9a8f-2b6d4e0c1a77",
  "report_version": "1.0",
  "mode": "daily_test",
  "started_at": "2026-10-16T08:30:02Z",
  "ended_at": "2026-10-16T08:44:19Z",
  "duration_seconds": 857,
  "company_count": 100,
  "outcomes": {
    "published": 61,
    "registry_only": 27,
    "not_found": 3,
    "registry_unavailable": 0,
    "not_processed_budget": 0,
    "failed": 9
  },
  "requests": {
    "total": 842,
    "by_kind": {
      "registry": 310,
      "website": 402,
      "plan_b": 0,
      "llm": 118,
      "retry": 9,
      "redirect_hop": 3,
      "playwright_page_equivalent": 0
    }
  },
  "llm_calls": 118,
  "input_tokens": 142300,
  "output_tokens": 18450,
  "tokens_estimated": true,
  "estimated_cost_usd": "0.0412",
  "cost_limit_usd": "10.00",
  "time_limit_min": 45,
  "stop_reason": "completed",
  "flags": {
    "soft_cap_reached": false,
    "brake_tripped": false,
    "kill_switch_tripped": false,
    "plan_a_outage_detected": false
  },
  "plan_b_used_count": 0,
  "rejections_by_reason": {
    "quote_not_found": 14,
    "money_blocked": 6,
    "identity_failed": 3,
    "below_threshold": 9
  },
  "checkpoint": {"checkpoint_id": "ckpt-0002", "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
  "config_hash": "2c26b46b68ffc68ff99b453c1d30413413422d706483bfa0f98a5e886266e7ae",
  "code_version": "a1b2c3d"
}
```

These numbers are illustrative and are not measured results. They show the shape of the report.

### 9.8 Event (live)

*\[json\]*

```json
{
  "job_id": "5f1c2a9e-7d3b-4c1e-9a8f-2b6d4e0c1a77",
  "seq": 1842,
  "ts": "2026-10-16T08:34:11Z",
  "type": "company.validator",
  "tag": "VALIDATOR",
  "orgnr": "923456783",
  "message": "2 verified, 1 rejected (quote not found)",
  "data": {"verified": 2, "rejected": 1, "reason_codes": ["quote_not_found"]}
}
```

### 9.9 Checkpoint

*\[json\]*

```json
{
  "checkpoint_id": "ckpt-0001",
  "job_id": "5f1c2a9e-7d3b-4c1e-9a8f-2b6d4e0c1a77",
  "created_at": "2026-10-16T08:40:00Z",
  "trigger": "company_end",
  "batch_index": null,
  "terminal_orgnrs": ["923456783", "984851006"],
  "pending_orgnrs": ["987654325", "500000015"],
  "ledger_snapshot": {"total_outbound_requests": 412, "llm_calls": 61, "estimated_cost_usd": "0.0210"},
  "file_hashes": {"output/dossiers.jsonl": "ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12cd34ef56ab12"},
  "job_status": "pass2_running",
  "sequence": 14,
  "previous_checkpoint_id": "ckpt-0000"
}
```

Note: the example file_hashes value is a placeholder.

### 9.10 Baseline summary (separate from daily run reports)

*\[json\]*

```json
{
  "baseline_id": "baseline-2026-10-18",
  "profiles_target": 1000,
  "batches": [
    {"batch_index": 1, "job_id": "5f1c2a9e-7d3b-4c1e-9a8f-2b6d4e0c1a77", "status": "completed", "requests_total": 0, "estimated_cost_usd": "0.0000"}
  ],
  "global_limits": {"request_cap": 14000, "cost_limit_usd": "5.00"},
  "global_totals": {"requests_total": 0, "estimated_cost_usd": "0.0000"},
  "stop_reason": null
}
```

This is a template with zero values. It does not describe any run that has occurred. The global totals are the sum of all batch ledgers and must be enforced across batches (SC-09, OQ-09).

## 10. Indexing strategy

| **Collection / file**       | **Index**                         | **Type**                             | **Purpose**             |
|-----------------------------|-----------------------------------|--------------------------------------|-------------------------|
| companies / companies.jsonl | orgnr                             | unique                               | Identity                |
| dossiers                    | orgnr                             | unique                               | Dossier lookup (E6)     |
| dossiers                    | processing_status                 | non-unique                           | Filter (E5)             |
| dossiers                    | registry_status                   | non-unique                           | Filter                  |
| dossiers                    | legal_name                        | text (Full); prefix in memory (Lite) | Search (E5 q)           |
| published_facts             | (orgnr, key)                      | compound                             | Dossier assembly        |
| published_facts             | sha256                            | non-unique                           | Evidence lookup         |
| rejections                  | (job_id, rejected_at)             | compound                             | Rejection Log (E8)      |
| rejections                  | reason_code                       | non-unique                           | Filter                  |
| processing_events           | (job_id, seq)                     | unique compound                      | SSE replay (E4)         |
| job_companies               | (job_id, orgnr)                   | unique                               | Job status              |
| evidence_snapshots          | sha256                            | unique                               | Vault lookup            |
| source_documents            | (orgnr, retrieved_at desc)        | compound                             | Source history          |
| financial_records           | (orgnr, metric, fiscal_year desc) | compound                             | Latest-year selection   |
| change_records              | (orgnr, detected_at desc)         | compound                             | Change Feed (E9)        |
| processing_jobs             | idempotency_key                   | unique sparse                        | Idempotency (TRD §17.3) |

## 11. Query strategy

- **Dossier list (E5):** Full mode: aggregation on dossiers with \$match for filters, sort on indexed fields, cursor on (sort_key, orgnr). Lite: in-memory filter and sort over the dossier index; cursor on (sort_key, orgnr).

- **Dossier detail (E6):** One read on dossiers plus published_facts by orgnr, financial_records latest year per metric, company_roles by orgnr.

- **Evidence (E7):** Read published_facts by fact_id; read evidence_snapshots by sha256; compute highlight offsets from stored quote position (stored at validation time as quote_start, quote_end, add to ValidationResult in implementation \[TR\]).

- **Rejection Log (E8):** Query rejections by job_id, then filters.

- **Event replay (E4):** Query processing_events where job_id and seq \> last_event_id, ordered by seq.

- **Budget (E11):** Read budget_ledgers for the job (or process totals in Lite).

Pagination: cursor-based; never offset-based for events.

## 12. Uniqueness rules

| **Rule**                        | **Enforcement (Lite)**                          | **Enforcement (Full)**                     |
|---------------------------------|-------------------------------------------------|--------------------------------------------|
| One Company per orgnr           | Check on write in memory index                  | Unique index                               |
| One Dossier per orgnr           | Check on write                                  | Unique index                               |
| One JobCompany per (job, orgnr) | Check on write                                  | Unique index                               |
| Event sequence unique per job   | Orchestrator allocates seq under lock           | Unique compound index                      |
| Snapshot sha256 unique          | File exists check (immutable write)             | Unique index                               |
| Idempotency key unique          | Key file per job                                | Unique sparse index                        |
| Published fact duplicate        | Check (orgnr, key, value_hash, sha256)          | Unique index                               |
| Forbidden personal fields       | Pydantic extra="forbid" and key filter on write | JSON Schema validator on collection \[TR\] |

## 13. Concurrency and transaction boundaries

### 13.1 Boundaries

| **Operation**               | **Boundary**                                                       | **Lite**                                                                                   | **Full**                                                                                                          |
|-----------------------------|--------------------------------------------------------------------|--------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| Budget reservation          | One atomic check-and-increment                                     | Lock around ledger                                                                         | Redis Lua script                                                                                                  |
| Company completion (Pass 2) | One unit: write dossier, facts, rejections and JobCompany together | Write a single company JSON record via temp file and rename; events appended after success | Single-document upsert for dossier; facts and rejections as keyed upserts; a company_complete marker written last |
| Event emission              | Append-only                                                        | Append to events.jsonl after seq allocation                                                | Insert into processing_events                                                                                     |
| Checkpoint                  | Write temp, fsync, rename                                          | Same                                                                                       | Insert into checkpoints and write file                                                                            |
| Run report                  | Write temp, rename                                                 | Same                                                                                       | Insert into run_reports                                                                                           |

### 13.2 Ordering rules

1\. The Governor reservation precedes the network call (TRD §13.2). A reservation without a recorded result is treated as spent (conservative).

2\. A company's facts are written only after its ValidationResults exist.

3\. The company_complete marker is written after all facts and rejections for that company; a resume ignores companies without the marker and re-runs them (idempotent upserts make re-runs safe).

4\. Events for a company are emitted only after the corresponding write succeeds, so the UI never shows an event for data that does not exist.

### 13.3 Concurrency control

- Lite: one process; orchestrator is the single writer for ledger and job files; workers hand results to the orchestrator via an asyncio queue. File writes are serialised.

- Full: multiple worker processes \[TR\]; the Governor uses Redis atomic scripts; Mongo writes use upserts keyed by natural keys (no read-modify-write races).

- Optimistic version field on BudgetLedger for audit (version), incremented on each checkpoint.

### 13.4 Transactions in MongoDB

Single-node MongoDB (typical Full mode) does not provide multi-document transactions. Design avoids them by using idempotent upserts and ordered writes with a completion marker (§13.2). If a replica set is configured later, the marker approach still applies.

## 14. Schema migration strategy

- schema_version on Dossier and report: "1.0" for this baseline.

- Lite: JSON files carry schema_version; a migration script (scripts/migrate.py \[TR\]) reads old versions and writes new ones into a new directory; old outputs are not modified.

- Full: MongoDB has no fixed schema; migrations are versioned scripts with a schema_migrations collection \[TR\]. Each migration is idempotent and recorded.

- Breaking changes (renamed fact key, changed enum) require an ADR and a major version bump (ADR-12).

- The fact menu (FactKey) may not change without a documented change (brief Rule 5).

- Migration tests: round-trip fixture from v1.0 to next version and back (TA-17).

## 15. Data lifecycle and retention

| **Data**                  | **Created**               | **Updated**                                   | **Retained**                                        | **Deleted by**                                 |
|---------------------------|---------------------------|-----------------------------------------------|-----------------------------------------------------|------------------------------------------------|
| Company, Dossier          | First job                 | Each job                                      | Indefinite (operator policy OQ-17)                  | Operator only (out of scope)                   |
| RegistryRecord            | Each registry read        | Never (append)                                | As evidence                                         | Operator                                       |
| CompanyRole               | With RegistryRecord       | Replaced on change (ChangeRecord keeps prior) | As dossier                                          | Operator                                       |
| FinancialRecord           | Each read                 | New year rows                                 | As dossier                                          | Operator                                       |
| SourceDocument            | Each fetch                | Never                                         | As evidence                                         | Operator                                       |
| EvidenceSnapshot          | First write of text       | Never (immutable)                             | While referenced; 30 days after unreferenced \[TR\] | Garbage collection job \[TR\]                  |
| CandidateFact             | Each extraction           | Validation attached                           | 90 days \[TR\] or per run                           | Retention job                                  |
| PublishedFact             | On publish                | Status to superseded on change                | As dossier                                          | Retention job for superseded (≥ 1 year \[TR\]) |
| ValidationResult          | On validation             | Never                                         | With CandidateFact                                  | With CandidateFact                             |
| RejectionRecord           | On rejection              | Never                                         | Per run; 90 days \[TR\]                             | Retention job                                  |
| ProcessingJob, JobCompany | On submission             | On status change                              | Indefinite (run history)                            | Operator                                       |
| ProcessingEvent           | Each event                | Never                                         | 30 days or per run \[TR\]                           | Retention job                                  |
| BudgetLedger              | At job creation           | Each checkpoint                               | With job                                            | With job                                       |
| Checkpoint                | Each batch or company end | Never                                         | Until job superseded                                | Retention job                                  |
| ChangeRecord              | On change                 | Never                                         | Indefinite                                          | Operator                                       |
| RunReport                 | At job end                | Never                                         | Indefinite                                          | Operator                                       |

**Privacy:** Names and roles are retained only as dossier content. No other personal data is collected (p.18). Retention periods marked \[TR\] are recommendations pending OQ-17.

**Exclusion from git:** snapshots and checkpoints are excluded from version control (p.12). Only dossiers and reports ship with the repository.

## 16. Lite-mode mapping

| **Entity**                      | **File / structure**                                                    | **Format**                       | **Writer**                                                          |
|---------------------------------|-------------------------------------------------------------------------|----------------------------------|---------------------------------------------------------------------|
| Company                         | output/companies.jsonl                                                  | JSON Lines                       | Orchestrator                                                        |
| Dossier                         | output/dossiers.jsonl (required by p.14, p.20)                          | JSON Lines; one dossier per line | Orchestrator (replace-by-orgnr on update via rewrite at checkpoint) |
| RegistryRecord                  | data/registry/{orgnr}/{retrieved_at}.json                               | JSON                             | Registry client                                                     |
| CompanyRole, FinancialRecord    | Embedded in dossier                                                     | JSON                             | Orchestrator                                                        |
| SourceDocument                  | output/sources.jsonl                                                    | JSON Lines                       | Scraper                                                             |
| EvidenceSnapshot                | data/snapshots/{sha256}.txt and .json                                   | Text and JSON                    | Evidence vault                                                      |
| CandidateFact, ValidationResult | output/candidates.jsonl                                                 | JSON Lines                       | Validators                                                          |
| PublishedFact                   | Embedded in dossier and output/facts.jsonl                              | JSON Lines                       | Confidence engine                                                   |
| RejectionRecord                 | output/rejections.jsonl (required by p.14, p.20)                        | JSON Lines                       | Validators                                                          |
| ProcessingJob, JobCompany       | output/jobs/{job_id}.json                                               | JSON                             | Orchestrator                                                        |
| ProcessingEvent                 | output/events.jsonl                                                     | JSON Lines                       | Event bus                                                           |
| BudgetLedger                    | output/ledger.json (snapshot) and output/ledger.jsonl (reservation log) | JSON                             | Governor                                                            |
| Checkpoint                      | output/checkpoints/{checkpoint_id}.json (required by p.20)              | JSON                             | Orchestrator                                                        |
| ChangeRecord                    | output/changes.jsonl                                                    | JSON Lines                       | Change Radar                                                        |
| RunReport                       | output/run_report.json (required by p.14, p.20)                         | JSON                             | Reporting                                                           |

Rules for Lite:

- Writes use temp file, fsync, rename.

- JSON Lines files are append-only except dossiers.jsonl, which is rewritten atomically at checkpoints from the in-memory index (or appended with a version and last-wins rule \[TR\] — ADR-02 decision pending).

- The in-memory index is rebuilt from files at startup and checked for duplicate keys (uniqueness §12).

- SQLite is not used (ADR-02).

## 17. Full-mode mapping

| **Entity**       | **Collection**     | **Key**            | **Indexes (see §10)**                                            |
|------------------|--------------------|--------------------|------------------------------------------------------------------|
| Company          | companies          | orgnr              | unique                                                           |
| Dossier          | dossiers           | orgnr              | unique; processing_status; registry_status; text(legal_name)     |
| RegistryRecord   | registry_records   | registry_record_id | (orgnr, retrieved_at desc); unique (orgnr, endpoint, raw_sha256) |
| CompanyRole      | company_roles      | role_id            | orgnr                                                            |
| FinancialRecord  | financial_records  | financial_id       | (orgnr, metric, fiscal_year desc)                                |
| SourceDocument   | source_documents   | source_id          | (orgnr, retrieved_at desc); sha256                               |
| EvidenceSnapshot | evidence_snapshots | sha256             | unique (text in volume)                                          |
| CandidateFact    | candidate_facts    | candidate_id       | (orgnr, key); source_id                                          |
| PublishedFact    | published_facts    | fact_id            | (orgnr, key); unique (orgnr, key, value_hash, sha256)            |
| ValidationResult | validation_results | validation_id      | candidate_id                                                     |
| RejectionRecord  | rejections         | rejection_id       | (job_id, rejected_at); reason_code                               |
| ProcessingJob    | processing_jobs    | job_id             | unique; unique sparse idempotency_key; (status, submitted_at)    |
| JobCompany       | job_companies      | (job_id, orgnr)    | unique compound                                                  |
| ProcessingEvent  | processing_events  | (job_id, seq)      | unique compound                                                  |
| BudgetLedger     | budget_ledgers     | job_id             | unique                                                           |
| Checkpoint       | checkpoints        | checkpoint_id      | (job_id, sequence)                                               |
| ChangeRecord     | change_records     | change_id          | (orgnr, detected_at desc)                                        |
| RunReport        | run_reports        | job_id             | unique                                                           |

Full-mode additions: Redis holds the queue and live counters (sp:{job_id}:\* keys). Redis is not the source of truth; the BudgetLedger document is written at each checkpoint and at job end, and the authoritative totals are reconciled from it on restart.

## 18. Consistency checks

| **Check**               | **Rule**                                                                       | **Test**              |
|-------------------------|--------------------------------------------------------------------------------|-----------------------|
| C1 Company identity     | Every Dossier.orgnr exists in Company                                          | Referential test      |
| C2 Fact keys            | Every PublishedFact.key ∈ FactKey menu                                         | Schema test           |
| C3 Money provenance     | FinancialRecord.method ∈ {registry, structured_fallback}; no LLM-sourced money | Contract test         |
| C4 Confidence           | Published ⇒ confidence ≥ 0.80                                                  | Unit test (TA-13)     |
| C5 Components           | confidence = q × v × g × (0.6s + 0.4f) for every published fact                | Property test         |
| C6 Evidence             | Every llm_verified PublishedFact has sha256 that exists in EvidenceSnapshot    | Referential test      |
| C7 Rejections distinct  | No PublishedFact id appears in RejectionRecord                                 | Set test              |
| C8 Timestamps           | All ts fields are UTC with Z                                                   | Schema test           |
| C9 Requests per company | JobCompany.requests_used ≤ 14                                                  | Invariant test        |
| C10 Totals              | RunReport.requests.total = BudgetLedger.total_outbound_requests                | Contract test (TA-14) |
| C11 Personal data       | No forbidden keys in CompanyRole                                               | Schema test           |
| C12 Round-trip          | JSON → Pydantic → JSON is stable for every example in §9                       | Contract test         |

The examples in §9 are intended to pass checks C1–C12 when treated as fixtures. They are documentation examples and must be re-checked when the implementation exists.
