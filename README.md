# Repo 1 — Financial Data MCP Server

> **MCP-compliant server** exposing financial data tools for LLM tool-calling and function execution.  
> Built with **Python 3.11+**, **SQLAlchemy 2.0**, **PostgreSQL**, and the [Model Context Protocol (MCP)](https://modelcontextprotocol.io).  
> Supports **stdio** and **SSE** transports, cursor-based pagination, rate limiting, MCP resources & prompts.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                    LLM / Agent Client                               │
│              (Claude Desktop, Cursor, MCP Inspector)                │
└──────────────────────┬──────────────────────┬───────────────────────┘
                       │  stdio (JSON-RPC)    │  SSE (HTTP)
                       ▼                      ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     MCP Server (server.py)                          │
│  ┌────────────┐  ┌──────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ 8 Tools    │  │ 1 Resource   │  │ 2 Prompts│  │ Rate Limiter│  │
│  └────────────┘  └──────────────┘  └──────────┘  └─────────────┘  │
│                           │                                         │
│  ┌────────────────────────▼─────────────────────────────────────┐  │
│  │           Service Layer (async, cursor pagination)           │  │
│  │  company_service · financial_service · stock_service          │  │
│  │  analyst_service · metrics (CAGR, drawdown, returns)         │  │
│  └────────────────────────┬─────────────────────────────────────┘  │
│                           │                                         │
│  ┌────────────────────────▼─────────────────────────────────────┐  │
│  │        SQLAlchemy 2.0 async ORM + Pydantic v2 schemas        │  │
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
| **MCP Server** | `app/mcp/server.py` | Registers 8 tools, 1 resource, 2 prompts.  JSON-RPC over stdio. |
| **SSE Transport** | `app/mcp/sse_server.py` | MCP over HTTP Server-Sent Events (port 8000). |
| **Tool Handlers** | `app/mcp/tools.py` | Input validation, rate limiting, response formatting. |
| **Services** | `app/services/*.py` | Async business logic, DB queries, cursor pagination. |
| **Models** | `app/models/*.py` | SQLAlchemy 2.0 ORM (4 tables, UUID PKs, indexes). |
| **Schemas** | `app/schemas/*.py` | Pydantic v2 response models + `ToolResponse` envelope. |
| **Rate Limiter** | `app/middleware/rate_limit.py` | Sliding-window per-tool rate limiting. |
| **Migrations** | `alembic/` | Alembic migration for full schema. |
| **Seed** | `scripts/seed.py` | Faker-based seed (10 companies, 80+ financials, 600+ prices, 40+ ratings). |
| **Tests** | `tests/` | 30+ pytest-asyncio tests (tools, pagination, rate limiting, security). |
| **Debug HTTP** | `app/dev/debug_server.py` | Optional `/debug/*` endpoints for manual testing (not MCP). |

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

---

## Running the MCP Server

### Option A: stdio transport (for Claude Desktop, Cursor)

```bash
python -m app.mcp.server
```

The server communicates over **stdin/stdout** using JSON-RPC per the MCP specification.

### Option B: SSE transport (for web clients)

```bash
python -m app.mcp.sse_server
# SSE stream:    GET  http://localhost:8000/sse
# Post messages: POST http://localhost:8000/messages?session_id=<id>
# Health check:  GET  http://localhost:8000/health
```

### Option C: HTTP debug server (optional, dev-only)

```bash
python -m app.dev.debug_server
# → http://localhost:8000/health
# → http://localhost:8000/docs  (Swagger UI)
```

> **Note:** The debug server is NOT part of the MCP specification — it is a convenience tool for development without an MCP client.

---

## Using with Claude Desktop

Add to your Claude Desktop config (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS):

```json
{
  "mcpServers": {
    "financial-data": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "env": {
        "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/financial_mcp"
      },
      "cwd": "/path/to/repo1-mcp-server"
    }
  }
}
```

Restart Claude Desktop, then try prompts like:

- *"Search for technology companies in the database"* → uses `search_companies`
- *"Compare Alpha Corp and Beta Industries on revenue"* → uses `compare_companies`
- *"Show me the stock price chart for ALPH over the last month"* → uses `get_stock_price_history`
- *"What are analysts saying about ALPH?"* → uses `get_analyst_ratings`
- *"Get the financial report for ALPH"* → uses `get_financial_report`
- *"Screen stocks with high revenue in the Technology sector"* → uses `screen_stocks`
- *"Show me an overview of the Technology sector"* → uses `get_sector_overview`

## Using with Cursor

Add to `.cursor/mcp.json` in your project:

```json
{
  "servers": {
    "financial-data": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "cwd": "/path/to/repo1-mcp-server"
    }
  }
}
```

## Testing with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python -m app.mcp.server
# Opens web UI at http://localhost:5173
```

---

## MCP Tools Reference (8 tools)

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

### 1. `search_companies`

Search by name or ticker with **cursor-based pagination**.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `query` | string | ✅ | Search term |
| `limit` | integer | | Max results (1-50, default 10) |
| `cursor` | string | | Opaque cursor from previous response |

**Response data:**

```json
{
  "companies": [{"ticker": "ALPH", "name": "Alpha Corp", "sector": "Technology", "market_cap": 500000000000.0}],
  "next_cursor": "eyJ0aWNrZXIiOiAiQUxQSCJ9",
  "has_more": true
}
```

### 2. `get_company_profile`

Full company profile by ticker.

| Parameter | Type | Required |
|---|---|---|
| `ticker` | string | ✅ |

### 3. `get_financial_report`

Per-year revenue, net_income, margins, and CAGR. Can also fetch specific quarter data.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `ticker` | string | ✅ | Company ticker |
| `years` | integer | | Years of history (default 3) |
| `year` | integer | | Specific fiscal year (optional) |
| `period` | integer | | Quarter number 1-4 (optional) |

### 4. `compare_companies`

Compare 2+ companies on a single metric.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `tickers` | string[] | ✅ | At least 2 tickers |
| `metric` | enum | ✅ | `revenue`, `net_income`, `market_cap`, `operating_margin`, `net_margin` |
| `year` | integer | | Specific year (defaults to latest) |

### 5. `get_stock_price_history`

Daily OHLC prices with **cursor-based pagination**.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `ticker` | string | ✅ | Company ticker |
| `start_date` | string | ✅ | YYYY-MM-DD |
| `end_date` | string | ✅ | YYYY-MM-DD |
| `limit` | integer | | Max rows per page (1-500, default 100) |
| `cursor` | string | | Pagination cursor |

### 6. `get_analyst_ratings`

Analyst rating counts, average price target, and 5 most recent ratings.

| Parameter | Type | Required |
|---|---|---|
| `ticker` | string | ✅ |

### 7. `screen_stocks`

Screen stocks by sector, market cap range, minimum revenue, and max debt-to-equity.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `sector` | string | | Filter by sector |
| `min_market_cap` | number | | Minimum market cap in USD |
| `max_market_cap` | number | | Maximum market cap in USD |
| `min_revenue` | number | | Minimum revenue in USD |
| `max_debt_to_equity` | number | | Maximum debt-to-equity ratio |

### 8. `get_sector_overview`

Get aggregated statistics for a sector: average market cap, average PE ratio, and average revenue growth.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `sector` | string | ✅ | Sector name (e.g., Technology, Healthcare) |

---

## MCP Resources (1)

Resources expose reusable, read-only data that clients can query independently of tools.

| URI | Description |
|---|---|
| `financial://metrics` | Available comparison metrics with descriptions |

### Example: List resources request

```json
{"jsonrpc": "2.0", "id": 1, "method": "resources/list"}
```

### Example: Read resource

```json
{"jsonrpc": "2.0", "id": 2, "method": "resources/read", "params": {"uri": "financial://sectors"}}
```

---

## MCP Prompts (2)

Prompt templates guide an LLM through multi-step analyses.

| Name | Description | Arguments |
|---|---|---|
| `sector_analysis` | Analyse all companies in a sector | `sector` (required) |
| `stock_momentum` | Find stocks with strong price momentum | `days` (optional, default 30) |

### Example: Get prompt

```json
{"jsonrpc": "2.0", "id": 3, "method": "prompts/get", "params": {"name": "sector_analysis", "arguments": {"sector": "Technology"}}}
```

---

## Security

### Input Validation

- All tool inputs are validated before DB queries.
- SQLAlchemy parameterised queries prevent SQL injection.
- Search queries are escaped via ILIKE patterns (no raw SQL).

### Rate Limiting

Every tool is rate-limited via a sliding-window algorithm:

| Tool | Limit |
|---|---|
| Most tools | 60 req / min |
| `compare_companies` | 30 req / min |

When exceeded, the response includes error code `RATE_LIMIT_EXCEEDED` with a retry-after hint.

### Why No Supabase RLS?

This MCP server runs locally as a single-user tool (stdio or SSE). Row Level Security is designed for multi-tenant web applications where different users should see different data.  Since the MCP client user has full access to all financial data by design, RLS adds complexity without benefit.  See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full ADR.

---

## Example MCP Protocol Messages

### Initialize

```json
{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "clientInfo": {"name": "test"}}}
```

### List Tools

```json
{"jsonrpc": "2.0", "id": 2, "method": "tools/list"}
```

### Call Tool

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "search_companies",
    "arguments": {"query": "Tech", "limit": 5}
  }
}
```

### Expected Response

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "{\"tool\":\"search_companies\",\"ok\":true,\"data\":{\"companies\":[...],\"next_cursor\":null,\"has_more\":false},\"meta\":{\"execution_ms\":8.3,\"row_count\":1}}"
      }
    ]
  }
}
```

