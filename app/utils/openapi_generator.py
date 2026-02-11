"""OpenAPI 3.0 specification generator for MCP tools.

This module converts MCP tool definitions into OpenAPI 3.0 specification,
allowing standard HTTP clients to interact with the MCP server via SSE transport.
"""

from __future__ import annotations

import json
from typing import Any

from mcp.types import Tool

from app.config import settings
from app.mcp.server import TOOL_DEFINITIONS


class OpenAPIGenerator:
    """Convert MCP tool schemas to OpenAPI 3.0 specification.

    Example:
        generator = OpenAPIGenerator()
        spec = generator.generate_spec()
        print(json.dumps(spec, indent=2))
    """

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.spec: dict[str, Any] = {}

    def generate_spec(self) -> dict[str, Any]:
        """Generate complete OpenAPI 3.0 specification.

        Returns:
            Complete OpenAPI 3.0 spec as dictionary
        """
        self.spec = {
            "openapi": "3.0.3",
            "info": self._build_info(),
            "servers": self._build_servers(),
            "paths": self._build_paths(),
            "components": self._build_components(),
            "tags": self._build_tags(),
        }
        return self.spec

    def _build_info(self) -> dict[str, Any]:
        """Build OpenAPI info section."""
        return {
            "title": f"{settings.mcp_server_name} API",
            "description": (
                "Financial Data MCP Server API. "
                "This API exposes financial data tools via HTTP/SSE transport "
                "following the Model Context Protocol specification."
            ),
            "version": settings.mcp_server_version,
            "contact": {
                "name": "API Support",
                "email": "api@example.com",
            },
            "license": {
                "name": "MIT",
                "url": "https://opensource.org/licenses/MIT",
            },
        }

    def _build_servers(self) -> list[dict[str, Any]]:
        """Build OpenAPI servers section."""
        return [
            {
                "url": self.server_url,
                "description": "Local development server",
            },
            {
                "url": "https://api.production.example.com",
                "description": "Production server",
            },
        ]

    def _build_paths(self) -> dict[str, Any]:
        """Build OpenAPI paths section with all tool endpoints."""
        paths: dict[str, Any] = {}

        # Health endpoint
        paths["/health"] = {
            "get": {
                "tags": ["Health"],
                "summary": "Health check",
                "description": "Check if the server is running and healthy.",
                "operationId": "healthCheck",
                "responses": {
                    "200": {
                        "description": "Server is healthy",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/HealthResponse"},
                                "example": {
                                    "status": "ok",
                                    "server": "financial-data-mcp",
                                    "version": "0.1.0",
                                },
                            }
                        },
                    }
                },
            }
        }

        # SSE endpoint for real-time updates
        paths["/sse"] = {
            "get": {
                "tags": ["Streaming"],
                "summary": "Server-Sent Events stream",
                "description": (
                    "Establish a Server-Sent Events connection for real-time "
                    "communication with the MCP server."
                ),
                "operationId": "sseStream",
                "responses": {
                    "200": {
                        "description": "SSE stream established",
                        "content": {
                            "text/event-stream": {
                                "schema": {
                                    "type": "string",
                                    "format": "binary",
                                }
                            }
                        },
                    }
                },
            }
        }

        # Tools list endpoint
        paths["/tools"] = {
            "get": {
                "tags": ["Tools"],
                "summary": "List all available tools",
                "description": "Get a list of all MCP tools with their schemas.",
                "operationId": "listTools",
                "responses": {
                    "200": {
                        "description": "List of tools",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ToolsList"}
                            }
                        },
                    }
                },
            }
        }

        # Individual tool execution endpoints
        for tool in TOOL_DEFINITIONS:
            path = f"/tools/{tool.name}"
            paths[path] = self._build_tool_path(tool)

        return paths

    def _build_tool_path(self, tool: Tool) -> dict[str, Any]:
        """Build OpenAPI path item for a single tool."""
        schema = tool.inputSchema

        # Convert JSON Schema to OpenAPI Schema
        request_schema = self._convert_json_schema_to_openapi(schema)

        # Build example request
        example_request = self._generate_example_request(schema)

        # Build example response
        example_response = self._generate_example_response(tool.name)

        return {
            "post": {
                "tags": ["Tools"],
                "summary": (
                    tool.description.split(".")[0] if tool.description else f"Execute {tool.name}"
                ),
                "description": tool.description or f"Execute the {tool.name} tool",
                "operationId": tool.name,
                "requestBody": {
                    "required": True,
                    "description": f"Parameters for {tool.name}",
                    "content": {
                        "application/json": {
                            "schema": request_schema,
                            "example": example_request,
                        }
                    },
                },
                "responses": {
                    "200": {
                        "description": "Tool executed successfully",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": f"#/components/schemas/ToolResponse"},
                                "example": example_response,
                            }
                        },
                    },
                    "400": {
                        "description": "Invalid request parameters",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "429": {
                        "description": "Rate limit exceeded",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                    "500": {
                        "description": "Internal server error",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ErrorResponse"}
                            }
                        },
                    },
                },
            }
        }

    def _convert_json_schema_to_openapi(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Convert MCP JSON Schema to OpenAPI Schema format."""
        openapi_schema: dict[str, Any] = {
            "type": schema.get("type", "object"),
        }

        # Convert properties
        if "properties" in schema:
            openapi_schema["properties"] = {}
            for prop_name, prop_schema in schema["properties"].items():
                openapi_schema["properties"][prop_name] = self._convert_property_schema(prop_schema)

        # Convert required fields
        if "required" in schema:
            openapi_schema["required"] = schema["required"]

        return openapi_schema

    def _convert_property_schema(self, prop: dict[str, Any]) -> dict[str, Any]:
        """Convert a single property schema."""
        result: dict[str, Any] = {}

        # Type mapping
        prop_type = prop.get("type", "string")
        result["type"] = prop_type

        # Description
        if "description" in prop:
            result["description"] = prop["description"]

        # Default value
        if "default" in prop:
            result["default"] = prop["default"]

        # Enum values
        if "enum" in prop:
            result["enum"] = prop["enum"]

        # Number constraints
        if prop_type in ["integer", "number"]:
            if "minimum" in prop:
                result["minimum"] = prop["minimum"]
            if "maximum" in prop:
                result["maximum"] = prop["maximum"]

        # String constraints
        if prop_type == "string":
            if "format" in prop:
                result["format"] = prop["format"]
            if "minLength" in prop:
                result["minLength"] = prop["minLength"]
            if "maxLength" in prop:
                result["maxLength"] = prop["maxLength"]

        # Array items
        if prop_type == "array" and "items" in prop:
            result["items"] = self._convert_property_schema(prop["items"])

        return result

    def _generate_example_request(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate an example request based on schema."""
        example: dict[str, Any] = {}

        if "properties" not in schema:
            return example

        for prop_name, prop_schema in schema["properties"].items():
            # Skip if it has a default and is not required
            if "default" in prop_schema and prop_name not in schema.get("required", []):
                continue

            prop_type = prop_schema.get("type", "string")

            if prop_type == "string":
                if prop_name == "ticker":
                    example[prop_name] = "AAPL"
                elif prop_name == "query":
                    example[prop_name] = "Apple"
                elif prop_name == "sector":
                    example[prop_name] = "Technology"
                elif "date" in prop_name.lower():
                    example[prop_name] = "2024-01-01"
                elif "metric" in prop_schema.get("enum", []):
                    example[prop_name] = prop_schema["enum"][0]
                else:
                    example[prop_name] = f"example_{prop_name}"

            elif prop_type == "integer":
                if prop_name == "limit":
                    example[prop_name] = 10
                elif prop_name == "years":
                    example[prop_name] = 3
                else:
                    example[prop_name] = 1

            elif prop_type == "number":
                if prop_name == "min_market_cap":
                    example[prop_name] = 1000000000
                elif prop_name == "max_debt_to_equity":
                    example[prop_name] = 2.5
                else:
                    example[prop_name] = 100.0

            elif prop_type == "array":
                if prop_name == "tickers":
                    example[prop_name] = ["AAPL", "MSFT", "GOOGL"]
                else:
                    example[prop_name] = []

            elif prop_type == "boolean":
                example[prop_name] = True

        return example

    def _generate_example_response(self, tool_name: str) -> dict[str, Any]:
        """Generate an example response for a tool."""
        examples: dict[str, dict[str, Any]] = {
            "search_companies": {
                "tool": "search_companies",
                "ok": True,
                "data": {
                    "companies": [
                        {
                            "ticker": "AAPL",
                            "name": "Apple Inc.",
                            "sector": "Technology",
                            "market_cap": 3000000000000,
                        }
                    ],
                    "next_cursor": None,
                    "has_more": False,
                },
                "error": None,
                "meta": {
                    "execution_ms": 12.5,
                    "row_count": 1,
                },
            },
            "get_company_profile": {
                "tool": "get_company_profile",
                "ok": True,
                "data": {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "sector": "Technology",
                    "industry": "Consumer Electronics",
                    "market_cap": 3000000000000,
                    "employees": 154000,
                    "ceo": "Tim Cook",
                    "founded_year": 1976,
                    "country": "US",
                },
                "error": None,
                "meta": {
                    "execution_ms": 8.3,
                    "row_count": 1,
                },
            },
            "default": {
                "tool": tool_name,
                "ok": True,
                "data": {},
                "error": None,
                "meta": {
                    "execution_ms": 10.0,
                    "row_count": 1,
                },
            },
        }

        return examples.get(tool_name, examples["default"])

    def _build_components(self) -> dict[str, Any]:
        """Build OpenAPI components section with schemas."""
        return {
            "schemas": {
                "HealthResponse": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string", "example": "ok"},
                        "server": {"type": "string", "example": settings.mcp_server_name},
                        "version": {"type": "string", "example": settings.mcp_server_version},
                    },
                    "required": ["status"],
                },
                "ToolsList": {
                    "type": "object",
                    "properties": {
                        "tools": {
                            "type": "array",
                            "items": {"$ref": "#/components/schemas/ToolDefinition"},
                        }
                    },
                },
                "ToolDefinition": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "description": {"type": "string"},
                        "inputSchema": {"type": "object"},
                    },
                },
                "ToolResponse": {
                    "type": "object",
                    "properties": {
                        "tool": {
                            "type": "string",
                            "description": "Name of the tool that was executed",
                        },
                        "ok": {
                            "type": "boolean",
                            "description": "Whether the execution was successful",
                        },
                        "data": {
                            "type": "object",
                            "description": "Response data (varies by tool)",
                        },
                        "error": {
                            "type": "object",
                            "nullable": True,
                            "properties": {
                                "error_code": {"type": "string"},
                            },
                        },
                        "meta": {
                            "type": "object",
                            "properties": {
                                "execution_ms": {"type": "number"},
                                "row_count": {"type": "integer"},
                            },
                        },
                    },
                    "required": ["tool", "ok", "data", "error", "meta"],
                },
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "tool": {"type": "string"},
                        "ok": {"type": "boolean", "example": False},
                        "data": {"type": "object", "nullable": True},
                        "error": {
                            "type": "object",
                            "properties": {
                                "error_code": {"type": "string"},
                                "message": {"type": "string"},
                                "hint": {"type": "string"},
                            },
                        },
                        "meta": {
                            "type": "object",
                            "properties": {
                                "execution_ms": {"type": "number"},
                                "row_count": {"type": "integer"},
                            },
                        },
                    },
                },
            },
            "securitySchemes": {
                "ApiKeyAuth": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key for authentication",
                },
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT token for authentication",
                },
            },
        }

    def _build_tags(self) -> list[dict[str, str]]:
        """Build OpenAPI tags section."""
        return [
            {"name": "Health", "description": "Health check endpoints"},
            {"name": "Tools", "description": "MCP tool execution endpoints"},
            {"name": "Streaming", "description": "Server-Sent Events streaming"},
        ]

    def to_json(self, indent: int = 2) -> str:
        """Generate OpenAPI spec as JSON string."""
        spec = self.generate_spec()
        return json.dumps(spec, indent=indent, default=str)


# Global generator instance
openapi_generator = OpenAPIGenerator()
