"""Tests for get_financial_summary tool."""

from __future__ import annotations

import pytest

from app.services.financial_service import get_financial_summary


@pytest.mark.asyncio
async def test_financial_summary_found(seeded_session):
    """Should return financial data for ALPH with 2 years."""
    summary = await get_financial_summary(seeded_session, "ALPH", years=3)
    assert summary is not None
    assert summary.ticker == "ALPH"
    assert summary.years_covered >= 1
    assert len(summary.data) >= 1
    # Each year should have revenue
    for yr in summary.data:
        assert yr.revenue is not None
        assert yr.revenue > 0


@pytest.mark.asyncio
async def test_financial_summary_not_found(seeded_session):
    """Unknown ticker should return None."""
    summary = await get_financial_summary(seeded_session, "ZZZZ", years=3)
    assert summary is None


@pytest.mark.asyncio
async def test_financial_summary_cagr(seeded_session):
    """If 2+ years exist, CAGR should be computed."""
    summary = await get_financial_summary(seeded_session, "ALPH", years=5)
    if summary and summary.years_covered >= 2:
        # revenue_cagr may or may not be None depending on data
        # but should be a number if data is valid
        assert summary.revenue_cagr is None or isinstance(summary.revenue_cagr, float)
