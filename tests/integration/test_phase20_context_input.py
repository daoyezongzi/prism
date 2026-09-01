"""Phase 20 structured context confirmation and Advisor binding evidence."""

from __future__ import annotations

from copy import deepcopy
import json

from fastapi.testclient import TestClient

from app.api import create_app
from app.store import SQLiteDecisionEventStore


OWNER = "phase20-context-owner"


def _client() -> tuple[TestClient, SQLiteDecisionEventStore]:
    store = SQLiteDecisionEventStore(":memory:")
    return TestClient(create_app(store)), store


def _template(client: TestClient, owner: str = OWNER) -> dict:
    response = client.get(
        "/api/v1/advisor/query-template",
        headers={"X-Owner-ID": owner},
    )
    assert response.status_code == 200
    return response.json()


def test_portfolio_context_confirmation_is_strict_and_side_effect_free() -> None:
    client, store = _client()
    template = _template(client)
    portfolio = deepcopy(template["portfolio"])
    portfolio["bundle_id"] = "phase20-imported-bundle-001"
    portfolio["position_snapshot"]["snapshot_id"] = "phase20-imported-snapshot-001"

    response = client.post(
        "/api/v1/advisor/context/portfolio",
        headers={"X-Owner-ID": OWNER},
        json={
            "schema_version": "portfolio-context-request.v1",
            "portfolio": portfolio,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "portfolio-context-response.v1"
    assert body["portfolio"]["bundle_id"] == "phase20-imported-bundle-001"
    assert body["portfolio"]["position_snapshot"]["snapshot_id"] == (
        "phase20-imported-snapshot-001"
    )
    assert body["position_count"] == 1
    assert body["fund_snapshot_count"] == 1
    assert body["holding_count"] == 4
    assert store.list(OWNER) == ()
    store.close()


def test_profile_context_confirmation_reuses_existing_scorer_deterministically() -> None:
    client, store = _client()
    template = _template(client)
    payload = {
        "schema_version": "profile-context-request.v1",
        "questionnaire": template["questionnaire"],
    }
    first = client.post(
        "/api/v1/advisor/context/profile",
        headers={"X-Owner-ID": OWNER},
        json=payload,
    )
    second = client.post(
        "/api/v1/advisor/context/profile",
        headers={"X-Owner-ID": OWNER},
        json=payload,
    )
    assert first.status_code == second.status_code == 200
    first_body = first.json()
    assert first_body == second.json()
    assert first_body["schema_version"] == "profile-context-response.v1"
    assert first_body["profile"]["owner_id"] == OWNER
    assert first_body["profile"]["questionnaire_id"] == template["questionnaire"][
        "questionnaire_id"
    ]
    assert first_body["profile"]["risk_score"] == "50.00"
    assert first_body["profile"]["risk_level"] == "BALANCED"
    assert store.list(OWNER) == ()
    store.close()


def test_context_confirmation_rejects_owner_mismatch_extra_sensitive_and_bad_time() -> None:
    client, store = _client()
    template = _template(client)

    wrong_owner = client.post(
        "/api/v1/advisor/context/portfolio",
        headers={"X-Owner-ID": "other-owner"},
        json={
            "schema_version": "portfolio-context-request.v1",
            "portfolio": template["portfolio"],
        },
    )
    assert wrong_owner.status_code == 403
    assert wrong_owner.json()["error_code"] == "OWNER_SCOPE"
    assert "other-owner" not in wrong_owner.text

    extra = {
        "schema_version": "portfolio-context-request.v1",
        "portfolio": template["portfolio"],
        "unexpected": True,
    }
    extra_response = client.post(
        "/api/v1/advisor/context/portfolio",
        headers={"X-Owner-ID": OWNER},
        json=extra,
    )
    assert extra_response.status_code == 422
    assert extra_response.json()["error_code"] == "INVALID_INPUT"
    assert "unexpected" not in extra_response.text

    sensitive = deepcopy(template["portfolio"])
    sensitive["position_snapshot"]["positions"][0]["asset_name"] = "secret account"
    sensitive_response = client.post(
        "/api/v1/advisor/context/portfolio",
        headers={"X-Owner-ID": OWNER},
        json={
            "schema_version": "portfolio-context-request.v1",
            "portfolio": sensitive,
        },
    )
    assert sensitive_response.status_code == 422
    assert sensitive_response.json()["error_code"] == "INVALID_INPUT"
    assert "secret account" not in sensitive_response.text

    bad_time = deepcopy(template["questionnaire"])
    bad_time["answered_at"] = "2026-09-02T00:00:00"
    bad_time_response = client.post(
        "/api/v1/advisor/context/profile",
        headers={"X-Owner-ID": OWNER},
        json={
            "schema_version": "profile-context-request.v1",
            "questionnaire": bad_time,
        },
    )
    assert bad_time_response.status_code == 422
    assert bad_time_response.json()["error_code"] == "INVALID_INPUT"
    store.close()


def test_context_confirmation_rejects_nested_owner_and_fund_parent_drift() -> None:
    client, store = _client()
    template = _template(client)

    nested_owner = deepcopy(template["portfolio"])
    nested_owner["position_snapshot"]["positions"][0]["owner_id"] = "other-owner"
    nested_owner_response = client.post(
        "/api/v1/advisor/context/portfolio",
        headers={"X-Owner-ID": OWNER},
        json={
            "schema_version": "portfolio-context-request.v1",
            "portfolio": nested_owner,
        },
    )
    assert nested_owner_response.status_code == 422
    assert nested_owner_response.json()["error_code"] == "INVALID_INPUT"
    assert "other-owner" not in nested_owner_response.text

    parent_drift = deepcopy(template["portfolio"])
    parent_drift["fund_holdings"][0]["parent_asset_id"] = "missing-parent"
    parent_response = client.post(
        "/api/v1/advisor/context/portfolio",
        headers={"X-Owner-ID": OWNER},
        json={
            "schema_version": "portfolio-context-request.v1",
            "portfolio": parent_drift,
        },
    )
    assert parent_response.status_code == 422
    assert parent_response.json()["error_code"] == "INVALID_INPUT"
    assert "missing-parent" not in parent_response.text
    store.close()


def test_confirmed_portfolio_is_bound_to_existing_advisor_receipt_and_event() -> None:
    client, store = _client()
    template = _template(client)
    portfolio = deepcopy(template["portfolio"])
    portfolio["bundle_id"] = "phase20-advisor-imported-bundle"
    portfolio["position_snapshot"]["snapshot_id"] = "phase20-advisor-imported-snapshot"

    confirmed = client.post(
        "/api/v1/advisor/context/portfolio",
        headers={"X-Owner-ID": OWNER},
        json={
            "schema_version": "portfolio-context-request.v1",
            "portfolio": portfolio,
        },
    )
    assert confirmed.status_code == 200
    questionnaire = deepcopy(template["questionnaire"])
    questionnaire["questionnaire_id"] = "phase20-advisor-questionnaire"
    query = {
        "schema_version": "advisor-query.v1",
        "query_id": "phase20-imported-query-001",
        "fixture_id": template["fixture_id"],
        "generated_at": template["generated_at"],
        "questionnaire": questionnaire,
        "portfolio": confirmed.json()["portfolio"],
    }
    response = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=query,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["event"]["result"]["receipt"]["portfolio_bundle_id"] == (
        "phase20-advisor-imported-bundle"
    )
    assert body["event"]["result"]["receipt"]["position_snapshot_id"] == (
        "phase20-advisor-imported-snapshot"
    )
    assert store.list(OWNER)
    store.close()


def test_context_static_boundary_has_same_origin_controls_and_no_raw_dom_injection() -> None:
    client, store = _client()
    page = client.get("/")
    js = client.get("/static/app.js")
    assert page.status_code == js.status_code == 200
    assert 'id="portfolio-json"' in page.text
    assert 'id="confirm-portfolio"' in page.text
    assert 'id="confirm-profile"' in page.text
    assert "/api/v1/advisor/context/portfolio" in js.text
    assert "/api/v1/advisor/context/profile" in js.text
    assert "JSON.parse" in js.text
    assert "innerHTML" not in js.text
    assert "https://" not in page.text
    assert "fetch(\"http" not in js.text
    store.close()
