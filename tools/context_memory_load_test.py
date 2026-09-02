"""Local-only concurrent load check for the Phase 29 context-memory boundary.

This is a fixture/ASGI measurement, not a production or external-SLA claim.  It
keeps each owner isolated, writes one immutable record, reads it concurrently,
and reopens the same SQLite file to verify the migration/restart boundary.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime
import json
from pathlib import Path
import tempfile
import time
from typing import Any

import httpx

from app.api import create_app
from app.service import FixtureAdvisorQueryService, confirm_questionnaire
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 4, tzinfo=UTC)


def _payload(owner_id: str) -> dict[str, object]:
    template = FixtureAdvisorQueryService().query_template(owner_id)
    profile = confirm_questionnaire(template.questionnaire)
    return {
        "schema_version": "context-memory-write-request.v1",
        "owner_id": owner_id,
        "questionnaire": template.questionnaire.model_dump(mode="json"),
        "profile": profile.model_dump(mode="json"),
        "portfolio": template.portfolio.model_dump(mode="json"),
    }


def _summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "p99_ms": None}
    ordered = sorted(values)

    def percentile(percent: float) -> float:
        position = (len(ordered) - 1) * percent / 100
        lower = int(position)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    return {
        "count": len(ordered),
        "p50_ms": round(percentile(50), 3),
        "p95_ms": round(percentile(95), 3),
        "p99_ms": round(percentile(99), 3),
    }


async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    owner_id: str,
    payload: dict[str, object] | None = None,
) -> tuple[float, httpx.Response | None]:
    started = time.perf_counter()
    try:
        response = await client.request(
            method,
            path,
            headers={"X-Owner-ID": owner_id},
            json=payload,
        )
    except Exception:
        return (time.perf_counter() - started) * 1000, None
    return (time.perf_counter() - started) * 1000, response


async def _run(concurrency: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as temp_dir:
        database = Path(temp_dir) / "context-memory-load.sqlite3"
        store = SQLiteDecisionEventStore(database)
        client_app = create_app(store, clock=lambda: NOW)
        owners = tuple(f"load-memory-owner-{index:03d}" for index in range(concurrency))
        payloads = {owner: _payload(owner) for owner in owners}
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=client_app),
            base_url="http://phase29.local",
            timeout=30,
        ) as client:
            writes = await asyncio.gather(
                *(_request(client, "POST", "/api/v1/advisor/context-memory", owner, payloads[owner]) for owner in owners)
            )
            reads = await asyncio.gather(
                *(_request(client, "GET", "/api/v1/advisor/context-memory", owner) for owner in owners)
            )

        write_statuses = [response.status_code for _, response in writes if response is not None]
        read_statuses = [response.status_code for _, response in reads if response is not None]
        owner_mismatches = 0
        for owner, (_, response) in zip(owners, reads):
            if response is None or response.status_code != 200:
                continue
            records = response.json().get("records", [])
            if len(records) != 1 or records[0].get("owner_id") != owner:
                owner_mismatches += 1
        result = {
            "schema_version": "context-memory-load-report.v1",
            "configured_owners": concurrency,
            "write_status_counts": {str(code): write_statuses.count(code) for code in sorted(set(write_statuses))},
            "read_status_counts": {str(code): read_statuses.count(code) for code in sorted(set(read_statuses))},
            "write_latency_ms": _summary([latency for latency, _ in writes]),
            "read_latency_ms": _summary([latency for latency, _ in reads]),
            "write_errors": sum(response is None or response.status_code != 200 for _, response in writes),
            "read_errors": sum(response is None or response.status_code != 200 for _, response in reads),
            "owner_mismatch_count": owner_mismatches,
            "store_rows_before": 0,
            "store_rows_after": sum(len(store.list_context_memory(owner)) for owner in owners),
        }
        store.close()
        reopened = SQLiteDecisionEventStore(database)
        result["reopened_rows"] = sum(len(reopened.list_context_memory(owner)) for owner in owners)
        reopened.close()
        return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--owners", type=int, default=100)
    args = parser.parse_args()
    if not 1 <= args.owners <= 1000:
        raise SystemExit("--owners must be between 1 and 1000")
    print(json.dumps(asyncio.run(_run(args.owners)), ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()
