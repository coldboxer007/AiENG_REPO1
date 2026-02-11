"""Tests for search_companies tool."""

from __future__ import annotations

import pytest

from app.services.company_service import search_companies


@pytest.mark.asyncio
async def test_search_by_ticker(seeded_session):
    """Search by exact ticker should return the matching company."""
    results, _ = await search_companies(seeded_session, "ALPH", limit=10)
    assert len(results) >= 1
    assert results[0].ticker == "ALPH"


@pytest.mark.asyncio
async def test_search_by_name_substring(seeded_session):
    """Search by name substring should return matches."""
    results, _ = await search_companies(seeded_session, "Alpha", limit=10)
    assert len(results) >= 1
    assert any(r.name == "Alpha Corp" for r in results)


@pytest.mark.asyncio
async def test_search_empty_query(seeded_session):
    """Empty-ish query should still work (returns all matching %)."""
    results, _ = await search_companies(seeded_session, "ZZZZ_NO_MATCH", limit=10)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_search_limit(seeded_session):
    """Limit parameter should cap results."""
    results, _ = await search_companies(seeded_session, "", limit=2)
    assert len(results) <= 2
