# 04 — UI/UX Design Specification

| Field | Value |
|---|---|
| Document | 04 — UI/UX Design Specification |
| Version | 1.0 (documentation baseline) |
| Date | 16 October 2026 |
| Status | Draft. No mockup files have been generated for this document; wireframes below are text-based. |
| Authoring role | Principal Product Designer / UI-UX Architect, with Senior Frontend Engineer review |
| Source direction | Manual p.19: "dark theme, clear numbers", calm corporate intelligence tool |
| Companion documents | 01 PRD (FR-UI-*), 02 TRD §17 (API E1–E12), 05 Backend Schema (field names), 03 Flows |

## Contents

1. Design principles
2. Information architecture and navigation
3. Design tokens (colour, glass, type, spacing, elevation)
4. Reusable components
5. Interaction standards (tables, forms, keyboard, live regions)
6. Responsive behaviour
7. Accessibility
8. Screens 1–7 (purpose through acceptance criteria)
9. Cross-screen states and error language
10. Data-source map

---

## 1. Design principles

**Primary design language: Glassmorphism.** Panels, tables, banners and the side panel are frosted glass surfaces: translucent fills with background blur and subtle 1 px borders, on a flat dark canvas. This is a design decision for this product; the source manual (p.19) specifies only "dark theme, clear numbers". Glass is a surface treatment only. It never changes layout, information hierarchy or status meaning (see P8 and the glass tokens in Section 3.4).

| # | Principle | Practical meaning |
|---|---|---|
| P1 | Calm first | Dark neutral canvas, one accent colour, no decorative gradients or background imagery. Glass is applied to surfaces only (Section 3.4). Motion limited to state changes. |
| P2 | Numbers are the interface | Meters and counts use tabular numerals, units and denominators ("74 / 100"). |
| P3 | Every fact has a receipt | Any published fact is one click from its quotation and saved page. |
| P4 | Honest about absence | Empty, blank, abstained and rejected states are visible and explained, never hidden. |
| P5 | Status is never colour alone | Each status has a text label and an icon shape plus colour. |
| P6 | The UI reports the Governor, it does not compute it | Meters read `/api/budget`; the browser does no budget arithmetic. |
| P7 | No fake verification | The UI shows a verification state only when a ValidationResult exists. No decorative "verified" badges. |
| P8 | Legibility over effect | Glass never sits behind long text and never lowers contrast below WCAG 2.2 AA. Where blur is unsupported or reduced transparency is requested, surfaces use opaque fallback fills. |

## 2. Information architecture and navigation

### 2.1 Site map

| Route | Screen | Primary user | Source |
|---|---|---|---|
| `/` | Redirect to `/command-center` | All | — |
| `/command-center` | 1 Command Center | P1 Evaluator | p.19 |
| `/jobs/{job_id}/terminal` | 2 Live Agent Terminal | P1, P3 | p.19 |
| `/dossiers` | 3 Dossier Explorer | P1, P2 | p.19 |
| `/dossiers/{orgnr}` | Dossier detail (side panel also available on Explorer) | P2 | p.19 |
| `/dossiers/{orgnr}/facts/{fact_id}` | 4 Evidence Viewer | P2, P4 | p.19 |
| `/rejections` | 5 Rejection Log | P4 | p.19 |
| `/changes` | 6 Change Feed | P2, P4 | p.19 |
| `/jobs/{job_id}/report` | 7 Run Report | P3, P4 | p.14, p.20 |

Note: the source describes five screens (p.19), with the Rejection Log and Change Feed combined as "Screen 5". The brief requires seven numbered screens: 1 Command Center, 2 Live Agent Terminal, 3 Dossier Explorer, 4 Evidence Viewer, 5 Rejection Log, 6 Change Feed, 7 Run Report. This document uses the brief's numbering. The Dossier Detail is a sub-view of Screen 3, and the Run Report is added from p.14 and p.20. The mapping is recorded in the Source Review Ledger (00, Section 3).

### 2.2 Global navigation model

- **Left sidebar** (desktop ≥ 960 px): Command Center, Live Terminal (shows the active job), Dossier Explorer, Rejection Log, Change Feed, Run Report (for the selected job).
- **Top bar:** product name, current job label and status pill, mode indicator (`Lite` or `Full`), and the config status (`valid` / `valid with warnings`).
- **Breadcrumbs** on detail routes: Dossier Explorer › {legal name} › {fact key}.
- **Active job selector** in the top bar: the most recent job by default. Switching job updates all screens.
- The Evidence Viewer is opened from a fact badge, never from the sidebar.

### 2.3 Global persistent elements

