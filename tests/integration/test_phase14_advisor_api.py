from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api import create_app
from app.gates import GateStatus
from app.service import AdvisorQueryRequest
from app.store import SQLiteDecisionEventStore
from tests.unit.test_advisor_query import _request


OWNER = "gate-owner-001"
RECORDED_AT = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def _client():
    store = SQLiteDecisionEventStore(":memory:")
    client = TestClient(create_app(store, clock=lambda: RECORDED_AT))
    return client, store


def test_advisor_query_api_runs_full_fixture_pipeline_and_is_idempotent() -> None:
    client, store = _client()
    request = _request(query_id="api-query-balanced-001")
    payload = request.model_dump(mode="json")
    first = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=payload,
    )
    assert first.status_code == 200
    assert first.json()["created"] is True
    assert first.json()["status"] == GateStatus.PASS.value
    assert first.json()["event"]["result"]["receipt"] is not None
    assert first.json()["event"]["result"]["trace"]["evidence"]

    repeated = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=payload,
    )
    assert repeated.status_code == 200
    assert repeated.json()["created"] is False
    assert repeated.json()["event"] == first.json()["event"]
    event_id = first.json()["event"]["event_id"]
    detail = client.get(
        f"/api/v1/decision-events/{event_id}", headers={"X-Owner-ID": OWNER}
    )
    assert detail.status_code == 200
    assert detail.json()["result"]["status"] == GateStatus.PASS.value
    store.close()


def test_advisor_query_api_exposes_profile_conditioned_reduce() -> None:
    client, store = _client()
    request = _request(query_id="api-query-conservative-001", conservative=True)
    response = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=request.model_dump(mode="json"),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == GateStatus.PASS.value
    assert {
        item["action_type"] for item in body["event"]["result"]["trace"]["recommendations"]
    } == {"REDUCE"}
    store.close()


def test_advisor_query_api_rejects_owner_fixture_and_contract_errors_safely() -> None:
    client, store = _client()
    request = _request(query_id="api-query-errors-001")
    wrong_owner = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": "other-owner"},
        json=request.model_dump(mode="json"),
    )
    assert wrong_owner.status_code == 403
    assert wrong_owner.json() == {
        "schema_version": "api-error.v1",
        "error_code": "OWNER_SCOPE",
        "message": "owner scope is not allowed",
    }

    unknown_fixture = request.model_copy(update={"fixture_id": "unknown-fixture"})
    unknown = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=unknown_fixture.model_dump(mode="json"),
    )
    assert unknown.status_code == 400
    assert unknown.json() == {
        "schema_version": "api-error.v1",
        "error_code": "ADVISOR_QUERY_ERROR",
        "message": "advisor query was refused",
    }

    invalid = request.model_dump(mode="json")
    invalid["generated_at"] = "not-a-time"
    invalid_response = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=invalid,
    )
    assert invalid_response.status_code == 422
    assert invalid_response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "INVALID_INPUT",
        "message": "request failed contract validation",
    }
    store.close()


def test_advisor_query_request_rejects_nested_owner_mismatch() -> None:
    request = _request(query_id="api-query-owner-mismatch-001")
    payload = request.model_dump(mode="json")
    payload["portfolio"]["owner_id"] = "other-owner"
    client, store = _client()
    response = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=payload,
    )
    assert response.status_code == 422
    assert response.json()["error_code"] == "INVALID_INPUT"
    assert "other-owner" not in response.text
    store.close()
