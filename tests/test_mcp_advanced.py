"""Tests for MCP resources, prompts, and SSE transport."""

from __future__ import annotations

import json
import pytest
from httpx import AsyncClient

from app.mcp.sse_server import app as sse_app
from app.mcp.server import create_mcp_server, TOOL_DEFINITIONS


class TestMCPTools:
    """Test MCP tool definitions and schemas."""

    def test_all_tools_have_definitions(self):
        """Test that all 8 tools have proper JSON schema definitions."""
        assert len(TOOL_DEFINITIONS) == 8

        tool_names = [t.name for t in TOOL_DEFINITIONS]
        expected_tools = [
            "search_companies",
            "get_company_profile",
            "get_financial_report",
            "compare_companies",
            "get_stock_price_history",
            "get_analyst_ratings",
            "screen_stocks",
            "get_sector_overview",
        ]

        for tool in expected_tools:
            assert tool in tool_names, f"Missing tool: {tool}"

    def test_tool_schemas_have_descriptions(self):
        """Test that all tools have descriptions in their schemas."""
        for tool in TOOL_DEFINITIONS:
            assert tool.description, f"Tool {tool.name} missing description"
            assert len(tool.description) > 10, f"Tool {tool.name} description too short"

    def test_tool_input_schemas_are_valid(self):
        """Test that all tools have valid JSON schema input definitions."""
        for tool in TOOL_DEFINITIONS:
            schema = tool.inputSchema
            assert schema.get("type") == "object", f"Tool {tool.name} schema must be object type"
            assert "properties" in schema, f"Tool {tool.name} schema missing properties"

    def test_search_companies_schema(self):
        """Test search_companies has proper pagination schema."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "search_companies")
        schema = tool.inputSchema

        assert "query" in schema["properties"]
        assert "limit" in schema["properties"]
        assert "cursor" in schema["properties"]
        assert schema["properties"]["limit"].get("minimum") == 1
        assert schema["properties"]["limit"].get("maximum") == 50

    def test_compare_companies_schema(self):
        """Test compare_companies has proper enum constraints."""
        tool = next(t for t in TOOL_DEFINITIONS if t.name == "compare_companies")
        schema = tool.inputSchema

        assert "tickers" in schema["properties"]
        assert "metric" in schema["properties"]
        assert "enum" in schema["properties"]["metric"]
        expected_metrics = ["revenue", "net_income", "market_cap", "operating_margin", "net_margin"]
        assert set(schema["properties"]["metric"]["enum"]) == set(expected_metrics)


class TestMCPResources:
    """Test MCP resources are properly defined."""

    def test_server_creation(self):
        """Test that MCP server can be created."""
        server = create_mcp_server()
        assert server is not None


class TestSSETransport:
    """Test SSE (Server-Sent Events) transport."""

    def test_sse_app_imports(self):
        """Test that SSE app can be imported."""
        from app.mcp.sse_server import app

        assert app is not None


class TestToolResponseFormat:
    """Test tool response format compliance."""

    def test_tool_response_structure(self):
        """Test that tool response helper creates proper structure."""
        from app.mcp.tools import _ok

        result = _ok("test_tool", {"data": "value"}, elapsed=1.5, row_count=5)

        # Should have standard response fields
        assert "tool" in result
        assert "ok" in result
        assert "data" in result
        assert "error" in result
        assert "meta" in result

        # Should be successful
        assert result["ok"] is True
        assert result["tool"] == "test_tool"
        assert result["meta"]["execution_ms"] == 1.5
        assert result["meta"]["row_count"] == 5

    def test_tool_error_response_structure(self):
        """Test that error response helper creates proper structure."""
        from app.mcp.tools import _error_response

        result = _error_response("test_tool", "TEST_ERROR", "Test message", elapsed=1.0)

        # Should have error structure
        assert result["ok"] is False
        assert "error" in result
        assert result["error"]["error_code"] == "TEST_ERROR"
        assert "message" in result["error"]


class TestDatabaseIndexes:
    """Test that database indexes are properly defined."""

    def test_company_model_has_indexes(self):
        """Test Company model has expected indexes."""
        from app.models.company import Company

        index_names = [idx.name for idx in Company.__table__.indexes]
        assert "ix_companies_ticker" in index_names
        assert "ix_companies_sector" in index_names
        assert "ix_companies_market_cap" in index_names

    def test_financial_model_has_indexes(self):
        """Test Financial model has expected indexes."""
        from app.models.financial import Financial

        index_names = [idx.name for idx in Financial.__table__.indexes]
        assert "ix_financials_company_id" in index_names
        assert "ix_financials_company_year_quarter" in index_names

    def test_stock_price_model_has_indexes(self):
        """Test StockPrice model has expected indexes."""
        from app.models.stock_price import StockPrice

        index_names = [idx.name for idx in StockPrice.__table__.indexes]
        assert "ix_stock_prices_company_id" in index_names
        assert "ix_stock_prices_date" in index_names
        assert "ix_stock_prices_company_date" in index_names

    def test_analyst_rating_model_has_indexes(self):
        """Test AnalystRating model has expected indexes."""
        from app.models.analyst_rating import AnalystRating

        index_names = [idx.name for idx in AnalystRating.__table__.indexes]
        assert "ix_analyst_ratings_company_id" in index_names
        assert "ix_analyst_ratings_date" in index_names
