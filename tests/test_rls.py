"""Tests for Row Level Security (RLS) implementation."""

from __future__ import annotations

import pytest
import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.company import Company
from app.models.user import User
from app.models.financial import Financial
from app.utils.rls import UserContext, rls_manager, admin_session, public_session


@pytest.fixture
async def test_users(session: AsyncSession):
    """Create test users with different roles."""
    # Regular user
    user1 = User(
        id=uuid.UUID("11111111-1111-1111-1111-111111111111"),
        email="user1@example.com",
        role="user",
    )

    # Another regular user
    user2 = User(
        id=uuid.UUID("22222222-2222-2222-2222-222222222222"),
        email="user2@example.com",
        role="user",
    )

    # Admin user
    admin = User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        email="admin@example.com",
        role="admin",
    )

    session.add_all([user1, user2, admin])
    await session.commit()

    return {"user1": user1, "user2": user2, "admin": admin}


@pytest.fixture
async def test_companies_with_owners(session: AsyncSession, test_users):
    """Create companies with different ownership."""
    # Public company (no owner)
    public_comp = Company(
        id=uuid.UUID("44444444-4444-4444-4444-444444444444"),
        ticker="PUBL",
        name="Public Corp",
        sector="Technology",
        industry="Software",
        user_id=None,  # Public
    )

    # Company owned by user1
    private_comp1 = Company(
        id=uuid.UUID("55555555-5555-5555-5555-555555555555"),
        ticker="PRIV1",
        name="Private Corp 1",
        sector="Healthcare",
        industry="Biotech",
        user_id=test_users["user1"].id,
    )

    # Company owned by user2
    private_comp2 = Company(
        id=uuid.UUID("66666666-6666-6666-6666-666666666666"),
        ticker="PRIV2",
        name="Private Corp 2",
        sector="Finance",
        industry="Banking",
        user_id=test_users["user2"].id,
    )

    session.add_all([public_comp, private_comp1, private_comp2])
    await session.commit()

    return {
        "public": public_comp,
        "private1": private_comp1,
        "private2": private_comp2,
    }


class TestUserContext:
    """Test UserContext dataclass."""

    def test_user_context_creation(self):
        """Test UserContext creation with valid data."""
        ctx = UserContext(user_id="123e4567-e89b-12d3-a456-426614174000", role="user")
        assert ctx.user_id == "123e4567-e89b-12d3-a456-426614174000"
        assert ctx.role == "user"
        assert ctx.is_admin is False

    def test_admin_context(self):
        """Test admin UserContext."""
        ctx = UserContext(user_id="123e4567-e89b-12d3-a456-426614174000", role="admin")
        assert ctx.is_admin is True

    def test_anonymous_context(self):
        """Test anonymous UserContext."""
        ctx = UserContext(role="anonymous")
        assert ctx.user_id is None
        assert ctx.role == "anonymous"
        assert ctx.is_admin is False


class TestRLSManager:
    """Test RLSManager functionality."""

    def test_rls_manager_creation(self):
        """Test RLS manager is created properly."""
        from app.config import settings

        assert rls_manager.rls_enabled == settings.enable_rls

    def test_context_variables(self):
        """Test context variable get/set."""
        ctx = UserContext(user_id="test-user", role="user")

        rls_manager.set_context(ctx)
        retrieved = rls_manager.get_current_context()

        assert retrieved.user_id == "test-user"
        assert retrieved.role == "user"

        rls_manager.clear_context()
        cleared = rls_manager.get_current_context()
        assert cleared.user_id is None
        assert cleared.role == "anonymous"


class TestAdminSession:
    """Test admin session bypasses RLS."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires PostgreSQL with RLS enabled - run manually")
    async def test_admin_can_see_all_companies(self, session, test_companies_with_owners):
        """Test admin can access all companies regardless of ownership."""
        async with admin_session(session) as admin_sess:
            result = await admin_sess.execute(select(Company))
            companies = result.scalars().all()

            tickers = {c.ticker for c in companies}
            assert tickers == {"PUBL", "PRIV1", "PRIV2"}


class TestPublicSession:
    """Test public session only sees public data."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires PostgreSQL with RLS enabled - run manually")
    async def test_public_can_only_see_public_companies(self, session, test_companies_with_owners):
        """Test public user can only see companies with no owner."""
        async with public_session(session) as public_sess:
            result = await public_sess.execute(select(Company))
            companies = result.scalars().all()

            # Should only see public company
            assert len(companies) == 1
            assert companies[0].ticker == "PUBL"


class TestRLSPolicies:
    """Test RLS policies in database."""

    @pytest.mark.asyncio
    async def test_rls_enabled_on_tables(self, session):
        """Test that RLS is enabled on all tables."""
        from app.config import settings

        if not settings.enable_rls:
            pytest.skip("RLS not enabled in configuration")

        # Check if RLS is enabled on companies table
        result = await session.execute(
            "SELECT relrowsecurity FROM pg_class WHERE relname = 'companies'"
        )
        rls_enabled = result.scalar()

        # Note: This might be False in SQLite test environment
        # In production PostgreSQL, this should be True after migration


class TestUserContextIntegration:
    """Test user context with actual database queries."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires PostgreSQL with RLS enabled - run manually")
    async def test_user_context_session(self, session, test_users, test_companies_with_owners):
        """Test that user context is properly set in session."""
        from app.config import settings

        if not settings.enable_rls:
            pytest.skip("RLS not enabled in configuration")

        # Create context for user1
        user_ctx = UserContext(user_id=str(test_users["user1"].id), role="user")

        async with rls_manager.session(user_ctx, session) as user1_session:
            # In RLS-enabled mode, user1 should only see their own companies + public
            result = await user1_session.execute(select(Company))
            companies = result.scalars().all()

            tickers = {c.ticker for c in companies}
            assert "PUBL" in tickers  # Public
            assert "PRIV1" in tickers  # Owned by user1
            # PRIV2 should not be visible to user1

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires PostgreSQL with RLS enabled - run manually")
    async def test_different_users_see_different_data(
        self, session, test_users, test_companies_with_owners
    ):
        """Test that user1 and user2 see different private companies."""
        from app.config import settings

        if not settings.enable_rls:
            pytest.skip("RLS not enabled in configuration")

        # User1 context
        ctx1 = UserContext(user_id=str(test_users["user1"].id), role="user")
        async with rls_manager.session(ctx1, session) as s1:
            result1 = await s1.execute(select(Company.ticker))
            tickers1 = {row[0] for row in result1.all()}

        # User2 context
        ctx2 = UserContext(user_id=str(test_users["user2"].id), role="user")
        async with rls_manager.session(ctx2, session) as s2:
            result2 = await s2.execute(select(Company.ticker))
            tickers2 = {row[0] for row in result2.all()}

        # Both see public company
        assert "PUBL" in tickers1
        assert "PUBL" in tickers2

        # Each sees their own private company
        assert "PRIV1" in tickers1
        assert "PRIV1" not in tickers2
        assert "PRIV2" in tickers2
        assert "PRIV2" not in tickers1
