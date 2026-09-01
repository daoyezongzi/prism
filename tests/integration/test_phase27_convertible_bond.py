from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import create_app
from app.convertible_bond import (
    ConvertibleBondResearchNodeResponse,
    ConvertibleBondResearchResponse,
    ConvertibleBondResearchScenarioId,
    ConvertibleBondRiskSummary,
)
from app.providers import ProviderOperation
from app.research import ResearchNodeKind, allowed_operations_for_node
from app.service import FixtureConvertibleBondResearchService
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 2, tzinfo=UTC)


def _client(*, convertible_bond_service: object | None = None):
    store = SQLiteDecisionEventStore(":memory:")
    client = TestClient(
        create_app(
            store,
            clock=lambda: NOW,
            convertible_bond_service=convertible_bond_service,
        )
    )
    return client, store


def _payload(
    *,
    owner: str = "phase27-owner",
    request_id: str = "phase27-convertible-001",
    scenario_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "convertible-bond-research-request.v1",
        "request_id": request_id,
        "owner_id": owner,
        "subject": "PRISM_CONVERTIBLE_BOND_DEMO_H",
        "period": "2026-Q2",
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    return payload


def test_convertible_template_is_safe_sorted_and_formula_explicit() -> None:
    client, store = _client()
    response = client.get(
        "/api/v1/advisor/convertible-bond-research-template",
        headers={"X-Owner-ID": "phase27-template-owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["manifest_id"] == "convertible-bond-research-demo-h-001"
    assert [item["metric"] for item in body["metrics"]] == sorted(
        item["metric"] for item in body["metrics"]
    )
    assert len(body["metrics"]) == 9
    assert {item["metric"] for item in body["metrics"] if item["derived"]} == {
        "conversion_value",
        "conversion_premium_pct",
    }
    assert all(
        item.get("formula")
        for item in body["metrics"]
        if item["derived"]
    )
    assert len(body["risk_rules"]) == 5
    assert {item["operator"] for item in body["risk_rules"]} >= {"LT", "GT", "GTE"}
    assert body["credit_rating_labels"]["4"] == "AA-"
    scenario_ids = [item["scenario_id"] for item in body["scenarios"]]
    assert scenario_ids == sorted(scenario_ids)
    assert scenario_ids == [
        item.value
        for item in sorted(ConvertibleBondResearchScenarioId, key=lambda item: item.value)
    ]
    assert "expected_value" not in response.text
    assert "convertible-bond-research-source-a" not in response.text
    assert "api_key" not in response.text.casefold()
    store.close()


def test_convertible_baseline_builds_formula_facts_risks_and_closed_trace() -> None:
    client, store = _client()
    payload = _payload()
    response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_status"] == "COMPLETED"
    assert body["pipeline_status"] == "READY"
    assert len(body["validations"]) == 7
    assert len(body["facts"]) == 9
    assert len(body["trace"]["facts"]) == 9
    assert len(body["trace"]["evidence"]) == 16
    values = {item["metric"]: item["value"] for item in body["facts"]}
    assert values["conversion_value"] == "125.00"
    assert values["conversion_premium_pct"] == "36.00"
    assert body["risk"]["status"] == "HIGH_RISK"
    assert {
        item["kind"]
        for item in body["findings"]
        if item["severity"] != "INFO"
    } == {
        "CONVERTIBLE_PREMIUM_WARNING",
        "CONVERTIBLE_BOND_FLOOR_WARNING",
        "CONVERTIBLE_NEGATIVE_YIELD",
        "CONVERTIBLE_CREDIT_RISK",
        "CONVERTIBLE_LIQUIDITY_RISK",
    }
    assert body["trace"]["recommendations"] == []
    assert store.list(payload["owner_id"]) == ()
    evidence_by_id = {item["evidence_id"]: item for item in body["trace"]["evidence"]}
    for fact in body["facts"]:
        assert fact["status"] == "VERIFIED"
        assert set(fact["evidence_ids"]).issubset(evidence_by_id)
    formula_evidence = [
        item for item in body["trace"]["evidence"]
        if item["provider"] == "prism-deterministic"
    ]
    assert {item["field"] for item in formula_evidence} == {
        "conversion_value",
        "conversion_premium_pct",
    }
    assert set(body["risk"]["finding_ids"]).issubset(
        {item["finding_id"] for item in body["findings"]}
    )
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
def test_convertible_scenarios_preserve_degraded_semantics(
    scenario_id: str,
    run_status: str,
    pipeline_status: str,
) -> None:
    client, store = _client()
    payload = _payload(
        request_id=f"phase27-{scenario_id}",
        scenario_id=scenario_id,
    )
    response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["run_status"] == run_status
    assert body["pipeline_status"] == pipeline_status
    if scenario_id == "BASELINE_READY":
        assert body["risk"]["status"] == "HIGH_RISK"
        assert len(body["facts"]) == 9
        store.close()
        return
    target = next(item for item in body["nodes"] if item["node_id"].endswith("source-b"))
    if scenario_id == "SOURCE_PARTIAL":
        assert target["status"] == "PARTIAL"
        assert target["missing_fields"] == ["bond_floor"]
        assert any(issue["code"] == "MISSING_FIELDS" for issue in target["issues"])
    elif scenario_id == "SOURCE_EMPTY":
        assert target["status"] == "EMPTY"
        assert "no records" in target["scope_description"]
    elif scenario_id == "SOURCE_DISAGREEMENT":
        assert target["status"] == "COMPLETE"
    elif scenario_id == "SOURCE_FAILED":
        assert target["status"] == "FAILED"
        assert any(issue["code"] == "SOURCE_UNAVAILABLE" for issue in target["issues"])
    assert body["risk"]["status"] == "NOT_ASSESSED"
    assert body["facts"] == []
    assert body["findings"] == []
    assert body["trace"]["facts"] == []
    assert body["trace"]["findings"] == []
    assert body["trace"]["evidence"]
    assert body["issues"]
    assert body["trace"]["recommendations"] == []
    store.close()


def test_convertible_disagreement_exposes_both_conversion_prices_without_promotion() -> None:
    client, store = _client()
    payload = _payload(
        request_id="phase27-disagreement-evidence",
        scenario_id="SOURCE_DISAGREEMENT",
    )
    response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    validation = next(
        item for item in body["validations"] if item["metric"] == "conversion_price"
    )
    assert validation["status"] == "UNRESOLVED"
    assert len(validation["supporting_evidence_ids"]) == 1
    assert len(validation["contradicting_evidence_ids"]) == 1
    evidence = [
        item for item in body["trace"]["evidence"] if item["field"] == "conversion_price"
    ]
    assert {item["value"] for item in evidence} == {"10.00", "11.00"}
    assert store.list(payload["owner_id"]) == ()
    store.close()


def test_convertible_replay_is_stable_and_scenario_changes_run_identity() -> None:
    client, store = _client()
    baseline = _payload(request_id="phase27-stable", scenario_id="BASELINE_READY")
    disagreement = _payload(request_id="phase27-stable", scenario_id="SOURCE_DISAGREEMENT")
    first = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": baseline["owner_id"]},
        json=baseline,
    )
    repeated = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": baseline["owner_id"]},
        json=baseline,
    )
    conflict = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": disagreement["owner_id"]},
        json=disagreement,
    )
    assert first.status_code == repeated.status_code == conflict.status_code == 200
    assert first.json() == repeated.json()
    assert first.json()["run_id"] != conflict.json()["run_id"]
    store.close()


