"""MCP tool handlers – the bridge between MCP protocol and service layer."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.schemas.common import ErrorDetail, Meta, ToolResponse
from app.services import company_service, financial_service, stock_service, analyst_service
from app.services.metrics import cagr

logger = logging.getLogger("mcp.tools")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ticker_not_found(tool: str, ticker: str, elapsed: float) -> dict:
    return ToolResponse(
        tool=tool,
        ok=False,
        data=None,
        error=ErrorDetail(
            error_code="TICKER_NOT_FOUND",
            message=f"No company found for ticker '{ticker}'",
            hint="Check spelling or use search_companies to find valid tickers.",
        ),
        meta=Meta(execution_ms=elapsed, row_count=0),
    ).model_dump()


def _error_response(tool: str, code: str, message: str, elapsed: float, hint: str | None = None) -> dict:
    return ToolResponse(
        tool=tool,
        ok=False,
        data=None,
        error=ErrorDetail(error_code=code, message=message, hint=hint),
        meta=Meta(execution_ms=elapsed, row_count=0),
    ).model_dump()


def _ok(tool: str, data, elapsed: float, row_count: int | None = None) -> dict:
    return ToolResponse(
        tool=tool,
        ok=True,
        data=data,
        error=None,
        meta=Meta(execution_ms=elapsed, row_count=row_count),
    ).model_dump()


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def handle_search_companies(arguments: dict) -> dict:
    """Search companies by name or ticker substring.

    Args:
        arguments: {"query": str, "limit": int (default 10)}
    """
    t0 = time.perf_counter()
    query = arguments.get("query", "")
    limit = int(arguments.get("limit", 10))

    if not query or not query.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "search_companies", "INVALID_INPUT", "query must be a non-empty string", elapsed
        )

    async with async_session_factory() as session:
        results = await company_service.search_companies(session, query, limit)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    logger.info("search_companies query=%s results=%d ms=%.1f", query, len(results), elapsed)
    return _ok(
        "search_companies",
        [r.model_dump() for r in results],
        elapsed,
        row_count=len(results),
    )


async def handle_get_company_profile(arguments: dict) -> dict:
    """Return full company profile for a ticker.

    Args:
        arguments: {"ticker": str}
    """
    t0 = time.perf_counter()
    ticker = arguments.get("ticker", "")

    if not ticker or not ticker.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_company_profile", "INVALID_INPUT", "ticker is required", elapsed
        )

    async with async_session_factory() as session:
        profile = await company_service.get_company_by_ticker(session, ticker)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    if profile is None:
        return _ticker_not_found("get_company_profile", ticker, elapsed)

    logger.info("get_company_profile ticker=%s ms=%.1f", ticker, elapsed)
    return _ok("get_company_profile", profile.model_dump(mode="json"), elapsed, row_count=1)


async def handle_get_financial_summary(arguments: dict) -> dict:
    """Return per-year revenue, margins, CAGR for a ticker.

    Args:
        arguments: {"ticker": str, "years": int (default 3)}
    """
    t0 = time.perf_counter()
    ticker = arguments.get("ticker", "")
    years = int(arguments.get("years", 3))

    if not ticker or not ticker.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_financial_summary", "INVALID_INPUT", "ticker is required", elapsed
        )

    async with async_session_factory() as session:
        summary = await financial_service.get_financial_summary(session, ticker, years)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    if summary is None:
        return _ticker_not_found("get_financial_summary", ticker, elapsed)

    logger.info("get_financial_summary ticker=%s years=%d ms=%.1f", ticker, years, elapsed)
    return _ok(
        "get_financial_summary",
        summary.model_dump(),
        elapsed,
        row_count=summary.years_covered,
    )


async def handle_compare_companies(arguments: dict) -> dict:
    """Compare multiple tickers on a chosen metric.

    Args:
        arguments: {
            "tickers": [str],
            "metric": one of revenue|net_income|market_cap|operating_margin|net_margin,
            "year": int (optional, defaults to latest)
        }
    """
    VALID_METRICS = {"revenue", "net_income", "market_cap", "operating_margin", "net_margin"}
    t0 = time.perf_counter()
    tickers = arguments.get("tickers", [])
    metric = arguments.get("metric", "")
    year = arguments.get("year")

    if not tickers or len(tickers) < 2:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "compare_companies", "INVALID_INPUT",
            "Provide at least 2 tickers", elapsed,
        )
    if metric not in VALID_METRICS:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "compare_companies", "INVALID_INPUT",
            f"metric must be one of {sorted(VALID_METRICS)}", elapsed,
        )

    comparison: list[dict] = []
    async with async_session_factory() as session:
        for tick in tickers:
            profile = await company_service.get_company_by_ticker(session, tick)
            if profile is None:
                elapsed = round((time.perf_counter() - t0) * 1000, 2)
                return _ticker_not_found("compare_companies", tick, elapsed)

            if metric == "market_cap":
                value = profile.market_cap
            else:
                summary = await financial_service.get_financial_summary(session, tick, years=1)
                if summary and summary.data:
                    row = summary.data[-1] if year is None else next(
                        (d for d in summary.data if d.year == int(year)), summary.data[-1]
                    )
                    value = getattr(row, metric, None)
                else:
                    value = None

            comparison.append({
                "ticker": tick.upper(),
                "metric": metric,
                "value": value,
            })

    # Determine winner
    valid_entries = [e for e in comparison if e["value"] is not None]
    winner = max(valid_entries, key=lambda e: e["value"])["ticker"] if valid_entries else None

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    explanation = (
        f"{winner} leads on {metric} among {[e['ticker'] for e in comparison]}."
        if winner else "Insufficient data to determine winner."
    )

    logger.info("compare_companies tickers=%s metric=%s ms=%.1f", tickers, metric, elapsed)
    return _ok(
        "compare_companies",
        {
            "comparison": comparison,
            "winner": winner,
            "explanation": explanation,
        },
        elapsed,
        row_count=len(comparison),
    )


async def handle_get_stock_price_history(arguments: dict) -> dict:
    """Return daily OHLC, returns, max drawdown for a date range.

    Args:
        arguments: {"ticker": str, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
    """
    t0 = time.perf_counter()
    ticker = arguments.get("ticker", "")
    start_str = arguments.get("start_date", "")
    end_str = arguments.get("end_date", "")

    if not ticker or not start_str or not end_str:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_stock_price_history", "INVALID_INPUT",
            "ticker, start_date, and end_date are all required", elapsed,
        )

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_stock_price_history", "INVALID_INPUT",
            "Dates must be YYYY-MM-DD", elapsed,
        )

    async with async_session_factory() as session:
        data = await stock_service.get_stock_price_history(session, ticker, start_date, end_date)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    if data is None:
        return _ticker_not_found("get_stock_price_history", ticker, elapsed)

    logger.info(
        "get_stock_price_history ticker=%s range=%s→%s rows=%d ms=%.1f",
        ticker, start_date, end_date, len(data.prices), elapsed,
    )
    return _ok(
        "get_stock_price_history",
        data.model_dump(mode="json"),
        elapsed,
        row_count=len(data.prices),
    )


async def handle_get_analyst_consensus(arguments: dict) -> dict:
    """Return analyst consensus for a ticker.

    Args:
        arguments: {"ticker": str}
    """
    t0 = time.perf_counter()
    ticker = arguments.get("ticker", "")

    if not ticker or not ticker.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_analyst_consensus", "INVALID_INPUT", "ticker is required", elapsed,
        )

    async with async_session_factory() as session:
        data = await analyst_service.get_analyst_consensus(session, ticker)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    if data is None:
        return _ticker_not_found("get_analyst_consensus", ticker, elapsed)

    logger.info("get_analyst_consensus ticker=%s ms=%.1f", ticker, elapsed)
    return _ok(
        "get_analyst_consensus",
        data.model_dump(mode="json"),
        elapsed,
        row_count=data.total_ratings,
    )
