from datetime import UTC, datetime
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


def test_recommendation_history_api_flow():
    client, store, advisor = _client()
    owner = "hist-api-owner-001"

    # Initially empty history
    res = client.get(
        "/api/v1/advisor/recommendation-history",
        headers={"X-Owner-ID": owner},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["schema_version"] == "recommendation-history-response.v1"
    assert data["total_count"] == 0
    assert data["items"] == []

    # Run advisor query to create an event
    tmpl = advisor.query_template(owner)
    q_res = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": owner},
        json={
            "query_id": "q-h-api-001",
            "fixture_id": "advisor-research-two-lineage-001",
            "generated_at": NOW.isoformat(),
            "questionnaire": tmpl.questionnaire.model_dump(mode="json"),
            "portfolio": tmpl.portfolio.model_dump(mode="json"),
        },
    )
    assert q_res.status_code == 200
    receipt1_id = q_res.json()["event"]["receipt_id"]

    # History should now have 1 item
    res = client.get(
        "/api/v1/advisor/recommendation-history",
        headers={"X-Owner-ID": owner},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == 1
    assert data["items"][0]["receipt_id"] == receipt1_id

    # Create second receipt with conservative profile
    q2 = tmpl.questionnaire.model_copy(update={"loss_tolerance_score": 1})
    q2_res = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": owner},
        json={
            "query_id": "q-h-api-002",
            "fixture_id": "advisor-research-two-lineage-001",
            "generated_at": NOW.isoformat(),
            "questionnaire": q2.model_dump(mode="json"),
            "portfolio": tmpl.portfolio.model_dump(mode="json"),
        },
    )
    assert q2_res.status_code == 200
    receipt2_id = q2_res.json()["event"]["receipt_id"]

    # Compare receipts
    comp_res = client.post(
        "/api/v1/advisor/recommendation-history/compare",
        headers={"X-Owner-ID": owner},
        json={
            "schema_version": "recommendation-comparison-request.v1",
            "owner_id": owner,
            "receipt_a_id": receipt1_id,
            "receipt_b_id": receipt2_id,
        },
    )
    assert comp_res.status_code == 200
    comp_data = comp_res.json()
    assert comp_data["schema_version"] == "recommendation-comparison-response.v1"
    assert comp_data["receipt_a_id"] == receipt1_id
    assert comp_data["receipt_b_id"] == receipt2_id
    assert "summary" in comp_data

    # Owner isolation: other owner cannot compare
    comp_unauth = client.post(
        "/api/v1/advisor/recommendation-history/compare",
        headers={"X-Owner-ID": "other-owner"},
        json={
            "schema_version": "recommendation-comparison-request.v1",
            "owner_id": "other-owner",
            "receipt_a_id": receipt1_id,
            "receipt_b_id": receipt2_id,
        },
    )
    assert comp_unauth.status_code in (404, 403)

    store.close()
