"""MCP tool handlers – the bridge between MCP protocol and service layer."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session_factory
from app.middleware.rate_limit import rate_limiter, TOOL_RATE_LIMITS
from app.models.company import Company
from app.models.financial import Financial
from app.schemas.common import ErrorDetail, Meta, ToolResponse
from app.services import company_service, financial_service, stock_service, analyst_service
from app.services.metrics import cagr

logger = logging.getLogger("mcp.tools")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_float(v: Decimal | float | None) -> float | None:
    """Convert Decimal/float/None to float safely."""
    if v is None:
        return None
    return float(v)


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


def _error_response(
    tool: str, code: str, message: str, elapsed: float, hint: str | None = None
) -> dict:
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


async def _check_rate_limit(tool_name: str, t0: float) -> dict | None:
    """Check rate limit for a tool.  Returns an error dict if blocked, else None."""
    limits = TOOL_RATE_LIMITS.get(tool_name, {})
    allowed, error_msg = await rate_limiter.check_rate_limit(
        tool_name,
        max_requests=limits.get("max_requests"),
        window_seconds=limits.get("window_seconds"),
    )
    if not allowed:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            tool_name,
            "RATE_LIMIT_EXCEEDED",
            error_msg or "Rate limit exceeded",
            elapsed,
            hint="Wait before retrying. Standard limit: 60 requests/minute.",
        )
    return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


async def handle_search_companies(arguments: dict) -> dict:
    """Search companies by name or ticker substring with cursor pagination.

    Args:
        arguments: {"query": str, "limit": int (default 10), "cursor": str | None}
    """
    t0 = time.perf_counter()

    # Rate limit check
    rate_error = await _check_rate_limit("search_companies", t0)
    if rate_error:
        return rate_error

    query = arguments.get("query", "")
    limit = int(arguments.get("limit", 10))
    cursor = arguments.get("cursor")

    if not query or not query.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "search_companies", "INVALID_INPUT", "query must be a non-empty string", elapsed
        )

    async with async_session_factory() as session:
        results, next_cursor = await company_service.search_companies(session, query, limit, cursor)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    logger.info("search_companies query=%s results=%d ms=%.1f", query, len(results), elapsed)
    return _ok(
        "search_companies",
        {
            "companies": [r.model_dump() for r in results],
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None,
        },
        elapsed,
        row_count=len(results),
    )


async def handle_get_company_profile(arguments: dict) -> dict:
    """Return full company profile for a ticker.

    Args:
        arguments: {"ticker": str}
    """
    t0 = time.perf_counter()

    rate_error = await _check_rate_limit("get_company_profile", t0)
    if rate_error:
        return rate_error

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


async def handle_get_financial_report(arguments: dict) -> dict:
    """Return financial report for a ticker.

    If year and period (quarter) are provided, return that specific report.
    Otherwise return the list of recent reports.

    Args:
        arguments: {"ticker": str, "years": int (default 3), "year": int (optional),
                     "period": int (optional, quarter 1-4)}
    """
    t0 = time.perf_counter()

    rate_error = await _check_rate_limit("get_financial_report", t0)
    if rate_error:
        return rate_error

    ticker = arguments.get("ticker", "")
    years = int(arguments.get("years", 3))
    specific_year = arguments.get("year")
    specific_period = arguments.get("period")

    if not ticker or not ticker.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_financial_report", "INVALID_INPUT", "ticker is required", elapsed
        )

    # If specific year+period requested, return that single report
    if specific_year is not None and specific_period is not None:
        async with async_session_factory() as session:
            comp_stmt = select(Company.id).where(func.upper(Company.ticker) == ticker.upper())
            comp_result = await session.execute(comp_stmt)
            company_id = comp_result.scalar_one_or_none()
            if company_id is None:
                elapsed = round((time.perf_counter() - t0) * 1000, 2)
                return _ticker_not_found("get_financial_report", ticker, elapsed)

            stmt = select(Financial).where(
                Financial.company_id == company_id,
                Financial.period_year == int(specific_year),
                Financial.period_quarter == int(specific_period),
            )
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()

        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        if row is None:
            return _error_response(
                "get_financial_report",
                "NOT_FOUND",
                f"No report for {ticker} year={specific_year} Q{specific_period}",
                elapsed,
            )
        report = {
            "period_year": row.period_year,
            "period_quarter": row.period_quarter,
            "revenue": _safe_float(row.revenue),
            "gross_profit": _safe_float(row.gross_profit),
            "operating_income": _safe_float(row.operating_income),
            "net_income": _safe_float(row.net_income),
            "eps": _safe_float(row.eps),
            "assets": _safe_float(row.assets),
            "liabilities": _safe_float(row.liabilities),
            "operating_margin": _safe_float(row.operating_margin),
            "net_margin": _safe_float(row.net_margin),
            "gross_margin": _safe_float(row.gross_margin),
            "debt_to_equity": _safe_float(row.debt_to_equity),
            "free_cash_flow": _safe_float(row.free_cash_flow),
            "report_date": str(row.report_date),
        }
        logger.info(
            "get_financial_report ticker=%s year=%s Q%s ms=%.1f",
            ticker,
            specific_year,
            specific_period,
            elapsed,
        )
        return _ok("get_financial_report", report, elapsed, row_count=1)

    # Otherwise fall back to summary (list of recent reports)
    async with async_session_factory() as session:
        summary = await financial_service.get_financial_summary(session, ticker, years)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    if summary is None:
        return _ticker_not_found("get_financial_report", ticker, elapsed)

    logger.info("get_financial_report ticker=%s years=%d ms=%.1f", ticker, years, elapsed)
    return _ok(
        "get_financial_report",
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

    rate_error = await _check_rate_limit("compare_companies", t0)
    if rate_error:
        return rate_error

    tickers = arguments.get("tickers", [])
    metric = arguments.get("metric", "")
    year = arguments.get("year")

    if not tickers or len(tickers) < 2:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "compare_companies",
            "INVALID_INPUT",
            "Provide at least 2 tickers",
            elapsed,
        )
    if metric not in VALID_METRICS:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "compare_companies",
            "INVALID_INPUT",
            f"metric must be one of {sorted(VALID_METRICS)}",
            elapsed,
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
                    row = (
                        summary.data[-1]
                        if year is None
                        else next(
                            (d for d in summary.data if d.year == int(year)), summary.data[-1]
                        )
                    )
                    value = getattr(row, metric, None)
                else:
                    value = None

            comparison.append(
                {
                    "ticker": tick.upper(),
                    "metric": metric,
                    "value": value,
                }
            )

    # Determine winner
    valid_entries = [e for e in comparison if e["value"] is not None]
    winner = max(valid_entries, key=lambda e: e["value"])["ticker"] if valid_entries else None

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    explanation = (
        f"{winner} leads on {metric} among {[e['ticker'] for e in comparison]}."
        if winner
        else "Insufficient data to determine winner."
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
    """Return daily OHLC, returns, max drawdown for a date range with cursor pagination.

    Args:
        arguments: {"ticker": str, "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD",
                     "limit": int (default 100), "cursor": str | None}
    """
    t0 = time.perf_counter()

    rate_error = await _check_rate_limit("get_stock_price_history", t0)
    if rate_error:
        return rate_error

    ticker = arguments.get("ticker", "")
    start_str = arguments.get("start_date", "")
    end_str = arguments.get("end_date", "")
    limit = int(arguments.get("limit", 100))
    cursor = arguments.get("cursor")

    if not ticker or not start_str or not end_str:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_stock_price_history",
            "INVALID_INPUT",
            "ticker, start_date, and end_date are all required",
            elapsed,
        )

    try:
        start_date = date.fromisoformat(start_str)
        end_date = date.fromisoformat(end_str)
    except ValueError:
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_stock_price_history",
            "INVALID_INPUT",
            "Dates must be YYYY-MM-DD",
            elapsed,
        )

    async with async_session_factory() as session:
        data = await stock_service.get_stock_price_history(
            session, ticker, start_date, end_date, limit, cursor
        )

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    if data is None:
        return _ticker_not_found("get_stock_price_history", ticker, elapsed)

    logger.info(
        "get_stock_price_history ticker=%s range=%s→%s rows=%d ms=%.1f",
        ticker,
        start_date,
        end_date,
        len(data.prices),
        elapsed,
    )
    return _ok(
        "get_stock_price_history",
        data.model_dump(mode="json"),
        elapsed,
        row_count=len(data.prices),
    )


async def handle_get_analyst_ratings(arguments: dict) -> dict:
    """Return analyst ratings for a ticker, including previous_rating field.

    Args:
        arguments: {"ticker": str}
    """
    t0 = time.perf_counter()

    rate_error = await _check_rate_limit("get_analyst_ratings", t0)
    if rate_error:
        return rate_error

    ticker = arguments.get("ticker", "")

    if not ticker or not ticker.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_analyst_ratings",
            "INVALID_INPUT",
            "ticker is required",
            elapsed,
        )

    async with async_session_factory() as session:
        data = await analyst_service.get_analyst_consensus(session, ticker)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    if data is None:
        return _ticker_not_found("get_analyst_ratings", ticker, elapsed)

    logger.info("get_analyst_ratings ticker=%s ms=%.1f", ticker, elapsed)
    return _ok(
        "get_analyst_ratings",
        data.model_dump(mode="json"),
        elapsed,
        row_count=data.total_ratings,
    )


# ---------------------------------------------------------------------------
# New tools per spec
# ---------------------------------------------------------------------------


async def handle_screen_stocks(arguments: dict) -> dict:
    """Screen stocks by sector, market cap, revenue, and debt-to-equity filters.

    Args:
        arguments: {
            "sector": str (optional),
            "min_market_cap": float (optional),
            "max_market_cap": float (optional),
            "min_revenue": float (optional),
            "max_debt_to_equity": float (optional),
        }
    """
    t0 = time.perf_counter()

    rate_error = await _check_rate_limit("screen_stocks", t0)
    if rate_error:
        return rate_error

    sector = arguments.get("sector")
    min_market_cap = arguments.get("min_market_cap")
    max_market_cap = arguments.get("max_market_cap")
    min_revenue = arguments.get("min_revenue")
    max_debt_to_equity = arguments.get("max_debt_to_equity")

    async with async_session_factory() as session:
        # Subquery: latest financial per company (max period_year, max period_quarter)
        latest_fin_sq = (
            select(
                Financial.company_id,
                func.max(Financial.period_year * 10 + Financial.period_quarter).label("max_key"),
            )
            .group_by(Financial.company_id)
            .subquery()
        )

        stmt = (
            select(
                Company.ticker,
                Company.name,
                Company.sector,
                Company.market_cap,
                Financial.revenue,
                Financial.net_income,
                Financial.debt_to_equity,
                Financial.gross_margin,
                Financial.operating_margin,
            )
            .join(Financial, Financial.company_id == Company.id)
            .join(
                latest_fin_sq,
                (Financial.company_id == latest_fin_sq.c.company_id)
                & (
                    (Financial.period_year * 10 + Financial.period_quarter)
                    == latest_fin_sq.c.max_key
                ),
            )
        )

        # Apply filters
        if sector:
            stmt = stmt.where(func.upper(Company.sector) == sector.upper())
        if min_market_cap is not None:
            stmt = stmt.where(Company.market_cap >= float(min_market_cap))
        if max_market_cap is not None:
            stmt = stmt.where(Company.market_cap <= float(max_market_cap))
        if min_revenue is not None:
            stmt = stmt.where(Financial.revenue >= float(min_revenue))
        if max_debt_to_equity is not None:
            stmt = stmt.where(Financial.debt_to_equity <= float(max_debt_to_equity))

        stmt = stmt.order_by(Company.market_cap.desc())
        result = await session.execute(stmt)
        rows = result.all()

    matches = [
        {
            "ticker": r.ticker,
            "name": r.name,
            "sector": r.sector,
            "market_cap": _safe_float(r.market_cap),
            "revenue": _safe_float(r.revenue),
            "net_income": _safe_float(r.net_income),
            "debt_to_equity": _safe_float(r.debt_to_equity),
            "gross_margin": _safe_float(r.gross_margin),
            "operating_margin": _safe_float(r.operating_margin),
        }
        for r in rows
    ]

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    logger.info("screen_stocks filters=%s results=%d ms=%.1f", arguments, len(matches), elapsed)
    return _ok(
        "screen_stocks",
        {"companies": matches, "total": len(matches)},
        elapsed,
        row_count=len(matches),
    )


async def handle_get_sector_overview(arguments: dict) -> dict:
    """Return aggregated stats for a specific sector.

    Args:
        arguments: {"sector": str}

    Returns avg market cap, avg PE ratio (market_cap / net_income), avg revenue growth.
    """
    t0 = time.perf_counter()

    rate_error = await _check_rate_limit("get_sector_overview", t0)
    if rate_error:
        return rate_error

    sector = arguments.get("sector", "")
    if not sector or not sector.strip():
        elapsed = round((time.perf_counter() - t0) * 1000, 2)
        return _error_response(
            "get_sector_overview",
            "INVALID_INPUT",
            "sector is required",
            elapsed,
        )

    async with async_session_factory() as session:
        # Company count & avg market cap
        comp_stmt = select(
            func.count().label("company_count"),
            func.avg(Company.market_cap).label("avg_market_cap"),
        ).where(func.upper(Company.sector) == sector.upper())
        comp_result = await session.execute(comp_stmt)
        comp_row = comp_result.one()

        if comp_row.company_count == 0:
            elapsed = round((time.perf_counter() - t0) * 1000, 2)
            return _error_response(
                "get_sector_overview",
                "NOT_FOUND",
                f"No companies found in sector '{sector}'",
                elapsed,
            )

        # Latest year financials for companies in this sector
        # Get company IDs in sector
        sector_ids_stmt = select(Company.id).where(func.upper(Company.sector) == sector.upper())

        # Aggregate latest quarter financials per company to estimate annual values
        # Use latest year available
        latest_year_stmt = select(func.max(Financial.period_year)).where(
            Financial.company_id.in_(sector_ids_stmt)
        )
        latest_year_result = await session.execute(latest_year_stmt)
        latest_year = latest_year_result.scalar()

        avg_pe_ratio: float | None = None
        avg_revenue_growth: float | None = None

        if latest_year:
            # Avg revenue and net_income for latest year (sum of quarters per company)
            fin_stmt = (
                select(
                    Financial.company_id,
                    func.sum(Financial.revenue).label("total_revenue"),
                    func.sum(Financial.net_income).label("total_net_income"),
                )
                .where(
                    Financial.company_id.in_(sector_ids_stmt),
                    Financial.period_year == latest_year,
                )
                .group_by(Financial.company_id)
            )
            fin_result = await session.execute(fin_stmt)
            fin_rows = fin_result.all()

            # Avg PE ratio: market_cap / net_income across sector companies
            pe_values: list[float] = []
            for frow in fin_rows:
                # Look up market cap
                mc_stmt = select(Company.market_cap).where(Company.id == frow.company_id)
                mc_result = await session.execute(mc_stmt)
                mc = mc_result.scalar()
                ni = float(frow.total_net_income) if frow.total_net_income else 0
                if mc and ni and ni > 0:
                    pe_values.append(float(mc) / ni)
            if pe_values:
                avg_pe_ratio = round(sum(pe_values) / len(pe_values), 2)

            # Revenue growth: compare latest_year vs latest_year - 1
            prev_year = latest_year - 1
            prev_fin_stmt = (
                select(
                    Financial.company_id,
                    func.sum(Financial.revenue).label("total_revenue"),
                )
                .where(
                    Financial.company_id.in_(sector_ids_stmt),
                    Financial.period_year == prev_year,
                )
                .group_by(Financial.company_id)
            )
            prev_result = await session.execute(prev_fin_stmt)
            prev_map = {
                r.company_id: float(r.total_revenue) for r in prev_result.all() if r.total_revenue
            }

            growth_values: list[float] = []
            for frow in fin_rows:
                curr_rev = float(frow.total_revenue) if frow.total_revenue else 0
                prev_rev = prev_map.get(frow.company_id, 0)
                if prev_rev > 0 and curr_rev > 0:
                    growth_values.append((curr_rev - prev_rev) / prev_rev)
            if growth_values:
                avg_revenue_growth = round(sum(growth_values) / len(growth_values), 4)

    elapsed = round((time.perf_counter() - t0) * 1000, 2)
    overview = {
        "sector": sector,
        "company_count": comp_row.company_count,
        "avg_market_cap": (
            round(float(comp_row.avg_market_cap), 2) if comp_row.avg_market_cap else None
        ),
        "avg_pe_ratio": avg_pe_ratio,
        "avg_revenue_growth": avg_revenue_growth,
    }

    logger.info("get_sector_overview sector=%s ms=%.1f", sector, elapsed)
    return _ok("get_sector_overview", overview, elapsed, row_count=comp_row.company_count)
