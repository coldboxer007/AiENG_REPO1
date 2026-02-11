"""MCP server bootstrap – registers tools, resources, prompts and runs transports."""

from __future__ import annotations

import asyncio
import json
import logging

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent, Resource, Prompt, PromptMessage, PromptArgument

from sqlalchemy import select, func

from app.config import settings
from app.db import async_session_factory
from app.models.company import Company
from app.mcp.tools import (
    handle_search_companies,
    handle_get_company_profile,
    handle_get_financial_report,
    handle_compare_companies,
    handle_get_stock_price_history,
    handle_get_analyst_ratings,
    handle_screen_stocks,
    handle_get_sector_overview,
)

logger = logging.getLogger("mcp.server")

# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[Tool] = [
    Tool(
        name="search_companies",
        description=(
            "Search for companies by name or ticker with cursor-based pagination. "
            "Returns matching companies with ticker, name, sector, and market_cap."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search term (name or ticker substring)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max results to return (1-50)",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                },
                "cursor": {
                    "type": "string",
                    "description": "Opaque pagination cursor from a previous response (optional)",
                },
            },
            "required": ["query"],
        },
    ),
    Tool(
        name="get_company_profile",
        description=("Get full company profile including market_cap, employees, and description."),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
            },
            "required": ["ticker"],
        },
    ),
    Tool(
        name="get_financial_report",
        description=(
            "Get financial report for a company. If year and period (quarter) are provided, "
            "return that specific report. Otherwise return per-year revenue, net_income, "
            "margins, and CAGR for recent years."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "years": {
                    "type": "integer",
                    "description": "Number of years of history (used when year/period not specified)",
                    "default": 3,
                },
                "year": {"type": "integer", "description": "Specific fiscal year (optional)"},
                "period": {
                    "type": "integer",
                    "description": "Quarter number 1-4 (optional, use with year)",
                },
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
                    "enum": [
                        "revenue",
                        "net_income",
                        "market_cap",
                        "operating_margin",
                        "net_margin",
                    ],
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
            "Get daily OHLC prices, simple returns, and max drawdown for a date range. "
            "Supports cursor-based pagination for large date ranges."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Company ticker symbol"},
                "start_date": {
                    "type": "string",
                    "format": "date",
                    "description": "Start date (YYYY-MM-DD)",
                },
                "end_date": {
                    "type": "string",
                    "format": "date",
                    "description": "End date (YYYY-MM-DD)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Max rows per page (1-500)",
                    "default": 100,
                    "minimum": 1,
                    "maximum": 500,
                },
                "cursor": {
                    "type": "string",
                    "description": "Opaque pagination cursor from a previous response (optional)",
                },
            },
            "required": ["ticker", "start_date", "end_date"],
        },
    ),
    Tool(
        name="get_analyst_ratings",
        description=(
            "Get analyst ratings: rating counts, average price target, previous ratings, "
            "and 5 most recent ratings."
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
        name="screen_stocks",
        description=(
            "Screen stocks by sector, market cap range, minimum revenue, and max debt-to-equity. "
            "Returns matching companies with key financial metrics."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sector": {"type": "string", "description": "Filter by sector (optional)"},
                "min_market_cap": {
                    "type": "number",
                    "description": "Minimum market cap in USD (optional)",
                },
                "max_market_cap": {
                    "type": "number",
                    "description": "Maximum market cap in USD (optional)",
                },
                "min_revenue": {
                    "type": "number",
                    "description": "Minimum revenue in USD (optional)",
                },
                "max_debt_to_equity": {
                    "type": "number",
                    "description": "Maximum debt-to-equity ratio (optional)",
                },
            },
            "required": [],
        },
    ),
    Tool(
        name="get_sector_overview",
        description=(
            "Get aggregated statistics for a specific sector: average market cap, "
            "average PE ratio, and average revenue growth."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "sector": {
                    "type": "string",
                    "description": "Sector name (e.g. Technology, Healthcare)",
                },
            },
            "required": ["sector"],
        },
    ),
]