| Element | Behaviour |
|---|---|
| Kill-switch banner | Appears in the top area when `killswitch.tripped` is received. Text: "Time limit safeguard active. Playwright disabled. Remaining companies use registry data only." Dismissible only for the session; the state stays visible in the sidebar footer. |
| Brake banner | Appears on `budget.brake`: "Request brake reached (1,950). No new outbound requests will be sent for this run." |
| Soft-cap warning | Appears on `budget.soft_cap` at 1,700: "Soft cap reached. Optional pages are skipped." |
| Connection indicator | Shows Live / Reconnecting / Offline (see §8.2). |

## 3. Design tokens

Design language: Glassmorphism (Section 1). The tokens in 3.1 set colour. The glass tokens in 3.4 set fill opacity, blur and border for glass surfaces. `bg.surface` and `bg.raised` are the tint of those fills and are also the opaque fallback values.

### 3.1 Colour (semantic)

Values are proposals. Contrast must meet WCAG 2.2 AA for normal text (4.5:1) and non-text UI (3:1).

| Token | Dark value (proposed) | Use |
|---|---|---|
| `bg.canvas` | `#0E1116` | Page background |
| `bg.surface` | `#161B22` | Panels, tables (glass tint and opaque fallback, see 3.4) |
| `bg.raised` | `#1C232C` | Side panel, modals (glass tint and opaque fallback, see 3.4) |
| `border.default` | `#2D3642` | Dividers, table lines |
| `text.primary` | `#E6EDF3` | Body text (contrast ≥ 12:1 on canvas) |
| `text.secondary` | `#9DA7B3` | Labels, metadata (≥ 6:1) |
| `text.muted` | `#7D8794` | Hints only, never sole information (≥ 4.6:1 on surface; verify) |
| `accent.primary` | `#4C8DFF` | Links, focus ring, primary button |
| `status.success` | `#3FB950` | Published, completed |
| `status.warning` | `#D29922` | Flag, soft cap, partial result |
| `status.danger` | `#F85149` | Rejected, failed, brake |
| `status.info` | `#58A6FF` | Registry-only, informational |
| `status.neutral` | `#8B949E` | Not processed, unavailable, informational flags (for example `no_website`) |
| `highlight.quote` | `#5C4B00` background with `#FFE58A` text | Quotation highlight in Evidence Viewer (yellow per p.19; text contrast verified at build) |

Rules: one accent colour; no gradients; no colour-only meaning; source-type colours are not used (source type is shown as text). Text contrast is measured on the glass composite (fill over canvas at the lowest fill opacity), not on the nominal token alone.

### 3.2 Typography

| Token | Family | Size / line height | Weight | Use |
|---|---|---|---|---|
| `type.display` | Inter (system fallback) | 28 / 34 | 600 | Screen titles |
| `type.h2` | Inter | 20 / 28 | 600 | Section headings |
| `type.h3` | Inter | 16 / 24 | 600 | Panel headings |
| `type.body` | Inter | 14 / 22 | 400 | Body |
| `type.small` | Inter | 12 / 18 | 500 | Labels, badges |
| `type.numeric` | Inter with `font-variant-numeric: tabular-nums` | 14 / 22 | 500 | Counts, money, meters |
| `type.mono` | JetBrains Mono (fallback: ui-monospace) | 13 / 20 | 400 | Orgnr, SHA-256, URLs, terminal lines |

Minimum font size is 12 px. Body text is 14 px at default zoom.

### 3.3 Spacing and layout

- 4 px base scale: 4, 8, 12, 16, 24, 32, 48.
- Panel padding 16 px (desktop), 12 px (mobile).
- Table row height 40 px (dense option 32 px).
- Max content width 1440 px; tables scroll horizontally inside their container, never the page.

### 3.4 Glass, elevation and radius

| Token | Value (proposed) | Use |
|---|---|---|
| `glass.surface` | Fill `rgba(22, 27, 34, 0.64)`; background blur 16 px | Panels, table containers, banners |
| `glass.raised` | Fill `rgba(28, 35, 44, 0.78)`; background blur 24 px | Side panel, modals, sticky headers over scrolling content |
| `glass.border` | `1px solid rgba(255, 255, 255, 0.12)` | Edge of every glass surface |
| `glass.dense` | Opaque `bg.surface`, no blur | DataTable body rows, TerminalLog, page text in EvidenceSplitView |
| `glass.fallback` | Opaque `bg.surface` or `bg.raised` | When `backdrop-filter` is unsupported, when reduced transparency is requested, in forced-colors mode and in print |

Rules:

- Blur is used only where content sits behind a surface (side panel over a table, sticky headers, modals, banners). The canvas is a flat colour with no decorative imagery.
- Dense-text regions use `glass.dense`, so blur never sits behind long text.
- Contrast is verified on the composite of the glass fill over the canvas and over the busiest content beneath it.
- Radius 6 px for panels and badges; 4 px for inputs.
- One elevation level for the side panel (`glass.raised`, 1 px `glass.border`, subtle shadow).

### 3.5 Motion

