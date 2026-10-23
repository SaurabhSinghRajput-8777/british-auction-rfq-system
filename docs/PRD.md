# PRD: British Auction in RFQ System

| | |
|---|---|
| **Status** | Draft v2.0 (revised after review) |
| **Scope** | Unchanged from the assignment |
| **Companion docs** | [`HLD.md`](./HLD.md) (architecture) · [`Technical-Design.md`](./Technical-Design.md) (schema, API, algorithm, transactions, tests) |

This document answers **what** the system must do and **how we know it is correct**. It contains requirements, business rules, assumptions, metrics and acceptance criteria. Architecture is in `HLD.md`; implementation detail is in `Technical-Design.md`.

**Source tags.** Every rule is tagged so reviewers can separate the assignment from our interpretation:
- **[A]** stated in the assignment
- **[I]** implementation assumption (the assignment is silent or ambiguous; see §7)

---

## 1. Overview

An RFQ (Request for Quotation) lets a buyer ask multiple suppliers (carriers) for quotes. A **British Auction** adds open, continuously improving bids, an **automatic extension** of the close time when late activity occurs, and a **forced close time** after which bidding stops no matter what. [A]

### 1.1 Goals [A]
1. Enable transparent and fair supplier competition
2. Prevent last-minute bidding manipulation
3. Encourage active supplier participation
4. Help buyers achieve better final pricing

### 1.2 In scope [A]
RFQ creation with British Auction option · supplier quote submission · automatic extension with three trigger types · forced-close cap · supplier ranking (L1, L2, L3 …) · auction listing page · auction details page with activity log · HLD, schema, backend, frontend.

### 1.3 Out of scope
Production authentication, supplier onboarding, award/PO workflow, payments, notifications, multi-lane RFQs, other auction formats, real-time push infrastructure, message brokers, microservices.

---

## 2. Terminology and Units

One name per concept is used in **all three documents, the database, the API and the UI code**.

| Concept | Name used everywhere | Type / unit | Notes |
|---|---|---|---|
| Bid start | `bid_start_time` | timestamp (UTC) | |
| Bid close, as entered at RFQ creation | `original_close_time` | timestamp (UTC) | Assignment/UI label: "Bid Close Date & Time". Never changes. |
| Bid close, after extensions | `current_close_time` | timestamp (UTC) | Starts equal to `original_close_time`; only ever moves forward |
| Forced close | `forced_close_time` | timestamp (UTC) | Assignment/UI label: "Forced Bid Close Date & Time". Never changes. |
| Trigger Window **X** | `trigger_window_minutes` | integer, **minutes** | |
| Extension Duration **Y** | `extension_minutes` | integer, **minutes** | |
| Extension Trigger | `extension_trigger` | enum | `BID_RECEIVED`, `ANY_RANK_CHANGE`, `L1_RANK_CHANGE` |
| Moment a bid is accepted | `accepted_at` | timestamp (UTC) | **Database clock**, read after the RFQ row lock is held |
| Pickup / Service Date | `pickup_date` | timestamp (UTC) | |
| Bid price used for ranking | `total_price` | decimal | `freight_charges + origin_charges + destination_charges` |

**Units rule:** durations are integer **minutes**; deadlines and event times are **UTC timestamps**. The UI converts to the viewer's timezone for display only.

---

## 3. Personas and User Stories

| Persona | Needs |
|---|---|
| **Buyer** | Create RFQs with auction rules; watch progress; understand why the auction was extended |
| **Supplier (carrier)** | Submit and revise quotes; see own rank, lowest bid and current close time |

| ID | Story |
|---|---|
| US-1 | As a buyer, I create an RFQ with British Auction enabled and configure X, Y and the extension trigger. |
| US-2 | As a buyer, I set a forced close time so the auction can never run past my deadline. |
| US-3 | As a supplier, I submit a quote (freight, origin, destination charges, transit time, validity). |
| US-4 | As a supplier, I submit a lower revised quote to beat competitors. |
| US-5 | As a supplier, I see my rank, the lowest bid and the live close time. |
| US-6 | As any user, I browse all auctions with lowest bid, close time, forced close time and status. |
| US-7 | As any user, I see an activity log of bids, extensions and the reason for each extension. |

