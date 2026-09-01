from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.api import create_app
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 6, tzinfo=UTC)


def _client() -> tuple[TestClient, SQLiteDecisionEventStore]:
    store = SQLiteDecisionEventStore(":memory:")
    return TestClient(create_app(store, clock=lambda: NOW)), store


def test_query_template_replay_rebinds_portfolio_and_profile_for_each_owner() -> None:
    client, store = _client()
    first = client.get(
        "/api/v1/advisor/query-template",
        headers={"X-Owner-ID": "phase18-context-owner"},
    )
    assert first.status_code == 200
    body = first.json()
    assert body["schema_version"] == "advisor-query-template.v1"
    assert body["questionnaire"]["owner_id"] == "phase18-context-owner"
    assert body["portfolio"]["owner_id"] == "phase18-context-owner"
    assert body["portfolio"]["position_snapshot"]["owner_id"] == "phase18-context-owner"
    assert all(
        position["owner_id"] == "phase18-context-owner"
        for position in body["portfolio"]["position_snapshot"]["positions"]
    )
    assert all(
        snapshot["owner_id"] == "phase18-context-owner"
        for snapshot in body["portfolio"]["fund_holdings"]
    )
    assert "api_key" not in first.text.casefold()

    repeated = client.get(
        "/api/v1/advisor/query-template",
        headers={"X-Owner-ID": "phase18-context-owner"},
    )
    assert repeated.status_code == 200
    assert repeated.json() == body

    other = client.get(
        "/api/v1/advisor/query-template",
        headers={"X-Owner-ID": "phase18-context-other"},
    )
    assert other.status_code == 200
    assert other.json()["questionnaire"]["owner_id"] == "phase18-context-other"
    assert "phase18-context-owner" not in other.text
    store.close()


def test_one_hundred_query_template_reads_are_deterministic_and_side_effect_free() -> None:
    client, store = _client()
    headers = {"X-Owner-ID": "phase18-template-replay"}
    first = client.get("/api/v1/advisor/query-template", headers=headers)
    assert first.status_code == 200
    expected = first.json()
    for _ in range(99):
        replay = client.get("/api/v1/advisor/query-template", headers=headers)
        assert replay.status_code == 200
        assert replay.json() == expected
    assert store.list("phase18-template-replay") == ()
    store.close()


def test_query_template_errors_and_static_context_boundary_are_safe() -> None:
    client, store = _client()
    missing = client.get("/api/v1/advisor/query-template")
    assert missing.status_code == 403
    assert missing.json()["error_code"] == "OWNER_SCOPE"

    sensitive = client.get(
        "/api/v1/advisor/query-template",
        headers={"X-Owner-ID": "api_key-owner"},
    )
    assert sensitive.status_code == 400
    assert sensitive.json() == {
        "schema_version": "api-error.v1",
        "error_code": "ADVISOR_QUERY_ERROR",
        "message": "advisor query was refused",
    }
    assert "api_key" not in sensitive.text.casefold()

    page = client.get("/")
    js = client.get("/static/app.js")
    css = client.get("/static/styles.css")
    assert page.status_code == js.status_code == css.status_code == 200
    assert 'id="portfolio-content"' in page.text
    assert 'id="profile-template-content"' in page.text
    assert 'href="#portfolio"' in page.text
    assert "/api/v1/advisor/query-template" in js.text
    assert "renderPortfolio" in js.text
    assert "renderProfileContext" in js.text
    assert "innerHTML" not in js.text
    assert "https://" not in page.text
    assert ".portfolio-panel" in css.text
    store.close()
