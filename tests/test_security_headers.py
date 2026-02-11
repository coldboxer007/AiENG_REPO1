"""Tests for security headers middleware."""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport

from app.mcp.sse_server import app
from app.middleware.security import (
    SecurityHeadersMiddleware,
    parse_cors_origins,
    SECURITY_HEADERS,
)


class TestSecurityHeadersMiddleware:
    """Test security headers are properly added to responses."""

    @pytest.mark.asyncio
    async def test_strict_transport_security_header(self):
        """Test HSTS header is present."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert "strict-transport-security" in response.headers
            hsts = response.headers["strict-transport-security"]
            assert "max-age=31536000" in hsts
            assert "includeSubDomains" in hsts

    @pytest.mark.asyncio
    async def test_content_type_options_header(self):
        """Test X-Content-Type-Options header is present."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert "x-content-type-options" in response.headers
            assert response.headers["x-content-type-options"] == "nosniff"

    @pytest.mark.asyncio
    async def test_frame_options_header(self):
        """Test X-Frame-Options header is present."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert "x-frame-options" in response.headers
            assert response.headers["x-frame-options"] == "DENY"

    @pytest.mark.asyncio
    async def test_content_security_policy_header(self):
        """Test Content-Security-Policy header is present."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert "content-security-policy" in response.headers
            csp = response.headers["content-security-policy"]
            assert "default-src" in csp
            assert "frame-ancestors 'none'" in csp

    @pytest.mark.asyncio
    async def test_referrer_policy_header(self):
        """Test Referrer-Policy header is present."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert "referrer-policy" in response.headers
            assert "strict-origin-when-cross-origin" in response.headers["referrer-policy"]

    @pytest.mark.asyncio
    async def test_permissions_policy_header(self):
        """Test Permissions-Policy header is present."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert "permissions-policy" in response.headers
            pp = response.headers["permissions-policy"]
            assert "camera=()" in pp
            assert "microphone=()" in pp

    @pytest.mark.asyncio
    async def test_request_id_header(self):
        """Test X-Request-ID header is present and is a valid UUID."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health")

            assert "x-request-id" in response.headers
            request_id = response.headers["x-request-id"]
            # Should be a valid UUID format
            assert len(request_id) == 36
            assert request_id.count("-") == 4

    @pytest.mark.asyncio
    async def test_request_id_is_unique(self):
        """Test that each request gets a unique request ID."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response1 = await client.get("/health")
            response2 = await client.get("/health")

            id1 = response1.headers["x-request-id"]
            id2 = response2.headers["x-request-id"]

            assert id1 != id2


class TestCORSMiddleware:
    """Test CORS headers are properly configured."""

    @pytest.mark.asyncio
    async def test_cors_headers_on_health_endpoint(self):
        """Test CORS headers are present on responses."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Send a preflight OPTIONS request
            response = await client.options(
                "/health",
                headers={
                    "Origin": "http://localhost:3000",
                    "Access-Control-Request-Method": "GET",
                },
            )

            # Should have CORS headers
            assert "access-control-allow-origin" in response.headers

    @pytest.mark.asyncio
    async def test_cors_allows_configured_origins(self):
        """Test that configured origins are allowed."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/health", headers={"Origin": "http://localhost:3000"})

            assert "access-control-allow-origin" in response.headers


class TestParseCorsOrigins:
    """Test CORS origins parsing utility."""

    def test_parse_wildcard(self):
        """Test parsing wildcard origin."""
        result = parse_cors_origins("*")
        assert result == ["*"]

    def test_parse_single_origin(self):
        """Test parsing single origin."""
        result = parse_cors_origins("https://example.com")
        assert result == ["https://example.com"]

    def test_parse_multiple_origins(self):
        """Test parsing multiple comma-separated origins."""
        result = parse_cors_origins("https://app1.com, https://app2.com, https://app3.com")
        assert result == [
            "https://app1.com",
            "https://app2.com",
            "https://app3.com",
        ]

    def test_parse_strips_whitespace(self):
        """Test that whitespace is stripped from origins."""
        result = parse_cors_origins("  https://app1.com  ,  https://app2.com  ")
        assert result == ["https://app1.com", "https://app2.com"]

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = parse_cors_origins("")
        assert result == []

    def test_parse_with_empty_items(self):
        """Test parsing string with empty items between commas."""
        result = parse_cors_origins("https://app1.com,,https://app2.com")
        assert result == ["https://app1.com", "https://app2.com"]


class TestSecurityHeadersConstants:
    """Test security headers constants."""

    def test_security_headers_dict_exists(self):
        """Test that SECURITY_HEADERS constant exists."""
        assert isinstance(SECURITY_HEADERS, dict)
        assert len(SECURITY_HEADERS) > 0

    def test_security_headers_has_required_headers(self):
        """Test that all required security headers are defined."""
        required_headers = [
            "Strict-Transport-Security",
            "X-Content-Type-Options",
            "X-Frame-Options",
            "X-XSS-Protection",
            "Content-Security-Policy",
            "Referrer-Policy",
            "Permissions-Policy",
        ]

        for header in required_headers:
            assert header in SECURITY_HEADERS

    def test_hsts_has_correct_values(self):
        """Test HSTS header has correct values."""
        hsts = SECURITY_HEADERS["Strict-Transport-Security"]
        assert "max-age=31536000" in hsts
        assert "includeSubDomains" in hsts
        assert "preload" in hsts

    def test_csp_is_not_empty(self):
        """Test CSP header is not empty."""
        csp = SECURITY_HEADERS["Content-Security-Policy"]
        assert len(csp) > 0
        assert "default-src" in csp
