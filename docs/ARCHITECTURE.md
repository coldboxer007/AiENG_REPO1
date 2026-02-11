# Architecture Decision Records

## ADR-001: Why No Supabase RLS?

**Context:** The assignment mentions "Supabase RLS policies if applicable."

**Decision:** Row Level Security is *not* implemented for this MCP server.

**Rationale:**

| Consideration | Detail |
|---|---|
| **Deployment model** | This is a **local tool** running via stdio or SSE on the developer's machine, not a multi-tenant web service. |
| **MCP servers** | Typically run with **service role credentials** (full DB access).  The person running the MCP client is the sole user. |
| **RLS purpose** | Designed for multi-user apps where User A should not see User B's data (e.g. a SaaS dashboard). |
| **Our use case** | Single user.  Full access to all financial data is the *expected* behaviour. |

**Consequences:**

- Simpler implementation and no RLS policy management overhead.
- No query-planning slowdown from per-row policy evaluation.
- If this server were ever deployed as a multi-tenant service, RLS policies on `companies`, `financials`, `stock_prices`, and `analyst_ratings` would need to be added.

---

## ADR-002: Service Layer vs Direct ORM Access

**Context:** Each of the 6 MCP tools calls a service function rather than inlining SQLAlchemy queries in the tool handler.

**Decision:** Keep a dedicated service layer (`app/services/`) for business logic.

**Rationale:**

- **Testability** – service functions accept a plain `AsyncSession` and can be tested with an in-memory SQLite database (see `tests/conftest.py`) without spinning up the MCP protocol.
- **Query optimisation** – central location for adding explicit `selectinload()`, indexes, and caching later.
- **Separation of concerns** – tool handlers deal with argument parsing, validation, error formatting, and rate limiting; services deal with SQL.

**Trade-offs:**

- More files to navigate (4 service files vs inline queries).
- Slight indirection for trivial CRUD.  Worthwhile at this project's scale.

---

## ADR-003: Cursor-Based vs Offset Pagination

**Context:** Pagination is required for `search_companies` and `get_stock_price_history` which may return hundreds of rows.

**Decision:** **Cursor-based pagination** using base64-encoded keyset tokens.

| | Offset (`LIMIT/OFFSET`) | Cursor (keyset) |
|---|---|---|
| **Performance** | Degrades linearly – DB must scan *N* rows to skip them | Constant time – uses index `WHERE col > last_value` |
| **Consistency** | Rows may shift if data is inserted between pages | Stable – each page starts right after the last seen key |
| **Arbitrary page access** | ✅ Jump to page 5 | ❌ Must traverse sequentially |

For financial data where consistency matters and pages are consumed sequentially by LLMs, cursor pagination wins.

**Implementation:**

```python
cursor = base64(json({"ticker": "AAPL"}))
# Next page: WHERE ticker > 'AAPL' ORDER BY ticker LIMIT N
```

---

## ADR-004: Lazy Loading Strategy

**Before (problematic):**

```python
financials = relationship("Financial", lazy="selectin")  # always loaded
stock_prices = relationship("StockPrice", lazy="selectin")  # always loaded
```

Every `SELECT * FROM companies WHERE …` also loaded ALL financials, stock prices, and analyst ratings for every matched company — even when the caller only needed the company name.

**After:**

```python
financials = relationship("Financial", lazy="select")  # loaded only on access
```

Service methods that need related data use explicit `selectinload()`:

```python
stmt = select(Company).options(selectinload(Company.financials)).where(…)
```

**Impact:** ~10× reduction in data transferred for simple company lookups.

---

## Database Index Strategy

```sql
-- Primary lookup indexes
ix_companies_ticker       ON companies(ticker)
ix_financials_company_id  ON financials(company_id)
ix_stock_prices_company_id ON stock_prices(company_id)
ix_stock_prices_date      ON stock_prices(date)
ix_analyst_ratings_company_id ON analyst_ratings(company_id)
uq_stock_prices_company_date  ON stock_prices(company_id, date)  -- unique constraint

-- Why these indexes?
-- 1. ix_companies_ticker: all 6 tools resolve tickers first
-- 2. ix_stock_prices_company_id + ix_stock_prices_date: range scans on stock history
-- 3. uq_stock_prices_company_date: prevents duplicate prices + acts as composite index
```

**Not added:**

A composite index `(company_id, date)` on `stock_prices` is already covered by the unique constraint `uq_stock_prices_company_date`.

---

## Rate Limiting Design

A sliding-window token bucket per tool, implemented in `app/middleware/rate_limit.py`.

| Tool | Limit |
|---|---|
| Most tools | 60 req / min |
| `compare_companies` | 30 req / min (heavier – loops over tickers) |

When a limit is exceeded the response includes:

```json
{
  "error_code": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded for 'search_companies'. Max 60 requests per 60s. Retry after 12s.",
  "hint": "Wait before retrying. Standard limit: 60 requests/minute."
}
```
