"""Performance benchmarks for MCP tools.

Run:
    python -m scripts.benchmark
"""

from __future__ import annotations

import asyncio
import time
from datetime import date

from app.db import async_session_factory
from app.services import company_service, stock_service, financial_service, analyst_service


async def _bench(label: str, coro_factory, iterations: int = 100):
    """Run a coroutine *iterations* times and print average wall-clock ms."""
    async with async_session_factory() as session:
        # Warm up
        await coro_factory(session)

        start = time.perf_counter()
        for _ in range(iterations):
            await coro_factory(session)
        elapsed = time.perf_counter() - start

    avg_ms = elapsed / iterations * 1000
    print(f"  {label}: {avg_ms:.2f} ms avg ({iterations} iterations)")
    return avg_ms


async def main():
    print("Running benchmarks …\n")

    await _bench(
        "search_companies('Tech', limit=10)",
        lambda s: company_service.search_companies(s, "Tech", limit=10),
    )

    await _bench(
        "get_company_by_ticker('ALPH')",
        lambda s: company_service.get_company_by_ticker(s, "ALPH"),
        iterations=200,
    )

    await _bench(
        "get_financial_summary('ALPH', years=3)",
        lambda s: financial_service.get_financial_summary(s, "ALPH", years=3),
    )

    await _bench(
        "get_stock_price_history('ALPH', 1 year)",
        lambda s: stock_service.get_stock_price_history(
            s, "ALPH", date(2024, 1, 1), date(2024, 12, 31)
        ),
        iterations=50,
    )

    await _bench(
        "get_analyst_consensus('ALPH')",
        lambda s: analyst_service.get_analyst_consensus(s, "ALPH"),
    )

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
