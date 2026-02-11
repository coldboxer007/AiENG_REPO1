# Row Level Security (RLS) Implementation

This document describes the Row Level Security (RLS) implementation for the Financial Data MCP Server.

## Overview

Row Level Security (RLS) is a PostgreSQL feature that enables fine-grained access control at the row level. It allows the database to enforce access policies automatically, ensuring users can only access data they're authorized to see.

## Architecture Decision

**Status:** Implemented  
**Date:** 2025-02-11  
**Decision:** Implement RLS with configuration flag for multi-tenant scenarios

### Context

The assignment requires RLS implementation, but the MCP server primarily operates in stdio mode where:
- It's a single-user tool (Claude Desktop, Cursor)
- User has full access to all data by design
- RLS adds complexity without immediate benefit

However, for SSE transport and production deployments:
- Multi-tenant scenarios require data isolation
- Security audits expect RLS
- Compliance requirements (GDPR, SOC2) often mandate RLS

### Decision

Implement full RLS with a configuration flag:
- `ENABLE_RLS=false` (default): RLS policies exist but are bypassed in stdio mode
- `ENABLE_RLS=true`: Full enforcement for SSE/production deployments

This satisfies the assignment requirement while maintaining simplicity for stdio mode.

## Implementation Details

### Database Schema Changes

#### New Tables

**users**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

#### Modified Tables

**companies** - Added `user_id` column
```sql
ALTER TABLE companies ADD COLUMN user_id UUID REFERENCES users(id);
CREATE INDEX ix_companies_user_id ON companies(user_id);
```

### RLS Policies

#### Companies Table

```sql
-- Enable RLS
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;

-- Policy: Users can see public companies (user_id IS NULL) or their own
CREATE POLICY companies_select_policy ON companies
    FOR SELECT
    USING (
        user_id IS NULL OR
        user_id = current_setting('app.current_user_id')::UUID OR
        current_setting('app.current_user_role') = 'admin'
    );

-- Policy: Users can only insert their own companies
CREATE POLICY companies_insert_policy ON companies
    FOR INSERT
    WITH CHECK (
        user_id = current_setting('app.current_user_id')::UUID OR
        current_setting('app.current_user_role') = 'admin'
    );

-- Policy: Users can only update their own companies
CREATE POLICY companies_update_policy ON companies
    FOR UPDATE
    USING (
        user_id = current_setting('app.current_user_id')::UUID OR
        current_setting('app.current_user_role') = 'admin'
    );

-- Policy: Users can only delete their own companies
CREATE POLICY companies_delete_policy ON companies
    FOR DELETE
    USING (
        user_id = current_setting('app.current_user_id')::UUID OR
        current_setting('app.current_user_role') = 'admin'
    );
```

#### Financials, Stock Prices, Analyst Ratings Tables

These tables use **policies through parent company**:

```sql
-- Example for financials
CREATE POLICY financials_select_policy ON financials
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM companies
            WHERE companies.id = financials.company_id
            AND (
                companies.user_id IS NULL OR
                companies.user_id = current_setting('app.current_user_id')::UUID OR
                current_setting('app.current_user_role') = 'admin'
            )
        )
    );
```

This pattern ensures that if a user can see a company, they can see all its related data.

## Python Implementation

### Configuration

```python
# app/config.py
class Settings(BaseSettings):
    enable_rls: bool = False  # Enable for production
    supabase_jwt_secret: str | None = None
    admin_api_key: str | None = None
```

### User Context

```python
# app/utils/rls.py
class UserContext:
    """Represents the current user for RLS."""
    
    def __init__(self, user_id: str | None = None, role: str = "anonymous"):
        self.user_id = user_id
        self.role = role
        self.is_admin = role == "admin"
```

### Session Management

```python
# app/utils/rls.py
class RLSManager:
    """Manages database sessions with RLS context."""
    
    async def session(self, user_ctx: UserContext | None = None):
        """Create a session with RLS context set."""
        session = async_session_factory()
        
        if self.rls_enabled:
            # Set PostgreSQL configuration parameters
            await session.execute(
                text("SELECT set_config('app.current_user_id', :user_id, true)"),
                {"user_id": user_ctx.user_id or "00000000-0000-0000-0000-000000000000"}
            )
            await session.execute(
                text("SELECT set_config('app.current_user_role', :role, true)"),
                {"role": user_ctx.role}
            )
        
        return session
```

### Helper Context Managers

```python
# Admin session - bypasses all RLS
async with admin_session() as session:
    result = await session.execute(select(Company))
    # Can see all companies

# Public session - only public data
async with public_session() as session:
    result = await session.execute(select(Company))
    # Can only see companies with user_id IS NULL

# User session - own data + public
async with rls_manager.session(UserContext(user_id="123", role="user")) as session:
    result = await session.execute(select(Company))
    # Can see own companies + public companies
```

## Usage Modes

### Mode 1: Stdio (Claude Desktop, Cursor)

```bash
# RLS disabled - all data accessible
ENABLE_RLS=false python -m app.mcp.server
```

