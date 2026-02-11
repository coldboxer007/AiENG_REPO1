"""Company-related Pydantic schemas."""

from __future__ import annotations

import uuid

from pydantic import BaseModel


class CompanyBrief(BaseModel):
    """Lightweight company row returned by search."""

    ticker: str
    name: str
    sector: str
    market_cap: float | None = None


class CompanyProfile(BaseModel):
    """Full company profile."""

    id: uuid.UUID
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: float | None = None
    employees: int | None = None
    description: str | None = None
    ceo: str | None = None
    founded_year: int | None = None
    country: str
    currency: str
