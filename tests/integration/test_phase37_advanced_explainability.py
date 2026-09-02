from datetime import UTC, datetime
from fastapi.testclient import TestClient

from app.api import create_app
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def _client():
    store = SQLiteDecisionEventStore(":memory:")
    app = create_app(store, clock=lambda: NOW)
    return TestClient(app), store


def test_advanced_explainability_api_flow():
    client, store = _client()
    owner = "exp-api-owner-001"

    # Template
    t_res = client.get(
        "/api/v1/advisor/explainability-template",
        headers={"X-Owner-ID": owner},
    )
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert t_data["schema_version"] == "explainability-template.v1"
    assert t_data["owner_id"] == owner

    # Run explainability
    run_res = client.post(
        "/api/v1/advisor/explainability-runs",
        headers={"X-Owner-ID": owner},
        json={
            "schema_version": "advanced-explainability-request.v1",
            "request_id": "exp-api-run-001",
            "owner_id": owner,
            "generated_at": NOW.isoformat(),
            "risk_score": "35.00",
            "risk_level": "BALANCED",
            "action_type": "HOLD",
            "asset": "ASSET-TECH-ETF-001",
            "tech_exposure_pct": "38.50",
            "tech_cap_pct": "40.00",
            "top_asset_weight_pct": "35.00",
            "finding_count": 6,
        },
    )
    assert run_res.status_code == 200
    run_data = run_res.json()
    assert run_data["schema_version"] == "advanced-explainability-response.v1"
    assert len(run_data["causal_nodes"]) >= 5
    assert len(run_data["causal_edges"]) >= 4
    assert len(run_data["key_drivers"]) >= 3
    assert len(run_data["counterfactuals"]) >= 2
    assert len(run_data["invalidation_triggers"]) >= 3

    # Owner mismatch
    mismatch_res = client.post(
        "/api/v1/advisor/explainability-runs",
        headers={"X-Owner-ID": "other-owner"},
        json={
            "schema_version": "advanced-explainability-request.v1",
            "request_id": "exp-api-run-002",
            "owner_id": owner,
            "generated_at": NOW.isoformat(),
            "risk_score": "35.00",
            "risk_level": "BALANCED",
            "action_type": "HOLD",
            "asset": "ASSET-TECH-ETF-001",
            "tech_exposure_pct": "38.50",
            "tech_cap_pct": "40.00",
            "top_asset_weight_pct": "35.00",
            "finding_count": 6,
        },
    )
    assert mismatch_res.status_code in (403, 422)

    store.close()
