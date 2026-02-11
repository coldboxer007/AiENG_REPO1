"""Tests for get_stock_price_history tool."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.stock_service import get_stock_price_history


@pytest.mark.asyncio
async def test_stock_history_found(seeded_session):
    """Should return price rows for ALPH within the seeded date range."""
    data = await get_stock_price_history(
        seeded_session, "ALPH", date(2024, 3, 1), date(2024, 3, 31)
    )
    assert data is not None
    assert data.ticker == "ALPH"
    assert len(data.prices) > 0
    # Each row should have a positive close
    for row in data.prices:
        assert row.close > 0


@pytest.mark.asyncio
async def test_stock_history_returns(seeded_session):
    """Total return and max drawdown should be computed."""
    data = await get_stock_price_history(
        seeded_session, "ALPH", date(2024, 3, 1), date(2024, 3, 31)
    )
    assert data is not None
    if len(data.prices) >= 2:
        assert data.total_return_pct is not None
        assert data.max_drawdown_pct is not None
        assert data.max_drawdown_pct <= 0  # drawdown is always negative or zero


@pytest.mark.asyncio
async def test_stock_history_not_found(seeded_session):
    """Unknown ticker returns None."""
    data = await get_stock_price_history(
        seeded_session, "ZZZZ", date(2024, 1, 1), date(2024, 12, 31)
    )
    assert data is None
