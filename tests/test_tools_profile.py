"""Tests for get_company_profile tool."""

from __future__ import annotations

import pytest

from app.services.company_service import get_company_by_ticker


@pytest.mark.asyncio
async def test_profile_found(seeded_session):
    """Known ticker should return full profile."""
    profile = await get_company_by_ticker(seeded_session, "ALPH")
    assert profile is not None
    assert profile.ticker == "ALPH"
    assert profile.name == "Alpha Corp"
    assert profile.sector == "Technology"
    assert profile.employees == 50_000


@pytest.mark.asyncio
async def test_profile_case_insensitive(seeded_session):
    """Ticker lookup should be case-insensitive."""
    profile = await get_company_by_ticker(seeded_session, "alph")
    assert profile is not None
    assert profile.ticker == "ALPH"


@pytest.mark.asyncio
async def test_profile_not_found(seeded_session):
    """Unknown ticker should return None."""
    profile = await get_company_by_ticker(seeded_session, "ZZZZ")
    assert profile is None
