"""Analyst-rating query service."""

from __future__ import annotations

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.analyst_rating import AnalystRating
from app.schemas.analyst import AnalystConsensusData, AnalystRatingRow, RatingCount


async def get_analyst_consensus(
    session: AsyncSession,
    ticker: str,
) -> AnalystConsensusData | None:
    """Return rating distribution, avg price target, and most recent ratings."""
    # Resolve company
    comp_stmt = select(Company.id).where(func.upper(Company.ticker) == ticker.upper())
    comp_result = await session.execute(comp_stmt)
    company_id = comp_result.scalar_one_or_none()
    if company_id is None:
        return None

    # Rating counts
    count_stmt = (
        select(
            AnalystRating.rating,
            func.count().label("cnt"),
        )
        .where(AnalystRating.company_id == company_id)
        .group_by(AnalystRating.rating)
        .order_by(func.count().desc())
    )
    count_result = await session.execute(count_stmt)
    rating_counts = [
        RatingCount(rating=row.rating, count=row.cnt) for row in count_result.all()
    ]
    total = sum(rc.count for rc in rating_counts)

    # Average price target
    avg_stmt = (
        select(func.avg(AnalystRating.price_target))
        .where(AnalystRating.company_id == company_id)
    )
    avg_result = await session.execute(avg_stmt)
    avg_pt = avg_result.scalar()
    avg_price_target = round(float(avg_pt), 2) if avg_pt is not None else None

    # Most recent 5
    recent_stmt = (
        select(AnalystRating)
        .where(AnalystRating.company_id == company_id)
        .order_by(AnalystRating.rating_date.desc())
        .limit(5)
    )
    recent_result = await session.execute(recent_stmt)
    recent = [
        AnalystRatingRow(
            firm_name=r.firm_name,
            rating=r.rating,
            price_target=float(r.price_target) if r.price_target else None,
            rating_date=r.rating_date,
            notes=r.notes,
        )
        for r in recent_result.scalars().all()
    ]

    return AnalystConsensusData(
        ticker=ticker.upper(),
        total_ratings=total,
        rating_counts=rating_counts,
        average_price_target=avg_price_target,
        recent_ratings=recent,
    )
