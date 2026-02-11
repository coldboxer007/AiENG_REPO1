"""Add RLS (Row Level Security) support to all tables

Revision ID: 0004_add_rls
Revises: 0003_add_performance_indexes
Create Date: 2025-02-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004_add_rls"
down_revision: str = "0003_add_performance_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add RLS support with user_id columns and policies."""

    # Add user_id column to companies table
    op.add_column(
        "companies",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_companies_user_id", "companies", ["user_id"])

    # Create users table for Supabase Auth integration
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False),
        sa.Column("role", sa.String(50), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # Enable RLS on all tables
    op.execute("ALTER TABLE companies ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE financials ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE stock_prices ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE analyst_ratings ENABLE ROW LEVEL SECURITY")

    # Create RLS policies for companies table
    op.execute("""
        CREATE POLICY companies_select_policy ON companies
        FOR SELECT
        USING (
            user_id IS NULL OR  -- Public companies
            user_id = current_setting('app.current_user_id', true)::uuid OR  -- Own companies
            current_setting('app.current_user_role', true) = 'admin'  -- Admin access
        )
    """)

    op.execute("""
        CREATE POLICY companies_insert_policy ON companies
        FOR INSERT
        WITH CHECK (
            user_id = current_setting('app.current_user_id', true)::uuid OR
            current_setting('app.current_user_role', true) = 'admin'
        )
    """)

    op.execute("""
        CREATE POLICY companies_update_policy ON companies
        FOR UPDATE
        USING (
            user_id = current_setting('app.current_user_id', true)::uuid OR
            current_setting('app.current_user_role', true) = 'admin'
        )
    """)

    op.execute("""
        CREATE POLICY companies_delete_policy ON companies
        FOR DELETE
        USING (
            user_id = current_setting('app.current_user_id', true)::uuid OR
            current_setting('app.current_user_role', true) = 'admin'
        )
    """)

    # Create RLS policies for financials table (inherits from companies)
    op.execute("""
        CREATE POLICY financials_select_policy ON financials
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM companies
                WHERE companies.id = financials.company_id
                AND (
                    companies.user_id IS NULL OR
                    companies.user_id = current_setting('app.current_user_id', true)::uuid OR
                    current_setting('app.current_user_role', true) = 'admin'
                )
            )
        )
    """)

    op.execute("""
        CREATE POLICY financials_modify_policy ON financials
        FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM companies
                WHERE companies.id = financials.company_id
                AND (
                    companies.user_id = current_setting('app.current_user_id', true)::uuid OR
                    current_setting('app.current_user_role', true) = 'admin'
                )
            )
        )
    """)

    # Create RLS policies for stock_prices table (inherits from companies)
    op.execute("""
        CREATE POLICY stock_prices_select_policy ON stock_prices
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM companies
                WHERE companies.id = stock_prices.company_id
                AND (
                    companies.user_id IS NULL OR
                    companies.user_id = current_setting('app.current_user_id', true)::uuid OR
                    current_setting('app.current_user_role', true) = 'admin'
                )
            )
        )
    """)

    op.execute("""
        CREATE POLICY stock_prices_modify_policy ON stock_prices
        FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM companies
                WHERE companies.id = stock_prices.company_id
                AND (
                    companies.user_id = current_setting('app.current_user_id', true)::uuid OR
                    current_setting('app.current_user_role', true) = 'admin'
                )
            )
        )
    """)

    # Create RLS policies for analyst_ratings table (inherits from companies)
    op.execute("""
        CREATE POLICY analyst_ratings_select_policy ON analyst_ratings
        FOR SELECT
        USING (
            EXISTS (
                SELECT 1 FROM companies
                WHERE companies.id = analyst_ratings.company_id
                AND (
                    companies.user_id IS NULL OR
                    companies.user_id = current_setting('app.current_user_id', true)::uuid OR
                    current_setting('app.current_user_role', true) = 'admin'
                )
            )
        )
    """)

    op.execute("""
        CREATE POLICY analyst_ratings_modify_policy ON analyst_ratings
        FOR ALL
        USING (
            EXISTS (
                SELECT 1 FROM companies
                WHERE companies.id = analyst_ratings.company_id
                AND (
                    companies.user_id = current_setting('app.current_user_id', true)::uuid OR
                    current_setting('app.current_user_role', true) = 'admin'
                )
            )
        )
    """)


def downgrade() -> None:
    """Remove RLS support."""
    # Drop policies
    for table in ["analyst_ratings", "stock_prices", "financials", "companies"]:
        op.execute(f"DROP POLICY IF EXISTS {table}_select_policy ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_insert_policy ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_update_policy ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_delete_policy ON {table}")
        op.execute(f"DROP POLICY IF EXISTS {table}_modify_policy ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    # Drop user_id column and index
    op.drop_index("ix_companies_user_id", table_name="companies")
    op.drop_column("companies", "user_id")

    # Drop users table
    op.drop_table("users")
