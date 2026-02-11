"""Tests for get_analyst_consensus tool."""

from __future__ import annotations

import pytest

from app.services.analyst_service import get_analyst_consensus


@pytest.mark.asyncio
async def test_analyst_consensus_found(seeded_session):
    """Should return consensus data for ALPH."""
    data = await get_analyst_consensus(seeded_session, "ALPH")
    assert data is not None
    assert data.ticker == "ALPH"
    assert data.total_ratings == 5
    assert data.average_price_target is not None
    assert data.average_price_target > 0
    assert len(data.recent_ratings) <= 5


@pytest.mark.asyncio
async def test_analyst_consensus_rating_counts(seeded_session):
    """Rating counts should sum to total."""
    data = await get_analyst_consensus(seeded_session, "ALPH")
    assert data is not None
    total_from_counts = sum(rc.count for rc in data.rating_counts)
    assert total_from_counts == data.total_ratings


@pytest.mark.asyncio
async def test_analyst_consensus_not_found(seeded_session):
    """Unknown ticker returns None."""
    data = await get_analyst_consensus(seeded_session, "ZZZZ")
    assert data is None
