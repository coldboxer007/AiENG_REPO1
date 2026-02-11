"""Analyst rating ORM model."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.company import Base


class AnalystRating(Base):
    __tablename__ = "analyst_ratings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    firm_name: Mapped[str] = mapped_column(String(150), nullable=False)
    rating: Mapped[str] = mapped_column(String(30), nullable=False)
    price_target: Mapped[float] = mapped_column(Numeric(12, 2), nullable=True)
    rating_date: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    company = relationship("Company", back_populates="analyst_ratings")

    __table_args__ = (
        Index("ix_analyst_ratings_company_id", "company_id"),
    )

    def __repr__(self) -> str:
        return f"<AnalystRating {self.firm_name} {self.rating} {self.company_id}>"
