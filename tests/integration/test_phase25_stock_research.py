from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.store import SQLiteDecisionEventStore
from app.stock import StockResearchScenarioId


NOW = datetime(2026, 9, 2, 2, tzinfo=UTC)


def _client():
    store = SQLiteDecisionEventStore(":memory:")
    client = TestClient(create_app(store, clock=lambda: NOW))
    return client, store


def _payload(
    *,
    owner: str = "phase25-owner",
    request_id: str = "phase25-stock-001",
    scenario_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "stock-research-request.v1",
        "request_id": request_id,
        "owner_id": owner,
        "subject": "PRISM_STOCK_DEMO_F",
        "period": "2026-Q2",
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    return payload


def test_stock_template_is_safe_sorted_and_explains_fixed_rules() -> None:
    client, store = _client()
    response = client.get(
        "/api/v1/advisor/stock-research-template",
        headers={"X-Owner-ID": "phase25-template-owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["manifest_id"] == "stock-research-demo-f-001"
    assert [item["metric"] for item in body["metrics"]] == sorted(
        item["metric"] for item in body["metrics"]
    )
    scenario_ids = [item["scenario_id"] for item in body["scenarios"]]
    assert scenario_ids == sorted(scenario_ids)
    assert scenario_ids == [
        item.value for item in sorted(StockResearchScenarioId, key=lambda item: item.value)
    ]
    assert len(body["risk_rules"]) == 3
    assert "expected_value" not in response.text
    assert "stock-research-source-a" not in response.text
    assert "api_key" not in response.text.casefold()
    store.close()


def test_baseline_builds_facts_anomalies_risk_and_closed_trace() -> None:
    client, store = _client()
    payload = _payload()
    response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_status"] == "COMPLETED"
    assert body["pipeline_status"] == "READY"
    assert len(body["validations"]) == 6
    assert len(body["facts"]) == 6
    assert len(body["trace"]["facts"]) == 6
    assert len(body["trace"]["evidence"]) == 12
    assert body["risk"]["status"] == "HIGH_RISK"
    assert {item["kind"] for item in body["findings"]} >= {
        "STOCK_CASHFLOW_QUALITY_ANOMALY",
        "STOCK_RECEIVABLE_QUALITY_ANOMALY",
        "STOCK_LEVERAGE_RISK",
    }
    assert body["trace"]["recommendations"] == []
    assert store.list(payload["owner_id"]) == ()
    evidence_ids = {item["evidence_id"] for item in body["trace"]["evidence"]}
    for fact in body["facts"]:
        assert fact["status"] == "VERIFIED"
        assert set(fact["evidence_ids"]).issubset(evidence_ids)
    finding_ids = {item["finding_id"] for item in body["findings"]}
    assert set(body["risk"]["finding_ids"]).issubset(finding_ids)
    store.close()


@pytest.mark.parametrize(
    ("scenario_id", "run_status", "pipeline_status"),
    [
        ("BASELINE_READY", "COMPLETED", "READY"),
        ("SOURCE_DISAGREEMENT", "COMPLETED", "REVIEW_REQUIRED"),
        ("SOURCE_PARTIAL", "FAILED", "REVIEW_REQUIRED"),
        ("SOURCE_EMPTY", "FAILED", "REVIEW_REQUIRED"),
        ("SOURCE_FAILED", "FAILED", "REVIEW_REQUIRED"),
    ],
)
def test_stock_scenarios_preserve_degraded_semantics(
    scenario_id: str,
    run_status: str,
    pipeline_status: str,
) -> None:
    client, store = _client()
    payload = _payload(
        request_id=f"phase25-{scenario_id}",
        scenario_id=scenario_id,
    )
    response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_status"] == run_status
    assert body["pipeline_status"] == pipeline_status
    if scenario_id == "BASELINE_READY":
        assert body["risk"]["status"] == "HIGH_RISK"
        assert len(body["facts"]) == 6
        store.close()
        return
    assert body["risk"]["status"] == "NOT_ASSESSED"
    assert body["facts"] == []
    assert body["findings"] == []
    assert body["trace"]["facts"] == []
    assert body["trace"]["findings"] == []
    assert body["trace"]["evidence"]
    assert body["issues"]
    assert body["trace"]["recommendations"] == []
    store.close()


def test_disagreement_exposes_both_debt_values_without_fact_promotion() -> None:
    client, store = _client()
    payload = _payload(
        request_id="phase25-disagreement-evidence",
        scenario_id="SOURCE_DISAGREEMENT",
    )
    response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    validation = next(item for item in body["validations"] if item["metric"] == "debt_ratio_pct")
    assert validation["status"] == "UNRESOLVED"
    assert len(validation["supporting_evidence_ids"]) == 1
    assert len(validation["contradicting_evidence_ids"]) == 1
    debt_evidence = [
        item for item in body["trace"]["evidence"] if item["field"] == "debt_ratio_pct"
    ]
    assert {item["value"] for item in debt_evidence} == {"78.00", "62.00"}
    assert store.list(payload["owner_id"]) == ()
    store.close()


def test_stock_replay_is_stable_and_scenario_changes_run_identity() -> None:
    client, store = _client()
    baseline = _payload(request_id="phase25-stable", scenario_id="BASELINE_READY")
    disagreement = _payload(request_id="phase25-stable", scenario_id="SOURCE_DISAGREEMENT")
    first = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": baseline["owner_id"]},
        json=baseline,
    )
    repeated = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": baseline["owner_id"]},
        json=baseline,
    )
    conflict = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": disagreement["owner_id"]},
        json=disagreement,
    )
    assert first.status_code == repeated.status_code == conflict.status_code == 200
    assert first.json() == repeated.json()
    assert first.json()["run_id"] != conflict.json()["run_id"]
    assert store.list(baseline["owner_id"]) == ()
    store.close()


