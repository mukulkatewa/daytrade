# DayTrade — Database Schema (v1)

## 1. Global conventions

| Concern | Decision | Why |
|---|---|---|
| Primary keys | `BIGINT GENERATED ALWAYS AS IDENTITY` | Small, fast, monotonically increasing. `orders.id` doubles as the time-priority tie-breaker. |
| Cash | `NUMERIC(18,2)` (Python `Decimal`) | Exact money in rupees. Never `FLOAT`. |
| Price | `NUMERIC(12,2)` **(changed)** | Same scale as cash, so `price × quantity` is always exact in cash — no rounding drift between trades and the ledger. |
| Quantity | `BIGINT` **(changed)** | Whole shares only in v1. Integers make matching simpler. |
| Tick size | Price must be a multiple of `0.05` **(new)** | Mirrors NSE tick size; enforced with a CHECK on order price. |
| Enum-like columns | `TEXT` + `CHECK (... IN (...))` | Easy to extend in a migration; Postgres `ENUM` types are painful to change. |
| Timestamps | `TIMESTAMPTZ`, `server_default now()` | One clock (the database) for all app servers. `updated_at` set via SQLAlchemy `onupdate`. |

**Invariant:** for every account, `SUM(ledger_entries.amount) = available_cash + reserved_cash`.

---

## 2. Tables

### 2.1 users

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | BIGINT | No | identity | PK |
| email | TEXT | No | — | Stored lowercased by the application |
| password_hash | TEXT | No | — | Never store plaintext passwords |
| created_at | TIMESTAMPTZ | No | now() | |

**Constraints:** PK(id), UNIQUE(email)
**Indexes:** unique index on email → login / lookup by email.

### 2.2 accounts

One cash account per user in v1.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | BIGINT | No | identity | PK |
| user_id | BIGINT | No | — | FK → users.id |
| available_cash | NUMERIC(18,2) | No | 0.00 | Spendable cash |
| reserved_cash | NUMERIC(18,2) | No | 0.00 | Held for open buy orders |
| created_at | TIMESTAMPTZ | No | now() | |
| updated_at | TIMESTAMPTZ | No | now() | onupdate now() |

**Constraints:** PK(id), FK(user_id), UNIQUE(user_id), CHECK(available_cash >= 0), CHECK(reserved_cash >= 0)
**Indexes:** unique index on user_id → find a user's account.

### 2.3 instruments

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | BIGINT | No | identity | PK |
| symbol | TEXT | No | — | e.g. `RELIANCE` |
| name | TEXT | No | — | Display name |
| last_price | NUMERIC(12,2) | Yes | NULL | **(new)** Last traded price; used for P&L. NULL until the first trade or seed price. |
| is_active | BOOLEAN | No | TRUE | Whether new orders may be placed |
| created_at | TIMESTAMPTZ | No | now() | |

**Constraints:** PK(id), UNIQUE(symbol), CHECK(last_price IS NULL OR last_price > 0)
**Indexes:** unique index on symbol → lookup by ticker.

### 2.4 holdings

Current position per (account, instrument). A snapshot, not history.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | BIGINT | No | identity | PK |
| account_id | BIGINT | No | — | FK → accounts.id |
| instrument_id | BIGINT | No | — | FK → instruments.id |
| quantity | BIGINT | No | 0 | **(changed)** Total shares owned; long-only |
| reserved_quantity | BIGINT | No | 0 | **(changed)** Held for open sell orders |
| average_price | NUMERIC(12,2) | Yes | NULL | **(changed)** Weighted-average cost; NULL when quantity is 0 |
| created_at | TIMESTAMPTZ | No | now() | |
| updated_at | TIMESTAMPTZ | No | now() | onupdate now() |

**Constraints:** PK(id), FK(account_id), FK(instrument_id), UNIQUE(account_id, instrument_id), CHECK(quantity >= 0), CHECK(reserved_quantity >= 0 AND reserved_quantity <= quantity), CHECK(average_price IS NULL OR average_price >= 0)
**Indexes:** unique (account_id, instrument_id) → load one holding; also serves "all holdings for an account" (leftmost column).

**Rules:**
- Keep zero-quantity rows in v1.
- Buy: `new_avg = (old_qty × old_avg + buy_qty × buy_price) / new_qty`; first buy → `new_avg = buy_price`. Round to 2 decimals.
- Sell: reduce `quantity` and `reserved_quantity`; average price unchanged.

### 2.5 orders

One row per submitted order. **v1 supports LIMIT orders only (changed).**

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | BIGINT | No | identity | PK; also the time-priority tie-breaker |
| user_id | BIGINT | No | — | FK → users.id |
| instrument_id | BIGINT | No | — | FK → instruments.id |
| client_order_id | TEXT | No | — | Idempotency key, unique per user |
| side | TEXT | No | — | `BUY` / `SELL` |
| order_type | TEXT | No | 'LIMIT' | **(changed)** Only `LIMIT` in v1; column kept so `MARKET` can be added later |
| price | NUMERIC(12,2) | No | — | **(changed)** Limit price, now required |
| quantity | BIGINT | No | — | **(changed)** Requested shares |
| filled_quantity | BIGINT | No | 0 | **(changed)** Cumulative executed shares |
| status | TEXT | No | 'OPEN' | See state machine (§3) |
| created_at | TIMESTAMPTZ | No | now() | |
| updated_at | TIMESTAMPTZ | No | now() | onupdate now() |

