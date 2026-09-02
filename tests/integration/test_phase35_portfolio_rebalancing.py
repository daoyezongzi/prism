from datetime import UTC, datetime
from decimal import Decimal
from fastapi.testclient import TestClient

from app.api import create_app
from app.service import FixtureAdvisorQueryService
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def _client():
    store = SQLiteDecisionEventStore(":memory:")
    advisor = FixtureAdvisorQueryService()
    app = create_app(store, clock=lambda: NOW, advisor_service=advisor)
    return TestClient(app), store, advisor


def test_portfolio_rebalancing_api_flow():
    client, store, advisor = _client()
    owner = "reb-api-owner-001"

    # Fetch template
    t_res = client.get(
        "/api/v1/advisor/rebalancing-template",
        headers={"X-Owner-ID": owner},
    )
    assert t_res.status_code == 200
    t_data = t_res.json()
    assert t_data["schema_version"] == "rebalancing-template.v1"
    assert t_data["owner_id"] == owner
    assert "bundle" in t_data
    assert "target_weights" in t_data

    # Submit rebalancing run
    req_body = {
        "schema_version": "portfolio-rebalancing-request.v1",
        "request_id": "reb-api-run-001",
        "owner_id": owner,
        "generated_at": NOW.isoformat(),
        "bundle": t_data["bundle"],
        "target_weights": {
            "ASSET-TECH-ETF-001": "25.00",
            "ASSET-CSI300-001": "45.00",
            "ASSET-DIVIDEND-001": "30.00",
        },
        "deadband_pct": "0.50",
        "max_turnover_pct": "100.00",
    }
    r_res = client.post(
        "/api/v1/advisor/rebalancing-runs",
        headers={"X-Owner-ID": owner},
        json=req_body,
    )
    assert r_res.status_code == 200
    r_data = r_res.json()
    assert r_data["schema_version"] == "portfolio-rebalancing-response.v1"
    assert r_data["status"] == "PASS"
    assert len(r_data["actions"]) > 0
    assert len(r_data["execution_steps"]) > 0
    assert "total_turnover_pct" in r_data["metrics"]

    # Owner isolation mismatch check
    mismatch_res = client.post(
        "/api/v1/advisor/rebalancing-runs",
        headers={"X-Owner-ID": "other-owner"},
        json=req_body,
    )
    assert mismatch_res.status_code in (403, 422)

    store.close()
