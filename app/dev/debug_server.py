"""FastAPI debug server – HTTP endpoints for manual tool testing.

This is NOT part of the MCP specification.  It is a convenience tool
for local development without an MCP client (Claude Desktop, Cursor).

Run with:
    python -m app.dev.debug_server
    # → http://localhost:8000/health
    # → http://localhost:8000/docs  (Swagger UI)
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

from app.config import settings
from app.mcp.tools import (
    handle_compare_companies,
    handle_get_analyst_consensus,
    handle_get_company_profile,
    handle_get_financial_summary,
    handle_get_stock_price_history,
    handle_search_companies,
)

logger = logging.getLogger("app.dev.debug_server")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Debug server starting (env=%s)", settings.app_env)
    yield
    logger.info("Debug server shutting down")


app = FastAPI(
    title="Financial Data MCP Server – Debug HTTP",
    description="Developer-only HTTP wrapper around the MCP tool handlers.",
    version=settings.mcp_server_version,
    lifespan=lifespan,
)


# ── Health ────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health():
    return {"status": "ok", "version": settings.mcp_server_version}


# ── Debug routes (call tools via HTTP for manual testing) ─────────────────────


@app.get("/debug/search_companies")
async def debug_search_companies(
    query: str = Query(...),
    limit: int = Query(10),
    cursor: str | None = Query(None),
):
    result = await handle_search_companies({"query": query, "limit": limit, "cursor": cursor})
    return JSONResponse(content=result)


@app.get("/debug/get_company_profile")
async def debug_get_company_profile(ticker: str = Query(...)):
    result = await handle_get_company_profile({"ticker": ticker})
    return JSONResponse(content=result)


@app.get("/debug/get_financial_summary")
async def debug_get_financial_summary(ticker: str = Query(...), years: int = Query(3)):
    result = await handle_get_financial_summary({"ticker": ticker, "years": years})
    return JSONResponse(content=result)


@app.get("/debug/compare_companies")
async def debug_compare_companies(
    tickers: str = Query(..., description="Comma-separated tickers"),
    metric: str = Query(...),
    year: int | None = Query(None),
):
    ticker_list = [t.strip() for t in tickers.split(",")]
    args: dict = {"tickers": ticker_list, "metric": metric}
    if year is not None:
        args["year"] = year
    result = await handle_compare_companies(args)
    return JSONResponse(content=result)


@app.get("/debug/get_stock_price_history")
async def debug_get_stock_price_history(
    ticker: str = Query(...),
    start_date: str = Query(...),
    end_date: str = Query(...),
    limit: int = Query(100),
    cursor: str | None = Query(None),
):
    result = await handle_get_stock_price_history(
        {"ticker": ticker, "start_date": start_date, "end_date": end_date,
         "limit": limit, "cursor": cursor}
    )
    return JSONResponse(content=result)


@app.get("/debug/get_analyst_consensus")
async def debug_get_analyst_consensus(ticker: str = Query(...)):
    result = await handle_get_analyst_consensus({"ticker": ticker})
    return JSONResponse(content=result)


# ── Run via uvicorn ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    uvicorn.run(
        "app.dev.debug_server:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=(settings.app_env == "development"),
    )