- Transitions 120–160 ms for state changes (badge colour, panel open).
- No autoplay animation. Progress bars update without easing when a value jumps.
- Respect `prefers-reduced-motion`: no transitions.

## 4. Reusable components

| Component | Purpose | Props / data | States | Source of data |
|---|---|---|---|---|
| `MeterCard` | Show value against limit | label, value, limit, unit, warn threshold | normal, warn (≥ soft cap), danger (≥ brake), unknown | `/api/budget` |
| `BudgetBar` | Horizontal bar with soft cap and brake markers | value, soft 1,700, brake 1,950, max 2,000 | as above | `/api/budget` |
| `StatusBadge` | Company or job status | status enum (§5 in 05) | per status | `/api/jobs/{id}`, `/api/dossiers` |
| `SourceBadge` | Fact provenance button | URL host, retrieved_at, sha256 (short), confidence | default, hover, focused | `/api/dossiers/{orgnr}` |
| `FlagChip` | Persisted flags (e.g. `website_unreachable`) | flag code, human label, tooltip | default | dossier flags |
| `DataTable` | Sortable, filterable, paginated table | columns, rows, sort, cursor | loading, empty, error, partial | list endpoints |
| `SidePanel` | Detail view opened from table row | content slot, close | open, closed, loading, error | detail endpoints |
| `EventLine` | One terminal line | timestamp, tag, message, severity | info, ok, warn, error | SSE |
| `TerminalLog` | Scrolling event list | events, filter state, follow state | streaming, paused, reconnecting, ended | SSE |
| `FileDropzone` | Upload TXT/CSV | accept, max size | idle, dragover, uploading, rejected | E1 |
| `InlineValidationList` | Accepted and rejected inputs | lines, reasons | empty, populated | E1 |
| `EvidenceSplitView` | Page text with highlight and fact | page text, highlight range, fact | loading, ready, missing snapshot | E7 |
| `HighlightedText` | Marks quote offsets in text | text, start, end | — | E7 |
| `EmptyState` | Explains absence | title, reason, next action | — | per screen |
| `ErrorBanner` | Describes a failed fetch or stream | code, message, retry | — | any |
| `ConnectionIndicator` | Live status | state | live, reconnecting, offline | SSE client |
| `HashText` | Monospace hash with copy button | full value, short form | copied | E7 |

## 5. Interaction standards

### 5.1 Tables

- Columns sortable by click and by keyboard (Enter on header). Sort state shown with `aria-sort`.
- Filters apply to the query (server-side cursors), not to a client-side slice, once rows exceed 200.
- Row click opens the SidePanel; Enter on a focused row does the same. Space selects (where selection exists).
- Empty filter results show "No companies match these filters" with a "Clear filters" action.

### 5.2 Forms

- Input validation runs on blur and on paste, and calls E1 (never blocks typing).
- Each rejected line shows the line number, the value (masked if longer than 40 characters), and the reason in plain language (for example "Wrong number of digits: 8 found, 9 required").
- Start button is disabled until at least one accepted number exists; the disabled reason is displayed below the button.
- Start is one action; double-clicks are ignored while the request is pending (the button shows a spinner and "Starting…"). The server also enforces idempotency (TRD §17.3).

### 5.3 Keyboard

| Key | Action |
|---|---|
| Tab / Shift+Tab | Move focus in logical order |
| Enter | Activate control; open row |
| Escape | Close SidePanel or dialog; return focus to trigger |
| `/` | Focus search field (Dossier Explorer, Rejection Log) |
| `g` then `c`, `t`, `d`, `r`, `h`, `e` | Go to Command Center, Terminal, Dossiers, Rejections, Changes, Report (documented shortcuts; optional) |
| Arrow keys | Move between table rows when a table has focus |
| Space | Pause or resume the Terminal follow mode when the Terminal has focus |

### 5.4 Live regions

- Terminal: `role="log"`, `aria-live="off"` by default; a separate visually hidden polite region announces batched summaries every 10 seconds ("12 new events: 4 registry, 5 scraper, 2 validator, 1 rejection"). Avoids flooding screen readers.
- Meters: values announced on change at most once every 5 seconds.
- Banners: `role="status"` for soft cap; `role="alert"` for brake and kill switch.

## 6. Responsive behaviour

| Breakpoint | Layout | Behaviour |
|---|---|---|
| ≥ 1280 px | Sidebar + content; side panel docked on the right (480 px) | Full tables |
| 960–1279 px | Collapsed sidebar (icons + labels on hover/focus); side panel overlays | Tables with horizontal scroll inside container |
| 600–959 px | Top navigation menu; side panel full width | Tables show primary columns; secondary columns in row expansion |
| < 600 px | Single column; tables become stacked cards | Evidence Viewer stacks page text above fact; highlights preserved |

Mobile is supported for viewing results; the Start action is available but the evaluator is expected to use desktop for uploads of large lists (acceptance criterion in §8).

## 7. Accessibility

