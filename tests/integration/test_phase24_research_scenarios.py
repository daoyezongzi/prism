from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.research import ResearchScenarioId
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 2, tzinfo=UTC)
MATRIX_ID = "specialist-matrix-four-track-001"


def _client():
    store = SQLiteDecisionEventStore(":memory:")
    client = TestClient(create_app(store, clock=lambda: NOW))
    return client, store


def _payload(
    *,
    owner: str = "phase24-owner",
    request_id: str = "phase24-research-001",
    scenario_id: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "schema_version": "research-specialist-matrix-request.v1",
        "matrix_id": MATRIX_ID,
        "request_id": request_id,
        "owner_id": owner,
        "generated_at": NOW.isoformat().replace("+00:00", "Z"),
    }
    if scenario_id is not None:
        payload["scenario_id"] = scenario_id
    return payload


def test_template_exposes_safe_sorted_scenario_catalog() -> None:
    client, store = _client()
    response = client.get(
        "/api/v1/advisor/research-matrix-template",
        headers={"X-Owner-ID": "phase24-template-owner"},
    )
    assert response.status_code == 200
    body = response.json()
    scenario_ids = [item["scenario_id"] for item in body["scenarios"]]
    assert scenario_ids == sorted(scenario_ids)
    assert scenario_ids == [item.value for item in sorted(ResearchScenarioId, key=lambda item: item.value)]
    assert all(item["label"] and item["description"] for item in body["scenarios"])
    assert "expected_value" not in response.text
    assert "matrix-macro-source-a" not in response.text
    assert "api_key" not in response.text.casefold()
    store.close()


@pytest.mark.parametrize(
    ("scenario_id", "run_status", "pipeline_status", "target_node", "target_status"),
    [
        (
            ResearchScenarioId.BASELINE_READY.value,
            "COMPLETED",
            "READY",
            None,
            None,
        ),
        (
            ResearchScenarioId.SOURCE_DISAGREEMENT.value,
            "COMPLETED",
            "REVIEW_REQUIRED",
            "macro-source-b",
            "COMPLETE",
        ),
        (
            ResearchScenarioId.SOURCE_PARTIAL.value,
            "FAILED",
            "REVIEW_REQUIRED",
            "fund-source-b",
            "PARTIAL",
        ),
        (
            ResearchScenarioId.SOURCE_EMPTY.value,
            "FAILED",
            "REVIEW_REQUIRED",
            "industry-source-b",
            "EMPTY",
        ),
        (
            ResearchScenarioId.SOURCE_FAILED.value,
            "FAILED",
            "REVIEW_REQUIRED",
            "stock-source-b",
            "FAILED",
        ),
    ],
)
def test_each_scenario_preserves_status_and_fact_boundary(
    scenario_id: str,
    run_status: str,
    pipeline_status: str,
    target_node: str | None,
    target_status: str | None,
) -> None:
    client, store = _client()
    payload = _payload(scenario_id=scenario_id, request_id=f"phase24-{scenario_id}")
    response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario"]["scenario_id"] == scenario_id
    assert body["run_status"] == run_status
    assert body["pipeline_status"] == pipeline_status
    assert len(body["nodes"]) == 8
    assert body["trace"]["recommendations"] == []
    if scenario_id == ResearchScenarioId.BASELINE_READY.value:
        assert len(body["validations"]) == 4
        assert len(body["trace"]["facts"]) == 4
        assert len(body["trace"]["findings"]) == 4
    else:
        assert body["trace"]["facts"] == []
        assert body["trace"]["findings"] == []
        assert body["issues"]
        assert target_node is not None
        node = next(item for item in body["nodes"] if item["node_id"] == target_node)
        assert node["status"] == target_status
    store.close()


