"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central settings pulled from .env / environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/financial_mcp"
    database_url_sync: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/financial_mcp"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # MCP
    mcp_server_name: str = "financial-data-mcp"
    mcp_server_version: str = "0.1.0"

    # FastAPI
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000

    # Security & RLS
    enable_rls: bool = False
    """Enable Row Level Security. Should be True for production Supabase deployments."""

    supabase_jwt_secret: str | None = None
    """JWT secret for Supabase Auth verification. Required if enable_rls=True."""

    admin_api_key: str | None = None
    """API key for admin operations. Used to bypass RLS for system operations."""

    cursor_secret: str = "change-me-in-production"
    """Secret key for signing pagination cursors. Rotate regularly in production."""

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_default: int = 60
    rate_limit_compare: int = 30

    # Security Headers
    enable_security_headers: bool = True
    allowed_origins: str = "*"
    """Comma-separated list of allowed CORS origins. Use '*' only in development."""


settings = Settings()