| Area | Requirement |
|---|---|
| Contrast | All text ≥ 4.5:1; non-text indicators ≥ 3:1 (WCAG 2.2 AA) |
| Focus | Visible focus ring (2 px `accent.primary`, 2 px offset) on all controls |
| Target size | Interactive targets ≥ 24 × 24 CSS px (WCAG 2.2 2.5.8 minimum) |
| Status | Never colour alone: badges contain text and icon shape |
| Names | Every icon-only button has an accessible name |
| Tables | Real `<table>` with `<th scope>`; captions for each table |
| Forms | Labels associated; errors linked with `aria-describedby` |
| Zoom | Usable at 200% zoom without horizontal scrolling of the page (tables scroll inside containers) |
| Motion | `prefers-reduced-motion` respected |
| Transparency | `prefers-reduced-transparency` respected: opaque fallback fills replace glass; the same fallback applies when `backdrop-filter` is unsupported and in forced-colors mode |
| Language | `lang="en"` on document; Norwegian quotations marked with `lang="no"` |
| Screen reader | Hashes and orgnr read digit-by-digit (`aria-label` with spaced digits) |
| Testing | Automated axe checks and one manual screen-reader pass recorded in the test report (06 Phase 9) |

## 8. Screens

Screens 1–7 follow the brief's numbering. For each screen: purpose, primary user, layout, hierarchy, components, interactions, navigation, loading, empty, error, success, partial-result, responsive, accessibility, data requirements, API dependencies, acceptance criteria.

### Screen 1 — Command Center

**Purpose:** Start a job, validate input, and watch the main meters.

**Primary user:** P1 Evaluator.

**Layout (desktop):**

```text
+------------------------------------------------------------------+
| Top bar: Signalpost | Job: daily-2026-10-16 [Running] | Lite |   |
+--------+---------------------------------------------------------+
| Nav    | Input panel                 | Meters                    |
|        | [ textarea: one number/line]| Companies  74 / 100       |
|        | [ Drop TXT or CSV here ]    | Requests   642 / 2,000    |
|        | Accepted 98   Rejected 2    | Cost       $0.04 / $10    |
|        | [Rejected list (expand)]    | LLM rate   12 / 40 (30 tgt)|
|        | [Start job]  (disabled why) | Elapsed    18:20 / 45:00  |
|        |                             | Stop reason: none         |
|        +-----------------------------+---------------------------|
|        | Budget warnings (banners)                               |
|        | Recent events (last 5) -> Open terminal                 |
+--------+---------------------------------------------------------+
```

**Information hierarchy:** (1) job status and Start action; (2) companies done; (3) request and cost meters; (4) time and LLM rate; (5) warnings and stop reason; (6) recent events.

**Components:** FileDropzone, textarea, InlineValidationList, MeterCard ×4, BudgetBar, StatusBadge, banners, EventLine (5).

**Meters required (source p.19):** companies done (e.g. 74/100), requests (e.g. 850/2,000), cost ($0.04/$10), LLM calls per minute vs 40 limit, elapsed time vs 45 minutes. The 30 RPM internal target is shown as a secondary marker.

**Interactions:**
- Paste text or drop file → E1 → live validation list.
- Expand rejected list; click line to highlight it in the textarea.
- Mode selector: `Daily test (100)` or `Baseline batch`. Changing mode updates the limits shown on meters (45 min / 2,000 / $10 vs 14,000 / $5 for the baseline run; 2 000 vs 14 000 are never shown on the same meter).
- Start → E2 → navigate to Terminal.

**Navigation:** Terminal link after start; Dossier Explorer link on completion.

**Loading state:** Validation shows a spinner next to the textarea; Start disabled while pending. Meters show "—" until first `budget.update`.

**Empty state:** No job yet: "Paste company numbers or drop a TXT or CSV file to begin. Numbers must be 9 digits and pass the MOD-11 check." Start disabled with reason "No valid numbers yet".

**Error state:** E1 unreachable: banner "Cannot reach the agent service. Check that `make run` is still running." with Retry. Input stays in place.

**Success state:** Job queued → "Job started. Open the terminal." Meters start.

**Partial-result state:** Job stopped with some companies registry-only: meter shows `published 60 / registry-only 25 / failed 2 / not processed 13` in a stacked summary with labels.

**Responsive:** Input and meters stack below 960 px; meters become a 2×2 grid.

**Accessibility:** Textarea labelled "Company numbers, one per line"; drop zone has a visible "Choose file" button; meters announced on change (5-second throttle).

**Data requirements:** Job status, counts, budget counters, stop reason, event feed.

**API dependencies:** E1, E2, E3, E4 (events for recent list), E11, E12.

