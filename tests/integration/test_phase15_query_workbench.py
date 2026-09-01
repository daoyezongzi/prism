from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api import create_app
from app.store import SQLiteDecisionEventStore


OWNER = "ui-owner-001"


def _client() -> tuple[TestClient, SQLiteDecisionEventStore]:
    store = SQLiteDecisionEventStore(":memory:")
    return TestClient(create_app(store, clock=lambda: datetime(2026, 9, 2, 5, tzinfo=UTC))), store


def test_query_template_is_owner_rebound_and_safe() -> None:
    client, store = _client()
    response = client.get(
        "/api/v1/advisor/query-template",
        headers={"X-Owner-ID": OWNER},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "advisor-query-template.v1"
    assert body["fixture_id"] == "advisor-research-two-lineage-001"
    assert body["questionnaire"]["owner_id"] == OWNER
    assert body["portfolio"]["owner_id"] == OWNER
    assert body["portfolio"]["position_snapshot"]["owner_id"] == OWNER
    assert all(
        item["owner_id"] == OWNER
        for item in body["portfolio"]["position_snapshot"]["positions"]
    )
    assert all(
        snapshot["owner_id"] == OWNER
        for snapshot in body["portfolio"]["fund_holdings"]
    )
    assert "api_key" not in response.text.casefold()
    store.close()


def test_query_template_requires_owner_scope() -> None:
    client, store = _client()
    response = client.get("/api/v1/advisor/query-template")
    assert response.status_code == 403
    assert response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "OWNER_SCOPE",
        "message": "owner scope is not allowed",
    }
    store.close()


def test_static_workbench_exposes_structured_query_without_unsafe_rendering() -> None:
    client, store = _client()
    page = client.get("/")
    css = client.get("/static/styles.css")
    js = client.get("/static/app.js")
    assert page.status_code == 200
    assert 'id="advisor-query-form"' in page.text
    assert 'id="run-advisor-query"' in page.text
    assert css.status_code == 200 and ".query-form" in css.text
    assert js.status_code == 200
    assert "/api/v1/advisor/query-template" in js.text
    assert "/api/v1/advisor/queries" in js.text
    assert "innerHTML" not in js.text
    assert "<script>" not in page.text
    store.close()
