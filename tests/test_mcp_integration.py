"""Integration tests for MCP server protocol – tools, resources, and prompts."""

from __future__ import annotations

import json

import pytest

from app.mcp.server import create_mcp_server, TOOL_DEFINITIONS


@pytest.mark.asyncio
async def test_mcp_list_tools():
    """MCP server should list all 8 tools."""
    server = create_mcp_server()
    # Access the internal handler registered via @server.list_tools()
    tools = TOOL_DEFINITIONS
    assert len(tools) == 8
    tool_names = {t.name for t in tools}
    assert tool_names == {
        "search_companies",
        "get_company_profile",
        "get_financial_report",
        "compare_companies",
        "get_stock_price_history",
        "get_analyst_ratings",
        "screen_stocks",
        "get_sector_overview",
    }


@pytest.mark.asyncio
async def test_tool_schemas_have_required_fields():
    """Every tool definition should have name, description, and inputSchema."""
    for tool in TOOL_DEFINITIONS:
        assert tool.name, "Tool must have a name"
        assert tool.description, f"Tool {tool.name} must have a description"
        assert tool.inputSchema, f"Tool {tool.name} must have an inputSchema"
        assert (
            "properties" in tool.inputSchema
        ), f"Tool {tool.name} inputSchema must have properties"


@pytest.mark.asyncio
async def test_search_companies_schema_has_cursor():
    """search_companies schema should include a cursor parameter."""
    search_tool = next(t for t in TOOL_DEFINITIONS if t.name == "search_companies")
    props = search_tool.inputSchema["properties"]
    assert "cursor" in props, "search_companies should support cursor pagination"
    assert "limit" in props


@pytest.mark.asyncio
async def test_stock_history_schema_has_cursor():
    """get_stock_price_history schema should include cursor + limit."""
    tool = next(t for t in TOOL_DEFINITIONS if t.name == "get_stock_price_history")
    props = tool.inputSchema["properties"]
    assert "cursor" in props
    assert "limit" in props
