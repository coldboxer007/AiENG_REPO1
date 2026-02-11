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
