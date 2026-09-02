from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from app.api import create_app
from app.service import (
    FixturePortfolioOptimizationService,
    FixtureScenarioSimulationService,
)
from app.simulation import (
    ScenarioDiffDimension,
    ScenarioSimulationId,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
    ScenarioSimulationStatus,
    ScenarioSimulationTemplateResponse,
)
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 2, tzinfo=UTC)


def _client(*, simulation_service: FixtureScenarioSimulationService | None = None):
    store = SQLiteDecisionEventStore(":memory:")
    client = TestClient(
        create_app(
            store,
            clock=lambda: NOW,
            scenario_simulation_service=simulation_service,
        )
    )
    return client, store


def _template(owner: str = "phase33-owner"):
    service = FixturePortfolioOptimizationService()
    opt_template = service.template(owner)
    return opt_template


def _request(
    scenario: ScenarioSimulationId = ScenarioSimulationId.BASELINE_READY,
    owner: str = "phase33-owner",
) -> ScenarioSimulationRequest:
    template = _template(owner)
    return ScenarioSimulationRequest(
        request_id="phase33-sim-request-001",
        owner_id=owner,
        generated_at=NOW,
        questionnaire=template.questionnaire,
        portfolio=template.portfolio,
        scenario_id=scenario,
    )


def test_scenario_template_endpoint_is_owner_closed_and_safe() -> None:
    client, store = _client()
    response = client.get(
        "/api/v1/advisor/scenario-simulation-template",
        headers={"X-Owner-ID": "test-owner-001"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == "scenario-simulation-template.v1"
    assert body["owner_id"] == "test-owner-001"
    assert len(body["scenarios"]) == 4
    scenario_ids = [s["scenario_id"] for s in body["scenarios"]]
    assert scenario_ids == sorted(scenario_ids)


def test_scenario_template_requires_owner_header() -> None:
    client, store = _client()
    response = client.get("/api/v1/advisor/scenario-simulation-template")
    assert response.status_code == 403


def test_baseline_ready_simulation_run() -> None:
    client, store = _client()
    req = _request(ScenarioSimulationId.BASELINE_READY, owner="owner-baseline")
    payload = req.model_dump(mode="json")
    response = client.post(
        "/api/v1/advisor/scenario-simulation-runs",
        headers={"X-Owner-ID": "owner-baseline"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    validated = ScenarioSimulationResponse.model_validate(body)
    assert validated.status == ScenarioSimulationStatus.READY
    assert validated.baseline.status == ScenarioSimulationStatus.READY
    assert validated.simulated.status == ScenarioSimulationStatus.READY
    assert len(validated.metric_diffs) > 0
    assert len(validated.target_diffs) > 0
    assert len(validated.issues) == 0

    # Verify no store side effect
    assert len(store.list("owner-baseline")) == 0


def test_tighter_tech_cap_simulation_run() -> None:
    client, store = _client()
    req = _request(ScenarioSimulationId.TIGHTER_TECH_CAP, owner="owner-tech-cap")
    payload = req.model_dump(mode="json")
    response = client.post(
        "/api/v1/advisor/scenario-simulation-runs",
        headers={"X-Owner-ID": "owner-tech-cap"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    validated = ScenarioSimulationResponse.model_validate(body)
    assert validated.status == ScenarioSimulationStatus.READY
    assert validated.scenario.scenario_id == ScenarioSimulationId.TIGHTER_TECH_CAP
    assert validated.assumption.delta == Decimal("-10.00")

    # Check metric diff for tech cap
    tech_cap_diff = next(
        d for d in validated.metric_diffs if d.metric_id == "metric:05:max_technology_cap_pct"
    )
    assert tech_cap_diff.delta == Decimal("-10.00")


def test_top_asset_trim_simulation_run() -> None:
    client, store = _client()
    req = _request(ScenarioSimulationId.TOP_ASSET_TRIM_10PP, owner="owner-top-trim")
    payload = req.model_dump(mode="json")
    response = client.post(
        "/api/v1/advisor/scenario-simulation-runs",
        headers={"X-Owner-ID": "owner-top-trim"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    validated = ScenarioSimulationResponse.model_validate(body)
    assert validated.status == ScenarioSimulationStatus.READY
    assert validated.scenario.scenario_id == ScenarioSimulationId.TOP_ASSET_TRIM_10PP

    # Check total portfolio value delta is 0
    val_diff = next(
        d for d in validated.metric_diffs if d.metric_id == "metric:01:total_portfolio_value_cny"
    )
    assert val_diff.delta == Decimal("0.00")


def test_lookthrough_partial_simulation_run() -> None:
    client, store = _client()
    req = _request(ScenarioSimulationId.LOOKTHROUGH_PARTIAL, owner="owner-partial")
    payload = req.model_dump(mode="json")
    response = client.post(
        "/api/v1/advisor/scenario-simulation-runs",
        headers={"X-Owner-ID": "owner-partial"},
        json=payload,
    )
    assert response.status_code == 200
    body = response.json()
    validated = ScenarioSimulationResponse.model_validate(body)
    assert validated.status == ScenarioSimulationStatus.REVIEW_REQUIRED
    assert validated.simulated.status == ScenarioSimulationStatus.REVIEW_REQUIRED
    assert len(validated.metric_diffs) == 0
    assert len(validated.target_diffs) == 0
    assert len(validated.issues) > 0


def test_owner_mismatch_is_forbidden() -> None:
    client, store = _client()
    req = _request(ScenarioSimulationId.BASELINE_READY, owner="owner-a")
    payload = req.model_dump(mode="json")
    response = client.post(
        "/api/v1/advisor/scenario-simulation-runs",
        headers={"X-Owner-ID": "owner-b"},
        json=payload,
    )
    assert response.status_code == 403
