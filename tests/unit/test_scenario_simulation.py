from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.optimization import OptimizationStatus
from app.service import FixturePortfolioOptimizationService
from app.simulation import (
    ScenarioAssumption,
    ScenarioDefinition,
    ScenarioDiffDimension,
    ScenarioMetricDiff,
    ScenarioOverlayType,
    ScenarioRunSide,
    ScenarioRunSummary,
    ScenarioSimulationId,
    ScenarioSimulationIssue,
    ScenarioSimulationRequest,
    ScenarioSimulationStatus,
    ScenarioSimulationTemplateResponse,
    ScenarioSimulationTrace,
    ScenarioTargetDiff,
    build_overlay,
    scenario_definitions,
)


NOW = datetime(2026, 9, 2, 2, tzinfo=UTC)


def _template(owner: str = "simulation-unit-owner"):
    service = FixturePortfolioOptimizationService()
    template = service.template(owner)
    return template


def _request(scenario: ScenarioSimulationId = ScenarioSimulationId.BASELINE_READY):
    template = _template()
    return ScenarioSimulationRequest(
        request_id="simulation-unit-request",
        owner_id=template.owner_id,
        generated_at=NOW,
        questionnaire=template.questionnaire,
        portfolio=template.portfolio,
        scenario_id=scenario,
    )


def test_scenario_catalog_is_complete_sorted_and_safe() -> None:
    definitions = scenario_definitions()
    assert tuple(item.scenario_id for item in definitions) == tuple(
        sorted(ScenarioSimulationId, key=lambda item: item.value)
    )
    response = ScenarioSimulationTemplateResponse(
        owner_id="catalog-owner",
        generated_at=NOW,
        scenarios=definitions,
        supported_dimensions=tuple(ScenarioDiffDimension),
    )
    assert response.model_dump(mode="json")["schema_version"] == "scenario-simulation-template.v1"
    with pytest.raises(ValidationError):
        ScenarioSimulationTemplateResponse(
            owner_id="catalog-owner",
            generated_at=NOW,
            scenarios=definitions[:-1],
            supported_dimensions=(ScenarioDiffDimension.INPUT,),
        )


def test_request_rejects_owner_extra_sensitive_and_naive_time() -> None:
    request = _request()
    payload = request.model_dump(mode="json")
    payload["questionnaire"]["owner_id"] = "other-owner"
    with pytest.raises(ValidationError):
        ScenarioSimulationRequest.model_validate(payload)
    payload = request.model_dump(mode="json")
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        ScenarioSimulationRequest.model_validate(payload)
    payload = request.model_dump(mode="json")
    payload["request_id"] = "request-api_key-leak"
    with pytest.raises(ValidationError):
        ScenarioSimulationRequest.model_validate(payload)
    payload = request.model_dump(mode="json")
    payload["generated_at"] = "2026-09-02T02:00:00"
    with pytest.raises(ValidationError):
        ScenarioSimulationRequest.model_validate(payload)


def test_top_asset_overlay_closes_total_and_is_deterministic() -> None:
    request = _request(ScenarioSimulationId.TOP_ASSET_TRIM_10PP)
    first = build_overlay(
        request.portfolio,
        request.scenario_id,
        base_technology_cap=Decimal("40"),
    )
    second = build_overlay(
        request.portfolio,
        request.scenario_id,
        base_technology_cap=Decimal("40"),
    )
    assert first == second
    assert first.portfolio != request.portfolio
    assert first.portfolio.owner_id == request.owner_id
    assert first.portfolio.bundle_id != request.portfolio.bundle_id
    assert first.portfolio.position_snapshot.snapshot_id != request.portfolio.position_snapshot.snapshot_id
    original_total = sum(
        (item.market_value for item in request.portfolio.position_snapshot.positions),
        Decimal("0"),
    )
    simulated_total = sum(
        (item.market_value for item in first.portfolio.position_snapshot.positions),
        Decimal("0"),
    )
    assert simulated_total == original_total
    original_by_id = {
        item.position_id: item.market_value
        for item in request.portfolio.position_snapshot.positions
    }
    simulated_by_id = {
        item.position_id: item.market_value
        for item in first.portfolio.position_snapshot.positions
    }
    assert sum(
        (simulated_by_id[key] - original_by_id[key] for key in original_by_id),
        Decimal("0"),
    ) == Decimal("0")
    assert first.assumption.hypothetical is True


def test_partial_overlay_requires_fund_lookthrough_and_preserves_input() -> None:
    template = _template()
    direct = template.portfolio.model_copy(update={"fund_holdings": ()})
    with pytest.raises(ValueError, match="requires fund holdings"):
        build_overlay(
            direct,
            ScenarioSimulationId.LOOKTHROUGH_PARTIAL,
            base_technology_cap=Decimal("40"),
        )
    built = build_overlay(
        template.portfolio,
        ScenarioSimulationId.LOOKTHROUGH_PARTIAL,
        base_technology_cap=Decimal("40"),
    )
    assert all(item.coverage_pct == Decimal("80.00") for item in built.portfolio.fund_holdings)
    assert all(item.coverage_pct != Decimal("80.00") for item in template.portfolio.fund_holdings)
    assert built.assumption.overlay_type == ScenarioOverlayType.DATA_COVERAGE


