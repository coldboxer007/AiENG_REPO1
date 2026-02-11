"""Initial schema – companies, financials, stock_prices, analyst_ratings

Revision ID: 0001_initial
Revises: 
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- companies ---
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(10), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("industry", sa.String(150), nullable=False),
        sa.Column("market_cap", sa.Numeric(20, 2)),
        sa.Column("employees", sa.Integer),
        sa.Column("description", sa.Text),
        sa.Column("country", sa.String(80), nullable=False, server_default="US"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="USD"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_companies_ticker", "companies", ["ticker"])

    # --- financials ---
    op.create_table(
        "financials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("period_year", sa.Integer, nullable=False),
        sa.Column("period_quarter", sa.Integer, nullable=True),
        sa.Column("revenue", sa.Numeric(20, 2)),
        sa.Column("gross_profit", sa.Numeric(20, 2)),
        sa.Column("operating_income", sa.Numeric(20, 2)),
        sa.Column("net_income", sa.Numeric(20, 2)),
        sa.Column("eps", sa.Numeric(10, 4)),
        sa.Column("assets", sa.Numeric(20, 2)),
        sa.Column("liabilities", sa.Numeric(20, 2)),
        sa.Column("operating_margin", sa.Numeric(8, 4)),
        sa.Column("net_margin", sa.Numeric(8, 4)),
        sa.Column("report_date", sa.Date, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_financials_company_id", "financials", ["company_id"])

    # --- stock_prices ---
    op.create_table(
        "stock_prices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("open", sa.Numeric(12, 4), nullable=False),
        sa.Column("high", sa.Numeric(12, 4), nullable=False),
        sa.Column("low", sa.Numeric(12, 4), nullable=False),
        sa.Column("close", sa.Numeric(12, 4), nullable=False),
        sa.Column("volume", sa.BigInteger, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("company_id", "date", name="uq_stock_prices_company_date"),
    )
    op.create_index("ix_stock_prices_company_id", "stock_prices", ["company_id"])
    op.create_index("ix_stock_prices_date", "stock_prices", ["date"])

    # --- analyst_ratings ---
    op.create_table(
        "analyst_ratings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("firm_name", sa.String(150), nullable=False),
        sa.Column("rating", sa.String(30), nullable=False),
        sa.Column("price_target", sa.Numeric(12, 2)),
        sa.Column("rating_date", sa.Date, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_analyst_ratings_company_id", "analyst_ratings", ["company_id"])


def downgrade() -> None:
    op.drop_table("analyst_ratings")
    op.drop_table("stock_prices")
    op.drop_table("financials")
    op.drop_table("companies")