---

## 4. Business Rules

These are the authoritative rules. `Technical-Design.md` specifies how each is enforced.

### 4.1 Time and bid acceptance
| ID | Rule | Src |
|---|---|---|
| BR-1 | **Bid acceptance:** a bid is valid **only if** `bid_start_time ≤ accepted_at < current_close_time`. | A (bidding stops at close) / I (exact boundary) |
| BR-2 | `accepted_at` is the **database clock** read **after acquiring the RFQ row lock**. Client and application-server clocks are never used for any auction decision. | I |
| BR-3 | A bid at exactly `current_close_time` is **rejected**. A bid at `current_close_time − 1 µs` is accepted. | I |
| BR-4 | No bid is ever accepted at or after `forced_close_time`. | A |

### 4.2 Extension
| ID | Rule | Src |
|---|---|---|
| BR-5 | **Trigger window:** the system monitors `[current_close_time − X minutes, current_close_time)`. Start is inclusive, end is exclusive. `current_close_time` here is the value **before** this bid's own extension. | A / I |
| BR-6 | **When triggers are evaluated:** only **after a bid has been accepted**, using the resulting ranking and the remaining time before `current_close_time`. Rejected bids never evaluate triggers and never change auction state. | I |
| BR-7 | **Trigger types** (exactly one is configured per RFQ): | A |
| | `BID_RECEIVED`: any accepted bid inside the trigger window | |
| | `ANY_RANK_CHANGE`: the full ordered list of supplier IDs holding current bids differs before vs after the accepted bid (`supplier_ids_before != supplier_ids_after`). Comparing merely the numerical rank of the bidder is insufficient. This includes a supplier's first bid entering the ranking (see §7, A-5). | |
| | `L1_RANK_CHANGE`: the supplier holding L1 differs before vs after the accepted bid (`l1_supplier_id_before != l1_supplier_id_after`). This includes transitioning from no bids to the first bidder. | |
| BR-8 | **Extension calculation:** `new_close_time = min(current_close_time + extension_minutes, forced_close_time)`. The extension is applied only if `new_close_time > current_close_time`. | A |
| BR-9 | **Forced-close cap:** no extension may move `current_close_time` beyond `forced_close_time`. If `current_close_time == forced_close_time`, no extension occurs and the attempt is logged. | A |
| BR-10 | An accepted bid causes **at most one** extension. Multiple accepted bids may each extend, until the cap is reached. | I |
| BR-11 | Extension is added to `current_close_time` (e.g. 6:00 PM → 6:05 PM), not to the bid time. | A |

### 4.3 Bids, ranking and history
| ID | Rule | Src |
|---|---|---|
| BR-12 | `total_price = freight_charges + origin_charges + destination_charges`. Only `total_price` affects rank. | I |
| BR-13 | **Revision:** a supplier may bid repeatedly; each new bid must be **strictly lower** than that supplier's own current bid. | A ("continuously lower their prices") / I |
| BR-14 | **Current ranking is separate from bid history.** Each supplier has exactly **one current bid**; ranking is computed from current bids only. Superseded bids appear in the history view and never in the ranking. | I |
| BR-15 | **Ranking order:** `total_price` ascending; ties broken by earlier `accepted_at`, then lower bid id. L1 is the first entry. | I |
| BR-16 | Bid records are immutable; they are never edited or deleted. | I |
| BR-16a | **Atomicity of rejected bids:** A rejected bid (e.g. auction inactive, bid not strictly lower, invalid payload) causes an immediate transaction rollback. **No bid-history record (`bid_submissions`/`bids`), no current-bid modification, no extension, and no success/activity audit event** is committed. (Rejected submission attempts return an HTTP 4xx error envelope; they do not write to the auction activity log). | I |