def test_stock_request_rejects_owner_scope_extra_sensitive_naive_unknown_and_wrong_scope() -> None:
    client, store = _client()
    payload = _payload()
    wrong_owner = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": "other-phase25-owner"},
        json=payload,
    )
    assert wrong_owner.status_code == 403
    assert wrong_owner.json()["error_code"] == "OWNER_SCOPE"

    extra = {**payload, "unexpected": "do-not-echo"}
    extra_response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=extra,
    )
    assert extra_response.status_code == 422
    assert extra_response.json()["error_code"] == "INVALID_INPUT"
    assert "do-not-echo" not in extra_response.text

    sensitive = {**payload, "request_id": "api_key"}
    sensitive_response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=sensitive,
    )
    assert sensitive_response.status_code == 422
    assert "api_key" not in sensitive_response.text.casefold()

    naive = {**payload, "generated_at": "2026-09-02T02:00:00"}
    naive_response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=naive,
    )
    assert naive_response.status_code == 422
    assert naive_response.json()["error_code"] == "INVALID_INPUT"

    unknown = {**payload, "scenario_id": "NOT_A_SCENARIO"}
    unknown_response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=unknown,
    )
    assert unknown_response.status_code == 422

    wrong_scope = {**payload, "subject": "OTHER_STOCK"}
    wrong_scope_response = client.post(
        "/api/v1/advisor/stock-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=wrong_scope,
    )
    assert wrong_scope_response.status_code == 400
    assert wrong_scope_response.json()["error_code"] == "STOCK_RESEARCH_ERROR"
    store.close()


def test_stock_workbench_static_boundary_is_text_only_and_same_origin() -> None:
    client, store = _client()
    page = client.get("/")
    js = client.get("/static/app.js")
    css = client.get("/static/styles.css")
    assert page.status_code == js.status_code == css.status_code == 200
    assert 'id="stock-research"' in page.text
    assert 'id="stock-research-scenario"' in page.text
    assert "synthetic/offline replay" in page.text
    assert "/api/v1/advisor/stock-research-template" in js.text
    assert "/api/v1/advisor/stock-research-runs" in js.text
    assert "innerHTML" not in js.text
    assert "https://" not in page.text
    assert ".stock-fact-grid" in css.text
    store.close()
