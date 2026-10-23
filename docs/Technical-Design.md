# Technical Design
## British Auction in RFQ System

| Field | Value |
|---|---|
| Status | Draft v1.1 |
| Stack | FastAPI, PostgreSQL, React, SQLAlchemy/Alembic recommended |
| Related documents | `PRD.md`, `HLD.md` |

## 1. Design goals

This document defines the data model, API contracts, bid transaction, extension algorithm, validation, error contract, and tests. The database is authoritative for auction timestamps and state. Any behavior not fixed by the assignment is explicitly identified as an implementation assumption.

## 2. Domain rules

- `C` = current close time; `F` = immutable Forced Close Time; `X` = trigger window minutes; `Y` = extension minutes.
- Trigger window: `[C - X, C)`.
- A bid is accepted only if `start_time <= accepted_at < C` and `accepted_at < F`.
- `accepted_at` is assigned by the database after the RFQ row lock has been acquired.
- Total price = freight + origin + destination, calculated by the server.
- Each supplier's accepted revision must be strictly lower than its previous accepted total for the same RFQ.
- Current ranking uses each supplier's latest accepted bid, ordered by total ascending and then accepted timestamp ascending.
- Extension: `new_C = min(C + Y, F)`.
- One accepted bid can trigger at most one extension.
- A rejected bid cannot change ranking, close time, or extension count.
- Current close time is monotonic and cannot exceed forced close time.

## 3. Database schema

The following SQL is a reference schema for PostgreSQL. Use migrations in the implementation. It intentionally fixes the nullable-configuration CHECK issue by combining `NOT NULL` requirements for the configuration fields when British Auction is enabled.

```sql
CREATE TABLE users (
    id          BIGSERIAL PRIMARY KEY,
    name        VARCHAR(120) NOT NULL,
    email       VARCHAR(160) NOT NULL UNIQUE,
    role        VARCHAR(20) NOT NULL
                CHECK (role IN ('BUYER', 'SUPPLIER', 'ADMIN')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE suppliers (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT UNIQUE REFERENCES users(id),
    carrier_name VARCHAR(160) NOT NULL,
    is_active    BOOLEAN NOT NULL DEFAULT TRUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE rfqs (
    id                      BIGSERIAL PRIMARY KEY,
    reference_id            VARCHAR(60) NOT NULL UNIQUE,
    name                    VARCHAR(200) NOT NULL,
    created_by              BIGINT REFERENCES users(id),
    currency                CHAR(3) NOT NULL DEFAULT 'USD',

    bid_start_time          TIMESTAMPTZ NOT NULL,
    original_close_time     TIMESTAMPTZ NOT NULL,
    current_close_time      TIMESTAMPTZ NOT NULL,
    forced_close_time       TIMESTAMPTZ NOT NULL,
    pickup_date             TIMESTAMPTZ NOT NULL,

    british_auction_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    trigger_window_minutes  INTEGER,
    extension_minutes       INTEGER,
    extension_trigger       VARCHAR(30),

    status                  VARCHAR(20) NOT NULL DEFAULT 'SCHEDULED'
                            CHECK (status IN
                              ('SCHEDULED','ACTIVE','CLOSED','FORCE_CLOSED')),
    extension_count         INTEGER NOT NULL DEFAULT 0
                            CHECK (extension_count >= 0),
    closed_at               TIMESTAMPTZ,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_close_after_start
        CHECK (original_close_time > bid_start_time),
    CONSTRAINT chk_forced_after_original
        CHECK (forced_close_time > original_close_time),
    CONSTRAINT chk_current_not_after_forced
        CHECK (current_close_time <= forced_close_time),
    CONSTRAINT chk_current_not_before_original
        CHECK (current_close_time >= original_close_time),
    CONSTRAINT chk_british_config CHECK (
        british_auction_enabled = FALSE OR (
            trigger_window_minutes IS NOT NULL
            AND trigger_window_minutes > 0
            AND extension_minutes IS NOT NULL
            AND extension_minutes > 0
            AND extension_trigger IS NOT NULL
            AND extension_trigger IN
              ('BID_RECEIVED','ANY_RANK_CHANGE','L1_RANK_CHANGE')
        )
    )
);

CREATE TABLE bids (
    id                   BIGSERIAL PRIMARY KEY,
    rfq_id               BIGINT NOT NULL REFERENCES rfqs(id),
    supplier_id          BIGINT NOT NULL REFERENCES suppliers(id),
    freight_charges      NUMERIC(14,2) NOT NULL CHECK (freight_charges >= 0),
    origin_charges       NUMERIC(14,2) NOT NULL CHECK (origin_charges >= 0),
    destination_charges  NUMERIC(14,2) NOT NULL CHECK (destination_charges >= 0),
    total_price          NUMERIC(14,2) NOT NULL CHECK (total_price > 0),
    transit_time_days    INTEGER NOT NULL CHECK (transit_time_days > 0),
    quote_valid_until    TIMESTAMPTZ NOT NULL,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_bids_rfq_supplier_time
    ON bids (rfq_id, supplier_id, created_at DESC, id DESC);
CREATE INDEX idx_bids_rfq_price
    ON bids (rfq_id, total_price, created_at);

CREATE TABLE activity_logs (
    id          BIGSERIAL PRIMARY KEY,
    rfq_id      BIGINT NOT NULL REFERENCES rfqs(id),
    bid_id      BIGINT REFERENCES bids(id),
    event_type  VARCHAR(40) NOT NULL CHECK (event_type IN (
        'RFQ_CREATED',
        'BID_SUBMITTED',
        'TIME_EXTENDED',
        'EXTENSION_SKIPPED_FORCED_CAP',
        'AUCTION_STARTED',
        'AUCTION_CLOSED',
        'AUCTION_FORCE_CLOSED'
    )),
    message     TEXT NOT NULL,
    metadata    JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_activity_logs_rfq_time
    ON activity_logs (rfq_id, created_at, id);
```

