"""Company query service."""

from __future__ import annotations

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.schemas.company import CompanyBrief, CompanyProfile


async def search_companies(
    session: AsyncSession,
    query: str,
    limit: int = 10,
) -> list[CompanyBrief]:
    """Search companies by ticker or name (case-insensitive ILIKE)."""
    pattern = f"%{query}%"
    stmt = (
        select(Company)
        .where(
            or_(
                Company.ticker.ilike(pattern),
                Company.name.ilike(pattern),
            )
        )
        .order_by(Company.ticker)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()
    return [
        CompanyBrief(
            ticker=r.ticker,
            name=r.name,
            sector=r.sector,
            market_cap=float(r.market_cap) if r.market_cap else None,
        )
        for r in rows
    ]


async def get_company_by_ticker(
    session: AsyncSession,
    ticker: str,
) -> CompanyProfile | None:
    """Return full profile for a single ticker (case-insensitive)."""
    stmt = select(Company).where(func.upper(Company.ticker) == ticker.upper())
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()
    if row is None:
        return None
    return CompanyProfile(
        id=row.id,
        ticker=row.ticker,
        name=row.name,
        sector=row.sector,
        industry=row.industry,
        market_cap=float(row.market_cap) if row.market_cap else None,
        employees=row.employees,
        description=row.description,
        country=row.country,
        currency=row.currency,
    )