def test_tighter_cap_is_hypothetical_and_does_not_mutate_budget_input() -> None:
    built = build_overlay(
        _template().portfolio,
        ScenarioSimulationId.TIGHTER_TECH_CAP,
        base_technology_cap=Decimal("40"),
    )
    assert built.technology_cap_override == Decimal("30.00")
    assert built.portfolio == _template().portfolio
    assert built.assumption.baseline_value == Decimal("40")
    assert built.assumption.scenario_value == Decimal("30.00")
    assert built.assumption.delta == Decimal("-10.00")


def test_diffs_require_real_paired_values_and_close_arithmetic() -> None:
    metric = ScenarioMetricDiff(
        metric_id="technology_weight_pct",
        dimension=ScenarioDiffDimension.EXPOSURE,
        label="Technology weight",
        baseline_value=Decimal("45.00"),
        scenario_value=Decimal("35.00"),
        delta=Decimal("-10.00"),
        unit="PCT",
    )
    target = ScenarioTargetDiff(
        target_id="asset-a",
        asset_name="Synthetic A",
        baseline_value=Decimal("45.00"),
        scenario_value=Decimal("35.00"),
        delta=Decimal("-10.00"),
    )
    assert metric.delta == Decimal("-10.00")
    assert target.delta == Decimal("-10.00")
    metric_payload = metric.model_dump(mode="python")
    metric_payload["delta"] = Decimal("-9.99")
    with pytest.raises(ValidationError):
        type(metric).model_validate(metric_payload)
    with pytest.raises(ValidationError):
        ScenarioMetricDiff(
            metric_id="missing",
            dimension=ScenarioDiffDimension.EXPOSURE,
            label="Missing",
            baseline_value=None,
            scenario_value=None,
            delta=Decimal("0"),
        )


def _summary(side: ScenarioRunSide, owner: str = "summary-owner") -> ScenarioRunSummary:
    return ScenarioRunSummary(
        side=side,
        status=ScenarioSimulationStatus.READY,
        owner_id=owner,
        profile_id="profile-001",
        profile_version=1,
        risk_level="BALANCED",
        portfolio_bundle_id="bundle-001" if side == ScenarioRunSide.BASELINE else "bundle-002",
        position_snapshot_id="snapshot-001" if side == ScenarioRunSide.BASELINE else "snapshot-002",
        exposure_report_id="exposure-001" if side == ScenarioRunSide.BASELINE else "exposure-002",
        concentration_report_id="concentration-001" if side == ScenarioRunSide.BASELINE else "concentration-002",
        assessment_id="assessment-001" if side == ScenarioRunSide.BASELINE else "assessment-002",
        assessment_status="REVIEW_REQUIRED",
        optimization_status=OptimizationStatus.READY,
        technology_weight_pct=Decimal("45.00") if side == ScenarioRunSide.BASELINE else Decimal("35.00"),
        top_asset_weight_pct=Decimal("45.00") if side == ScenarioRunSide.BASELINE else Decimal("35.00"),
        asset_hhi=Decimal("2500.00"),
        sector_hhi=Decimal("3000.00"),
    )


def test_response_closes_identity_status_and_rejects_non_ready_diffs() -> None:
    baseline = _summary(ScenarioRunSide.BASELINE)
    simulated = _summary(ScenarioRunSide.SCENARIO)
    scenario = scenario_definitions()[0]
    assumption = ScenarioAssumption(
        overlay_type=ScenarioOverlayType.IDENTITY,
        dimension="OBSERVED_SNAPSHOT",
        summary="identity",
    )
    trace = ScenarioSimulationTrace(
        owner_id="summary-owner",
        profile_id="profile-001",
        scenario_id=ScenarioSimulationId.BASELINE_READY,
        input_fingerprint="fingerprint-001",
        baseline_run_id="run-001",
        simulated_run_id="run-002",
        baseline_bundle_id="bundle-001",
        simulated_bundle_id="bundle-002",
        baseline_snapshot_id="snapshot-001",
        simulated_snapshot_id="snapshot-002",
        source_contribution_ids=("exposure-a",),
        calculation_steps=("calculate",),
        invalidation_conditions=("input changes",),
    )
    from app.simulation import ScenarioSimulationResponse

    response = ScenarioSimulationResponse(
        simulation_id="simulation-001",
        request_id="request-001",
        owner_id="summary-owner",
        generated_at=NOW,
        scenario=scenario,
        assumption=assumption,
        profile_id="profile-001",
        profile_version=1,
        baseline=baseline,
        simulated=simulated,
        metric_diffs=(
            ScenarioMetricDiff(
                metric_id="technology_weight_pct",
                dimension=ScenarioDiffDimension.EXPOSURE,
                label="Technology weight",
                baseline_value=Decimal("45.00"),
                scenario_value=Decimal("35.00"),
                delta=Decimal("-10.00"),
                unit="PCT",
            ),
        ),
        target_diffs=(),
        status=ScenarioSimulationStatus.READY,
        invalidation_conditions=("input changes",),
        trace=trace,
    )
    assert response.status == ScenarioSimulationStatus.READY
    bad = response.model_dump(mode="python")
    bad["status"] = "REVIEW_REQUIRED"
    with pytest.raises(ValidationError):
        type(response).model_validate(bad)