### 3.1 Schema implementation notes

1. Use `NUMERIC`, not floating-point, for monetary values.
2. Compute `total_price` on the server. Do not trust a client-provided total.
3. If database-level enforcement of `total_price = freight + origin + destination` is desired, add a CHECK constraint for that equality; always retain server-side calculation.
4. The `bids` table is the immutable history. Do not overwrite a supplier's prior bid.
5. Current ranking is a query/view over the latest accepted bid per `(rfq_id, supplier_id)`, not a ranking of every historical bid.
6. Add a closure-event uniqueness/idempotency strategy in the implementation, such as a state transition guarded by the RFQ row lock and writing the event only when the terminal state changes.
7. If British Auction is disabled, configuration may be null; no extension is performed and the auction closes at its fixed current close time.
8. `CHECK` constraints do not replace API validation or transaction logic.

### 3.2 Current ranking query

```sql
WITH latest_per_supplier AS (
    SELECT DISTINCT ON (b.rfq_id, b.supplier_id)
           b.rfq_id,
           b.supplier_id,
           b.id AS bid_id,
           b.total_price,
           b.created_at
    FROM bids b
    WHERE b.rfq_id = :rfq_id
    ORDER BY b.rfq_id, b.supplier_id, b.created_at DESC, b.id DESC
)
SELECT
    ROW_NUMBER() OVER (ORDER BY total_price ASC, created_at ASC, bid_id ASC) AS rank,
    supplier_id,
    bid_id,
    total_price,
    created_at
FROM latest_per_supplier
ORDER BY rank;
```

The tie-break uses the earlier accepted bid. `id` is a final deterministic tie-breaker if timestamps are equal at the database's stored precision.

## 4. Bid submission transaction

All operations that affect a bid's validity or auction close time must be serialized for the same RFQ. Use one database transaction and a consistent RFQ-row-locking strategy.

```text
BEGIN

1. SELECT the RFQ row FOR UPDATE.
2. After acquiring the lock, obtain a fresh database timestamp.
3. Resolve the auction state from the locked row and timestamp.
4. Reject if not started, terminal, now >= current_close_time, or now >= forced_close_time.
5. Validate supplier exists and is active.
6. Compute the supplier's latest accepted bid; reject unless new total is strictly lower.
7. Compute ranking_before using latest bid per supplier.
8. Insert the immutable bid with database accepted_at.
9. Compute ranking_after using latest bid per supplier.
10. Insert BID_SUBMITTED activity event.
11. If British Auction is enabled and current close time's trigger window contains accepted_at:
      a. Evaluate the configured trigger using ranking_before/ranking_after.
      b. If it qualifies, compute new_close = MIN(current_close + Y, forced_close).
      c. If new_close > current_close, update current_close_time and extension_count,
         then insert TIME_EXTENDED with old/new close times, trigger, and bid ID.
      d. Otherwise insert EXTENSION_SKIPPED_FORCED_CAP if the trigger qualifies.
12. Commit.

COMMIT
```

