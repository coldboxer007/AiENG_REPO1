"""Row Level Security (RLS) context management for multi-tenant database access.

This module provides utilities for managing user context in PostgreSQL RLS policies.
It supports both stdio mode (single-user, RLS disabled) and SSE mode (multi-tenant, RLS enabled).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

# Context variable for current user in async context
_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)
_current_user_role: ContextVar[str] = ContextVar("current_user_role", default="anonymous")


class UserContext:
    """Represents the current user context for RLS.

    Attributes:
        user_id: UUID of the authenticated user, or None for anonymous/public access
        role: User role - 'admin', 'user', or 'anonymous'
        is_admin: Whether the user has admin privileges
    """

    def __init__(self, user_id: str | uuid.UUID | None = None, role: str = "anonymous"):
        self.user_id = str(user_id) if user_id else None
        self.role = role
        self.is_admin = role == "admin"

    def __repr__(self) -> str:
        return f"<UserContext user_id={self.user_id} role={self.role}>"


class RLSManager:
    """Manages Row Level Security context for database sessions.

    Usage:
        # In stdio mode (no RLS)
        async with rls_manager.session() as session:
            result = await session.execute(query)

        # In SSE mode with user authentication
        async with rls_manager.session(user_context) as session:
            result = await session.execute(query)
    """

    def __init__(self):
        self.rls_enabled = settings.enable_rls

    @asynccontextmanager
    async def session(
        self,
        user_ctx: UserContext | None = None,
        session: AsyncSession | None = None,
    ) -> AsyncGenerator[AsyncSession, None]:
        """Create a database session with RLS context set.

        Args:
            user_ctx: User context for RLS. If None and RLS is enabled,
                     only public data will be accessible.
            session: Existing session to use. If None, creates new session.

        Yields:
            AsyncSession with RLS context configured
        """
        from app.db import async_session_factory

        should_close = session is None
        session = session or async_session_factory()

        try:
            # Set RLS context variables in PostgreSQL
            if self.rls_enabled:
                await self._set_rls_context(session, user_ctx or UserContext())

            yield session

        finally:
            if should_close:
                await session.close()

    async def _set_rls_context(
        self,
        session: AsyncSession,
        user_ctx: UserContext,
    ) -> None:
        """Set PostgreSQL configuration parameters for RLS policies.

        These parameters are read by RLS policies using current_setting().
        """
        # Set current user ID for RLS policies
        await session.execute(
            text("SELECT set_config('app.current_user_id', :user_id, true)"),
            {"user_id": user_ctx.user_id or "00000000-0000-0000-0000-000000000000"},
        )

        # Set current user role for admin bypass
        await session.execute(
            text("SELECT set_config('app.current_user_role', :role, true)"),
            {"role": user_ctx.role},
        )

    def get_current_context(self) -> UserContext:
        """Get the current user context from context variables."""
        return UserContext(
            user_id=_current_user_id.get(),
            role=_current_user_role.get(),
        )

    def set_context(self, user_ctx: UserContext) -> None:
        """Set the current user context in context variables."""
        _current_user_id.set(user_ctx.user_id)
        _current_user_role.set(user_ctx.role)

    def clear_context(self) -> None:
        """Clear the current user context."""
        _current_user_id.set(None)
        _current_user_role.set("anonymous")


# Global RLS manager instance
rls_manager = RLSManager()


@asynccontextmanager
async def admin_session(
    session: AsyncSession | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a session with admin privileges (bypasses RLS).

    Use this for system operations that need to access all data.

    Example:
        async with admin_session() as session:
            # Can read all companies regardless of user_id
            result = await session.execute(select(Company))
    """
    admin_ctx = UserContext(role="admin")
    async with rls_manager.session(admin_ctx, session) as sess:
        yield sess


@asynccontextmanager
async def public_session(
    session: AsyncSession | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Create a session for public/unauthenticated access.

    Only public companies (user_id IS NULL) will be visible.

    Example:
        async with public_session() as session:
            # Can only read public companies
            result = await session.execute(select(Company))
    """
    public_ctx = UserContext(role="anonymous")
    async with rls_manager.session(public_ctx, session) as sess:
        yield sess
