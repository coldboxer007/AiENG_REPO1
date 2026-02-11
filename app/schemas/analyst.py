"""Analyst-rating Pydantic schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class AnalystRatingRow(BaseModel):
    """Single analyst rating entry."""

    firm_name: str
    rating: str
    previous_rating: str | None = None
    price_target: float | None = None
    rating_date: date
    notes: str | None = None


class RatingCount(BaseModel):
    """Count for a single rating label."""

    rating: str
    count: int


class AnalystConsensusData(BaseModel):
    """Aggregated analyst consensus."""

    ticker: str
    total_ratings: int
    rating_counts: list[RatingCount]
    average_price_target: float | None = None
    recent_ratings: list[AnalystRatingRow]