### 4.4 Status and closure
| ID | Rule | Src |
|---|---|---|
| BR-17 | **Single status definition** (below) is evaluated against the effective close deadline (`current_close_time`) and is used consistently for reads, bid submission, and scheduled/lazy closure. | I |
| BR-18 | **Terminal status immutability:** Once an auction transitions to a terminal state (`CLOSED` or `FORCE_CLOSED`) and is persisted, its terminal status is permanently immutable and cannot later change under any circumstance. | I |
| BR-19 | **Closure classification:** If an active auction reaches its deadline when `current_close_time = forced_close_time`, it becomes `FORCE_CLOSED`. If it closes at any time when `current_close_time < forced_close_time`, it becomes `CLOSED`. | A / I |
| BR-20 | Terminal transitions and their audit events are **idempotent**: repeated or concurrent closure attempts produce one terminal state and exactly one closure audit event. | I |
| BR-21 | The shared closure routine (callable by the scheduler or lazily by requests) persists the terminal state and records the closure audit event. The bid API **independently enforces the deadline** (BR-1). Correctness never depends on the scheduler running on time. | I |
| BR-22 | A closed or force-closed auction is read-only. | A |

| Status | Condition (evaluated at time `t`, where `terminal_status` is not already persisted) |
|---|---|
| **Scheduled** | `t < bid_start_time` |
| **Active** | `bid_start_time ≤ t < current_close_time` |
| **Force Closed** | `t ≥ current_close_time` **and** `current_close_time = forced_close_time` |
| **Closed** | `t ≥ current_close_time` **and** `current_close_time < forced_close_time` |
*(Note: If a terminal status is already persisted in the database, that persisted status is returned directly, ensuring immutability).*

---

## 5. Functional Requirements

### 5.1 RFQ creation
| ID | Requirement | Src |
|---|---|---|
| FR-1 | Buyer creates an RFQ with: RFQ name, reference ID (unique), `bid_start_time`, `original_close_time`, `forced_close_time`, `pickup_date`, British Auction option. | A |
| FR-2 | When British Auction is enabled, `trigger_window_minutes` (X), `extension_minutes` (Y) and `extension_trigger` are **all mandatory**. | A |
| FR-3 | Validation (enforced in the API and again in the database): | A |
| | `forced_close_time > original_close_time` | |
| | `original_close_time > bid_start_time` | |
| | X and Y are integers ≥ 1 | |
| | `extension_trigger` is one of the three allowed values | |
| | reference ID is unique | |
| FR-4 | `forced_close_time` and `original_close_time` are immutable after creation; `current_close_time` initialises to `original_close_time`. | A |

### 5.2 Quote (bid) submission
| ID | Requirement | Src |
|---|---|---|
| FR-5 | Quote fields: carrier name (from the supplier profile), freight charges, origin charges, destination charges, transit time (days), quote validity (date). | A |
| FR-6 | Charges ≥ 0; `total_price > 0`; transit time ≥ 1 day; quote validity must be after `accepted_at`. | I |
| FR-7 | Submission follows BR-1 to BR-16. | A / I |
| FR-8 | Response tells the supplier their rank, whether the auction was extended, and the new close time. | I |

### 5.3 Auction listing page [A]
Columns: RFQ name / ID · current lowest bid · `current_close_time` · `forced_close_time` · status (Active / Closed / Force Closed; Scheduled also shown).
Lowest bid = lowest **current** bid (BR-14). "No bids yet" when none.

### 5.4 Auction details page [A]
- All supplier bids sorted by price, with rank L1, L2, L3 … (**current ranking**)
- Quote details for each: charges, total, transit time, quote validity
- **Bid history** (all submissions, including superseded), visually separate from the ranking
- Auction configuration: X, Y, trigger type
- Activity log: bid submissions, time extensions, **reason for each extension**, closure

---

## 6. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Correctness | Auction state changes are atomic and serialised per RFQ (details in `Technical-Design.md` §5) |
| Auditability | Bids and log entries are append-only; every extension records old close, new close, trigger and triggering bid |
| Resilience | Correct behaviour even if the scheduler is late, down, or runs twice |
| Performance (demo target) | Bid submission < 300 ms p95 with ~20 concurrent suppliers on one auction |
| Portability | `docker compose up` starts DB, API and frontend, with seed data |

