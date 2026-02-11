"""Tests for MCP tool handlers (the full handler path through tools.py).

These tests exercise the tool handler functions directly, which covers
input validation, rate limiting, session creation, and response
formatting layers that service-level tests do not.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.mcp.tools import (
    handle_search_companies,
    handle_get_company_profile,
    handle_get_financial_summary,
    handle_compare_companies,
    handle_get_stock_price_history,
    handle_get_analyst_consensus,
    _error_response,
    _ok,
    _ticker_not_found,
)


# ---------------------------------------------------------------------------
# Helper tests
# ---------------------------------------------------------------------------


def test_error_response_shape():
    """_error_response should produce a well-formed ToolResponse dict."""
    resp = _error_response("test_tool", "TEST_ERR", "Something broke", 1.23, hint="Try again")
    assert resp["tool"] == "test_tool"
    assert resp["ok"] is False
    assert resp["error"]["error_code"] == "TEST_ERR"
    assert resp["error"]["hint"] == "Try again"
    assert resp["meta"]["execution_ms"] == 1.23


def test_ok_response_shape():
    """_ok should produce a well-formed ToolResponse dict."""
    resp = _ok("test_tool", {"foo": "bar"}, 2.34, row_count=5)
    assert resp["ok"] is True
    assert resp["data"] == {"foo": "bar"}
    assert resp["meta"]["row_count"] == 5


def test_ticker_not_found_shape():
    """_ticker_not_found should produce a TICKER_NOT_FOUND error."""
    resp = _ticker_not_found("test_tool", "ZZZZ", 0.5)
    assert resp["ok"] is False
    assert resp["error"]["error_code"] == "TICKER_NOT_FOUND"
    assert "ZZZZ" in resp["error"]["message"]


# ---------------------------------------------------------------------------
# Input validation (these run without a database by catching early returns)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_companies_empty_query():
    """Empty query should fail with INVALID_INPUT."""
    result = await handle_search_companies({"query": ""})
    assert result["ok"] is False
    assert result["error"]["error_code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_search_companies_whitespace_query():
    """Whitespace-only query should fail."""
    result = await handle_search_companies({"query": "   "})
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_get_company_profile_empty_ticker():
    """Empty ticker should fail."""
    result = await handle_get_company_profile({"ticker": ""})
    assert result["ok"] is False
    assert result["error"]["error_code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_get_financial_summary_empty_ticker():
    """Empty ticker should fail."""
    result = await handle_get_financial_summary({"ticker": ""})
    assert result["ok"] is False


@pytest.mark.asyncio
async def test_compare_companies_too_few_tickers():
    """Need at least 2 tickers."""
    result = await handle_compare_companies({"tickers": ["ALPH"], "metric": "revenue"})
    assert result["ok"] is False
    assert "2 tickers" in result["error"]["message"]


@pytest.mark.asyncio
async def test_compare_companies_invalid_metric():
    """Invalid metric should fail."""
    result = await handle_compare_companies({"tickers": ["ALPH", "BETA"], "metric": "bogus"})
    assert result["ok"] is False
    assert "metric must be one of" in result["error"]["message"]


@pytest.mark.asyncio
async def test_stock_history_missing_fields():
    """Missing required fields should fail."""
    result = await handle_get_stock_price_history({"ticker": "ALPH"})
    assert result["ok"] is False
    assert result["error"]["error_code"] == "INVALID_INPUT"


@pytest.mark.asyncio
async def test_stock_history_bad_date_format():
    """Malformed dates should fail."""
    result = await handle_get_stock_price_history({
        "ticker": "ALPH",
        "start_date": "not-a-date",
        "end_date": "2024-01-01",
    })
    assert result["ok"] is False
    assert "YYYY-MM-DD" in result["error"]["message"]


@pytest.mark.asyncio
async def test_analyst_consensus_empty_ticker():
    """Empty ticker should fail."""
    result = await handle_get_analyst_consensus({"ticker": ""})
    assert result["ok"] is False


# ---------------------------------------------------------------------------
# Rate limiting integration in handlers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_handler_returns_rate_limit_error():
    """When rate limiter says no, the handler should return RATE_LIMIT_EXCEEDED."""
    with patch("app.mcp.tools.rate_limiter") as mock_rl:
        mock_rl.check_rate_limit = AsyncMock(return_value=(False, "Rate limit exceeded"))
        result = await handle_search_companies({"query": "Tech"})
        assert result["ok"] is False
        assert result["error"]["error_code"] == "RATE_LIMIT_EXCEEDED"