TOOL_HANDLERS = {
    "search_companies": handle_search_companies,
    "get_company_profile": handle_get_company_profile,
    "get_financial_report": handle_get_financial_report,
    "compare_companies": handle_compare_companies,
    "get_stock_price_history": handle_get_stock_price_history,
    "get_analyst_ratings": handle_get_analyst_ratings,
    "screen_stocks": handle_screen_stocks,
    "get_sector_overview": handle_get_sector_overview,
}

# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_mcp_server() -> Server:
    """Create and configure the MCP server instance."""
    server = Server(settings.mcp_server_name)

    # ── Tools ─────────────────────────────────────────────────────────────

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

    # ── Resources ─────────────────────────────────────────────────────────

    @server.list_resources()
    async def list_resources() -> list[Resource]:
        """Expose reusable data resources for MCP clients."""
        return [
            Resource(
                uri="financial://metrics",
                name="Available Metrics",
                description="List of all comparable financial metrics with descriptions",
                mimeType="application/json",
            ),
        ]

    @server.read_resource()
    async def read_resource(uri: str) -> str:
        """Read a named resource."""
        if str(uri) == "financial://metrics":
            return json.dumps(
                {
                    "metrics": [
                        "revenue",
                        "net_income",
                        "market_cap",
                        "operating_margin",
                        "net_margin",
                    ],
                    "descriptions": {
                        "revenue": "Total revenue in USD",
                        "net_income": "Net income after taxes in USD",
                        "market_cap": "Market capitalisation in USD",
                        "operating_margin": "Operating income / revenue (ratio)",
                        "net_margin": "Net income / revenue (ratio)",
                    },
                },
                indent=2,
            )

        raise ValueError(f"Unknown resource: {uri}")

    # ── Prompts ───────────────────────────────────────────────────────────

    @server.list_prompts()
    async def list_prompts() -> list[Prompt]:
        """Provide prompt templates for common financial analyses."""
        return [
            Prompt(
                name="sector_analysis",
                description="Analyse all companies in a specific sector",
                arguments=[
                    PromptArgument(
                        name="sector",
                        description="Sector to analyse (e.g. Technology, Healthcare)",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="stock_momentum",
                description="Find stocks with strong recent price momentum",
                arguments=[
                    PromptArgument(
                        name="days",
                        description="Lookback period in days (default 30)",
                        required=False,
                    ),
                ],
            ),
        ]

    @server.get_prompt()
    async def get_prompt(name: str, arguments: dict | None = None) -> list[PromptMessage]:
        """Return a filled prompt template."""
        args = arguments or {}

        if name == "sector_analysis":
            sector = args.get("sector", "Technology")
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Analyse the {sector} sector using these steps:\n\n"
                            f"1. Use search_companies to find all {sector} companies\n"
                            "2. For each company, get_financial_report for the last 3 years\n"
                            "3. Use compare_companies to rank them by revenue growth (revenue)\n"
                            "4. Get get_analyst_ratings for the top 3 performers\n"
                            "5. Summarise which companies are best positioned for growth\n\n"
                            "Focus on revenue trends, profitability margins, and analyst sentiment."
                        ),
                    ),
                )
            ]

        if name == "stock_momentum":
            days = int(args.get("days", 30))
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=(
                            f"Find stocks with strong momentum in the last {days} days:\n\n"
                            "1. For each company in the database:\n"
                            f"   - Use get_stock_price_history for the last {days} days\n"
                            "   - Note the total_return_pct\n"
                            "2. Rank companies by total return\n"
                            "3. For top 5 performers:\n"
                            "   - Get get_analyst_ratings\n"
                            "   - Check if analyst sentiment aligns with price momentum\n"
                            "4. Identify momentum + positive analyst sentiment plays"
                        ),
                    ),
                )
            ]

        raise ValueError(f"Unknown prompt: {name}")

    return server


# ---------------------------------------------------------------------------
# Entry-point: run MCP server over stdio
# ---------------------------------------------------------------------------


async def run_mcp_server() -> None:
    """Start the MCP server using stdio transport."""
    server = create_mcp_server()
    logger.info(
        "Starting MCP server '%s' v%s (stdio)",
        settings.mcp_server_name,
        settings.mcp_server_version,
    )

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