---

## 7. Implementation Assumptions

The assignment does not specify these. They are **our** interpretation, not assignment requirements, and each is isolated in code so it can be changed.

| ID | Topic | Assumption | Alternative if the reviewer disagrees |
|---|---|---|---|
| A-1 | Ranking price | Rank uses `total_price` only; transit time and validity are informational. | Weighted scoring (out of scope) |
| A-2 | Equal bids | Equal totals rank by earlier `accepted_at`, then lower bid id. | Share the rank / reject equal bids |
| A-3 | Revisions | Suppliers may revise; a revision must be strictly lower than their own current bid. | Allow any revision |
| A-4 | "Winning" bid | No award workflow exists. L1 at close is shown as the **final lowest bid**; the buyer's award decision is outside the system. | Add award step |
| A-5 | Rank-change definition | Ranking = ordered list of suppliers with a current bid. `ANY_RANK_CHANGE` compares the full ordered list of supplier IDs before vs after accepting a bid (`supplier_ids_before != supplier_ids_after`); comparing merely the numerical rank of the bidder is insufficient. It fires if before ≠ after, which explicitly includes a supplier's **first bid** (new entrant adding an ID). `L1_RANK_CHANGE` compares `l1_supplier_id_before != l1_supplier_id_after`, which includes none → first bidder. A bidder improving their price without altering the ordered list of supplier IDs does not fire either trigger. | Count only changes among already-ranked suppliers |
| A-6 | Closing boundary | Window start inclusive; close time exclusive (BR-3, BR-5). | n/a |
| A-7 | Authentication | Demonstration-only identity mechanism: seeded users selected by an `X-User-Id` header resolved by the backend against the database and enforcing role permissions (`BUYER` vs `SUPPLIER`). This is not production authentication; the frontend cannot grant or alter its own role, as the backend strictly authorizes requests against the seeded database records. | Real auth (OAuth2/JWT) |
| A-8 | Pickup date | Informational; not constrained against close times (UI may warn if earlier than `forced_close_time`). | Enforce ordering |
| A-9 | Visibility | Open bidding: carrier names and prices of all current bids are visible to participants. | Anonymise competitors |
| A-10 | Single price per RFQ | One RFQ = one lane/shipment; no line items. | Multi-lane |

---

## 8. Success Metrics (Demo Metrics)

> **These are demo metrics.** They are computed from the system's own data to show how the product *would* be evaluated. They do **not** prove causation, and no target values are claimed. Real validation requires production data and a controlled comparison (British Auction vs fixed deadline on comparable RFQs).

Notation for one RFQ: `T_orig = original_close_time`. "Price at time t" = lowest `total_price` among bids with `accepted_at < t` (history-based, so it is not distorted by later bids).

| ID | Metric | Formula | Baseline (the "non-extended" comparison) |
|---|---|---|---|
| M1 | **Bids per RFQ** | `COUNT(accepted bids)` per RFQ; report the arithmetic mean across all RFQs (RFQs with zero accepted bids are included with a count of 0). | Bids accepted **before** `T_orig` (what a fixed-deadline RFQ would have collected). Extension-period bids = `COUNT(accepted_at ≥ T_orig)`. For each RFQ, report both and the extension-period share: `(extension-period bids) / (total accepted bids for that RFQ)`. If an RFQ has 0 total accepted bids, its extension-period share is defined as 0% (or excluded from the ratio average, while being counted as 0 in total bids mean). |
| M2 | **Price improvement from extension** | `(P_orig − P_final) / P_orig`, where `P_orig` = price at `T_orig`, `P_final` = final L1 price. Defined only for auctions with ≥ 1 bid before `T_orig`. | `P_orig`, the best price the buyer would have had at the original deadline |
| M3 | **Extension effectiveness** | `(# extended auctions with P_final < P_orig) / (# extended auctions)`; also mean extensions per extended auction | An extended auction with `P_final = P_orig` counts as ineffective |
| M4 | **Overall price reduction** | `(P_first − P_final) / P_first`, where `P_first` = lowest price at the first bid | n/a (descriptive) |

