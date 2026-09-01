"""Phase 22 structured investment intent and deterministic plan preview."""

from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient

from app.api import create_app
from app.api.contracts import AdvisorIntentRequest, AdvisorPlanResponse
from app.store import SQLiteDecisionEventStore


OWNER = "phase22-intent-owner"


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


def _request(template: dict, *, intent_type: str = "TECHNOLOGY_EXPOSURE_REVIEW") -> dict:
    questionnaire = template["questionnaire"]
    portfolio = template["portfolio"]
    return {
        "schema_version": "advisor-intent-request.v1",
        "intent_id": "phase22-intent-001",
        "owner_id": OWNER,
        "intent_type": intent_type,
        "generated_at": template["generated_at"],
        "portfolio_bundle_id": portfolio["bundle_id"],
        "position_snapshot_id": portfolio["position_snapshot"]["snapshot_id"],
        "questionnaire_id": questionnaire["questionnaire_id"],
    }


def test_both_structured_intents_map_to_the_existing_four_track_plan() -> None:
    client, store = _client()
    template = _template(client)
    plans = []
    for intent_type in ("TECHNOLOGY_EXPOSURE_REVIEW", "PORTFOLIO_RISK_REVIEW"):
        response = client.post(
            "/api/v1/advisor/plans",
            headers={"X-Owner-ID": OWNER},
            json=_request(template, intent_type=intent_type),
        )
        assert response.status_code == 200
        body = response.json()
        plans.append(body)
        assert body["schema_version"] == "advisor-plan-response.v1"
        assert body["intent_type"] == intent_type
        assert body["owner_id"] == OWNER
        assert body["node_count"] == 8
        assert set(body["roles"]) == {"MACRO", "INDUSTRY", "STOCK", "ETF_FUND"}
        assert body["scope_description"]
        assert "recommend" not in response.text.casefold()
        assert "finding" not in response.text.casefold()
        assert "evidence" not in response.text.casefold()

    assert plans[0]["plan_id"] != plans[1]["plan_id"]
    replay = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=_request(template),
    )
    assert replay.status_code == 200
    assert replay.json() == plans[0]
    assert store.list(OWNER) == ()
    store.close()


def test_intent_request_and_response_models_are_strict_and_timezone_bound() -> None:
    client, store = _client()
    template = _template(client)
    valid = _request(template)
    assert AdvisorIntentRequest.model_validate(valid).intent_id == "phase22-intent-001"
    response = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=valid,
    )
    assert response.status_code == 200
    assert AdvisorPlanResponse.model_validate(response.json()).node_count == 8

    extra = {**valid, "unexpected": True}
    extra_response = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=extra,
    )
    assert extra_response.status_code == 422
    assert extra_response.json()["error_code"] == "INVALID_INPUT"
    assert "unexpected" not in extra_response.text

    naive = {**valid, "generated_at": "2026-09-02T00:00:00"}
    naive_response = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=naive,
    )
    assert naive_response.status_code == 422
    assert naive_response.json()["error_code"] == "INVALID_INPUT"

    sensitive = {**valid, "questionnaire_id": "secret-questionnaire"}
    sensitive_response = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=sensitive,
    )
    assert sensitive_response.status_code == 422
    assert sensitive_response.json()["error_code"] == "INVALID_INPUT"
    assert "secret-questionnaire" not in sensitive_response.text
    store.close()


def test_intent_plan_is_owner_scoped_and_has_no_persistence_side_effect() -> None:
    client, store = _client()
    template = _template(client)
    valid = _request(template)

    missing = client.post("/api/v1/advisor/plans", json=valid)
    assert missing.status_code == 403
    assert missing.json()["error_code"] == "OWNER_SCOPE"

    wrong_header = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": "phase22-other-owner"},
        json=valid,
    )
    assert wrong_header.status_code == 403
    assert wrong_header.json()["error_code"] == "OWNER_SCOPE"
    assert "phase22-other-owner" not in wrong_header.text

    wrong_body = {**valid, "owner_id": "phase22-other-owner"}
    wrong_body_response = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=wrong_body,
    )
    assert wrong_body_response.status_code == 403
    assert wrong_body_response.json()["error_code"] == "OWNER_SCOPE"
    assert "phase22-other-owner" not in wrong_body_response.text

    unknown_intent = {**valid, "intent_type": "FREE_FORM_ADVICE"}
    unknown_response = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=unknown_intent,
    )
    assert unknown_response.status_code == 422
    assert unknown_response.json()["error_code"] == "INVALID_INPUT"
    assert "FREE_FORM_ADVICE" not in unknown_response.text

    assert store.list(OWNER) == ()
    store.close()


def test_intent_plan_does_not_mutate_or_replace_advisor_query_flow() -> None:
    client, store = _client()
    template = _template(client)
    plan = client.post(
        "/api/v1/advisor/plans",
        headers={"X-Owner-ID": OWNER},
        json=_request(template),
    )
    assert plan.status_code == 200

    questionnaire = deepcopy(template["questionnaire"])
    questionnaire["questionnaire_id"] = "phase22-query-questionnaire"
    query = {
        "schema_version": "advisor-query.v1",
        "query_id": "phase22-query-001",
        "fixture_id": template["fixture_id"],
        "generated_at": template["generated_at"],
        "questionnaire": questionnaire,
        "portfolio": template["portfolio"],
    }
    response = client.post(
        "/api/v1/advisor/queries",
        headers={"X-Owner-ID": OWNER},
        json=query,
    )
    assert response.status_code == 200
    assert response.json()["event"]["owner_id"] == OWNER
    assert store.list(OWNER)
    store.close()


def test_static_intent_planning_boundary_is_same_origin_and_text_only() -> None:
    client, store = _client()
    page = client.get("/")
    js = client.get("/static/app.js")
    css = client.get("/static/styles.css")
    assert page.status_code == js.status_code == css.status_code == 200
    assert 'id="intent-type"' in page.text
    assert 'id="preview-advisor-plan"' in page.text
    assert 'id="advisor-plan-content"' in page.text
    assert "/api/v1/advisor/plans" in js.text
    assert "renderAdvisorPlan" in js.text
    assert "clearAdvisorPlan" in js.text
    assert "innerHTML" not in js.text
    assert "https://" not in page.text
    assert "fetch(\"http" not in js.text
    assert ".intent-planning" in css.text
    store.close()
