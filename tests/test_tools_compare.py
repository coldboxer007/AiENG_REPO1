"""Tests for compare_companies tool (via the handler directly)."""

from __future__ import annotations

import pytest

from app.services.company_service import get_company_by_ticker
from app.services.financial_service import get_financial_summary


@pytest.mark.asyncio
async def test_compare_both_exist(seeded_session):
    """Both tickers should resolve."""
    p_a = await get_company_by_ticker(seeded_session, "ALPH")
    p_b = await get_company_by_ticker(seeded_session, "BETA")
    assert p_a is not None
    assert p_b is not None
    # market_cap comparison
    assert p_a.market_cap > p_b.market_cap  # 500B > 120B


@pytest.mark.asyncio
async def test_compare_missing_ticker(seeded_session):
    """One missing ticker should be detected."""
    p = await get_company_by_ticker(seeded_session, "XXXX")
    assert p is None