def test_convertible_request_rejects_scope_extra_sensitive_naive_unknown_and_owner() -> None:
    client, store = _client()
    payload = _payload()
    wrong_owner = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": "other-phase27-owner"},
        json=payload,
    )
    assert wrong_owner.status_code == 403
    assert wrong_owner.json()["error_code"] == "OWNER_SCOPE"

    extra_response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json={**payload, "unexpected": "do-not-echo"},
    )
    assert extra_response.status_code == 422
    assert extra_response.json()["error_code"] == "INVALID_INPUT"
    assert "do-not-echo" not in extra_response.text

    sensitive_response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json={**payload, "request_id": "api_key"},
    )
    assert sensitive_response.status_code == 422
    assert "api_key" not in sensitive_response.text.casefold()

    naive_response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json={**payload, "generated_at": "2026-09-02T02:00:00"},
    )
    assert naive_response.status_code == 422
    assert naive_response.json()["error_code"] == "INVALID_INPUT"

    unknown_response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json={**payload, "scenario_id": "NOT_A_SCENARIO"},
    )
    assert unknown_response.status_code == 422

    wrong_scope_response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json={**payload, "subject": "OTHER_CONVERTIBLE"},
    )
    assert wrong_scope_response.status_code == 400
    assert wrong_scope_response.json()["error_code"] == "CONVERTIBLE_BOND_RESEARCH_ERROR"
    store.close()


def test_convertible_api_revalidates_injected_output_and_rejects_scope_drift() -> None:
    class DriftedConvertibleService:
        def __init__(self) -> None:
            self._delegate = FixtureConvertibleBondResearchService()

        def template(self, owner_id: str):
            return self._delegate.template(owner_id)

        async def run(self, request):
            result = await self._delegate.run(request)
            return result.model_copy(update={"subject": "DRIFTED_CONVERTIBLE"})

    client, store = _client(convertible_bond_service=DriftedConvertibleService())
    payload = _payload(request_id="phase27-injected-drift")
    response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 400
    assert response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "CONVERTIBLE_BOND_RESEARCH_ERROR",
        "message": "convertible-bond research was refused",
    }
    assert "DRIFTED_CONVERTIBLE" not in response.text
    store.close()


