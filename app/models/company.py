"""Company ORM model."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, Numeric, String, Text, Integer, DateTime, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Shared declarative base for all models."""

    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    sector: Mapped[str] = mapped_column(String(100), nullable=False)
    industry: Mapped[str] = mapped_column(String(150), nullable=False)
    market_cap: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    employees: Mapped[int] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    ceo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    country: Mapped[str] = mapped_column(String(80), nullable=False, default="US")
    currency: Mapped[str] = mapped_column(String(10), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # RLS: Owner of this company (NULL = public company)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    # Relationships – use lazy="select" (default) so we only load related
    # data when explicitly requested via selectinload() / joinedload().
    # This prevents N+1 queries and unnecessary data transfer.
    financials = relationship("Financial", back_populates="company", lazy="select")
    stock_prices = relationship("StockPrice", back_populates="company", lazy="select")
    analyst_ratings = relationship("AnalystRating", back_populates="company", lazy="select")
    owner = relationship("User", back_populates="companies", lazy="select")

    __table_args__ = (
        Index("ix_companies_ticker", "ticker"),
        Index("ix_companies_sector", "sector"),
        Index("ix_companies_market_cap", "market_cap"),
        Index("ix_companies_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<Company {self.ticker} – {self.name}>"