def test_disagreement_exposes_both_values_without_promoting_fact() -> None:
    client, store = _client()
    payload = _payload(
        request_id="phase24-disagreement-evidence",
        scenario_id=ResearchScenarioId.SOURCE_DISAGREEMENT.value,
    )
    response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    macro_validation = next(
        item for item in body["validations"] if item["claim_id"] == "claim-macro-policy-rate"
    )
    assert macro_validation["status"] == "UNRESOLVED"
    assert len(macro_validation["supporting_evidence_ids"]) == 1
    assert len(macro_validation["contradicting_evidence_ids"]) == 1
    macro_evidence = [
        item
        for item in body["trace"]["evidence"]
        if item["field"] == "policy_rate_pct"
    ]
    assert {item["value"] for item in macro_evidence} == {"2.50", "3.25"}
    assert {item["source"] for item in macro_evidence} == {
        "matrix-macro-source-a",
        "matrix-macro-source-b",
    }
    assert store.list(payload["owner_id"]) == ()
    store.close()


def test_scenario_changes_are_part_of_run_identity() -> None:
    client, store = _client()
    base_payload = _payload(request_id="phase24-same-request", scenario_id="BASELINE_READY")
    conflict_payload = _payload(
        request_id="phase24-same-request",
        scenario_id=ResearchScenarioId.SOURCE_DISAGREEMENT.value,
    )
    base = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": base_payload["owner_id"]},
        json=base_payload,
    )
    conflict = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": conflict_payload["owner_id"]},
        json=conflict_payload,
    )
    assert base.status_code == conflict.status_code == 200
    assert base.json()["run_id"] != conflict.json()["run_id"]
    assert store.list(base_payload["owner_id"]) == ()
    store.close()


@pytest.mark.parametrize("scenario_id", [item.value for item in ResearchScenarioId])
def test_scenario_replay_is_stable_and_side_effect_free(scenario_id: str) -> None:
    client, store = _client()
    payload = _payload(
        request_id=f"phase24-replay-{scenario_id}",
        scenario_id=scenario_id,
    )
    first = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    repeated = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=payload,
    )
    assert first.status_code == repeated.status_code == 200
    assert first.json() == repeated.json()
    assert store.list(payload["owner_id"]) == ()
    store.close()


def test_scenario_request_rejects_scope_extra_sensitive_naive_and_unknown_inputs() -> None:
    client, store = _client()
    payload = _payload(scenario_id=ResearchScenarioId.BASELINE_READY.value)

    wrong_owner = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": "other-phase24-owner"},
        json=payload,
    )
    assert wrong_owner.status_code == 403
    assert wrong_owner.json()["error_code"] == "OWNER_SCOPE"

    extra = {**payload, "unexpected": "do-not-echo"}
    extra_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=extra,
    )
    assert extra_response.status_code == 422
    assert extra_response.json()["error_code"] == "INVALID_INPUT"
    assert "do-not-echo" not in extra_response.text

    unknown = {**payload, "scenario_id": "NOT_A_SCENARIO"}
    unknown_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=unknown,
    )
    assert unknown_response.status_code == 422
    assert unknown_response.json()["error_code"] == "INVALID_INPUT"

    sensitive = {**payload, "scenario_id": "api_key"}
    sensitive_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=sensitive,
    )
    assert sensitive_response.status_code == 422
    assert "api_key" not in sensitive_response.text.casefold()

    naive = {**payload, "generated_at": "2026-09-02T02:00:00"}
    naive_response = client.post(
        "/api/v1/advisor/research-runs",
        headers={"X-Owner-ID": payload["owner_id"]},
        json=naive,
    )
    assert naive_response.status_code == 422
    assert naive_response.json()["error_code"] == "INVALID_INPUT"
    store.close()


def test_research_scenario_workbench_static_boundary_is_text_only() -> None:
    client, store = _client()
    page = client.get("/")
    js = client.get("/static/app.js")
    css = client.get("/static/styles.css")
    assert page.status_code == 200
    assert 'id="research-scenario"' in page.text
    assert "离线合成演示" in page.text
    assert js.status_code == 200
    assert "scenario_id" in js.text
    assert "可用证据" in js.text
    assert "innerHTML" not in js.text
    assert "https://" not in page.text
    assert css.status_code == 200 and ".research-scenario-picker" in css.text
    store.close()
