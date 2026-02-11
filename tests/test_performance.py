"""Performance, edge-case, and security tests."""

from __future__ import annotations

from datetime import date

import pytest

from sqlalchemy import select

from app.models.company import Company
from app.services.company_service import search_companies
from app.services.stock_service import get_stock_price_history


@pytest.mark.asyncio
async def test_sql_injection_protection(seeded_session):
    """Service layer should be safe from SQL injection via parameterised queries."""
    malicious_query = "'; DROP TABLE companies; --"
    results, _ = await search_companies(seeded_session, malicious_query, limit=10)

    # Should return 0 results, not error
    assert results == []

    # Table should still exist and contain data
    stmt = select(Company).limit(1)
    result = await seeded_session.execute(stmt)
    assert result.scalar_one_or_none() is not None


@pytest.mark.asyncio
async def test_unicode_search(seeded_session):
    """Searching with Unicode characters should not crash."""
    results, _ = await search_companies(seeded_session, "日本語テスト", limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_very_long_query(seeded_session):
    """Extremely long search queries should not blow up."""
    results, _ = await search_companies(seeded_session, "A" * 5000, limit=10)
    assert results == []


@pytest.mark.asyncio
async def test_negative_limit_clamped(seeded_session):
    """Limit should be silently clamped to at most 50."""
    results, _ = await search_companies(seeded_session, "", limit=9999)
    # Should not exceed 50 (the hard cap) even though we asked for 9999
    assert len(results) <= 50


@pytest.mark.asyncio
async def test_stock_history_empty_range(seeded_session):
    """Date range with no data should return empty prices, not None."""
    data = await get_stock_price_history(
        seeded_session, "ALPH", date(2020, 1, 1), date(2020, 1, 31)
    )
    assert data is not None
    assert len(data.prices) == 0


@pytest.mark.asyncio
async def test_stock_history_single_day(seeded_session):
    """Query for a single trading day should work."""
    data = await get_stock_price_history(
        seeded_session, "ALPH", date(2024, 3, 4), date(2024, 3, 4)
    )
    assert data is not None
    assert len(data.prices) <= 1
