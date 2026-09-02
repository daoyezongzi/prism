"""Local 100-request smoke test for the Phase 30 provider resilience boundary."""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta
import json
import time

from app.providers import (
    InMemoryProviderCache,
    ProviderExecutionPolicy,
    ProviderIssue,
    ProviderIssueCode,
    ProviderOperation,
    ProviderRecord,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    execute_with_budget,
)
from app.providers.fingerprint import compute_request_fingerprint


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class _LoadProvider:
    def __init__(self, name: str, *, failing: bool = False) -> None:
        self._name = name
        self.failing = failing
        self.calls = 0

    @property
    def name(self) -> str:
        return self._name

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        self.calls += 1
        fingerprint = compute_request_fingerprint(request)
        if self.failing:
            return ProviderResult(
                request_id=request.request_id,
                request_fingerprint=fingerprint,
                provider=self.name,
                status=ProviderStatus.FAILED,
                retrieved_at=NOW,
                issues=(
                    ProviderIssue(
                        code=ProviderIssueCode.TRANSPORT_ERROR,
                        stage="load-test",
                        safe_message="synthetic provider unavailable",
                        retriable=True,
                    ),
                ),
            )
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            provider=self.name,
            status=ProviderStatus.SUCCESS,
            retrieved_at=NOW,
            records=(
                ProviderRecord(
                    source="load-test-source",
                    record_id="load-test-record",
                    fields={"value": "1.0"},
                    units={"value": "pct"},
                    period="2026-Q2",
                    observed_at=NOW,
                    lineage_id="load-test-lineage",
                ),
            ),
        )


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=UTC)


def _request(index: int) -> ProviderRequest:
    return ProviderRequest(
        request_id=f"resilience-load-{index}",
        operation=ProviderOperation.MARKET_DATA,
        subject="PUBLIC-LOAD-SYMBOL",
        required_fields=("value",),
        parameters={"period": "2026-Q2"},
        timeout_ms=1000,
    )


async def _run(count: int) -> dict[str, object]:
    clock = _Clock(NOW)
    cache = InMemoryProviderCache(
        ttl_ms=1000,
        stale_grace_ms=3000,
        max_entries=8,
        clock=clock,
    )
    healthy = _LoadProvider("load-primary")
    policy = ProviderExecutionPolicy(cache=cache)
    first_request = _request(0)
    await execute_with_budget(healthy, first_request, policy=policy)

    started = time.perf_counter()
    fresh_results = await asyncio.gather(
        *(
            execute_with_budget(healthy, _request(index), policy=policy)
            for index in range(count)
        )
    )
    fresh_ms = (time.perf_counter() - started) * 1000

    clock.value = NOW + timedelta(milliseconds=1500)
    failing = _LoadProvider("load-primary", failing=True)
    stale_policy = ProviderExecutionPolicy(cache=cache)
    started = time.perf_counter()
    stale_results = await asyncio.gather(
        *(
            execute_with_budget(failing, _request(index), policy=stale_policy)
            for index in range(count, count * 2)
        )
    )
    stale_ms = (time.perf_counter() - started) * 1000

    all_results = [*fresh_results, *stale_results]
    return {
        "requests": count,
        "fresh": {
            "http_equivalent_successes": sum(
                result.status in {ProviderStatus.SUCCESS, ProviderStatus.PARTIAL}
                for result in fresh_results
            ),
            "cache_fresh_modes": sum(result.serving_mode.value == "CACHE_FRESH" for result in fresh_results),
            "elapsed_ms": round(fresh_ms, 3),
        },
        "stale": {
            "http_equivalent_successes": sum(
                result.status in {ProviderStatus.SUCCESS, ProviderStatus.PARTIAL}
                for result in stale_results
            ),
            "stale_modes": sum(result.serving_mode.value == "CACHE_STALE_FALLBACK" for result in stale_results),
            "elapsed_ms": round(stale_ms, 3),
        },
        "provider_calls": {
            "healthy": healthy.calls,
            "failing": failing.calls,
        },
        "cache": cache.stats().__dict__ if hasattr(cache.stats(), "__dict__") else {
            "entries": cache.stats().entries,
            "hits": cache.stats().hits,
            "stale_hits": cache.stats().stale_hits,
            "misses": cache.stats().misses,
            "writes": cache.stats().writes,
            "evictions": cache.stats().evictions,
            "bypasses": cache.stats().bypasses,
        },
        "resilience": stale_policy.counters().snapshot().__dict__ if hasattr(stale_policy.counters().snapshot(), "__dict__") else {
            "cache_fresh": stale_policy.counters().snapshot().cache_fresh,
            "primary_calls": stale_policy.counters().snapshot().primary_calls,
            "fallback_calls": stale_policy.counters().snapshot().fallback_calls,
            "fallback_results": stale_policy.counters().snapshot().fallback_results,
            "stale_fallbacks": stale_policy.counters().snapshot().stale_fallbacks,
            "failed_results": stale_policy.counters().snapshot().failed_results,
            "private_bypasses": stale_policy.counters().snapshot().private_bypasses,
        },
        "errors": sum(result.status == ProviderStatus.FAILED for result in all_results),
        "request_ids_unique": len({result.request_id for result in all_results}) == len(all_results),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--requests", type=int, default=100)
    args = parser.parse_args()
    if args.requests < 1 or args.requests > 1000:
        raise SystemExit("--requests must be between 1 and 1000")
    print(json.dumps(asyncio.run(_run(args.requests)), ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