**Important timestamp detail:** PostgreSQL `now()`/`CURRENT_TIMESTAMP` is fixed at transaction start. To satisfy the “time after lock” acceptance boundary, use a fresh clock reading after acquiring the RFQ lock (for example, `clock_timestamp()`), capture it once as `accepted_at`, and use that same value consistently for bid acceptance and trigger-window checks. Use the same locked RFQ state for the comparison. Do not compare against a stale client clock.

If the transaction fails, the bid, close-time update, extension count, and activity events all roll back together.

## 5. Extension engine

```python
def calculate_new_close(current_close, forced_close, extension_minutes):
    return min(
        current_close + timedelta(minutes=extension_minutes),
        forced_close,
    )
```

Trigger evaluation:

- `BID_RECEIVED`: true for every valid accepted bid in the trigger window.
- `ANY_RANK_CHANGE`: compare the ordered supplier IDs in ranking before and after the accepted bid. Any difference is a change.
- `L1_RANK_CHANGE`: compare the L1 supplier ID before and after the accepted bid. Empty-to-first-supplier is a change.

| Situation | `ANY_RANK_CHANGE` | `L1_RANK_CHANGE` |
|---|---:|---:|
| First bid ever | Yes | Yes |
| New supplier enters in last position | Yes | No |
| New supplier becomes L1 | Yes | Yes |
| Supplier lowers price but supplier order does not change | No | No |
| Supplier moves above another but is not L1 | Yes | No |
| Current L1 lowers price but remains L1 | No | No |

If `current_close_time == forced_close_time`, the qualifying bid can still be accepted before that deadline, but no additional time can be added. Log the skipped extension. At `accepted_at >= forced_close_time`, reject the bid.

## 6. Status resolution and scheduler

Status is resolved from current database time and timestamps:
- Before start: `SCHEDULED`.
- Before current close: `ACTIVE`.
- At/after current close, where current close is earlier than forced close: `CLOSED`.
- At/after the forced deadline when the auction has reached the forced deadline: `FORCE_CLOSED`.

The resolver must be shared by read endpoints and bid submission. The scheduler periodically finds elapsed auctions and persists terminal status. It must lock the RFQ row, re-check the state, and write the closure event only if it actually transitions the auction into a terminal state. Repeated scheduler runs must not duplicate closure events.

## 7. API specification

Base path: `/api/v1`

| Method | Endpoint | Purpose | Access |
|---|---|---|---|
| `POST` | `/rfqs` | Create an RFQ | Buyer |
| `GET` | `/rfqs` | List auctions; support status, search, and pagination | All demo roles |
| `GET` | `/rfqs/{id}` | Auction details, current ranking, status, close times | All demo roles |
| `POST` | `/rfqs/{id}/bids` | Submit a bid | Supplier |
| `GET` | `/rfqs/{id}/bids` | Bid history and current rank view | All demo roles |
| `GET` | `/rfqs/{id}/activity` | Paginated activity history | All demo roles |
| `GET` | `/suppliers` | List demo suppliers for the role switcher | All demo roles |
| `GET` | `/health` | Health check and server time | Public for local demo |

### 7.1 Create RFQ request

```json
{
  "reference_id": "RFQ-2026-0001",
  "name": "Delhi to Mumbai FTL",
  "bid_start_time": "2026-11-02T10:00:00Z",
  "bid_close_time": "2026-11-02T12:30:00Z",
  "forced_bid_close_time": "2026-11-02T13:30:00Z",
  "pickup_date": "2026-11-05T09:00:00Z",
  "british_auction": {
    "enabled": true,
    "trigger_window_minutes": 10,
    "extension_minutes": 5,
    "extension_trigger": "L1_RANK_CHANGE"
  }
}
```

### 7.2 Submit bid request

```json
{
  "supplier_id": 3,
  "freight_charges": 42000.00,
  "origin_charges": 1500.00,
  "destination_charges": 2000.00,
  "transit_time_days": 3,
  "quote_valid_until": "2026-11-20T00:00:00Z"
}
```

The client does not send `total_price`, accepted timestamp, rank, or extension outcome as trusted fields.

### 7.3 Successful bid response

