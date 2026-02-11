"""Add performance indexes for query optimization

Revision ID: 0003_add_performance_indexes
Revises: 0002_align_schema_with_spec
Create Date: 2025-02-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_add_performance_indexes"
down_revision: str = "0002_align_schema_with_spec"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Composite index for stock price time-series queries (company_id + date)
    # Critical for get_stock_price_history tool performance
    op.create_index(
        "ix_stock_prices_company_date",
        "stock_prices",
        ["company_id", "date"],
        unique=False,
    )

    # Composite index for financial reports lookup
    # Optimizes get_financial_report and compare_companies tools
    op.create_index(
        "ix_financials_company_year_quarter",
        "financials",
        ["company_id", "period_year", "period_quarter"],
        unique=False,
    )

    # Index on sector for screening and overview queries
    # Optimizes screen_stocks and get_sector_overview tools
    op.create_index(
        "ix_companies_sector",
        "companies",
        ["sector"],
        unique=False,
    )

    # Index on market_cap for screening queries with min/max filters
    # Optimizes screen_stocks tool
    op.create_index(
        "ix_companies_market_cap",
        "companies",
        ["market_cap"],
        unique=False,
    )

    # Index on analyst rating date for recent ratings queries
    # Optimizes get_analyst_ratings tool (fetching 5 most recent)
    op.create_index(
        "ix_analyst_ratings_date",
        "analyst_ratings",
        ["rating_date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_analyst_ratings_date", table_name="analyst_ratings")
    op.drop_index("ix_companies_market_cap", table_name="companies")
    op.drop_index("ix_companies_sector", table_name="companies")
    op.drop_index("ix_financials_company_year_quarter", table_name="financials")
    op.drop_index("ix_stock_prices_company_date", table_name="stock_prices")
