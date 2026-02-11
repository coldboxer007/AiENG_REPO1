"""Financial report ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Integer, Numeric, Float
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.company import Base


class Financial(Base):
    __tablename__ = "financials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    period_year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_quarter: Mapped[int | None] = mapped_column(Integer, nullable=True)
    revenue: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    gross_profit: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    operating_income: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    net_income: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    eps: Mapped[float] = mapped_column(Numeric(10, 4), nullable=True)
    assets: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    liabilities: Mapped[float] = mapped_column(Numeric(20, 2), nullable=True)
    operating_margin: Mapped[float] = mapped_column(Numeric(8, 4), nullable=True)
    net_margin: Mapped[float] = mapped_column(Numeric(8, 4), nullable=True)
    gross_margin: Mapped[float | None] = mapped_column(Float, nullable=True)
    debt_to_equity: Mapped[float | None] = mapped_column(Float, nullable=True)
    free_cash_flow: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company", back_populates="financials")

    __table_args__ = (
        Index("ix_financials_company_id", "company_id"),
        Index("ix_financials_company_year_quarter", "company_id", "period_year", "period_quarter"),
    )

    def __repr__(self) -> str:
        q = f"Q{self.period_quarter}" if self.period_quarter else "Annual"
        return f"<Financial {self.company_id} {self.period_year} {q}>"
