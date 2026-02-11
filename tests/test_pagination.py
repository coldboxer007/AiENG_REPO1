"""Cursor-based pagination tests."""

from __future__ import annotations

from datetime import date

import pytest

from app.services.company_service import search_companies
from app.services.stock_service import get_stock_price_history


@pytest.mark.asyncio
async def test_search_pagination_first_page(seeded_session):
    """First page should return results and a cursor when more exist."""
    results, cursor = await search_companies(seeded_session, "", limit=1)
    assert len(results) == 1
    # We seeded 3 companies, so there should be more
    assert cursor is not None


@pytest.mark.asyncio
async def test_search_pagination_second_page(seeded_session):
    """Second page via cursor should return different results."""
    results1, cursor1 = await search_companies(seeded_session, "", limit=1)
    assert cursor1 is not None

    results2, cursor2 = await search_companies(seeded_session, "", limit=1, cursor=cursor1)
    assert len(results2) == 1
    # No overlap
    assert results1[0].ticker != results2[0].ticker


@pytest.mark.asyncio
async def test_search_pagination_exhaustion(seeded_session):
    """Paginating through everything should eventually return cursor=None."""
    all_tickers: set[str] = set()
    cursor = None
    for _ in range(10):  # safety bound
        results, cursor = await search_companies(seeded_session, "", limit=2, cursor=cursor)
        for r in results:
            all_tickers.add(r.ticker)
        if cursor is None:
            break
    # We seeded 3 companies
    assert len(all_tickers) == 3
    assert cursor is None  # finished


@pytest.mark.asyncio
async def test_search_pagination_invalid_cursor(seeded_session):
    """An invalid cursor should be silently ignored (start from beginning)."""
    results, _ = await search_companies(seeded_session, "", limit=10, cursor="not_valid_base64!!!")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_stock_pagination_first_page(seeded_session):
    """Stock price history should support pagination."""
    data = await get_stock_price_history(
        seeded_session, "ALPH", date(2024, 3, 1), date(2024, 3, 31), limit=5
    )
    assert data is not None
    assert len(data.prices) <= 5


@pytest.mark.asyncio
async def test_stock_pagination_traverse(seeded_session):
    """Traversing via cursor should return all stock rows without overlap."""
    all_dates: list[date] = []
    cursor = None
    for _ in range(20):
        data = await get_stock_price_history(
            seeded_session,
            "ALPH",
            date(2024, 3, 1),
            date(2024, 3, 31),
            limit=3,
            cursor=cursor,
        )
        assert data is not None
        for p in data.prices:
            all_dates.append(p.date)
        cursor = data.next_cursor
        if cursor is None:
            break
    # No duplicate dates
    assert len(all_dates) == len(set(all_dates))
