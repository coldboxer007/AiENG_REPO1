# Repo 1 — Financial Data MCP Server

> **MCP-compliant server** exposing financial data tools for LLM tool-calling and function execution.  
> Built with **Python 3.11+**, **FastAPI**, **SQLAlchemy 2.0**, **PostgreSQL**, and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LLM / Agent Client                          │
│                   (Claude, GPT, custom agent)                      │
└────────────────────────────┬────────────────────────────────────────┘
                             │  MCP (stdio / JSON-RPC)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        MCP Server (server.py)                       │
│  ┌────────────┐  ┌──────────────────┐  ┌────────────────────────┐  │
│  │ Tool Defs  │  │  Tool Handlers   │  │ ToolResponse envelope  │  │
│  └────────────┘  └────────┬─────────┘  └────────────────────────┘  │
│                           │                                         │
│  ┌────────────────────────▼─────────────────────────────────────┐  │
│  │              Service Layer (async)                            │  │
│  │  company_service · financial_service · stock_service          │  │
│  │  analyst_service · metrics (CAGR, drawdown, returns)         │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │                                         │
│  ┌────────────────────────▼─────────────────────────────────────┐  │
│  │           SQLAlchemy 2.0 async ORM + Pydantic v2             │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
└───────────────────────────┼─────────────────────────────────────────┘
                            │
                 ┌──────────▼──────────┐
                 │   PostgreSQL 16     │
                 │  (Docker / Supabase)│
                 └─────────────────────┘
