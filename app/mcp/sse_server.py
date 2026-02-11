"""SSE (Server-Sent Events) transport for the MCP financial-data server.

This module exposes the same MCP server over HTTP using SSE, which
is useful for web-based MCP clients, testing, and scenarios where
stdio transport is not available.

Run with:
    python -m app.mcp.sse_server

The server starts on http://0.0.0.0:8000 by default.
SSE endpoint: GET  /sse
Message post: POST /messages
Health check: GET  /health
"""

from __future__ import annotations

import json
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse

from app.config import settings
from app.mcp.server import create_mcp_server
from app.utils.openapi_generator import openapi_generator
from app.middleware.security import SecurityHeadersMiddleware, parse_cors_origins
from fastapi.middleware.cors import CORSMiddleware

logger = logging.getLogger("mcp.sse")

# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

# In-memory message queues keyed by session_id
_sessions: dict[str, asyncio.Queue] = {}
_session_counter = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown for the SSE application."""
    logger.info(
        "MCP SSE transport starting on %s:%s",
        settings.fastapi_host,
        settings.fastapi_port,
    )
    yield
    logger.info("MCP SSE transport shutting down")
    _sessions.clear()


app = FastAPI(
    title="MCP Financial Server – SSE Transport",
    version=settings.mcp_server_version,
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=parse_cors_origins(settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add security headers middleware
app.add_middleware(SecurityHeadersMiddleware)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "transport": "sse",
        "version": settings.mcp_server_version,
    }


# ---------------------------------------------------------------------------
# OpenAPI Documentation
# ---------------------------------------------------------------------------


@app.get("/openapi.json", response_class=JSONResponse)
async def openapi_json():
    """Return OpenAPI 3.0 specification."""
    spec = openapi_generator.generate_spec()
    return spec


@app.get("/docs")
async def swagger_ui():
    """Serve Swagger UI HTML page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MCP Financial Server - API Documentation</title>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui.css" />
        <style>
            html { box-sizing: border-box; overflow: -moz-scrollbars-vertical; overflow-y: scroll; }
            *, *:before, *:after { box-sizing: inherit; }
            body { margin: 0; background: #fafafa; }
            .topbar { display: none; }
        </style>
    </head>
    <body>
        <div id="swagger-ui"></div>
        <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-bundle.js"></script>
        <script src="https://unpkg.com/swagger-ui-dist@5.9.0/swagger-ui-standalone-preset.js"></script>
        <script>
            window.onload = function() {
                window.ui = SwaggerUIBundle({
                    url: '/openapi.json',
                    dom_id: '#swagger-ui',
                    deepLinking: true,
                    presets: [
                        SwaggerUIBundle.presets.apis,
                        SwaggerUIStandalonePreset
                    ],
                    plugins: [
                        SwaggerUIBundle.plugins.DownloadUrl
                    ],
                    layout: "StandaloneLayout",
                    validatorUrl: null
                });
            };
        </script>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")


@app.get("/redoc")
async def redoc():
    """Serve ReDoc HTML page."""
    html_content = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>MCP Financial Server - API Documentation</title>
        <link rel="stylesheet" href="https://fonts.googleapis.com/css?family=Montserrat:300,400,700|Roboto:300,400,700" />
        <style>
            body { margin: 0; padding: 0; }
        </style>
    </head>
    <body>
        <redoc spec-url='/openapi.json'></redoc>
        <script src="https://cdn.redoc.ly/redoc/v2.1.3/bundles/redoc.standalone.js"></script>
    </body>
    </html>
    """
    return Response(content=html_content, media_type="text/html")


# ---------------------------------------------------------------------------
# REST API Endpoints (Direct HTTP access to MCP tools)
# ---------------------------------------------------------------------------


mcp_server = create_mcp_server()


@app.get("/tools", response_class=JSONResponse)
async def list_tools():
    """List all available MCP tools with their schemas."""
    try:
        tools = await mcp_server.list_tools()
        return {
            "tools": [tool.model_dump() for tool in tools],
            "count": len(tools),
        }
    except Exception as e:
        logger.error("Error listing tools: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to list tools", "message": str(e)},
        )


@app.post("/tools/{tool_name}", response_class=JSONResponse)
async def execute_tool(tool_name: str, request: Request):
    """Execute an MCP tool directly via HTTP POST.

    This endpoint allows calling MCP tools without using SSE transport.
    Useful for simple integrations, testing, and debugging.

    Example:
        POST /tools/search_companies
        {"query": "Apple", "limit": 5}

    Returns:
        Standard ToolResponse JSON
    """
    try:
        arguments = await request.json()
        logger.debug("Executing tool %s with args: %s", tool_name, arguments)

        result = await mcp_server.call_tool(tool_name, arguments)

        # Parse the result (it's a list of TextContent)
        content = result[0].text if result else "{}"
        response_data = json.loads(content)

        return response_data

    except json.JSONDecodeError as e:
        logger.error("Invalid JSON in request body: %s", e)
        return JSONResponse(
            status_code=400,
            content={
                "tool": tool_name,
                "ok": False,
                "error": {
                    "error_code": "INVALID_JSON",
                    "message": f"Invalid JSON in request body: {str(e)}",
                },
                "meta": {"execution_ms": 0, "row_count": 0},
            },
        )
    except Exception as e:
        logger.error("Error executing tool %s: %s", tool_name, e)
        return JSONResponse(
            status_code=500,
            content={
                "tool": tool_name,
                "ok": False,
                "error": {
                    "error_code": "EXECUTION_ERROR",
                    "message": str(e),
                },
                "meta": {"execution_ms": 0, "row_count": 0},
            },
        )


@app.get("/resources", response_class=JSONResponse)
async def list_resources():
    """List all available MCP resources."""
    try:
        resources = await mcp_server.list_resources()
        return {
            "resources": [resource.model_dump() for resource in resources],
            "count": len(resources),
        }
    except Exception as e:
        logger.error("Error listing resources: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to list resources", "message": str(e)},
        )


@app.get("/resources/{uri:path}", response_class=JSONResponse)
async def read_resource(uri: str):
    """Read an MCP resource by URI.

    Example:
        GET /resources/financial://metrics
    """
    try:
        content = await mcp_server.read_resource(uri)
        return {
            "uri": uri,
            "content": content,
            "mime_type": "application/json",
        }
    except ValueError as e:
        return JSONResponse(
            status_code=404,
            content={"error": "Resource not found", "message": str(e)},
        )
    except Exception as e:
        logger.error("Error reading resource %s: %s", uri, e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to read resource", "message": str(e)},
        )


@app.get("/prompts", response_class=JSONResponse)
async def list_prompts():
    """List all available MCP prompts."""
    try:
        prompts = await mcp_server.list_prompts()
        return {
            "prompts": [prompt.model_dump() for prompt in prompts],
            "count": len(prompts),
        }
    except Exception as e:
        logger.error("Error listing prompts: %s", e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to list prompts", "message": str(e)},
        )


@app.post("/prompts/{prompt_name}", response_class=JSONResponse)
async def get_prompt(prompt_name: str, request: Request):
    """Get an MCP prompt with arguments.

    Example:
        POST /prompts/sector_analysis
        {"sector": "Technology"}
    """
    try:
        body = await request.json()
        arguments = body.get("arguments", {})

        messages = await mcp_server.get_prompt(prompt_name, arguments)
        return {
            "name": prompt_name,
            "messages": [message.model_dump() for message in messages],
        }
    except ValueError as e:
        return JSONResponse(
            status_code=404,
            content={"error": "Prompt not found", "message": str(e)},
        )
    except Exception as e:
        logger.error("Error getting prompt %s: %s", prompt_name, e)
        return JSONResponse(
            status_code=500,
            content={"error": "Failed to get prompt", "message": str(e)},
        )


# ---------------------------------------------------------------------------
# SSE endpoint
# ---------------------------------------------------------------------------


@app.get("/sse")
async def sse_endpoint(request: Request):
    """Server-Sent Events stream for MCP protocol messages.

    The client opens this endpoint to receive messages from the MCP
    server.  The client posts requests to ``/messages?session_id=<id>``
    and reads the server responses from this stream.
    """
    global _session_counter
    _session_counter += 1
    session_id = f"session-{_session_counter}"

    queue: asyncio.Queue = asyncio.Queue()
    _sessions[session_id] = queue

    async def event_generator():
        # First event: tell the client where to POST requests
        yield {
            "event": "endpoint",
            "data": f"/messages?session_id={session_id}",
        }

        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    message = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield {
                        "event": "message",
                        "data": json.dumps(message, default=str),
                    }
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield {"comment": "keepalive"}
        finally:
            _sessions.pop(session_id, None)

    return EventSourceResponse(event_generator())


# ---------------------------------------------------------------------------
# Message endpoint (client → server)
# ---------------------------------------------------------------------------


@app.post("/messages")
async def messages_endpoint(request: Request, session_id: str):
    """Receive a JSON-RPC request from the client, process it, and
    push the response onto the SSE stream for the matching session.
    """
    queue = _sessions.get(session_id)
    if queue is None:
        return JSONResponse(
            status_code=404,
            content={"error": f"Session '{session_id}' not found. Connect to /sse first."},
        )

    body = await request.json()
    logger.debug("SSE recv session=%s body=%s", session_id, body)

    server = create_mcp_server()

    # Route the JSON-RPC method
    method = body.get("method", "")
    params = body.get("params", {})
    rpc_id = body.get("id")

    response: dict[str, Any]

    if method == "tools/list":
        tools = await server.list_tools()
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"tools": [t.model_dump() for t in tools]},
        }

    elif method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = await server.call_tool(tool_name, arguments)
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"content": [c.model_dump() for c in result]},
        }

    elif method == "resources/list":
        resources = await server.list_resources()
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"resources": [r.model_dump() for r in resources]},
        }

    elif method == "resources/read":
        uri = params.get("uri", "")
        content = await server.read_resource(uri)
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"contents": [{"uri": uri, "text": content, "mimeType": "application/json"}]},
        }

    elif method == "prompts/list":
        prompts = await server.list_prompts()
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"prompts": [p.model_dump() for p in prompts]},
        }

    elif method == "prompts/get":
        prompt_name = params.get("name", "")
        arguments = params.get("arguments", {})
        messages = await server.get_prompt(prompt_name, arguments)
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {"messages": [m.model_dump() for m in messages]},
        }

    elif method == "initialize":
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": False},
                    "resources": {"listChanged": False},
                    "prompts": {"listChanged": False},
                },
                "serverInfo": {
                    "name": settings.mcp_server_name,
                    "version": settings.mcp_server_version,
                },
            },
        }

    else:
        response = {
            "jsonrpc": "2.0",
            "id": rpc_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not found",
            },
        }

    # Push response onto the SSE stream
    await queue.put(response)

    return Response(status_code=202, content="Accepted")


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    uvicorn.run(
        "app.mcp.sse_server:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=False,
    )
