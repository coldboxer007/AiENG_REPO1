"""Stock-price Pydantic schemas."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class StockPriceRow(BaseModel):
    """Single day of OHLC data."""

    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int
    daily_return: float | None = None


class StockPriceHistoryData(BaseModel):
    """Stock price history with computed stats and optional pagination."""

    ticker: str
    start_date: date
    end_date: date
    prices: list[StockPriceRow]
    total_return_pct: float | None = None
    max_drawdown_pct: float | None = None
    next_cursor: str | None = None
    has_more: bool = False
