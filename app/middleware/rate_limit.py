"""Rate limiting middleware for MCP tools.

Uses a token-bucket algorithm (sliding window) to restrict how many
requests each tool can handle within a configurable time window.

Standard tools: 60 requests / minute
Heavy tools (compare_companies): 30 requests / minute
"""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from typing import Deque, Dict


class RateLimiter:
    """Sliding-window rate limiter.

    Thread-safe via asyncio.Lock.  Each tool gets its own request window.

    Attributes:
        default_max_requests: Default cap per tool (per window).
        default_window_seconds: Default sliding-window length in seconds.
    """

    def __init__(
        self,
        default_max_requests: int = 60,
        default_window_seconds: int = 60,
    ) -> None:
        self.default_max_requests = default_max_requests
        self.default_window_seconds = default_window_seconds
        # tool_name -> deque of timestamps
        self._requests: Dict[str, Deque[float]] = defaultdict(lambda: deque(maxlen=200))
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        tool_name: str,
        max_requests: int | None = None,
        window_seconds: int | None = None,
    ) -> tuple[bool, str | None]:
        """Check whether a request to *tool_name* is within the rate limit.

        Returns:
            (allowed, error_message) – *allowed* is ``True`` if the request
            should proceed.  *error_message* is ``None`` when allowed, or a
            human-readable explanation when denied.
        """
        max_req = max_requests or self.default_max_requests
        window = window_seconds or self.default_window_seconds

        async with self._lock:
            now = time.time()
            timestamps = self._requests[tool_name]

            # Evict timestamps outside the current window
            while timestamps and timestamps[0] < now - window:
                timestamps.popleft()

            if len(timestamps) >= max_req:
                retry_after = int(timestamps[0] + window - now) + 1
                return False, (
                    f"Rate limit exceeded for '{tool_name}'. "
                    f"Max {max_req} requests per {window}s. "
                    f"Retry after {retry_after}s."
                )

            timestamps.append(now)
            return True, None

    async def reset(self, tool_name: str | None = None) -> None:
        """Reset counters.  If *tool_name* is ``None``, reset everything."""
        async with self._lock:
            if tool_name:
                self._requests.pop(tool_name, None)
            else:
                self._requests.clear()


# Module-level singleton used by tool handlers.
rate_limiter = RateLimiter()

# Per-tool limits (override defaults for heavy tools)
TOOL_RATE_LIMITS: dict[str, dict[str, int]] = {
    "search_companies": {"max_requests": 60, "window_seconds": 60},
    "get_company_profile": {"max_requests": 60, "window_seconds": 60},
    "get_financial_report": {"max_requests": 60, "window_seconds": 60},
    "compare_companies": {"max_requests": 30, "window_seconds": 60},
    "get_stock_price_history": {"max_requests": 60, "window_seconds": 60},
    "get_analyst_ratings": {"max_requests": 60, "window_seconds": 60},
    "screen_stocks": {"max_requests": 30, "window_seconds": 60},
    "get_sector_overview": {"max_requests": 60, "window_seconds": 60},
}
