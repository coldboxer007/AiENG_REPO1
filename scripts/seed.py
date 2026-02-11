#!/usr/bin/env python3
"""Seed script – populates the database with realistic dummy financial data.

Run after migrations:
    python -m scripts.seed
"""

from __future__ import annotations

import random
import uuid
from datetime import date, datetime, timedelta, timezone

from faker import Faker
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import settings
from app.models.company import Base, Company
from app.models.financial import Financial
from app.models.stock_price import StockPrice
from app.models.analyst_rating import AnalystRating

fake = Faker()
Faker.seed(42)
random.seed(42)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SECTORS = [
    ("Technology", ["Software", "Semiconductors", "IT Services", "Cloud Computing"]),
    ("Healthcare", ["Pharmaceuticals", "Biotech", "Medical Devices"]),
    ("Finance", ["Banking", "Insurance", "Asset Management"]),
    ("Energy", ["Oil & Gas", "Renewable Energy"]),
    ("Consumer Goods", ["Retail", "Food & Beverage", "Apparel"]),
]

RATING_LABELS = ["Strong Buy", "Buy", "Hold", "Underperform", "Sell"]
ANALYST_FIRMS = [
    "Goldman Sachs", "Morgan Stanley", "JP Morgan", "Barclays",
    "Citi", "BofA Securities", "UBS", "Deutsche Bank",
    "Credit Suisse", "Jefferies", "Raymond James", "Piper Sandler",
]

# Generate 10 unique tickers
TICKERS: list[str] = []
_used: set[str] = set()
while len(TICKERS) < 10:
    t = fake.lexify(text="????", letters="ABCDEFGHIJKLMNOPQRSTUVWXYZ").upper()
    if len(t) <= 5 and t not in _used:
        _used.add(t)
        TICKERS.append(t)


def _random_market_cap() -> float:
    return round(random.uniform(500_000_000, 2_000_000_000_000), 2)


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------


def seed_companies(session: Session) -> list[Company]:
    """Create 10 companies."""
    companies: list[Company] = []
    for ticker in TICKERS:
        sector, industries = random.choice(SECTORS)
        company = Company(
            id=uuid.uuid4(),
            ticker=ticker,
            name=fake.company(),
            sector=sector,
            industry=random.choice(industries),
            market_cap=_random_market_cap(),
            employees=random.randint(500, 150_000),
            description=fake.paragraph(nb_sentences=3),
            country=random.choice(["US", "US", "US", "UK", "DE", "JP"]),
            currency="USD",
        )
        session.add(company)
        companies.append(company)
    session.flush()
    return companies


def seed_financials(session: Session, companies: list[Company]) -> int:
    """Generate 80+ financial report rows (quarterly across 2 years per company)."""
    count = 0
    for comp in companies:
        base_revenue = random.uniform(1e8, 5e10)
        for year in [2023, 2024]:
            for quarter in [1, 2, 3, 4]:
                revenue = base_revenue * (1 + random.uniform(-0.05, 0.10))
                gross_profit = revenue * random.uniform(0.35, 0.70)
                operating_income = gross_profit * random.uniform(0.20, 0.60)
                net_income = operating_income * random.uniform(0.60, 0.90)
                eps = net_income / random.randint(100_000_000, 1_000_000_000)
                assets = base_revenue * random.uniform(1.5, 4.0)
                liabilities = assets * random.uniform(0.30, 0.65)
                operating_margin = operating_income / revenue if revenue else 0
                net_margin = net_income / revenue if revenue else 0

                month = quarter * 3
                report_dt = date(year, month, min(28, random.randint(15, 28)))

                session.add(
                    Financial(
                        id=uuid.uuid4(),
                        company_id=comp.id,
                        period_year=year,
                        period_quarter=quarter,
                        revenue=round(revenue, 2),
                        gross_profit=round(gross_profit, 2),
                        operating_income=round(operating_income, 2),
                        net_income=round(net_income, 2),
                        eps=round(eps, 4),
                        assets=round(assets, 2),
                        liabilities=round(liabilities, 2),
                        operating_margin=round(operating_margin, 4),
                        net_margin=round(net_margin, 4),
                        report_date=report_dt,
                    )
                )
                count += 1
                base_revenue = revenue  # drift forward
    session.flush()
    return count


def seed_stock_prices(session: Session, companies: list[Company]) -> int:
    """Generate 600+ daily stock price rows."""
    count = 0
    start = date(2024, 1, 2)
    # ~65 trading days per company ⇒ 10×65 = 650 rows
    for comp in companies:
        price = random.uniform(20.0, 500.0)
        current = start
        for _ in range(65):
            if current.weekday() >= 5:  # skip weekends
                current += timedelta(days=1)
                continue
            change = price * random.uniform(-0.04, 0.04)
            open_p = round(price + random.uniform(-1, 1), 4)
            close_p = round(price + change, 4)
            high_p = round(max(open_p, close_p) + random.uniform(0, 2), 4)
            low_p = round(min(open_p, close_p) - random.uniform(0, 2), 4)
            if low_p <= 0:
                low_p = 0.01

            session.add(
                StockPrice(
                    id=uuid.uuid4(),
                    company_id=comp.id,
                    date=current,
                    open=open_p,
                    high=high_p,
                    low=low_p,
                    close=close_p,
                    volume=random.randint(500_000, 50_000_000),
                )
            )
            count += 1
            price = float(close_p)
            current += timedelta(days=1)
    session.flush()
    return count


def seed_analyst_ratings(session: Session, companies: list[Company]) -> int:
    """Generate 40+ analyst rating rows."""
    count = 0
    for comp in companies:
        n_ratings = random.randint(4, 8)
        for _ in range(n_ratings):
            session.add(
                AnalystRating(
                    id=uuid.uuid4(),
                    company_id=comp.id,
                    firm_name=random.choice(ANALYST_FIRMS),
                    rating=random.choice(RATING_LABELS),
                    price_target=round(random.uniform(20.0, 600.0), 2),
                    rating_date=fake.date_between(start_date="-1y", end_date="today"),
                    notes=fake.sentence() if random.random() > 0.4 else None,
                )
            )
            count += 1
    session.flush()
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print("🌱  Seeding database …")
    engine = create_engine(settings.database_url_sync, echo=False)

    # Create all tables (fallback if migrations haven't run)
    Base.metadata.create_all(engine)
    # Also import and create other model tables
    Financial.__table__.create(engine, checkfirst=True)
    StockPrice.__table__.create(engine, checkfirst=True)
    AnalystRating.__table__.create(engine, checkfirst=True)

    with Session(engine) as session:
        # Wipe existing data
        session.execute(AnalystRating.__table__.delete())
        session.execute(StockPrice.__table__.delete())
        session.execute(Financial.__table__.delete())
        session.execute(Company.__table__.delete())
        session.commit()

        companies = seed_companies(session)
        print(f"  ✅ {len(companies)} companies")

        n_fin = seed_financials(session, companies)
        print(f"  ✅ {n_fin} financial reports")

        n_sp = seed_stock_prices(session, companies)
        print(f"  ✅ {n_sp} stock price rows")

        n_ar = seed_analyst_ratings(session, companies)
        print(f"  ✅ {n_ar} analyst ratings")

        session.commit()

    print("🎉  Seeding complete!")


if __name__ == "__main__":
    main()