**Acceptance criteria:**
- AC-UI-01: Pasting 3 valid and 2 invalid lines shows 3 accepted and 2 rejected with reasons within 1 second of pausing typing.
- AC-UI-02: Start is disabled when accepted count is 0, with the reason shown.
- AC-UI-03: Meters show the same values as `/api/budget` (TA-15).
- AC-UI-04: Soft-cap and brake banners appear within 2 seconds of the event.
- AC-UI-05: A file over 1 MB is rejected with a message stating the 1 MB limit.

### Screen 2 — Live Agent Terminal

**Purpose:** Show the agent's work as it happens: registry, scraper, LLM and validator events.

**Primary user:** P1 Evaluator; P3 Engineer for debugging.

**Layout:**

```text
+----------------------------------------------------------------+
| Filter: [All v] [Registry] [Scraper] [LLM] [Validator] [Errors]|
| Search: [____]   Follow (on)  Pause  Jump to latest            |
+----------------------------------------------------------------+
| 08:34:01 [REGISTRY]  923456783 Main record ok                  |
| 08:34:02 [SCRAPER]   923456783 fetched about page (6,000 chars)|
| 08:34:04 [LLM]       923456783 3 facts proposed                |
| 08:34:04 [VALIDATOR] 923456783 2 verified, 1 rejected (quote not found) |
| 08:34:05 [VALIDATOR] 923456783 rejected: money_blocked         |
| ...                                                            |
+----------------------------------------------------------------+
| Connection: Live | Events: 1,842 | Showing 200                  |
+----------------------------------------------------------------+
```

**Information hierarchy:** (1) event text, (2) tag, (3) timestamp, (4) orgnr. Colour adds severity only.

**Components:** TerminalLog, EventLine, filter chips, search field, ConnectionIndicator, "Jump to latest" button.

**Tag set (source p.19):** `[REGISTRY]`, `[SCRAPER]`, `[LLM]`, `[VALIDATOR]`. Additional tags: `[BUDGET]`, `[KILL-SWITCH]`, `[JOB]`, `[ERROR]`. Tags are derived from event types (TRD §17.3 E4).

**Interactions:**
- Filters by source tag and by severity; combined filters are AND.
- Search matches text and orgnr.
- Follow mode: auto-scroll to newest; scrolling up pauses follow and shows "Jump to latest (n new)".
- Click an orgnr: opens SidePanel for that company's dossier status (not full dossier).
- Space pauses/resumes follow when the log has focus.

**Navigation:** Back to Command Center; link to Dossier Explorer filtered to job's companies.

**Loading state:** "Connecting to event stream…" until first event or heartbeat.

**Empty state:** "No events yet. The terminal will fill as the job starts."

**Error state:** Stream failure: ConnectionIndicator shows Reconnecting with backoff (1, 2, 4, 8 s, max 15 s); after 5 failures: "Live updates stopped. Showing last known events. Retry" button. Events already shown are kept.

**Success state:** `job.finished` line with stop reason and link to Run Report.

**Partial-result state:** Stream ends with `stop_reason` (for example request_brake); the log remains and shows the banner.

**Responsive:** Full width; tag column collapses to a coloured letter with text in the row on small screens (text remains).

**Accessibility:** `role="log"`; batched announcements (§5.4); filters are buttons with `aria-pressed`.

**Data requirements:** Events with id, ts, type, orgnr, message, data.

**API dependencies:** E4 (SSE with `Last-Event-ID`), E3 for status on load.

**Acceptance criteria:**
- AC-UI-06: Events appear within 2 seconds of server emission (TRD recommendation, NFR-PERF-005).
- AC-UI-07: After a forced disconnect, the client reconnects and shows no duplicate or missing event ids.
- AC-UI-08: Scrolling up stops auto-scroll; a new event does not move the viewport.
- AC-UI-09: Filter "Validator" shows only validator events.

### Screen 3 — Dossier Explorer

**Purpose:** Find companies and see their processing and verification state.

**Primary user:** P2 Compliance analyst; P1 Evaluator.

**Layout:**

```text
+-----------------------------------------------------------------------+
| Search [name or orgnr____]  Status [All v]  Job [latest v]  Export ... |
+------------------------------------------------------------+----------+
| Orgnr      | Legal name   | Reg. status | Processing | Facts | Fin |  Side  |
| 923456783  | Eksempel AS  | Active      | Published  |   4   | Yes |  panel |
| ...                                                        |          |
+------------------------------------------------------------+----------+
| Showing 1–50 of 100 | Next                                             |
+-----------------------------------------------------------------------+
```

**Columns (source p.19 and the brief):** Orgnr (mono), Legal name, Registry status (active, deleted, bankrupt, not_found, etc.), Relevant registry fields (org form, municipality or town), Processing status, Retrieval Date (`data_freshness`: latest retrieval time of any input for the company), Financial availability (Plan A, Plan B, Plan C labelled "Plan A", "Plan B (fallback)", "Unavailable"), Verified-fact count (AI-published facts only; registry fields are reported separately). Fact As-Of Date (`as_of`: the date a published fact is stated to apply to) is stored per fact, so it is not a table column; it is shown on each fact in the side panel and in Dossier Detail. The two labels are never merged or abbreviated to "freshness".

