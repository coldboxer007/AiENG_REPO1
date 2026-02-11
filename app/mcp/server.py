"""MCP server bootstrap – registers tools and runs the stdio transport."""

from __future__ import annotations

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from app.config import settings
from app.mcp.tools import (
    handle_search_companies,
    handle_get_company_profile,
    handle_get_financial_summary,
    handle_compare_companies,
    handle_get_stock_price_history,
    handle_get_analyst_consensus,
)

logger = logging.getLogger("mcp.server")

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="search_companies",
        description=(
            "Search for companies by name or ticker. "
            "Returns matching companies with ticker, name, sector, and market_cap."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search term (name or ticker substring)"},
                "limit": {"type": "integer", "description": "Max results to return", "default": 10},
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_company_profile",
        description=(
            "Get full company profile including market_cap, employees, and description."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
            },
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_financial_summary",
        description=(
            "Get per-year revenue, net_income, margins, and CAGR for a company."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "years": {"type": "integer", "description": "Number of years of history", "default": 3},
            },
            "required": ["ticker"],
        },
    ),
    Tool(
        name="compare_companies",
        description=(
            "Compare multiple companies on a single financial metric. "
            "Returns a comparison table, the winner, and a short explanation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "tickers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of ticker symbols (min 2)",
                },
                "metric": {
                    "type": "string",
                    "enum": ["revenue", "net_income", "market_cap", "operating_margin", "net_margin"],
                    "description": "Metric to compare",
                },
                "year": {
                    "type": "integer",
                    "description": "Optional specific year to compare (defaults to latest)",
                },
            },
            "required": ["tickers", "metric"],
        },
    ),
    Tool(
        name="get_stock_price_history",
        description=(
            "Get daily OHLC prices, simple returns, and max drawdown for a date range."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "start_date": {"type": "string", "format": "date", "description": "Start date (YYYY-MM-DD)"},
                "end_date": {"type": "string", "format": "date", "description": "End date (YYYY-MM-DD)"},
            },
            "required": ["ticker", "start_date", "end_date"],
        },
    ),
    Tool(
        name="get_analyst_consensus",
        description=(
            "Get analyst consensus: rating counts, average price target, and 5 most recent ratings."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
            },
            "required": ["ticker"],
        },
    ),
]

TOOL_HANDLERS = {
    "search_companies": handle_search_companies,
    "get_company_profile": handle_get_company_profile,
    "get_financial_summary": handle_get_financial_summary,
    "compare_companies": handle_compare_companies,
    "get_stock_price_history": handle_get_stock_price_history,
    "get_analyst_consensus": handle_get_analyst_consensus,
}

# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_mcp_server() -> Server:
    """Create and configure the MCP server instance."""
    server = Server(settings.mcp_server_name)

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return TOOL_DEFINITIONS

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list[TextContent]:
        handler = TOOL_HANDLERS.get(name)
        if handler is None:
            error_payload = {
                "tool": name,
                "ok": False,
                "error": {
                    "error_code": "UNKNOWN_TOOL",
                    "message": f"Tool '{name}' is not registered",
                    "hint": f"Available tools: {list(TOOL_HANDLERS.keys())}",
                },
                "meta": {"execution_ms": 0, "row_count": 0},
            }
            return [TextContent(type="text", text=json.dumps(error_payload, default=str))]

        result = await handler(arguments or {})
        return [TextContent(type="text", text=json.dumps(result, default=str))]

    return server


# ---------------------------------------------------------------------------
# Entry-point: run MCP server over stdio
# ---------------------------------------------------------------------------


async def run_mcp_server() -> None:
    """Start the MCP server using stdio transport."""
    server = create_mcp_server()
    logger.info("Starting MCP server '%s' v%s (stdio)", settings.mcp_server_name, settings.mcp_server_version)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main() -> None:
    """CLI entry-point."""
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run_mcp_server())


if __name__ == "__main__":
    main()