def test_convertible_response_risk_cannot_hide_triggered_findings() -> None:
    client, store = _client()
    payload = _payload(request_id="phase27-risk-closure")
    response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    original = ConvertibleBondResearchResponse.model_validate(response.json())
    forged = original.model_copy(
        update={
            "risk": ConvertibleBondRiskSummary(
                status="CLEAR",
                summary="规则未触发；这不是交易建议。",
                finding_ids=(),
            )
        }
    )
    with pytest.raises(ValidationError):
        ConvertibleBondResearchResponse.model_validate(forged.model_dump(mode="python"))
    store.close()


def test_convertible_response_rejects_forged_formula_values_and_duplicate_metrics() -> None:
    client, store = _client()
    payload = _payload(request_id="phase27-formula-closure")
    response = client.post(
        "/api/v1/advisor/convertible-bond-research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    original = ConvertibleBondResearchResponse.model_validate(response.json())
    forged_facts = list(original.facts)
    conversion_index = next(
        index for index, fact in enumerate(forged_facts) if fact.metric == "conversion_value"
    )
    forged_conversion = forged_facts[conversion_index].model_copy(update={"value": "999.00"})
    forged_facts[conversion_index] = forged_conversion
    forged_trace = original.trace.model_copy(update={"facts": tuple(sorted(forged_facts, key=lambda item: item.fact_id))})
    with pytest.raises(ValidationError):
        ConvertibleBondResearchResponse.model_validate(
            original.model_copy(update={"facts": tuple(sorted(forged_facts, key=lambda item: item.fact_id)), "trace": forged_trace}).model_dump(mode="python")
        )

    duplicate_facts = list(original.facts)
    duplicate_facts[-1] = duplicate_facts[-1].model_copy(update={"metric": duplicate_facts[0].metric})
    duplicate_facts = tuple(sorted(duplicate_facts, key=lambda item: item.fact_id))
    duplicate_trace = original.trace.model_copy(update={"facts": duplicate_facts})
    with pytest.raises(ValidationError):
        ConvertibleBondResearchResponse.model_validate(
            original.model_copy(update={"facts": duplicate_facts, "trace": duplicate_trace}).model_dump(mode="python")
        )
    store.close()


def test_convertible_explicit_operation_and_node_kind_are_compatible() -> None:
    assert ProviderOperation.CONVERTIBLE_BOND_DATA.value == "CONVERTIBLE_BOND_DATA"
    assert ProviderOperation.CONVERTIBLE_BOND_DATA in allowed_operations_for_node(
        ResearchNodeKind.CONVERTIBLE_BOND
    )


def test_convertible_workbench_static_boundary_is_text_only_and_same_origin() -> None:
    client, store = _client()
    page = client.get("/")
    js = client.get("/static/app.js")
    css = client.get("/static/styles.css")
    assert page.status_code == js.status_code == css.status_code == 200
    assert 'id="convertible-bond-research"' in page.text
    assert 'id="convertible-bond-research-scenario"' in page.text
    assert "synthetic/offline replay" in page.text
    assert "/api/v1/advisor/convertible-bond-research-template" in js.text
    assert "/api/v1/advisor/convertible-bond-research-runs" in js.text
    assert "innerHTML" not in js.text
    assert "https://" not in page.text
    assert ".convertible-bond-research-panel" in css.text
    store.close()


def _node_projection_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "node_id": "convertible-bond-research-source-a",
        "required": True,
        "status": "COMPLETE",
        "started_at": NOW,
        "finished_at": NOW,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize(
    "payload",
    [
        _node_projection_payload(missing_fields=("bond_floor",)),
        _node_projection_payload(
            issues=(
                {"code": "SOURCE_UNAVAILABLE", "safe_message": "source requires review"},
            )
        ),
        _node_projection_payload(status="PARTIAL"),
        _node_projection_payload(status="EMPTY"),
        _node_projection_payload(
            status="EMPTY", scope_description="empty source", missing_fields=("metric",)
        ),
        _node_projection_payload(status="FAILED"),
        _node_projection_payload(
            status="FAILED",
            issues=({"code": "SOURCE_UNAVAILABLE", "safe_message": "source failed"},),
            missing_fields=("metric",),
        ),
        _node_projection_payload(status="PENDING", started_at=NOW),
        _node_projection_payload(status="RUNNING", started_at=None, finished_at=None),
        _node_projection_payload(
            status="RUNNING",
            issues=({"code": "SOURCE_UNAVAILABLE", "safe_message": "source requires review"},),
        ),
        _node_projection_payload(status="CANCELLED"),
    ],
)
def test_convertible_node_projection_rejects_contradictory_state(payload: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        ConvertibleBondResearchNodeResponse.model_validate(payload)