```json
{
  "bid_id": 87,
  "total_price": "45500.00",
  "rank": 1,
  "extended": true,
  "previous_close_time": "2026-11-02T12:30:00Z",
  "current_close_time": "2026-11-02T12:35:00Z",
  "extension_reason": "L1 changed from Supplier B to Supplier C within the trigger window"
}
```

Use a consistent serialization format for monetary values; decimal strings avoid JSON floating-point ambiguity.

### 7.4 Error contract

Use one consistent response structure, for example:

```json
{
  "error": {
    "code": "AUCTION_NOT_ACTIVE",
    "message": "Bids are accepted only while the auction is active."
  }
}
```

| HTTP | Error code | Meaning |
|---|---|---|
| `400` | `VALIDATION_ERROR` | Invalid field or rule violation |
| `403` | `FORBIDDEN` | Caller role cannot perform the action |
| `404` | `NOT_FOUND` | RFQ or supplier does not exist |
| `409` | `DUPLICATE_REFERENCE` | RFQ reference ID already exists |
| `409` | `BID_NOT_LOWER` | New total is not lower than the supplier's latest bid |
| `409` | `AUCTION_NOT_ACTIVE` | Auction not started or bidding deadline elapsed |
| `409` | `SUPPLIER_INACTIVE` | Supplier is not active |

Use `400` consistently for domain validation errors and `409` for state conflicts. If the implementation uses `422` for Pydantic request-shape validation, document that distinction explicitly and do not use `400` and `422` interchangeably for the same condition.

## 8. Frontend requirements

1. **Listing page:** name/reference, lowest current bid, current close, forced close, status, create action.
2. **Create RFQ page:** required fields, conditional British Auction configuration, inline date and X/Y validation.
3. **Details page:** status/countdown, configuration, current supplier ranking, quote components, bid form, activity log.
4. Poll active details every 3–5 seconds. Stop frequent polling after terminal state.
5. Countdown is display-only; API remains authoritative. Use server time/offset and show timezone clearly.
6. Show a visible update when an extension changes the close time.
7. Provide empty states for no bids, not-yet-started, closed, and force-closed auctions.
8. Keyboard-navigable forms; do not use color as the only status indicator.

## 9. Test plan

### 9.1 Unit tests
- Total calculation and charge validation.
- Lower-revision rule.
- Ranking order and equal-price tie-break.
- Each trigger inside and outside the window.
- First bid and new supplier ranking behavior.
- No extension when rank remains unchanged for rank-based triggers.
- Extension capped at forced close.
- No extension possible when current close equals forced close.
- Half-open trigger-window boundaries.

### 9.2 API/integration tests
- RFQ date validation, configuration validation, duplicate reference.
- Bid before start, exactly at close, after close, and at/after forced close.
- Inactive supplier, invalid quote validity, and non-lower bid.
- Bid insert and activity log roll back together on failure.
- Current ranking uses only latest bid per supplier.
- Status correctness without scheduler execution.
- Scheduler retries do not duplicate closure events.
- Listing returns correct current lowest bid, close times, and status.

### 9.3 Concurrency tests
- Submit multiple bids for one RFQ concurrently.
- Race a bid against the closing boundary.
- Race two qualifying bids that could both extend the auction.
- Confirm ranking is calculated from the serialized state.
- Confirm close time never exceeds forced close.
- Confirm one bid cannot cause duplicate extensions and event rows correspond to committed state.

### 9.4 End-to-end smoke test
Create RFQ → submit bids from two suppliers → confirm ranking → trigger extension → confirm close-time/countdown update and reason in activity log → verify auction becomes read-only at close.

## 10. Suggested implementation layout

```text
backend/
  app/
    main.py
    api/
      rfqs.py
      bids.py
      suppliers.py
      activity.py
    services/
      auction_service.py
      ranking.py
      extension_engine.py
      status_resolver.py
    models/
    schemas/
    repositories/
    core/
      config.py
      database.py
      time_utils.py
    scheduler.py
  tests/
  alembic/
frontend/
  src/
    pages/
    components/
    api/
docs/
  PRD.md
  HLD.md
  Technical-Design.md
docker-compose.yml
README.md
```

## 11. Open implementation assumptions

- Currency defaults to USD in the schema example; make it explicit in the UI and do not implement conversion.
- The assignment does not specify manual cancellation/closure; it remains out of scope.
- No arbitrary maximum extension count is added; Forced Close Time is the cap.
- Supplier identity is visible in the open-auction demo.
- Demo role switching is not production authentication.