**Components:** DataTable, SearchField, Select filters, StatusBadge, SidePanel, pagination.

**Side panel (dossier summary):** Registry block (name, status, address, website as text, roles list: names and roles only), Financial block (year, currency, unit as printed, amount values with method and source badge), Facts list (key, value, Norwegian value, Fact As-Of Date, SourceBadge), Flags (FlagChip), Changes (link to Change Feed, if any). Full page link: `/dossiers/{orgnr}`.

**Interactions:**
- Search is debounced (300 ms) and calls E5 with `q`.
- Sort on any column (server-side).
- Filter by processing status, financial availability, has website.
- Row click opens SidePanel; "Open full dossier" link.
- Export button: download current result as JSON (optional, later release) — labelled as later.

**Navigation:** Row → SidePanel → Evidence Viewer via SourceBadge.

**Loading state:** Skeleton rows (text-free placeholders with `aria-busy="true"`).

**Empty state:** No dossiers yet: "No dossiers yet. Start a job from the Command Center." Filter empty: "No companies match these filters."

**Error state:** "Could not load dossiers (503). Retry." Table keeps last loaded rows, marked stale.

**Success state:** Table populated; counts shown ("100 companies in this job").

**Partial-result state:** Rows with `registry_only`, `not_processed_budget`, `time_limit_registry_only` are shown with a visible reason text in the Processing column, not hidden.

**Responsive:** Columns beyond Orgnr, Name, Processing collapse into the row expansion below 960 px.

**Accessibility:** Table caption ("Companies in dossier store"); sort buttons announce direction; SidePanel focus moves to heading on open and returns on close.

**Data requirements:** From E5 list items (see 05 `Dossier`); detail from E6. Retrieval Date comes from `Dossier.data_freshness` (E5); Fact As-Of Date comes from `PublishedFact.as_of` (E6).

**API dependencies:** E5, E6, E7 (via SourceBadge).

**Acceptance criteria:**
- AC-UI-10: Search for an orgnr returns the company within 1 second on a 1,000-company store (TRD target).
- AC-UI-11: Each row displays processing status text, never colour only.
- AC-UI-12: Financial availability shows the plan used, e.g. "Plan A".
- AC-UI-13: A company with no website shows "Registry only: no website on registry".
- AC-UI-14: Verified-fact count equals the number of PublishedFact records for that company.

### Screen 4 — Evidence Viewer

**Purpose:** Prove one fact: show the extracted fact beside the saved page with the quotation highlighted.

**Primary user:** P2 Compliance analyst; P4 Reviewer.

**Layout (split view):**

```text
+-------------------------------------------------------------------+
| Breadcrumb: Dossiers > Eksempel AS > products                      |
+------------------------------+------------------------------------+
| FACT (left)                  | SAVED PAGE (right)                 |
| Key: products                | URL: https://...   retrieved 08:33 |
| Value (EN): Sells fish feed  | SHA-256: ab12…9f (copy)            |
| Value (NO): Selger fôr …     | Final URL: (same)                  |
| Quotation (exact, NO):       | ----------------------------------- |
|  "Vi leverer fôr til …"      |  … text … [Vi leverer fôr til …]   |
| Source: about page           |  … text … (highlight yellow)       |
| Retrieved: 2026-10-16 08:33Z |                                     |
| SHA-256: ab12…               |                                     |
| Validation: Passed (Q V G)   |                                     |
| Confidence: 0.88             |                                     |
| Components: Q 1 V 1 G 1      |                                     |
|   S 0.8 F 1.0                |                                     |
| Tags: —                      |                                     |
+------------------------------+------------------------------------+
```

For a rejected fact (same route with `?status=rejected` or from the Rejection Log): the left panel shows the reason code, failed stage and diagnostic; the right panel shows the page with search text highlighted if found, or "Quotation not found in saved page".

**Information hierarchy:** (1) the fact and its validation outcome; (2) the quotation highlight; (3) provenance (URL, time, hash); (4) confidence components.

**Components:** EvidenceSplitView, HighlightedText, HashText, FlagChip, validation outcome block.

**Interactions:**
- Click a quote in the left panel to scroll the right panel to the highlight.
- Copy hash; open source URL in a new tab (`rel="noopener noreferrer"`).
- Toggle between "Norwegian value" and "English value" display; the quotation is never translated and is always shown as stored.
- For registry facts: the right panel shows the JSON path and raw value instead of page text.

**Navigation:** Back to dossier; previous and next fact within the same company.

**Loading state:** Skeleton panels; page text loads separately.

**Empty state:** Not applicable for a valid fact id. For a company with no facts: "No facts were published for this company. See the Rejection Log or the registry fields."

