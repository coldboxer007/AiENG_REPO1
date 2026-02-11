"""Company query service."""

from __future__ import annotations

import base64
import json

from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.schemas.company import CompanyBrief, CompanyProfile


async def search_companies(
    session: AsyncSession,
    query: str,
    limit: int = 10,
    cursor: str | None = None,
) -> tuple[list[CompanyBrief], str | None]:
    """Search companies by ticker or name (case-insensitive ILIKE) with cursor pagination.

    Args:
        session: Async DB session.
        query: Search term (matched against ticker and name).
        limit: Maximum number of results per page (capped at 50).
        cursor: Opaque cursor from a previous response to fetch the next page.

    Returns:
        Tuple of (results, next_cursor).  ``next_cursor`` is ``None`` when
        there are no more pages.
    """
    limit = min(limit, 50)  # hard cap

    # Decode cursor
    last_ticker: str | None = None
    if cursor:
        try:
            decoded = json.loads(base64.b64decode(cursor).decode())
            last_ticker = decoded.get("ticker")
        except Exception:
            pass  # Invalid cursor – start from beginning

    pattern = f"%{query}%"
    stmt = (
        select(Company)
        .where(
            or_(
                Company.ticker.ilike(pattern),
                Company.name.ilike(pattern),
            )
        )
    )

    # Apply cursor condition (keyset pagination)
    if last_ticker:
        stmt = stmt.where(Company.ticker > last_ticker)

    # Fetch one extra row to determine if there are more results
    stmt = stmt.order_by(Company.ticker).limit(limit + 1)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    # Build next cursor
    next_cursor: str | None = None
    if has_more and rows:
        cursor_data = {"ticker": rows[-1].ticker}
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

    results = [
        CompanyBrief(
            ticker=r.ticker,
            name=r.name,
            sector=r.sector,
            market_cap=float(r.market_cap) if r.market_cap else None,
        )
        for r in rows
    ]

    return results, next_cursor


async def get_company_by_ticker(
    session: AsyncSession,
    ticker: str,
) -> CompanyProfile | None:
    """Return full profile for a single ticker (case-insensitive).

    Uses a simple SELECT without loading relationships – the service
    layer for financials / stock_prices / ratings handles its own queries.
    """
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
