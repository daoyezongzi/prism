"""Strict contracts for bounded, auditable hypothetical simulations.

Simulation output is deliberately separate from Evidence, Fact, Finding,
Recommendation and Decision Receipt contracts.  It describes a deterministic
overlay over an observed snapshot; it never turns the overlay into an observed
financial fact.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.optimization import OptimizationStatus
from app.portfolio import PortfolioImportBundle
from app.profile import RiskLevel, RiskQuestionnaire
from app.risk import BudgetAssessmentStatus


SCENARIO_SIMULATION_METHODOLOGY_VERSION = "SCENARIO_SIMULATION_V1"
_CENT = Decimal("0.01")
_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "secret",
    "token",
    "credential",
    "cookie",
)


Unit = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=64),
]


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _sensitive(serialized: str) -> bool:
    normalized = serialized.casefold().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_SUBSTRINGS)


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT)


class ScenarioSimulationId(StrEnum):
    BASELINE_READY = "BASELINE_READY"
    LOOKTHROUGH_PARTIAL = "LOOKTHROUGH_PARTIAL"
    TIGHTER_TECH_CAP = "TIGHTER_TECH_CAP"
    TOP_ASSET_TRIM_10PP = "TOP_ASSET_TRIM_10PP"


class ScenarioSimulationStatus(StrEnum):
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class ScenarioOverlayType(StrEnum):
    IDENTITY = "IDENTITY"
    LIMIT_OVERRIDE = "LIMIT_OVERRIDE"
    PORTFOLIO_ALLOCATION_SHIFT = "PORTFOLIO_ALLOCATION_SHIFT"
    DATA_COVERAGE = "DATA_COVERAGE"


class ScenarioRunSide(StrEnum):
    BASELINE = "BASELINE"
    SCENARIO = "SCENARIO"


class ScenarioDiffDimension(StrEnum):
    INPUT = "INPUT"
    EXPOSURE = "EXPOSURE"
    CONCENTRATION = "CONCENTRATION"
    RISK_BUDGET = "RISK_BUDGET"
    OPTIMIZATION = "OPTIMIZATION"


class ScenarioSimulationIssue(ContractModel):
    """Safe issue projection; raw provider/exception payloads are forbidden."""

    code: NonEmptyStr
    safe_message: NonEmptyStr
    dimension: ScenarioDiffDimension | None = None
    target_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario simulation issue must not contain sensitive fields")
        return self


class ScenarioDefinition(ContractModel):
    """One fixed, server-owned hypothetical scenario."""

    scenario_id: ScenarioSimulationId
    label: NonEmptyStr
    description: NonEmptyStr
    overlay_type: ScenarioOverlayType
    parameter_summary: NonEmptyStr

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario definition must not contain sensitive metadata")
        return self


class ScenarioAssumption(ContractModel):
    """Typed description of a hypothetical overlay, never an observed fact."""

    overlay_type: ScenarioOverlayType
    dimension: NonEmptyStr
    target_id: NonEmptyStr | None = None
    baseline_value: Decimal | None = None
    scenario_value: Decimal | None = None
    delta: Decimal | None = None
    unit: Unit | None = None
    summary: NonEmptyStr
    hypothetical: Literal[True] = True

    @model_validator(mode="after")
    def validate_assumption(self) -> Self:
        if (self.baseline_value is None) != (self.scenario_value is None):
            raise ValueError("assumption baseline and scenario values must be paired")
        if self.baseline_value is not None:
            baseline = _quantize(self.baseline_value)
            scenario = _quantize(self.scenario_value)  # type: ignore[arg-type]
            if self.delta is None or _quantize(self.delta) != _quantize(scenario - baseline):
                raise ValueError("assumption delta does not close baseline and scenario values")
            if self.unit is None:
                raise ValueError("numeric assumption requires a unit")
        elif self.delta is not None or self.unit is not None:
            raise ValueError("non-numeric assumption must not carry numeric delta or unit")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario assumption must not contain sensitive fields")
        return self


class ScenarioTargetDiff(ContractModel):
    """Before/after target row; it is not an order or recommendation."""

    target_id: NonEmptyStr
    asset_name: NonEmptyStr
    baseline_value: Decimal | None = None
    scenario_value: Decimal | None = None
    delta: Decimal | None = None
    unit: Unit = "PCT"

    @model_validator(mode="after")
    def validate_target_diff(self) -> Self:
        if (self.baseline_value is None) != (self.scenario_value is None):
            raise ValueError("target diff values must be paired")
        if self.baseline_value is None:
            if self.delta is not None:
                raise ValueError("target diff without values must not carry delta")
        elif self.delta is None or _quantize(self.delta) != _quantize(self.scenario_value - self.baseline_value):  # type: ignore[operator]
            raise ValueError("target diff delta does not close values")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario target diff must not contain sensitive fields")
        return self


class ScenarioMetricDiff(ContractModel):
    """One deterministic metric delta with no missing-value fabrication."""

    metric_id: NonEmptyStr
    dimension: ScenarioDiffDimension
    label: NonEmptyStr
    baseline_value: Decimal | None = None
    scenario_value: Decimal | None = None
    delta: Decimal | None = None
    unit: Unit | None = None

    @model_validator(mode="after")
    def validate_metric_diff(self) -> Self:
        if (self.baseline_value is None) != (self.scenario_value is None):
            raise ValueError("metric diff values must be paired")
        if self.baseline_value is None:
            if self.delta is not None or self.unit is not None:
                raise ValueError("missing metric values must not carry delta or unit")
        else:
            if self.delta is None or _quantize(self.delta) != _quantize(self.scenario_value - self.baseline_value):  # type: ignore[operator]
                raise ValueError("metric diff delta does not close values")
            if self.unit is None:
                raise ValueError("numeric metric diff requires a unit")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario metric diff must not contain sensitive fields")
        return self


class ScenarioRunSummary(ContractModel):
    """Safe projection of one side of a simulation."""

    side: ScenarioRunSide
    status: ScenarioSimulationStatus
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    profile_version: int = Field(ge=1)
    risk_level: RiskLevel
    portfolio_bundle_id: NonEmptyStr
    position_snapshot_id: NonEmptyStr
    exposure_report_id: NonEmptyStr | None = None
    concentration_report_id: NonEmptyStr | None = None
    assessment_id: NonEmptyStr | None = None
    assessment_status: BudgetAssessmentStatus | None = None
    optimization_status: OptimizationStatus | None = None
    technology_weight_pct: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    top_asset_weight_pct: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("100"))
    asset_hhi: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("10000"))
    sector_hhi: Decimal | None = Field(default=None, ge=Decimal("0"), le=Decimal("10000"))
    targets: tuple[ScenarioTargetDiff, ...] = Field(default_factory=tuple)
    issues: tuple[ScenarioSimulationIssue, ...] = Field(default_factory=tuple)
    source_contribution_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if len(set(self.source_contribution_ids)) != len(self.source_contribution_ids):
            raise ValueError("scenario source contribution IDs must be unique")
        target_ids = [target.target_id for target in self.targets]
        if target_ids != sorted(target_ids) or len(target_ids) != len(set(target_ids)):
            raise ValueError("scenario target summaries must be unique and sorted")
        if self.status == ScenarioSimulationStatus.READY:
            if self.optimization_status != OptimizationStatus.READY:
                raise ValueError("READY scenario summary requires READY optimization")
            if self.technology_weight_pct is None or self.top_asset_weight_pct is None:
                raise ValueError("READY scenario summary requires exposure metrics")
            if self.asset_hhi is None or self.sector_hhi is None:
                raise ValueError("READY scenario summary requires concentration metrics")
            if self.issues:
                raise ValueError("READY scenario summary must not carry issues")
        else:
            if self.optimization_status == OptimizationStatus.READY:
                raise ValueError("non-READY scenario summary must not carry READY optimization")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario run summary must not contain sensitive fields")
        return self


class ScenarioSimulationTrace(ContractModel):
    schema_version: Literal["scenario-simulation-trace.v1"] = "scenario-simulation-trace.v1"
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    scenario_id: ScenarioSimulationId
    input_fingerprint: NonEmptyStr
    baseline_run_id: NonEmptyStr
    simulated_run_id: NonEmptyStr
    baseline_bundle_id: NonEmptyStr
    simulated_bundle_id: NonEmptyStr
    baseline_snapshot_id: NonEmptyStr
    simulated_snapshot_id: NonEmptyStr
    methodology_version: Literal["SCENARIO_SIMULATION_V1"] = SCENARIO_SIMULATION_METHODOLOGY_VERSION
    source_contribution_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    calculation_steps: tuple[NonEmptyStr, ...] = Field(min_length=1)
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    derived_values_are_hypothetical: Literal[True] = True

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        if len(set(self.source_contribution_ids)) != len(self.source_contribution_ids):
            raise ValueError("scenario trace contribution IDs must be unique")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario trace must not contain sensitive fields")
        return self


class ScenarioSimulationRequest(ContractModel):
    schema_version: Literal["scenario-simulation-request.v1"] = "scenario-simulation-request.v1"
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    questionnaire: RiskQuestionnaire
    portfolio: PortfolioImportBundle
    scenario_id: ScenarioSimulationId = ScenarioSimulationId.BASELINE_READY

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if self.questionnaire.owner_id != self.owner_id:
            raise ValueError("questionnaire owner_id does not match request owner_id")
        if self.portfolio.owner_id != self.owner_id:
            raise ValueError("portfolio owner_id does not match request owner_id")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario simulation request must not contain sensitive fields")
        return self


class ScenarioSimulationTemplateResponse(ContractModel):
    schema_version: Literal["scenario-simulation-template.v1"] = "scenario-simulation-template.v1"
    owner_id: NonEmptyStr
    generated_at: datetime
    methodology_version: Literal["SCENARIO_SIMULATION_V1"] = SCENARIO_SIMULATION_METHODOLOGY_VERSION
    scenarios: tuple[ScenarioDefinition, ...] = Field(min_length=4)
    supported_dimensions: tuple[ScenarioDiffDimension, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_template(self) -> Self:
        _aware(self.generated_at, "generated_at")
        scenario_ids = [item.scenario_id for item in self.scenarios]
        if scenario_ids != sorted(scenario_ids, key=lambda item: item.value):
            raise ValueError("scenario definitions must be sorted by scenario_id")
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("scenario definitions must not contain duplicates")
        if set(scenario_ids) != set(ScenarioSimulationId):
            raise ValueError("scenario template must contain every simulation scenario")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario simulation template must not contain sensitive fields")
        return self


class ScenarioSimulationResponse(ContractModel):
    schema_version: Literal["scenario-simulation-response.v1"] = "scenario-simulation-response.v1"
    simulation_id: NonEmptyStr
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    scenario: ScenarioDefinition
    assumption: ScenarioAssumption
    profile_id: NonEmptyStr
    profile_version: int = Field(ge=1)
    baseline: ScenarioRunSummary
    simulated: ScenarioRunSummary
    metric_diffs: tuple[ScenarioMetricDiff, ...] = Field(default_factory=tuple)
    target_diffs: tuple[ScenarioTargetDiff, ...] = Field(default_factory=tuple)
    status: ScenarioSimulationStatus
    issues: tuple[ScenarioSimulationIssue, ...] = Field(default_factory=tuple)
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    trace: ScenarioSimulationTrace

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if self.baseline.side != ScenarioRunSide.BASELINE:
            raise ValueError("baseline summary must be BASELINE side")
        if self.simulated.side != ScenarioRunSide.SCENARIO:
            raise ValueError("simulated summary must be SCENARIO side")
        for summary in (self.baseline, self.simulated):
            if summary.owner_id != self.owner_id:
                raise ValueError("scenario summary owner does not match response owner")
            if summary.profile_id != self.profile_id:
                raise ValueError("scenario summary profile does not match response profile")
            if summary.profile_version != self.profile_version:
                raise ValueError("scenario summary profile version does not match response")
        if self.trace.owner_id != self.owner_id or self.trace.profile_id != self.profile_id:
            raise ValueError("scenario trace identity does not match response")
        if self.trace.scenario_id != self.scenario.scenario_id:
            raise ValueError("scenario trace scenario does not match response")
        if self.trace.baseline_bundle_id != self.baseline.portfolio_bundle_id:
            raise ValueError("scenario trace baseline bundle does not match response")
        if self.trace.simulated_bundle_id != self.simulated.portfolio_bundle_id:
            raise ValueError("scenario trace simulated bundle does not match response")
        if self.trace.baseline_snapshot_id != self.baseline.position_snapshot_id:
            raise ValueError("scenario trace baseline snapshot does not match response")
        if self.trace.simulated_snapshot_id != self.simulated.position_snapshot_id:
            raise ValueError("scenario trace simulated snapshot does not match response")
        if tuple(self.invalidation_conditions) != tuple(self.trace.invalidation_conditions):
            raise ValueError("scenario invalidation conditions do not match trace")

        metric_ids = [item.metric_id for item in self.metric_diffs]
        if metric_ids != sorted(metric_ids) or len(metric_ids) != len(set(metric_ids)):
            raise ValueError("scenario metric diffs must be unique and sorted")
        target_ids = [item.target_id for item in self.target_diffs]
        if target_ids != sorted(target_ids) or len(target_ids) != len(set(target_ids)):
            raise ValueError("scenario target diffs must be unique and sorted")

        statuses = {self.baseline.status, self.simulated.status}
        expected = (
            ScenarioSimulationStatus.BLOCKED
            if ScenarioSimulationStatus.BLOCKED in statuses
            else ScenarioSimulationStatus.REVIEW_REQUIRED
            if ScenarioSimulationStatus.REVIEW_REQUIRED in statuses
            else ScenarioSimulationStatus.READY
        )
        if self.status != expected:
            raise ValueError("scenario response status does not match side statuses")
        if self.status == ScenarioSimulationStatus.READY:
            if self.issues or self.baseline.issues or self.simulated.issues:
                raise ValueError("READY scenario response must not carry issues")
        elif self.metric_diffs or self.target_diffs:
            raise ValueError("non-READY scenario response must not carry fabricated diffs")
        if _sensitive(self.model_dump_json()):
            raise ValueError("scenario simulation response must not contain sensitive fields")
        return self


__all__ = [
    "SCENARIO_SIMULATION_METHODOLOGY_VERSION",
    "ScenarioAssumption",
    "ScenarioDefinition",
    "ScenarioDiffDimension",
    "ScenarioMetricDiff",
    "ScenarioOverlayType",
    "ScenarioRunSide",
    "ScenarioRunSummary",
    "ScenarioSimulationId",
    "ScenarioSimulationIssue",
    "ScenarioSimulationRequest",
    "ScenarioSimulationResponse",
    "ScenarioSimulationStatus",
    "ScenarioSimulationTemplateResponse",
    "ScenarioSimulationTrace",
    "ScenarioTargetDiff",
]