**Error state:** Snapshot missing: "The saved page for this fact is missing from the evidence vault (hash {short}). The fact cannot be verified from storage. Report the hash to the operator." This case is also a failure of replay (TRD §15.3).

**Success state:** Highlight shown; validation outcome "Passed".

**Partial-result state:** Quote found but the page is truncated at 6,000 characters for LLM use: the viewer shows the full saved text and notes "Saved text is longer than the text sent to the model."

**Responsive:** Below 600 px, the page panel moves below the fact panel and the highlight remains.

**Accessibility:** Highlights use a text marker in addition to colour (for example `[ ... ]` in the text-only copy and a `<mark>` element); `aria-current` on the active highlight; the page text is `lang` matched to the page language.

**Data requirements:** Fact, validation components, snapshot text, metadata.

**API dependencies:** E7; E6 for company context.

**Acceptance criteria:**
- AC-UI-15: For every published fact in the trap demo, the quote is highlighted in the saved text.
- AC-UI-16: The hash shown equals the SHA-256 of the saved text file (verified by test).
- AC-UI-17: Rejected facts show the reason code exactly as stored.
- AC-UI-18: No fact shows a "verified" label unless a ValidationResult with pass status exists.

### Screen 5 — Rejection Log

**Purpose:** Show what the system refused to publish and why. Shows honesty.

**Primary user:** P4 Reviewer; P2.

**Layout:** Table with filters (stage, reason, company) and a detail panel.

**Columns (source p.8; brief):** Rejected value (truncated; full in panel), Company (orgnr and name), Source (URL host), Validation stage (identity, quote, value, money, confidence), Reason code (for example `quote_translated`), Timestamp (UTC), Diagnostic summary.

**Detail panel:** full rejected value, quote as stored (if any), page snapshot link (Evidence Viewer), stage diagnostic (for example "Q score 0.90 below 0.95").

**Interactions:** Filter by stage and reason; search; sort by time; open detail; link to the Evidence Viewer when a snapshot exists.

**Loading / empty / error / success / partial:** Empty: "No facts were rejected in this job." (valid state). Partial: Some rejections recorded before a stop; the list notes the stop reason.

**Responsive:** Columns collapse as in Screen 3.

**Accessibility:** Stage and reason are text; table caption.

**Data requirements:** RejectionRecord (05).

**API dependencies:** E8.

**Acceptance criteria:**
- AC-UI-19: Trap Set rejections appear with reasons `money_blocked` and `identity_failed` as applicable.
- AC-UI-20: Filtering by stage returns only that stage.

### Screen 6 — Change Feed

**Purpose:** Show what changed since the previous run, with before and after values.

**Primary user:** P2; P4.

**Layout:** Table: Company, Field, Previous value, New value, Source, Change timestamp, Evidence (links). Filter by date range and field.

**Interactions:** Diff display: previous in one column, new in another; differences emphasised by text marker and bold, not colour alone. Each "Evidence" link opens Evidence Viewer for the new value.

**States:** Empty: "No changes since the last run. Change Radar re-checks only companies whose registry record changed." Loading and error as in Screen 3. Partial: "Change detection ran for 40 of 100 companies. Others were not checked (budget or time limit)." (Change Radar is a later release; the screen is designed now and marked later.)

**Accessibility:** Diff uses `<del>` and `<ins>` with visually hidden labels "previous" and "new".

**Data requirements:** ChangeRecord.

**API dependencies:** E9; E7.

**Acceptance criteria:**
- AC-UI-21: Each change row displays previous and new values, source and timestamp.
- AC-UI-22: A company with no change does not appear.

### Screen 7 — Run Report

**Purpose:** One page that summarises a run and proves the limits were respected.

**Primary user:** P3, P4; P1 for the submission.

**Layout (top to bottom):**
1. Job summary: job id, mode, start and end time (UTC), duration, stop reason, checkpoint status.
2. Outcomes: count of companies by processing status (published, registry-only, failed, not found, not processed), with percentages of the input count. `no_website` is a flag, not a status: companies with no registry-listed website are counted under registry-only, and that row shows a sub-line "of which flagged no_website".
3. Budget: total outbound requests with breakdown (registry, website, Plan B, LLM, retries, redirect hops, Playwright equivalents); limits and soft cap, brake and remaining; displays `plan_b_used_count` in the budget UI block.
4. LLM: calls, input tokens, output tokens, estimated cost, cost limit.
5. Flags: soft cap reached, brake tripped, kill switch tripped, Plan A outage detected, Plan B used count.
6. Rejections: total and by reason code (link to Rejection Log filtered).
7. Checkpoint: last file name, hash, batch number.

**Components:** SummaryTable, MeterCard, BudgetBar, FlagChip, link list.

**Interactions:** Export JSON (the same file as `run_report.json`); print stylesheet provided.

