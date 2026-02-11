"""Pure math / metric helpers (no DB access)."""

from __future__ import annotations


def cagr(start_value: float, end_value: float, years: int) -> float | None:
    """Compound Annual Growth Rate.

    Returns None when inputs are non-positive or years < 1.
    """
    if years < 1 or start_value <= 0 or end_value <= 0:
        return None
    return (end_value / start_value) ** (1.0 / years) - 1.0


def simple_return(prev_close: float, curr_close: float) -> float | None:
    """Daily simple return."""
    if prev_close == 0:
        return None
    return (curr_close - prev_close) / prev_close


def max_drawdown(closes: list[float]) -> float | None:
    """Maximum drawdown from a series of close prices.

    Returns a negative percentage (e.g. -0.15 for -15%).
    Returns None if fewer than 2 prices.
    """
    if len(closes) < 2:
        return None
    peak = closes[0]
    mdd = 0.0
    for price in closes:
        if price > peak:
            peak = price
        dd = (price - peak) / peak
        if dd < mdd:
            mdd = dd
    return mdd