**Constraints:**
- PK(id), FK(user_id), FK(instrument_id)
- UNIQUE(user_id, client_order_id)
- CHECK(side IN ('BUY','SELL'))
- CHECK(order_type IN ('LIMIT')) **(changed)**
- CHECK(status IN ('OPEN','PARTIALLY_FILLED','FILLED','CANCELLED','REJECTED'))
- CHECK(price > 0)
- CHECK(mod(price, 0.05) = 0) **(new — tick size; use `mod()`, not `%` — Alembic escapes `%` to `%%`, which Postgres rejects)**
- CHECK(quantity > 0)
- CHECK(filled_quantity >= 0 AND filled_quantity <= quantity)

**Indexes:**

| Index | Columns | WHERE | Supports |
|---|---|---|---|
| uq_orders_user_client_order | (user_id, client_order_id) | — | Idempotent retries |
| ix_orders_book_sell **(fixed)** | (instrument_id, price ASC, id ASC) | side='SELL' AND status IN ('OPEN','PARTIALLY_FILLED') | Best ask: lowest price, then oldest |
| ix_orders_book_buy **(new)** | (instrument_id, price DESC, id ASC) | side='BUY' AND status IN ('OPEN','PARTIALLY_FILLED') | Best bid: highest price, then oldest |
| ix_orders_user_created | (user_id, created_at DESC) | — | A user's order list (open or all) |

*Fix explained:* a `PARTIALLY_FILLED` order is still resting in the book, so the book indexes must include it. `id` replaces `created_at` as the tie-breaker because ids never collide.

**Rules:**
- Buy price = maximum acceptable price; sell price = minimum acceptable price.
- Trade price = the **resting (maker)** order's price.
- Out of scope for v1 (noted, not built): MARKET orders, request-hash check on idempotency-key reuse, fees.

### 2.6 trades

One row per match between a buy and a sell order.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | BIGINT | No | identity | PK |
| buy_order_id | BIGINT | No | — | FK → orders.id |
| sell_order_id | BIGINT | No | — | FK → orders.id |
| price | NUMERIC(12,2) | No | — | **(changed)** Execution price |
| quantity | BIGINT | No | — | **(changed)** Executed shares |
| executed_at | TIMESTAMPTZ | No | now() | |

**Constraints:** PK(id), FK(buy_order_id), FK(sell_order_id), CHECK(buy_order_id <> sell_order_id), CHECK(price > 0), CHECK(quantity > 0)
**Indexes:** (buy_order_id), (sell_order_id) → executions per order. "My trade history" joins through orders; denormalize only if measured slow.

**Rules (enforced in application logic inside a transaction, not by the DB):** both orders share the instrument, have opposite sides, are open, and the trade quantity ≤ each order's remaining quantity.

### 2.7 ledger_entries

Append-only record of cash movements — the source of truth for balances.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| id | BIGINT | No | identity | PK |
| account_id | BIGINT | No | — | FK → accounts.id |
| trade_id | BIGINT | Yes | NULL | FK → trades.id; NULL for deposits etc. |
| entry_type | TEXT | No | — | See CHECK |
| amount | NUMERIC(18,2) | No | — | Signed rupees: + adds cash, − removes |
| created_at | TIMESTAMPTZ | No | now() | |

**Constraints:** PK(id), FK(account_id), FK(trade_id), CHECK(amount <> 0), CHECK(entry_type IN ('DEPOSIT','WITHDRAWAL','BUY_SETTLEMENT','SELL_SETTLEMENT','FEE','REVERSAL'))
**Indexes:** (account_id, created_at DESC) → ledger history; (trade_id) → entries for a trade.

**Rules:**
- Never UPDATE or DELETE; fix mistakes with a `REVERSAL` entry.
- Reservations move cash between `available_cash` and `reserved_cash` without changing the total, so they create **no** ledger entry.
- The opening balance is a `DEPOSIT` entry, so the invariant in §1 holds from the first row.
- Ledger insert + account balance update happen in the **same transaction**.

---

## 3. Order state machine

```
            ┌──────────── fill (partial) ───────────┐
            │                                       ▼
  submit ─► OPEN ──── fill (complete) ────► FILLED ◄── fill (complete) ── PARTIALLY_FILLED
            │                                                                │   ▲
            │                                                                │   └ fill (partial)
            ├──── cancel ──► CANCELLED ◄──────────── cancel ─────────────────┘
            │
  submit ─► REJECTED   (validation / insufficient funds — never enters the book)
```

| From | Event | To |
|---|---|---|
| — | submit, valid | OPEN |
| — | submit, invalid / insufficient funds | REJECTED |
| OPEN | partial fill | PARTIALLY_FILLED |
| OPEN / PARTIALLY_FILLED | fill completes quantity | FILLED |
| PARTIALLY_FILLED | another partial fill | PARTIALLY_FILLED |
| OPEN / PARTIALLY_FILLED | user cancels | CANCELLED (release unfilled reservation) |

**Terminal states:** FILLED, CANCELLED, REJECTED. Any transition out of these is a bug and must be refused.