**Characteristics:**
- Single user tool
- Full database access
- Simpler mental model
- Faster performance (no context switching)

### Mode 2: SSE with Authentication

```bash
# RLS enabled - multi-tenant
ENABLE_RLS=true python -m app.mcp.sse_server
```

**Characteristics:**
- Multi-user web application
- Data isolation per user
- Public companies visible to all
- Private companies isolated

### Mode 3: Admin Operations

```python
from app.utils.rls import admin_session

async def system_maintenance():
    """Admin task that needs access to all data."""
    async with admin_session() as session:
        # Can modify any company's data
        # Bypasses all RLS policies
        pass
```

## Security Considerations

### 1. Policy Bypass Prevention

RLS policies use `current_setting()` which:
- Can only be set by the application
- Is session-local (not shared across connections)
- Requires explicit `SECURITY DEFINER` functions to bypass

### 2. SQL Injection Protection

All user inputs are parameterized:
```python
# Safe - uses SQLAlchemy ORM
session.execute(select(Company).where(Company.ticker == ticker))

# Safe - uses parameterized queries
session.execute(
    text("SELECT * FROM companies WHERE ticker = :ticker"),
    {"ticker": ticker}
)
```

### 3. JWT Verification

When RLS is enabled with Supabase:
```python
# Verify JWT token before setting context
try:
    payload = jwt.decode(token, settings.supabase_jwt_secret, algorithms=["HS256"])
    user_ctx = UserContext(
        user_id=payload["sub"],
        role=payload.get("role", "user")
    )
except jwt.InvalidTokenError:
    raise AuthenticationError()
```

## Migration Path

### From Non-RLS to RLS

1. **Prepare Database**
   ```bash
   alembic upgrade head  # Creates user_id column and policies
   ```

2. **Seed Users Table**
   ```python
   # Create admin user
   admin = User(email="admin@example.com", role="admin")
   ```

3. **Assign Existing Companies**
   ```sql
   -- Make all existing companies public
   UPDATE companies SET user_id = NULL;
   ```

4. **Enable RLS**
   ```bash
   export ENABLE_RLS=true
   ```

## Testing

### Test Scenarios

```python
# test_rls.py
class TestRLSPolicies:
    async def test_public_can_see_public_companies(self):
        """Public users see only public data."""
        async with public_session() as session:
            result = await session.execute(select(Company))
            companies = result.scalars().all()
            assert all(c.user_id is None for c in companies)

    async def test_user_can_see_own_companies(self):
        """Users see their own + public companies."""
        ctx = UserContext(user_id="user123", role="user")
        async with rls_manager.session(ctx) as session:
            result = await session.execute(select(Company))
            companies = result.scalars().all()
            # Contains public + user123's companies
            
    async def test_admin_can_see_all(self):
        """Admins bypass RLS."""
        async with admin_session() as session:
            result = await session.execute(select(Company))
            companies = result.scalars().all()
            # Contains ALL companies
```

## Monitoring

### RLS Performance Impact

```sql
-- Check if RLS is causing slow queries
SELECT 
    query,
    calls,
    total_time,
    mean_time
FROM pg_stat_statements
WHERE query LIKE '%companies%'
ORDER BY mean_time DESC;
```

### Policy Effectiveness

```sql
-- Count rows by visibility (admin query)
SELECT 
    CASE 
        WHEN user_id IS NULL THEN 'public'
        ELSE 'private'
    END as visibility,
    COUNT(*) as count
FROM companies
GROUP BY visibility;
```

## Troubleshooting

### Issue: RLS Policies Not Enforcing

**Symptoms:** Users see data they shouldn't

**Solutions:**
1. Check `ENABLE_RLS=true` is set
2. Verify policies exist: `\d companies` in psql
3. Check context is set: `SELECT current_setting('app.current_user_id')`

### Issue: Performance Degradation

**Symptoms:** Slow queries after enabling RLS

**Solutions:**
1. Add indexes on `user_id` columns
2. Use `EXPLAIN ANALYZE` to check query plans
3. Consider disabling RLS for read-heavy analytics queries

### Issue: Admin Can't Access Data

**Symptoms:** Admin API calls fail with permission denied

**Solutions:**
1. Use `admin_session()` context manager
2. Verify admin role: `SELECT current_setting('app.current_user_role')`
3. Check admin user exists in `users` table

## Best Practices

1. **Always use parameterized queries** - Never concatenate SQL strings
2. **Set context before every transaction** - Don't rely on session persistence
3. **Test with RLS enabled** - Run test suite with `ENABLE_RLS=true`
4. **Audit regularly** - Check for policy violations in logs
5. **Document exceptions** - Any bypass should be documented

## Future Enhancements

- **Row-level encryption** - Encrypt sensitive PII fields
- **Audit logging** - Log all RLS policy evaluations
- **Dynamic policies** - Time-based access (e.g., market hours only)
- **Attribute-based access** - Fine-grained field-level permissions

## References

- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [Supabase RLS Guide](https://supabase.com/docs/guides/auth/row-level-security)
- [OWASP RLS Best Practices](https://owasp.org/www-project-top-ten/)
