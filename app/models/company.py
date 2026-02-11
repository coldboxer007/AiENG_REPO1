"""Company ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Index, Numeric, String, Text, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all models."""

    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(150), nullable=False)
    market_cap: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    employees: Mapped[int] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    country: Mapped[str] = mapped_column(String(80), nullable=False, default="US")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    financials = relationship("Financial", back_populates="company", lazy="selectin")
    stock_prices = relationship("StockPrice", back_populates="company", lazy="selectin")
    analyst_ratings = relationship("AnalystRating", back_populates="company", lazy="selectin")

    __table_args__ = (
        Index("ix_companies_ticker", "ticker"),
    )

    def __repr__(self) -> str:
        return f"<Company {self.ticker} – {self.name}>"