```

### Key Components

| Layer | Files | Purpose |
|---|---|---|
| **MCP Server** | `app/mcp/server.py`, `app/mcp/tools.py` | Registers 6 MCP tools, handles JSON-RPC over stdio |
| **FastAPI** | `app/main.py` | `/health` + `/debug/*` HTTP endpoints for manual testing |
| **Services** | `app/services/*.py` | Async business logic, DB queries, metrics |
| **Models** | `app/models/*.py` | SQLAlchemy 2.0 ORM (4 tables, UUID PKs, indexes) |
| **Schemas** | `app/schemas/*.py` | Pydantic v2 response models + `ToolResponse` envelope |
| **Migrations** | `alembic/` | Alembic migration for full schema |
| **Seed** | `scripts/seed.py` | Faker-based seed (10 companies, 80+ financials, 600+ prices, 40+ ratings) |
| **Tests** | `tests/` | 16 pytest-asyncio tests across all 6 tools |

---

## Setup

### Prerequisites

- **Python 3.11+**
- **Docker** (for local Postgres) **OR** a Supabase Postgres URL

### 1. Clone & create virtual environment

```bash
cd repo1-mcp-server
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

pip install -e ".[dev]"
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env if using Supabase (otherwise Docker defaults are fine)
```

### 3. Start PostgreSQL

**Option A — Docker (recommended):**

```bash
docker compose up -d
```

**Option B — Supabase:**

Update `DATABASE_URL` and `DATABASE_URL_SYNC` in `.env` with your Supabase connection strings.

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Seed the database

```bash
python -m scripts.seed
```

### 6. Run the MCP server (stdio transport)

```bash
python -m app.mcp.server
```

The server communicates over **stdin/stdout** using JSON-RPC per the MCP specification.

### 7. Run FastAPI debug server (optional)

```bash
python -m app.main
# → http://localhost:8000/health
# → http://localhost:8000/docs  (Swagger UI)
```

### 8. Run tests

```bash
pytest -v
```

---

## MCP Tools Reference

All tools return the standard **ToolResponse** envelope:

```json
{
  "tool": "<tool_name>",
  "ok": true,
  "data": { ... },
  "error": null,
  "meta": { "execution_ms": 12.5, "row_count": 3 }
}
```

On error:

```json
{
  "tool": "<tool_name>",
  "ok": false,
  "data": null,
  "error": { "error_code": "TICKER_NOT_FOUND", "message": "...", "hint": "..." },
  "meta": { "execution_ms": 1.2, "row_count": 0 }
}
```

---

## Quick Demo — 6 Example Tool Calls

Below are example calls (via the `/debug` HTTP endpoints) and expected responses.

### 1. `search_companies`

```bash
curl "http://localhost:8000/debug/search_companies?query=Alph&limit=5"
```

```json
{
  "tool": "search_companies",
  "ok": true,
  "data": [
    { "ticker": "ALPH", "name": "Alpha Corp", "sector": "Technology", "market_cap": 500000000000.0 }
  ],
  "error": null,
  "meta": { "execution_ms": 8.3, "row_count": 1 }
}
```

### 2. `get_company_profile`

```bash
curl "http://localhost:8000/debug/get_company_profile?ticker=ALPH"
```

```json
{
  "tool": "get_company_profile",
  "ok": true,
  "data": {
    "id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
    "ticker": "ALPH",
    "name": "Alpha Corp",
    "sector": "Technology",
    "industry": "Software",
    "market_cap": 500000000000.0,
    "employees": 50000,
    "description": "A leading technology company.",
    "country": "US",
    "currency": "USD"
  },
  "error": null,
  "meta": { "execution_ms": 5.1, "row_count": 1 }
}
```

### 3. `get_financial_summary`

```bash
curl "http://localhost:8000/debug/get_financial_summary?ticker=ALPH&years=2"
```

```json
{
  "tool": "get_financial_summary",
  "ok": true,
  "data": {
    "ticker": "ALPH",
    "years_covered": 2,
    "data": [
      { "year": 2023, "revenue": 200000000000.0, "net_income": 40000000000.0, "operating_margin": 0.30, "net_margin": 0.20, "eps": 5.0 },
      { "year": 2024, "revenue": 210000000000.0, "net_income": 44000000000.0, "operating_margin": 0.30, "net_margin": 0.20, "eps": 5.5 }
    ],
    "revenue_cagr": 0.05,
    "net_income_cagr": 0.10
  },
  "error": null,
  "meta": { "execution_ms": 12.0, "row_count": 2 }
}
```

### 4. `compare_companies`

```bash
curl "http://localhost:8000/debug/compare_companies?tickers=ALPH,BETA&metric=market_cap"
```

```json
{
  "tool": "compare_companies",
  "ok": true,
  "data": {
    "comparison": [
      { "ticker": "ALPH", "metric": "market_cap", "value": 500000000000.0 },
      { "ticker": "BETA", "metric": "market_cap", "value": 120000000000.0 }
    ],
    "winner": "ALPH",
    "explanation": "ALPH leads on market_cap among ['ALPH', 'BETA']."
  },
  "error": null,
  "meta": { "execution_ms": 9.2, "row_count": 2 }
}
```

### 5. `get_stock_price_history`

```bash
curl "http://localhost:8000/debug/get_stock_price_history?ticker=ALPH&start_date=2024-03-01&end_date=2024-03-15"
```

```json
{
  "tool": "get_stock_price_history",
  "ok": true,
  "data": {
    "ticker": "ALPH",
    "start_date": "2024-03-01",
    "end_date": "2024-03-15",
    "prices": [
      { "date": "2024-03-01", "open": 150.0, "high": 152.5, "low": 148.0, "close": 151.2, "volume": 5000000, "daily_return": null },
      { "date": "2024-03-04", "open": 151.2, "high": 153.0, "low": 149.5, "close": 152.0, "volume": 4500000, "daily_return": 0.00529101 }
    ],
    "total_return_pct": 0.012,
    "max_drawdown_pct": -0.008
  },
  "error": null,
  "meta": { "execution_ms": 7.5, "row_count": 10 }
}
```

### 6. `get_analyst_consensus`

```bash
curl "http://localhost:8000/debug/get_analyst_consensus?ticker=ALPH"
```

```json
{
  "tool": "get_analyst_consensus",
  "ok": true,
  "data": {
    "ticker": "ALPH",
    "total_ratings": 5,
    "rating_counts": [
      { "rating": "Strong Buy", "count": 2 },
      { "rating": "Buy", "count": 2 },
      { "rating": "Hold", "count": 1 }
    ],
    "average_price_target": 170.0,
    "recent_ratings": [
      { "firm_name": "Citi", "rating": "Strong Buy", "price_target": 180.0, "rating_date": "2024-06-05", "notes": null },
      { "firm_name": "Barclays", "rating": "Buy", "price_target": 175.0, "rating_date": "2024-06-04", "notes": "Note from Barclays" }
    ]
  },
  "error": null,
  "meta": { "execution_ms": 6.0, "row_count": 5 }
}
```

---

## Formatting

```bash
ruff check app/ tests/ scripts/
black --check app/ tests/ scripts/
```

---

## License

MIT
