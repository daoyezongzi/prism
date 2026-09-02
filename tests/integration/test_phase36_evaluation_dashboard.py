from datetime import UTC, datetime
from fastapi.testclient import TestClient

from app.api import create_app
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def _client():
    store = SQLiteDecisionEventStore(":memory:")
    app = create_app(store, clock=lambda: NOW)
    return TestClient(app), store


def test_evaluation_dashboard_api_flow():
    client, store = _client()
    owner = "eval-api-owner-001"

    # Get summary
    res = client.get(
        "/api/v1/advisor/evaluation-dashboard-summary",
        headers={"X-Owner-ID": owner},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["schema_version"] == "evaluation-dashboard-response.v1"
    assert data["total_cases"] > 0
    assert data["passed_cases"] == data["total_cases"]
    assert "summary" in data
    assert "latency" in data
    assert data["summary"]["case_pass_rate_pct"] == "100.00"

    # Run custom subset
    post_res = client.post(
        "/api/v1/advisor/evaluation-dashboard-runs",
        headers={"X-Owner-ID": owner},
        json={
            "schema_version": "evaluation-dashboard-request.v1",
            "request_id": "eval-run-001",
            "operator_id": owner,
            "generated_at": NOW.isoformat(),
            "selected_cases": ["balanced-hold"],
            "repeat_count": 1,
        },
    )
    assert post_res.status_code == 200
    post_data = post_res.json()
    assert post_data["total_cases"] == 1
    assert post_data["passed_cases"] == 1

    # Operator mismatch
    mismatch_res = client.post(
        "/api/v1/advisor/evaluation-dashboard-runs",
        headers={"X-Owner-ID": "mismatch-operator"},
        json={
            "schema_version": "evaluation-dashboard-request.v1",
            "request_id": "eval-run-002",
            "operator_id": owner,
            "generated_at": NOW.isoformat(),
            "repeat_count": 1,
        },
    )
    assert mismatch_res.status_code in (403, 422)

    store.close()
