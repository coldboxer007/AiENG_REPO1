"""Rate limiting tests."""

from __future__ import annotations

import pytest

from app.middleware.rate_limit import RateLimiter


@pytest.mark.asyncio
async def test_rate_limit_allows_within_window():
    """Requests within the limit should all be allowed."""
    limiter = RateLimiter()
    for _ in range(10):
        allowed, err = await limiter.check_rate_limit("test_tool", max_requests=10)
        assert allowed is True
        assert err is None


@pytest.mark.asyncio
async def test_rate_limit_blocks_over_window():
    """The N+1-th request should be blocked when the limit is N."""
    limiter = RateLimiter()

    for _ in range(60):
        allowed, _ = await limiter.check_rate_limit("test_tool", max_requests=60)
        assert allowed is True

    # 61st request must be blocked
    allowed, error_msg = await limiter.check_rate_limit("test_tool", max_requests=60)
    assert allowed is False
    assert error_msg is not None
    assert "Rate limit exceeded" in error_msg


@pytest.mark.asyncio
async def test_rate_limit_per_tool_isolation():
    """Rate limits should be independent per tool."""
    limiter = RateLimiter()

    # Exhaust tool_a
    for _ in range(5):
        await limiter.check_rate_limit("tool_a", max_requests=5)

    allowed_a, _ = await limiter.check_rate_limit("tool_a", max_requests=5)
    assert allowed_a is False

    # tool_b should still be fine
    allowed_b, _ = await limiter.check_rate_limit("tool_b", max_requests=5)
    assert allowed_b is True


@pytest.mark.asyncio
async def test_rate_limit_reset():
    """Resetting counters should allow requests again."""
    limiter = RateLimiter()

    for _ in range(5):
        await limiter.check_rate_limit("tool_c", max_requests=5)

    allowed, _ = await limiter.check_rate_limit("tool_c", max_requests=5)
    assert allowed is False

    await limiter.reset("tool_c")

    allowed, _ = await limiter.check_rate_limit("tool_c", max_requests=5)
    assert allowed is True


@pytest.mark.asyncio
async def test_rate_limit_retry_after_message():
    """Blocked response should include retry-after guidance."""
    limiter = RateLimiter()
    for _ in range(3):
        await limiter.check_rate_limit("tool_d", max_requests=3, window_seconds=60)

    _, msg = await limiter.check_rate_limit("tool_d", max_requests=3, window_seconds=60)
    assert "Retry after" in msg
