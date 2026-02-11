"""Shared ToolResponse envelope and error schema."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Structured error returned when a tool fails."""

    error_code: str
    message: str
    hint: str | None = None


class Meta(BaseModel):
    """Execution metadata attached to every response."""

    execution_ms: float = Field(..., description="Wall-clock milliseconds")
    row_count: int | None = Field(None, description="Number of rows returned")


class ToolResponse(BaseModel):
    """Standard envelope for every tool result."""

    tool: str
    ok: bool
    data: Any | None = None
    error: ErrorDetail | None = None
    meta: Meta
