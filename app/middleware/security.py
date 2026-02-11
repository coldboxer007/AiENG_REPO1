"""Security headers middleware for OWASP compliance.

This module provides middleware for adding security headers to all HTTP responses,
following OWASP Secure Headers Project recommendations.
"""

from __future__ import annotations

import uuid
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add OWASP-recommended security headers to all responses.

    This middleware implements the following security headers:
    - Strict-Transport-Security (HSTS)
    - X-Content-Type-Options
    - X-Frame-Options
    - X-XSS-Protection
    - Content-Security-Policy
    - Referrer-Policy
    - Permissions-Policy
    - X-Request-ID
    - X-RateLimit headers (when rate limiting is active)

    Usage:
        app.add_middleware(SecurityHeadersMiddleware)
    """

    def __init__(self, app: Callable, enabled: bool = True):
        super().__init__(app)
        self.enabled = enabled if settings.enable_security_headers else False

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request and add security headers to response."""
        # Generate request ID for tracing
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        # Process the request
        response = await call_next(request)

        if not self.enabled:
            # Still add request ID even if other headers disabled
            response.headers["X-Request-ID"] = request_id
            return response

        # Add security headers
        self._add_hsts_header(response)
        self._add_content_type_options(response)
        self._add_frame_options(response)
        self._add_xss_protection(response)
        self._add_content_security_policy(response)
        self._add_referrer_policy(response)
        self._add_permissions_policy(response)
        self._add_request_id(response, request_id)

        return response

    def _add_hsts_header(self, response: Response) -> None:
        """Add Strict-Transport-Security header.

        Forces HTTPS connections for the specified duration.
        """
        # max-age: 1 year (31536000 seconds)
        # includeSubDomains: Apply to all subdomains
        # preload: Allow browser preload lists
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    def _add_content_type_options(self, response: Response) -> None:
        """Add X-Content-Type-Options header.

        Prevents MIME type sniffing which can lead to XSS attacks.
        """
        response.headers["X-Content-Type-Options"] = "nosniff"

    def _add_frame_options(self, response: Response) -> None:
        """Add X-Frame-Options header.

        Prevents clickjacking by controlling iframes.
        """
        response.headers["X-Frame-Options"] = "DENY"

    def _add_xss_protection(self, response: Response) -> None:
        """Add X-XSS-Protection header.

        Legacy browser XSS protection (deprecated but still useful).
        """
        response.headers["X-XSS-Protection"] = "1; mode=block"

    def _add_content_security_policy(self, response: Response) -> None:
        """Add Content-Security-Policy header.

        Mitigates XSS attacks by controlling resource loading.
        """
        # Strict CSP for API server
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.redoc.ly",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data: https:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'self'",
            "form-action 'self'",
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

    def _add_referrer_policy(self, response: Response) -> None:
        """Add Referrer-Policy header.

        Controls how much referrer information is shared.
        """
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    def _add_permissions_policy(self, response: Response) -> None:
        """Add Permissions-Policy header.

        Controls browser features and APIs.
        """
        permissions = [
            "accelerometer=()",
            "camera=()",
            "geolocation=()",
            "gyroscope=()",
            "magnetometer=()",
            "microphone=()",
            "payment=()",
            "usb=()",
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions)

    def _add_request_id(self, response: Response, request_id: str) -> None:
        """Add X-Request-ID header for request tracing."""
        response.headers["X-Request-ID"] = request_id


class CORSMiddleware:
    """CORS middleware with configurable origins.

    Usage:
        from fastapi.middleware.cors import CORSMiddleware as FastAPICORSMiddleware
        app.add_middleware(
            FastAPICORSMiddleware,
            allow_origins=parse_cors_origins(settings.allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    """

    pass  # Documentation only - use FastAPI's built-in CORS


def parse_cors_origins(origins_string: str) -> list[str]:
    """Parse CORS origins from comma-separated string.

    Args:
        origins_string: Comma-separated list of origins, or "*" for all

    Returns:
        List of allowed origins

    Example:
        >>> parse_cors_origins("https://app1.com, https://app2.com")
        ["https://app1.com", "https://app2.com"]

        >>> parse_cors_origins("*")
        ["*"]
    """
    if origins_string == "*":
        return ["*"]

    return [origin.strip() for origin in origins_string.split(",") if origin.strip()]


# Security header values for reference
SECURITY_HEADERS = {
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com https://cdn.redoc.ly; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: https:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self'"
    ),
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    ),
}