SQL for each is in `Technical-Design.md` §11. If the demo database holds some RFQs with British Auction disabled, M1 may additionally be compared against their mean bids per RFQ, labelled as a *demo comparison only*.

---

## 9. Acceptance Criteria

**Fixture F1** (used below). `bid_start_time` 17:00 · `original_close_time` 18:00 · `forced_close_time` 18:30 · X = 10 · Y = 5. Suppliers A, B, C. Before each test: A's current bid 1000, B's current bid 1100 (ranking A = L1, B = L2). Trigger type is stated per test. All times same day, UTC.

### 9.1 Creation and validation
| ID | Given → When → Then |
|---|---|
| AC-1 | `forced_close_time ≤ original_close_time` → create RFQ → `422 INVALID_AUCTION_CONFIG`; nothing stored |
| AC-2 | British Auction enabled, any of X / Y / trigger missing → create → `422 INVALID_AUCTION_CONFIG` (and a direct SQL insert with a NULL is also rejected by the DB constraint) |
| AC-3 | X = 0 or Y = 0 → create → rejected as above |
| AC-4 | Valid payload → create → RFQ stored with `current_close_time = original_close_time`; `RFQ_CREATED` log entry exists |

### 9.2 Bid acceptance and the closing boundary
| ID | Given → When → Then |
|---|---|
| AC-5 | F1 → bid accepted at 17:59:59.999 → `201`; bid stored; `accepted_at` is the DB clock time |
| AC-6 | F1, no extension possible (trigger `L1_RANK_CHANGE`, bid doesn't change L1) → bid at exactly 18:00:00 → `409 AUCTION_NOT_ACTIVE`; nothing stored |
| AC-7 | F1 → bid at 16:59 → `409 AUCTION_NOT_ACTIVE` (details: status `SCHEDULED`) |
| AC-8 | After close → any bid → `409 AUCTION_NOT_ACTIVE`, regardless of scheduler state |
| AC-9 | A rejected bid (any reason, e.g. inactive, `BID_NOT_LOWER`, validation error) → entire transaction rolls back; no bid-history record, no current-bid modification, no extension, and no activity audit entry is committed. Auction state, ranking, and activity logs remain completely **unchanged**; no extension is evaluated. |
| AC-10 | A's current bid is 1000 → A bids 1000 or 1050 → `409 BID_NOT_LOWER` |

### 9.3 Extension triggers
| ID | Trigger | Given → When → Then |
|---|---|---|
| AC-11 | `BID_RECEIVED` | F1 → C bids 1200 at 17:55 → extended 18:00 → 18:05; log has reason |
| AC-12 | `BID_RECEIVED` | F1 → bid at 17:49:59 → **not** extended (outside window) |
| AC-13 | `BID_RECEIVED` | F1 → bid at exactly 17:50:00 → extended (window start inclusive) |
| AC-14 | `ANY_RANK_CHANGE` | F1 → B bids 900 at 17:58 (B passes A) → extended |
| AC-15 | `ANY_RANK_CHANGE` | F1 → B bids 1050 at 17:58 (still behind A, order unchanged) → **not** extended |
| AC-16 | `ANY_RANK_CHANGE` | F1 → new supplier C bids 1200 at 17:58 (enters last) → extended (A-5) |
| AC-17 | `L1_RANK_CHANGE` | F1 → B bids 900 at 17:58 → L1 A → B → extended |
| AC-18 | `L1_RANK_CHANGE` | F1 → C bids 1200 at 17:58 (enters last) → **not** extended |
| AC-19 | `L1_RANK_CHANGE` | F1 → A (L1) lowers own bid to 950 at 17:58 → **not** extended |
| AC-20 | any | Bid outside the window changes L1 at 17:30 → **not** extended |
| AC-21 | any | After one extension to 18:05, a bid at 18:03 (window now 17:55 – 18:05) → evaluated against the **new** window; may extend again |

### 9.4 Forced-close cap
| ID | Given → When → Then |
|---|---|
| AC-22 | `current_close_time` 18:28, qualifying bid at 18:27 → `new_close = min(18:33, 18:30) = 18:30`; `TIME_EXTENDED` logged with `capped = true` |
| AC-23 | `current_close_time` = 18:30 (= forced), qualifying bid at 18:29 → bid accepted; **no** extension; `EXTENSION_SKIPPED` logged with reason |
| AC-24 | `current_close_time` = 18:30 → bid at 18:30:00 → `409 AUCTION_NOT_ACTIVE` |
| AC-25 | Attempt to set `current_close_time > forced_close_time` directly in SQL → rejected by DB constraint |
| AC-26 | Auction ends at 18:30 with `current_close_time = forced_close_time` → status **Force Closed**; ended earlier (e.g. 18:10) → **Closed** |

### 9.5 Ranking and history
| ID | Given → When → Then |
|---|---|
| AC-27 | A bids 1000 then 900 → ranking shows A once at 900; history shows both 1000 and 900 (1000 marked superseded) |
| AC-28 | A's old bid (1000) is lower than B's current (950)? n/a. Instead: A superseded 1000 → 1050 attempt is rejected, so ranking never regresses |
| AC-29 | Two suppliers with equal totals → the one with earlier `accepted_at` is the higher rank |
| AC-30 | Listing "current lowest bid" equals the L1 price on the details page |

### 9.6 Status, scheduler and idempotency
| ID | Given → When → Then |
|---|---|
| AC-31 | Scheduler stopped; time passes `current_close_time` → read listing/details → status already Closed / Force Closed |
| AC-32 | Scheduler runs twice (or two instances concurrently) → exactly one terminal state and exactly one `AUCTION_CLOSED`/`AUCTION_FORCE_CLOSED` log entry |
| AC-33 | Scheduler-recorded `closed_at` equals the `current_close_time` at closure, not the time the job ran |

### 9.7 Concurrency (full procedures in `Technical-Design.md` §10)
| ID | Given → When → Then |
|---|---|
| AC-34 | Two simultaneous valid bids → both processed one after the other; ranking, extension count and `current_close_time` are consistent with sequential processing |
| AC-35 | A bid racing with closure → either accepted **and** extends the auction, or rejected with `409`; never accepted after the auction ended |
| AC-36 | N simultaneous qualifying bids near the cap → `current_close_time ≤ forced_close_time`; `extension_count` equals number of `TIME_EXTENDED` entries |
| AC-37 | The same supplier submits two bids concurrently → at most one lower-than-current bid wins; the other gets `BID_NOT_LOWER` |

### 9.8 API contract
| ID | Given → When → Then |
|---|---|
| AC-38 | No/unknown user → any API → `401 UNAUTHENTICATED` |
| AC-39 | Supplier calls create RFQ, or buyer submits a bid → `403 FORBIDDEN` |
| AC-40 | Unknown RFQ id → `404 RFQ_NOT_FOUND` |
| AC-41 | Every error response uses the single envelope and codes in `Technical-Design.md` §8.3 |

### 9.9 UI and audit
| ID | Given → When → Then |
|---|---|
| AC-42 | Listing shows name/ID, lowest bid, current close time, forced close time, status; refreshes automatically |
| AC-43 | Details page shows ranked current bids, history, X/Y/trigger, and activity log entries for bids, extensions (old → new close, reason) and closure |
| AC-44 | Bid form is hidden/disabled when status is not Active; countdown follows `current_close_time` after an extension |

---

## 10. Deliverables

| Deliverable | Document / artefact |
|---|---|
| Simple HLD with architecture diagram | `HLD.md` |
| Schema design for database tables | `Technical-Design.md` §4 |
| Backend code | FastAPI service per `Technical-Design.md` |
| Frontend code | React app (listing, create RFQ, details) |

## 11. Open Questions

| # | Question | Default taken |
|---|---|---|
| Q1 | Should a new supplier's first bid count as a rank change for `ANY_RANK_CHANGE`? | Yes (A-5) |
| Q2 | Should competitor identities be hidden from suppliers? | No, visible (A-9) |
| Q3 | Is a supplier allowed to revise upward? | No (A-3) |