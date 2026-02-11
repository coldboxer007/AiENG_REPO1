"""align_schema_with_spec

Revision ID: 0002_align_schema_with_spec
Revises: 0001_initial
Create Date: 2025-06-01 00:00:00.000000

Adds columns required by the Technical Hiring Assignment spec:
- companies: ceo (String), founded_year (Integer)
- financials: gross_margin (Float), debt_to_equity (Float), free_cash_flow (Float)
- analyst_ratings: previous_rating (String)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0002_align_schema_with_spec"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- companies ---
    op.add_column("companies", sa.Column("ceo", sa.String(255), nullable=True))
    op.add_column("companies", sa.Column("founded_year", sa.Integer, nullable=True))

    # --- financials ---
    op.add_column("financials", sa.Column("gross_margin", sa.Float, nullable=True))
    op.add_column("financials", sa.Column("debt_to_equity", sa.Float, nullable=True))
    op.add_column("financials", sa.Column("free_cash_flow", sa.Float, nullable=True))

    # --- analyst_ratings ---
    op.add_column("analyst_ratings", sa.Column("previous_rating", sa.String(30), nullable=True))


def downgrade() -> None:
    op.drop_column("analyst_ratings", "previous_rating")
    op.drop_column("financials", "free_cash_flow")
    op.drop_column("financials", "debt_to_equity")
    op.drop_column("financials", "gross_margin")
    op.drop_column("companies", "founded_year")
    op.drop_column("companies", "ceo")
