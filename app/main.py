"""FastAPI application – backwards-compatible entry-point.

The primary interface is the MCP server (stdio or SSE).
This module re-exports the debug server for `python -m app.main` convenience.
See ``app.dev.debug_server`` for the actual implementation.
"""

from app.dev.debug_server import app  # noqa: F401 – re-export for uvicorn

if __name__ == "__main__":
    import logging
    import uvicorn
    from app.config import settings

    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    uvicorn.run(
        "app.main:app",
        host=settings.fastapi_host,
        port=settings.fastapi_port,
        reload=(settings.app_env == "development"),
    )