**States:** Running: "Report available when the job finishes" (409 from E10). Empty: "No report for this job." Error: retry. Partial: stop reasons shown prominently.

**Responsive:** Single column at all sizes below 960 px.

**Accessibility:** Headings for each section; tables with captions; numbers with units.

**Data requirements:** RunReport (05).

**API dependencies:** E10, E11.

**Acceptance criteria:**
- AC-UI-23: All numbers equal run_report.json (TA-14).
- AC-UI-24: Stop reason is shown in the first screen view.
- AC-UI-25: Limits (45 min, 2,000, $10 or 14,000, $5) appear with the mode label.

### Dossier Detail — sub-view of Screen 3 (not a numbered screen)

**Purpose:** Full profile for one company (sections: identity, registry, roles, financials, facts, flags, changes, evidence index).

**Layout:** Header with name, orgnr, registry status and processing status; tabs or sections for Registry, Financials, Facts, Rejections for this company, Changes, Evidence index.

**Rules shown on this page:**
- Financial values show amount as printed, unit, currency, year, source, method and retrieval time.
- Money numbers are shown only from registry or Plan B sources; there is no facts row with money from AI (this is enforced by validation and is a display check, not a substitute).
- Personal data: roles show names and roles only (p.18).

**States:** Loading skeleton; 404 "No dossier for this organisation number."; partial "Registry only" banner.

**Acceptance criteria:**
- AC-UI-26: Financial rows show explicit unit and year or "Unavailable: reason".
- AC-UI-27: No birth date or personal identifier fields are rendered.

## 9. Cross-screen states and error language

### 9.1 State model (all data screens)

| State | Trigger | Display |
|---|---|---|
| Loading | Request pending > 300 ms | Skeleton with `aria-busy` |
| Empty | Zero results, no error | Explanatory EmptyState with next action |
| Error | Non-2xx or network error | ErrorBanner with code and retry; stale data marked |
| Success | Results present | Normal view |
| Partial | Results present with stop reason or flags | Normal view plus visible banner or flags |

### 9.2 Error language rules

- State what happened, then what the user can do: "Cannot reach the agent service. Check that the server is running, then retry."
- Never show stack traces or internal exception names.
- Use the source reason codes in technical contexts (for example `quote_not_found`) with a plain-language label beside them.

### 9.3 Reason-code labels (examples)

| Code | Label |
|---|---|
| `mod11_checksum_failed` | Check digit is wrong |
| `length_not_9` | Must be 9 digits |
| `quote_translated` | Quotation was translated, so it cannot be verified |
| `quote_not_found` | Quotation not found in saved page |
| `money_blocked` | Money amount from a language model is not allowed |
| `identity_failed` | Page does not match the registered company |
| `value_unsupported` | Statement is not supported by the quotation |
| `below_threshold` | Confidence below 0.80 |
| `website_unreachable` | Website did not respond |
| `blocked_403` | Website refused access |
| `request_brake` | Request limit reached; registry data only |
| `time_limit_registry_only` | Time safeguard active; registry data only |
| `not_processed_budget` | Not processed: budget limit reached before this company |
| `financials_unavailable` | Financial data unavailable |
| `llm_skipped` | AI extraction skipped; registry data only |

## 10. Data-source map

| UI element | Source endpoint | Field |
|---|---|---|
| Companies done | E3 `completed_count` / `input_count` | Job |
| Requests | E11 `total_outbound_requests` | BudgetLedger |
| Cost | E11 `estimated_cost_usd` | BudgetLedger |
| LLM calls per minute | E11 `llm_calls_last_60s` | BudgetLedger |
| Elapsed time | E3 `elapsed_seconds` | Job |
| Stop reason | E3 `stop_reason` | Job |
| Terminal lines | E4 events | Event |
| Dossier table | E5 items | Dossier |
| Dossier detail | E6 | Dossier |
| Retrieval Date | E5 `data_freshness` | Dossier |
| Fact As-Of Date | E6 `as_of` | PublishedFact |
| Evidence | E7 | EvidenceSnapshot |
| Rejections | E8 | RejectionRecord |
| Changes | E9 | ChangeRecord |
| Run report | E10 | RunReport |

Every UI element above has a data source; no element is populated from client-side guesses.

## 11. Acceptance summary

| Screen | Criteria IDs |
|---|---|
| Command Center | AC-UI-01 to AC-UI-05 |
| Live Terminal | AC-UI-06 to AC-UI-09 |
| Dossier Explorer | AC-UI-10 to AC-UI-14 |
| Evidence Viewer | AC-UI-15 to AC-UI-18 |
| 5 Rejection Log | AC-UI-19, AC-UI-20 |
| 6 Change Feed | AC-UI-21, AC-UI-22 |
| 7 Run Report | AC-UI-23 to AC-UI-25 |
| Dossier Detail (sub-view) | AC-UI-26, AC-UI-27 |