---

## Tests

```bash
# Run all tests
pytest -v

# With coverage
pytest --cov=app tests/

# Individual test suites
pytest tests/test_tools_search.py -v
pytest tests/test_pagination.py -v
pytest tests/test_rate_limiting.py -v
pytest tests/test_performance.py -v
pytest tests/test_mcp_integration.py -v
```

---

## Performance

Benchmarks (local PostgreSQL 16, Apple M-series):

| Tool | Avg Latency |
|---|---|
| `search_companies` | ~8 ms |
| `get_company_profile` | ~5 ms |
| `get_financial_report` (3 years) | ~12 ms |
| `get_stock_price_history` (1 year, ~250 rows) | ~15 ms |
| `get_analyst_ratings` | ~6 ms |
| `compare_companies` | ~10 ms |
| `screen_stocks` | ~20 ms |
| `get_sector_overview` | ~15 ms |

Run benchmarks:

```bash
python -m scripts.benchmark
```

---

## Formatting

```bash
ruff check app/ tests/ scripts/
black --check app/ tests/ scripts/
```

---

## Project Documentation

- [Architecture Decision Records](docs/ARCHITECTURE.md) – explains RLS, pagination, lazy loading, and rate limiting design choices.
- [Database Schema](docs/SCHEMA.md) – complete database schema documentation with ERD diagram.

---

## License

MIT
