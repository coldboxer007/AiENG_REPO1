"""Stock-price query service."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.stock_price import StockPrice
from app.schemas.stock import StockPriceHistoryData, StockPriceRow
from app.services.metrics import max_drawdown, simple_return


async def get_stock_price_history(
    session: AsyncSession,
    ticker: str,
    start_date: date,
    end_date: date,
) -> StockPriceHistoryData | None:
    """Return OHLC data, daily returns, and max drawdown for the given range."""
    # Resolve company
    comp_stmt = select(Company.id).where(func.upper(Company.ticker) == ticker.upper())
    comp_result = await session.execute(comp_stmt)
    company_id = comp_result.scalar_one_or_none()
    if company_id is None:
        return None

    stmt = (
        select(StockPrice)
        .where(
            StockPrice.company_id == company_id,
            StockPrice.date >= start_date,
            StockPrice.date <= end_date,
        )
        .order_by(StockPrice.date)
    )
    result = await session.execute(stmt)
    rows = result.scalars().all()

    prices: list[StockPriceRow] = []
    closes: list[float] = []
    prev_close: float | None = None
    for r in rows:
        c = float(r.close)
        ret = simple_return(prev_close, c) if prev_close is not None else None
        prices.append(
            StockPriceRow(
                date=r.date,
                open=float(r.open),
                high=float(r.high),
                low=float(r.low),
                close=c,
                volume=r.volume,
                daily_return=round(ret, 8) if ret is not None else None,
            )
        )
        closes.append(c)
        prev_close = c

    total_ret = None
    if len(closes) >= 2:
        total_ret = round((closes[-1] - closes[0]) / closes[0], 6)

    mdd = max_drawdown(closes)

    return StockPriceHistoryData(
        ticker=ticker.upper(),
        start_date=start_date,
        end_date=end_date,
        prices=prices,
        total_return_pct=total_ret,
        max_drawdown_pct=round(mdd, 6) if mdd is not None else None,
    )
