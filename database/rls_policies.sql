-- Supabase Row Level Security Policies
-- Run this in Supabase SQL Editor after running migrations

-- ============================================================
-- Users Table
-- ============================================================

-- Enable RLS on users table (for Supabase Auth integration)
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

-- Users can only see their own profile
CREATE POLICY users_select_own ON users
    FOR SELECT
    USING (id = auth.uid() OR EXISTS (
        SELECT 1 FROM users u WHERE u.id = auth.uid() AND u.role = 'admin'
    ));

-- Users can only update their own profile
CREATE POLICY users_update_own ON users
    FOR UPDATE
    USING (id = auth.uid());

-- ============================================================
-- Companies Table
-- ============================================================

-- Note: RLS is enabled via migration, policies are created there too
-- These are additional Supabase-specific policies for JWT authentication

-- Allow public read access to companies with no user_id (public companies)
CREATE POLICY companies_public_read ON companies
    FOR SELECT
    USING (
        user_id IS NULL OR
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM users u 
            WHERE u.id = auth.uid() AND u.role = 'admin'
        )
    );

-- Allow authenticated users to create companies
CREATE POLICY companies_authenticated_insert ON companies
    FOR INSERT
    WITH CHECK (
        auth.uid() IS NOT NULL AND
        (user_id = auth.uid() OR EXISTS (
            SELECT 1 FROM users u 
            WHERE u.id = auth.uid() AND u.role = 'admin'
        ))
    );

-- Allow owners to update their companies
CREATE POLICY companies_owner_update ON companies
    FOR UPDATE
    USING (
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM users u 
            WHERE u.id = auth.uid() AND u.role = 'admin'
        )
    );

-- Allow owners to delete their companies
CREATE POLICY companies_owner_delete ON companies
    FOR DELETE
    USING (
        user_id = auth.uid() OR
        EXISTS (
            SELECT 1 FROM users u 
            WHERE u.id = auth.uid() AND u.role = 'admin'
        )
    );

-- ============================================================
-- Financial Reports Table
-- ============================================================

-- Public read access through parent company
CREATE POLICY financials_public_read ON financials
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            WHERE c.id = financials.company_id
            AND (
                c.user_id IS NULL OR
                c.user_id = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM users u 
                    WHERE u.id = auth.uid() AND u.role = 'admin'
                )
            )
        )
    );

-- Modify access through parent company ownership
CREATE POLICY financials_owner_modify ON financials
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            WHERE c.id = financials.company_id
            AND (
                c.user_id = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM users u 
                    WHERE u.id = auth.uid() AND u.role = 'admin'
                )
            )
        )
    );

-- ============================================================
-- Stock Prices Table
-- ============================================================

-- Public read access through parent company
CREATE POLICY stock_prices_public_read ON stock_prices
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            WHERE c.id = stock_prices.company_id
            AND (
                c.user_id IS NULL OR
                c.user_id = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM users u 
                    WHERE u.id = auth.uid() AND u.role = 'admin'
                )
            )
        )
    );

-- Modify access through parent company ownership
CREATE POLICY stock_prices_owner_modify ON stock_prices
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            WHERE c.id = stock_prices.company_id
            AND (
                c.user_id = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM users u 
                    WHERE u.id = auth.uid() AND u.role = 'admin'
                )
            )
        )
    );

-- ============================================================
-- Analyst Ratings Table
-- ============================================================

-- Public read access through parent company
CREATE POLICY analyst_ratings_public_read ON analyst_ratings
    FOR SELECT
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            WHERE c.id = analyst_ratings.company_id
            AND (
                c.user_id IS NULL OR
                c.user_id = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM users u 
                    WHERE u.id = auth.uid() AND u.role = 'admin'
                )
            )
        )
    );

-- Modify access through parent company ownership
CREATE POLICY analyst_ratings_owner_modify ON analyst_ratings
    FOR ALL
    USING (
        EXISTS (
            SELECT 1 FROM companies c
            WHERE c.id = analyst_ratings.company_id
            AND (
                c.user_id = auth.uid() OR
                EXISTS (
                    SELECT 1 FROM users u 
                    WHERE u.id = auth.uid() AND u.role = 'admin'
                )
            )
        )
    );

-- ============================================================
-- Helper Functions
-- ============================================================

-- Function to check if current user is admin
CREATE OR REPLACE FUNCTION is_admin()
RETURNS BOOLEAN AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1 FROM users 
        WHERE id = auth.uid() AND role = 'admin'
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get current user role
CREATE OR REPLACE FUNCTION get_current_user_role()
RETURNS TEXT AS $$
BEGIN
    RETURN (
        SELECT role FROM users 
        WHERE id = auth.uid()
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
