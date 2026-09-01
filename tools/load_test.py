"""Repeatable, local-only load checks for the fixture-first HTTP boundary.

The runner deliberately measures the ASGI application in process.  It is useful for
regression and isolation checks, but its numbers are not a production deployment or
external-SLA measurement.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
import json
import re
import sys
import time
from typing import Any, Literal

import httpx

from app.api import create_app
from app.store import SQLiteDecisionEventStore


Scenario = Literal["template", "research", "advisor"]
SCENARIOS: tuple[Scenario, ...] = ("template", "research", "advisor")
FIXED_GENERATED_AT = datetime(2026, 9, 2, 1, tzinfo=UTC)
MATRIX_ID = "specialist-matrix-four-track-001"
SENSITIVE_MARKERS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "secret",
    "token",
    "credential",
    "cookie",
)


@dataclass(frozen=True)
class LoadConfig:
    """Validated workload configuration."""

    scenario: Scenario = "template"
    concurrency: int = 100
    requests_per_user: int = 1
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        if self.scenario not in SCENARIOS:
            raise ValueError(f"scenario must be one of {', '.join(SCENARIOS)}")
        if not isinstance(self.concurrency, int) or isinstance(self.concurrency, bool):
            raise ValueError("concurrency must be an integer")
        if not 1 <= self.concurrency <= 1000:
            raise ValueError("concurrency must be between 1 and 1000")
        if not isinstance(self.requests_per_user, int) or isinstance(
            self.requests_per_user, bool
        ):
            raise ValueError("requests_per_user must be an integer")
        if not 1 <= self.requests_per_user <= 1000:
            raise ValueError("requests_per_user must be between 1 and 1000")
        if isinstance(self.timeout_seconds, bool) or not isinstance(
            self.timeout_seconds, (int, float)
        ):
            raise ValueError("timeout_seconds must be a number")
        if not 0 < self.timeout_seconds <= 300:
            raise ValueError("timeout_seconds must be between 0 and 300")


@dataclass(frozen=True)
class LatencySummary:
    count: int
    min_ms: float | None
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    max_ms: float | None


@dataclass(frozen=True)
class RequestObservation:
    latency_ms: float
    status: str
    error_code: str | None = None


@dataclass(frozen=True)
class OperationResult:
    latency_ms: float
    observations: tuple[RequestObservation, ...]
    error_code: str | None = None
    owner_mismatch: bool = False

    @property
    def completed(self) -> bool:
        return self.error_code is None and not self.owner_mismatch


@dataclass(frozen=True)
class LoadReport:
    schema_version: str
    scenario: Scenario
    transport: str
    configured_concurrency: int
    requests_per_user: int
    logical_operations: int
    total_requests: int
    completed: int
    failed: int
    duration_ms: float
    latency_ms: LatencySummary
    status_counts: dict[str, int]
    error_counts: dict[str, int]
    owner_mismatch_count: int
    store_rows_before: int
    store_rows_after: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def percentile(values: list[float] | tuple[float, ...], percent: float) -> float:
    """Return a linearly interpolated percentile from a non-empty sample."""

    if not values:
        raise ValueError("percentile requires at least one value")
    if not 0 <= percent <= 100:
        raise ValueError("percent must be between 0 and 100")
    ordered = sorted(float(value) for value in values)
    position = (len(ordered) - 1) * percent / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def summarize_latencies(values: list[float]) -> LatencySummary:
    if not values:
        return LatencySummary(0, None, None, None, None, None)
    return LatencySummary(
        count=len(values),
        min_ms=round(min(values), 3),
        p50_ms=round(percentile(values, 50), 3),
        p95_ms=round(percentile(values, 95), 3),
        p99_ms=round(percentile(values, 99), 3),
        max_ms=round(max(values), 3),
    )


def _owner_id(scenario: Scenario, user_index: int) -> str:
    return f"load-{scenario}-owner-{user_index:04d}"


def _generated_at_json() -> str:
    return FIXED_GENERATED_AT.isoformat().replace("+00:00", "Z")


def _contains_sensitive(value: object) -> bool:
    if isinstance(value, dict):
        return any(_contains_sensitive(key) or _contains_sensitive(item) for key, item in value.items())
    if isinstance(value, (list, tuple)):
        return any(_contains_sensitive(item) for item in value)
    if isinstance(value, str):
        normalized = value.casefold().replace("-", "_")
        return any(marker in normalized for marker in SENSITIVE_MARKERS)
    return False


def _safe_api_error(response: httpx.Response, payload: object) -> str:
    if isinstance(payload, dict):
        code = payload.get("error_code")
        if isinstance(code, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,64}", code):
            return f"API_{code.upper()}"
    return f"HTTP_{response.status_code}"


async def _request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    owner_id: str,
    json_body: dict[str, object] | None = None,
) -> tuple[RequestObservation, object | None]:
    started = time.perf_counter()
    try:
        response = await client.request(
            method,
            path,
            headers={"X-Owner-ID": owner_id},
            json=json_body,
        )
    except httpx.TimeoutException:
        return (
            RequestObservation(
                latency_ms=(time.perf_counter() - started) * 1000,
                status="timeout",
                error_code="TIMEOUT",
            ),
            None,
        )
    except Exception:
        return (
            RequestObservation(
                latency_ms=(time.perf_counter() - started) * 1000,
                status="transport_error",
                error_code="TRANSPORT_ERROR",
            ),
            None,
        )
    latency_ms = (time.perf_counter() - started) * 1000
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError):
        return (
            RequestObservation(
                latency_ms=latency_ms,
                status=str(response.status_code),
                error_code="INVALID_JSON",
            ),
            None,
        )
    if _contains_sensitive(payload):
        return (
            RequestObservation(
                latency_ms=latency_ms,
                status=str(response.status_code),
                error_code="SENSITIVE_DATA",
            ),
            payload,
        )
    if response.status_code < 200 or response.status_code >= 300:
        return (
            RequestObservation(
                latency_ms=latency_ms,
                status=str(response.status_code),
                error_code=_safe_api_error(response, payload),
            ),
            payload,
        )
    return RequestObservation(latency_ms=latency_ms, status=str(response.status_code)), payload


def _template_owner_mismatch(payload: object, owner_id: str) -> bool:
    if not isinstance(payload, dict):
        return True
    questionnaire = payload.get("questionnaire")
    portfolio = payload.get("portfolio")
    if not isinstance(questionnaire, dict) or not isinstance(portfolio, dict):
        return True
    if questionnaire.get("owner_id") != owner_id or portfolio.get("owner_id") != owner_id:
        return True
    snapshot = portfolio.get("position_snapshot")
    if not isinstance(snapshot, dict) or snapshot.get("owner_id") != owner_id:
        return True
    positions = snapshot.get("positions")
    if not isinstance(positions, list) or any(
        not isinstance(position, dict) or position.get("owner_id") != owner_id
        for position in positions
    ):
        return True
    funds = portfolio.get("fund_holdings")
    if not isinstance(funds, list) or any(
        not isinstance(fund, dict) or fund.get("owner_id") != owner_id
        for fund in funds
    ):
        return True
    return False


def _validate_template(payload: object, owner_id: str) -> str | None:
    if not isinstance(payload, dict) or payload.get("schema_version") != "advisor-query-template.v1":
        return "CONTRACT_ERROR"
    if _template_owner_mismatch(payload, owner_id):
        return "OWNER_MISMATCH"
    return None


def _validate_research(
    payload: object,
    owner_id: str,
    request_id: str,
) -> str | None:
    if not isinstance(payload, dict) or payload.get("schema_version") != "research-matrix-response.v1":
        return "CONTRACT_ERROR"
    if payload.get("owner_id") != owner_id:
        return "OWNER_MISMATCH"
    if payload.get("request_id") != request_id:
        return "REQUEST_ID_MISMATCH"
    if payload.get("pipeline_status") != "READY":
        return "PIPELINE_NOT_READY"
    if payload.get("run_status") != "COMPLETED":
        return "RUN_NOT_COMPLETED"
    nodes = payload.get("nodes")
    if not isinstance(nodes, list) or len(nodes) != 8:
        return "NODE_COUNT_MISMATCH"
    trace = payload.get("trace")
    if not isinstance(trace, dict) or trace.get("recommendations"):
        return "UNEXPECTED_RECOMMENDATION"
    if not trace.get("facts") or not trace.get("findings"):
        return "TRACE_INCOMPLETE"
    return None


def _validate_advisor(
    payload: object,
    owner_id: str,
    query_id: str,
) -> str | None:
    if not isinstance(payload, dict) or payload.get("schema_version") != "advisor-query-response.v1":
        return "CONTRACT_ERROR"
    if payload.get("owner_id") != owner_id:
        return "OWNER_MISMATCH"
    if payload.get("query_id") != query_id:
        return "QUERY_ID_MISMATCH"
    if payload.get("status") != "PASS":
        return "ADVISOR_NOT_PASS"
    event = payload.get("event")
    if not isinstance(event, dict) or event.get("owner_id") != owner_id:
        return "OWNER_MISMATCH"
    return None


def _research_payload(owner_id: str, request_id: str) -> dict[str, object]:
    return {
        "schema_version": "research-specialist-matrix-request.v1",
        "matrix_id": MATRIX_ID,
        "request_id": request_id,
        "owner_id": owner_id,
        "generated_at": _generated_at_json(),
    }


def _advisor_payload(template: object, query_id: str) -> dict[str, object] | None:
    if not isinstance(template, dict):
        return None
    questionnaire = template.get("questionnaire")
    if not isinstance(questionnaire, dict):
        return None
    payload = json.loads(json.dumps(template))
    payload["schema_version"] = "advisor-query.v1"
    payload["query_id"] = query_id
    payload["questionnaire"]["questionnaire_id"] = f"{query_id}-questionnaire"
    return payload


async def _operation(
    client: httpx.AsyncClient,
    config: LoadConfig,
    owner_id: str,
    user_index: int,
    iteration: int,
) -> OperationResult:
    started = time.perf_counter()
    observations: list[RequestObservation] = []
    error_code: str | None = None
    owner_mismatch = False

    if config.scenario == "template":
        observation, payload = await _request(
            client,
            "GET",
            "/api/v1/advisor/query-template",
            owner_id=owner_id,
        )
        observations.append(observation)
        if observation.error_code is not None:
            error_code = observation.error_code
        else:
            error_code = _validate_template(payload, owner_id)
    elif config.scenario == "research":
        request_id = f"load-research-request-{user_index:04d}-{iteration:04d}"
        observation, payload = await _request(
            client,
            "POST",
            "/api/v1/advisor/research-runs",
            owner_id=owner_id,
            json_body=_research_payload(
                owner_id,
                request_id,
            ),
        )
        observations.append(observation)
        if observation.error_code is not None:
            error_code = observation.error_code
        else:
            error_code = _validate_research(payload, owner_id, request_id)
    else:
        template_observation, template = await _request(
            client,
            "GET",
            "/api/v1/advisor/query-template",
            owner_id=owner_id,
        )
        observations.append(template_observation)
        if template_observation.error_code is not None:
            error_code = template_observation.error_code
        else:
            template_error = _validate_template(template, owner_id)
            if template_error is not None:
                error_code = template_error
            else:
                query_id = f"load-advisor-query-{user_index:04d}-{iteration:04d}"
                payload = _advisor_payload(
                    template,
                    query_id,
                )
                if payload is None:
                    error_code = "CONTRACT_ERROR"
                else:
                    observation, response_payload = await _request(
                        client,
                        "POST",
                        "/api/v1/advisor/queries",
                        owner_id=owner_id,
                        json_body=payload,
                    )
                    observations.append(observation)
                    if observation.error_code is None:
                        error_code = _validate_advisor(
                            response_payload,
                            owner_id,
                            query_id,
                        )

    owner_mismatch = error_code == "OWNER_MISMATCH"
    return OperationResult(
        latency_ms=(time.perf_counter() - started) * 1000,
        observations=tuple(observations),
        error_code=error_code,
        owner_mismatch=owner_mismatch,
    )


async def run_load_test(
    config: LoadConfig,
    *,
    app: Any,
    store: SQLiteDecisionEventStore,
) -> LoadReport:
    """Run a bounded local workload against an injected app and store."""

    owners = [_owner_id(config.scenario, index) for index in range(config.concurrency)]
    before = sum(len(store.list(owner)) for owner in owners)
    logical_operations = config.concurrency * config.requests_per_user
    results: list[OperationResult] = []
    started = time.perf_counter()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://prism.local",
        timeout=config.timeout_seconds,
    ) as client:
        async def worker(user_index: int) -> list[OperationResult]:
            return [
                await _operation(
                    client,
                    config,
                    owners[user_index],
                    user_index,
                    iteration,
                )
                for iteration in range(config.requests_per_user)
            ]

        batches = await asyncio.gather(
            *(worker(user_index) for user_index in range(config.concurrency))
        )
    results = [result for batch in batches for result in batch]
    after = sum(len(store.list(owner)) for owner in owners)
    if len(results) != logical_operations:
        raise RuntimeError("load runner did not produce one result per operation")

    observations = [
        observation
        for result in results
        for observation in result.observations
    ]
    status_counts = Counter(item.status for item in observations)
    error_counts = Counter(
        error
        for result in results
        for error in ((result.error_code,) if result.error_code else ())
    )
    completed = sum(result.completed for result in results)
    failed = logical_operations - completed
    owner_mismatch_count = sum(result.owner_mismatch for result in results)
    expected_rows = logical_operations if config.scenario == "advisor" else 0
    if after - before != expected_rows:
        error_counts["STORE_SIDE_EFFECT"] += 1
        if failed == 0:
            completed -= 1
            failed = 1
    if any(result.error_code == "OWNER_MISMATCH" for result in results):
        error_counts["OWNER_MISMATCH"] = sum(
            result.error_code == "OWNER_MISMATCH" for result in results
        )
    return LoadReport(
        schema_version="load-test-report.v1",
        scenario=config.scenario,
        transport="httpx.ASGITransport",
        configured_concurrency=config.concurrency,
        requests_per_user=config.requests_per_user,
        logical_operations=logical_operations,
        total_requests=len(observations),
        completed=completed,
        failed=failed,
        duration_ms=round((time.perf_counter() - started) * 1000, 3),
        latency_ms=summarize_latencies([result.latency_ms for result in results]),
        status_counts=dict(sorted(status_counts.items())),
        error_counts=dict(sorted(error_counts.items())),
        owner_mismatch_count=owner_mismatch_count,
        store_rows_before=before,
        store_rows_after=after,
    )


def _build_local_app() -> tuple[Any, SQLiteDecisionEventStore]:
    store = SQLiteDecisionEventStore(":memory:")
    app = create_app(store, clock=lambda: FIXED_GENERATED_AT)
    return app, store


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=SCENARIOS, default="template")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--requests-per-user", type=int, default=1)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit machine-readable JSON")
    return parser


def _print_human(report: LoadReport) -> None:
    latency = report.latency_ms
    print(
        f"scenario={report.scenario} transport={report.transport} "
        f"operations={report.logical_operations} requests={report.total_requests} "
        f"completed={report.completed} failed={report.failed}"
    )
    print(
        f"latency_ms min={latency.min_ms} p50={latency.p50_ms} "
        f"p95={latency.p95_ms} p99={latency.p99_ms} max={latency.max_ms}"
    )
    print(
        f"status_counts={json.dumps(report.status_counts, sort_keys=True)} "
        f"error_counts={json.dumps(report.error_counts, sort_keys=True)} "
        f"owner_mismatches={report.owner_mismatch_count} "
        f"store_rows={report.store_rows_before}->{report.store_rows_after}"
    )


async def _main_async(args: argparse.Namespace) -> int:
    try:
        config = LoadConfig(
            scenario=args.scenario,
            concurrency=args.concurrency,
            requests_per_user=args.requests_per_user,
            timeout_seconds=args.timeout_seconds,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    app, store = _build_local_app()
    try:
        report = await run_load_test(config, app=app, store=store)
    finally:
        store.close()
    if args.as_json:
        print(json.dumps(report.as_dict(), ensure_ascii=False, sort_keys=True))
    else:
        _print_human(report)
    return 0 if report.failed == 0 else 1


def main() -> int:
    return asyncio.run(_main_async(_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "LatencySummary",
    "LoadConfig",
    "LoadReport",
    "SCENARIOS",
    "main",
    "percentile",
    "run_load_test",
    "summarize_latencies",
]
