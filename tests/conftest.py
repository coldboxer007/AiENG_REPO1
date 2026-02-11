"""Shared pytest fixtures – uses async SQLite for fast in-memory tests."""

from __future__ import annotations

import asyncio
import uuid
import random
from datetime import date, datetime, timezone

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.company import Base, Company
from app.models.financial import Financial
from app.models.stock_price import StockPrice
from app.models.analyst_rating import AnalystRating


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the whole test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create an async SQLite engine for testing."""
    eng = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def session(engine):
    """Provide a transactional async session that rolls back after each test."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as sess:
        async with sess.begin():
            yield sess
        # Rollback is implicit because we never commit


@pytest_asyncio.fixture
async def seeded_session(engine):
    """Session pre-loaded with a small set of test data."""
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as sess:
        # Clean tables first
        for table in reversed(Base.metadata.sorted_tables):
            await sess.execute(table.delete())
        await sess.commit()

        # --- Companies ---
        comp_a = Company(
            id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
            ticker="ALPH",
            name="Alpha Corp",
            sector="Technology",
            industry="Software",
            market_cap=500_000_000_000,
            employees=50_000,
            description="A leading technology company.",
            country="US",
            currency="USD",
        )
        comp_b = Company(
            id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
            ticker="BETA",
            name="Beta Industries",
            sector="Healthcare",
            industry="Biotech",
            market_cap=120_000_000_000,
            employees=12_000,
            description="A healthcare company.",
            country="US",
            currency="USD",
        )
        comp_c = Company(
            id=uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc"),
            ticker="GAMA",
            name="Gamma Finance",
            sector="Finance",
            industry="Banking",
            market_cap=80_000_000_000,
            employees=30_000,
            description="A global bank.",
            country="UK",
            currency="GBP",
        )
        sess.add_all([comp_a, comp_b, comp_c])
        await sess.flush()

        # --- Financials (quarterly for 2023 and 2024 for comp_a) ---
        for year in [2023, 2024]:
            for q in [1, 2, 3, 4]:
                sess.add(
                    Financial(
                        id=uuid.uuid4(),
                        company_id=comp_a.id,
                        period_year=year,
                        period_quarter=q,
                        revenue=50_000_000_000 + random.randint(-5_000_000_000, 5_000_000_000),
                        gross_profit=25_000_000_000,
                        operating_income=15_000_000_000,
                        net_income=10_000_000_000 + (year - 2023) * 1_000_000_000,
                        eps=5.0 + (year - 2023) * 0.5,
                        assets=200_000_000_000,
                        liabilities=80_000_000_000,
                        operating_margin=0.30,
                        net_margin=0.20,
                        report_date=date(year, q * 3, 15),
                    )
                )
        # Also add for comp_b (one year only)
        for q in [1, 2, 3, 4]:
            sess.add(
                Financial(
                    id=uuid.uuid4(),
                    company_id=comp_b.id,
                    period_year=2024,
                    period_quarter=q,
                    revenue=20_000_000_000,
                    gross_profit=12_000_000_000,
                    operating_income=6_000_000_000,
                    net_income=4_000_000_000,
                    eps=3.0,
                    assets=100_000_000_000,
                    liabilities=40_000_000_000,
                    operating_margin=0.30,
                    net_margin=0.20,
                    report_date=date(2024, q * 3, 15),
                )
            )
        await sess.flush()

        # --- Stock Prices (comp_a, ~30 days) ---
        price = 150.0
        for i in range(30):
            d = date(2024, 3, 1) + __import__("datetime").timedelta(days=i)
            if d.weekday() >= 5:
                continue
            change = price * random.uniform(-0.02, 0.02)
            c = round(price + change, 4)
            sess.add(
                StockPrice(
                    id=uuid.uuid4(),
                    company_id=comp_a.id,
                    date=d,
                    open=round(price, 4),
                    high=round(max(price, c) + 1, 4),
                    low=round(min(price, c) - 1, 4),
                    close=c,
                    volume=random.randint(1_000_000, 10_000_000),
                )
            )
            price = c
        await sess.flush()

        # --- Analyst Ratings (comp_a) ---
        firms = ["Goldman Sachs", "Morgan Stanley", "JP Morgan", "Barclays", "Citi"]
        ratings = ["Strong Buy", "Buy", "Hold", "Buy", "Strong Buy"]
        for j, (firm, rating) in enumerate(zip(firms, ratings)):
            sess.add(
                AnalystRating(
                    id=uuid.uuid4(),
                    company_id=comp_a.id,
                    firm_name=firm,
                    rating=rating,
                    price_target=round(160 + j * 5, 2),
                    rating_date=date(2024, 6, 1 + j),
                    notes=f"Note from {firm}" if j % 2 == 0 else None,
                )
            )
        await sess.flush()
        await sess.commit()

        yield sess
