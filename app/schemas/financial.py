"""Financial-related Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel


class YearFinancials(BaseModel):
    """Annual financial summary for one year."""

    year: int
    revenue: float | None = None
    net_income: float | None = None
    operating_margin: float | None = None
    net_margin: float | None = None
    eps: float | None = None
    gross_margin: float | None = None
    debt_to_equity: float | None = None
    free_cash_flow: float | None = None


class FinancialSummary(BaseModel):
    """Multi-year financial summary with CAGR."""

    ticker: str
    years_covered: int
    data: list[YearFinancials]
    revenue_cagr: float | None = None
    net_income_cagr: float | None = None
