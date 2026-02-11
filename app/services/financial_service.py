"""Financial query service."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.financial import Financial
from app.schemas.financial import FinancialSummary, YearFinancials
from app.services.metrics import cagr


async def get_financial_summary(
    session: AsyncSession,
    ticker: str,
    years: int = 3,
) -> FinancialSummary | None:
    """Return per-year financials for the last N years + CAGR.

    Annual rows (period_quarter IS NULL) are preferred; if none exist we fall
    back to summing quarterly rows per year.
    """
    # Resolve company
    comp_stmt = select(Company.id).where(func.upper(Company.ticker) == ticker.upper())
    comp_result = await session.execute(comp_stmt)
    company_id = comp_result.scalar_one_or_none()
    if company_id is None:
        return None

    # Try annual rows first
    annual_stmt = (
        select(Financial)
        .where(
            Financial.company_id == company_id,
            Financial.period_quarter.is_(None),
        )
        .order_by(Financial.period_year.desc())
        .limit(years)
    )
    annual_result = await session.execute(annual_stmt)
    rows = list(annual_result.scalars().all())

    if not rows:
        # Fallback: aggregate quarterly rows
        q_stmt = (
            select(
                Financial.period_year,
                func.sum(Financial.revenue).label("revenue"),
                func.sum(Financial.net_income).label("net_income"),
                func.avg(Financial.operating_margin).label("operating_margin"),
                func.avg(Financial.net_margin).label("net_margin"),
                func.avg(Financial.eps).label("eps"),
            )
            .where(Financial.company_id == company_id)
            .group_by(Financial.period_year)
            .order_by(Financial.period_year.desc())
            .limit(years)
        )
        q_result = await session.execute(q_stmt)
        q_rows = q_result.all()
        year_data = [
            YearFinancials(
                year=r.period_year,
                revenue=_to_float(r.revenue),
                net_income=_to_float(r.net_income),
                operating_margin=_to_float(r.operating_margin),
                net_margin=_to_float(r.net_margin),
                eps=_to_float(r.eps),
            )
            for r in q_rows
        ]
    else:
        year_data = [
            YearFinancials(
                year=r.period_year,
                revenue=_to_float(r.revenue),
                net_income=_to_float(r.net_income),
                operating_margin=_to_float(r.operating_margin),
                net_margin=_to_float(r.net_margin),
                eps=_to_float(r.eps),
            )
            for r in rows
        ]

    # Sort ascending for CAGR calc
    year_data_sorted = sorted(year_data, key=lambda x: x.year)
    revenue_cagr = None
    ni_cagr = None
    if len(year_data_sorted) >= 2:
        first, last = year_data_sorted[0], year_data_sorted[-1]
        n = last.year - first.year
        if n > 0:
            if first.revenue and last.revenue:
                revenue_cagr = cagr(first.revenue, last.revenue, n)
            if first.net_income and last.net_income:
                ni_cagr = cagr(first.net_income, last.net_income, n)

    return FinancialSummary(
        ticker=ticker.upper(),
        years_covered=len(year_data),
        data=year_data_sorted,
        revenue_cagr=round(revenue_cagr, 6) if revenue_cagr is not None else None,
        net_income_cagr=round(ni_cagr, 6) if ni_cagr is not None else None,
    )


def _to_float(v: Decimal | float | None) -> float | None:
    if v is None:
        return None
    return float(v)
