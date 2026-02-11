"""Stock-price query service."""

from __future__ import annotations

import base64
import json
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
    limit: int = 100,
    cursor: str | None = None,
) -> StockPriceHistoryData | None:
    """Return OHLC data, daily returns, and max drawdown for the given range.

    Supports cursor-based pagination for large date ranges.

    Args:
        session: Async DB session.
        ticker: Company ticker.
        start_date: Inclusive start date.
        end_date: Inclusive end date.
        limit: Max rows per page (capped at 500).
        cursor: Opaque pagination cursor from a previous response.

    Returns:
        ``None`` if the ticker is not found.  Otherwise a
        ``StockPriceHistoryData`` with a ``next_cursor`` field when more
        pages exist.
    """
    limit = min(limit, 500)

    # Resolve company
    comp_stmt = select(Company.id).where(func.upper(Company.ticker) == ticker.upper())
    comp_result = await session.execute(comp_stmt)
    company_id = comp_result.scalar_one_or_none()
    if company_id is None:
        return None

    # Decode cursor
    cursor_date: date | None = None
    if cursor:
        try:
            decoded = json.loads(base64.b64decode(cursor).decode())
            cursor_date = date.fromisoformat(decoded["date"])
        except Exception:
            pass

    stmt = select(StockPrice).where(
        StockPrice.company_id == company_id,
        StockPrice.date >= start_date,
        StockPrice.date <= end_date,
    )

    if cursor_date:
        stmt = stmt.where(StockPrice.date > cursor_date)

    stmt = stmt.order_by(StockPrice.date).limit(limit + 1)

    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    # Build next cursor
    next_cursor: str | None = None
    if has_more and rows:
        cursor_data = {"date": rows[-1].date.isoformat()}
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()

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
        next_cursor=next_cursor,
        has_more=has_more,
    )
