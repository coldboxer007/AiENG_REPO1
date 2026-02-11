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
    database_url: str = (
        "postgresql+asyncpg://postgres:postgres@localhost:5432/financial_mcp"
    )
    database_url_sync: str = (
        "postgresql+psycopg2://postgres:postgres@localhost:5432/financial_mcp"
    )

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # MCP
    mcp_server_name: str = "financial-data-mcp"
    mcp_server_version: str = "0.1.0"

    # FastAPI
    fastapi_host: str = "0.0.0.0"
    fastapi_port: int = 8000


settings = Settings()
