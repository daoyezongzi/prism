import asyncio
import json
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api import create_app
from app.store import SQLiteDecisionEventStore
from tools.load_test import (
    LoadConfig,
    percentile,
    run_load_test,
    summarize_latencies,
)


REPO_ROOT = Path(__file__).parents[2]


def _app() -> tuple[FastAPI, SQLiteDecisionEventStore]:
    store = SQLiteDecisionEventStore(":memory:")
    return create_app(store), store


def test_percentiles_are_interpolated_and_empty_summary_is_explicit() -> None:
    values = [1, 2, 3, 4]
    assert percentile(values, 0) == 1
    assert percentile(values, 50) == 2.5
    assert percentile(values, 95) == 3.85
    assert summarize_latencies([]).count == 0
    assert summarize_latencies([]).p95_ms is None
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        percentile(values, 101)


def test_load_config_rejects_unsafe_or_empty_workloads() -> None:
    with pytest.raises(ValueError):
        LoadConfig(scenario="unknown")  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        LoadConfig(concurrency=0)
    with pytest.raises(ValueError):
        LoadConfig(requests_per_user=0)
    with pytest.raises(ValueError):
        LoadConfig(timeout_seconds=0)


def test_one_hundred_concurrent_template_operations_keep_owner_closure() -> None:
    app, store = _app()
    try:
        report = asyncio.run(
            run_load_test(
                LoadConfig(scenario="template", concurrency=100),
                app=app,
                store=store,
            )
        )
        assert report.schema_version == "load-test-report.v1"
        assert report.logical_operations == 100
        assert report.total_requests == 100
        assert report.completed == 100
        assert report.failed == 0
        assert report.status_counts == {"200": 100}
        assert report.error_counts == {}
        assert report.owner_mismatch_count == 0
        assert report.store_rows_before == report.store_rows_after == 0
        assert report.latency_ms.count == 100
        assert report.latency_ms.p50_ms is not None
        assert report.latency_ms.p95_ms is not None
        assert report.latency_ms.p99_ms is not None
    finally:
        store.close()


def test_one_hundred_concurrent_research_operations_are_ready_and_side_effect_free() -> None:
    app, store = _app()
    try:
        report = asyncio.run(
            run_load_test(
                LoadConfig(scenario="research", concurrency=100),
                app=app,
                store=store,
            )
        )
        assert report.completed == 100
        assert report.failed == 0
        assert report.total_requests == 100
        assert report.status_counts == {"200": 100}
        assert report.error_counts == {}
        assert report.owner_mismatch_count == 0
        assert report.store_rows_after == 0
    finally:
        store.close()


def test_advisor_operations_measure_template_plus_query_and_scope_events() -> None:
    app, store = _app()
    try:
        report = asyncio.run(
            run_load_test(
                LoadConfig(scenario="advisor", concurrency=8, requests_per_user=2),
                app=app,
                store=store,
            )
        )
        assert report.logical_operations == 16
        assert report.total_requests == 32
        assert report.completed == 16
        assert report.failed == 0
        assert report.status_counts == {"200": 32}
        assert report.error_counts == {}
        assert report.owner_mismatch_count == 0
        assert report.store_rows_after == 16
        for index in range(8):
            owner = f"load-advisor-owner-{index:04d}"
            assert len(store.list(owner)) == 2
    finally:
        store.close()


def test_runner_reports_http_failures_instead_of_swallowing_them() -> None:
    bad_app = FastAPI()

    @bad_app.get("/api/v1/advisor/query-template")
    async def refused_template() -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "schema_version": "api-error.v1",
                "error_code": "UPSTREAM_TIMEOUT",
                "message": "safe refusal",
            },
        )

    store = SQLiteDecisionEventStore(":memory:")
    try:
        report = asyncio.run(
            run_load_test(
                LoadConfig(scenario="template", concurrency=1),
                app=bad_app,
                store=store,
            )
        )
        assert report.completed == 0
        assert report.failed == 1
        assert report.status_counts == {"503": 1}
        assert report.error_counts == {"API_UPSTREAM_TIMEOUT": 1}
    finally:
        store.close()


def test_runner_rejects_sensitive_error_payloads_without_echoing_them() -> None:
    leaking_app = FastAPI()

    @leaking_app.get("/api/v1/advisor/query-template")
    async def leaking_template() -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "schema_version": "api-error.v1",
                "error_code": "UPSTREAM_ERROR",
                "details": {"api_key": "must-not-escape"},
            },
        )

    store = SQLiteDecisionEventStore(":memory:")
    try:
        report = asyncio.run(
            run_load_test(
                LoadConfig(scenario="template", concurrency=1),
                app=leaking_app,
                store=store,
            )
        )
        assert report.failed == 1
        assert report.error_counts == {"SENSITIVE_DATA": 1}
    finally:
        store.close()


def test_runner_marks_owner_mismatch_as_a_failed_operation() -> None:
    mismatched_app = FastAPI()

    @mismatched_app.get("/api/v1/advisor/query-template")
    async def mismatched_template() -> dict[str, object]:
        return {
            "schema_version": "advisor-query-template.v1",
            "questionnaire": {"owner_id": "other-owner"},
            "portfolio": {"owner_id": "other-owner"},
        }

    store = SQLiteDecisionEventStore(":memory:")
    try:
        report = asyncio.run(
            run_load_test(
                LoadConfig(scenario="template", concurrency=1),
                app=mismatched_app,
                store=store,
            )
        )
        assert report.failed == 1
        assert report.owner_mismatch_count == 1
        assert report.error_counts == {"OWNER_MISMATCH": 1}
    finally:
        store.close()


def test_cli_smoke_emits_versioned_json_report() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "tools.load_test",
            "--scenario",
            "template",
            "--concurrency",
            "2",
            "--json",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_version"] == "load-test-report.v1"
    assert report["transport"] == "httpx.ASGITransport"
    assert report["completed"] == 2
    assert report["failed"] == 0
