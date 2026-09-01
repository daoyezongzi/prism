"""Strict contracts for deterministic portfolio target proposals.

The optimization card is intentionally a target-structure proposal.  It is
not a recommendation, order, or claim of return/risk optimality.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.portfolio import PortfolioImportBundle
from app.profile import RiskLevel, RiskQuestionnaire
from app.risk import BudgetAssessmentStatus


METHODOLOGY_VERSION = "CAP_AND_REDISTRIBUTE_V1"
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


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _sensitive(serialized: str) -> bool:
    normalized = serialized.casefold().replace("-", "_")
    return any(token in normalized for token in _SENSITIVE_SUBSTRINGS)


def _pct(value: Decimal, field_name: str) -> None:
    if value < Decimal("0") or value > Decimal("100"):
        raise ValueError(f"{field_name} must be between 0 and 100")


class OptimizationScenarioId(StrEnum):
    BASELINE_READY = "BASELINE_READY"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    INFEASIBLE = "INFEASIBLE"


class OptimizationStatus(StrEnum):
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class OptimizationIssueCode(StrEnum):
    INPUT_PARTIAL = "INPUT_PARTIAL"
    INPUT_FAILED = "INPUT_FAILED"
    INPUT_UNCLASSIFIED = "INPUT_UNCLASSIFIED"
    NON_BASE_CURRENCY = "NON_BASE_CURRENCY"
    INFEASIBLE_CONSTRAINTS = "INFEASIBLE_CONSTRAINTS"
    INVALID_SCENARIO = "INVALID_SCENARIO"


class OptimizationDimension(StrEnum):
    ASSET = "ASSET"
    SECTOR = "SECTOR"
    TECHNOLOGY = "TECHNOLOGY"
    UNCLASSIFIED = "UNCLASSIFIED"


class OptimizationDisposition(StrEnum):
    WITHIN_LIMIT = "WITHIN_LIMIT"
    REPAIRED = "REPAIRED"
    OVER_LIMIT = "OVER_LIMIT"
    UNRESOLVED = "UNRESOLVED"


class OptimizationScenarioDefinition(ContractModel):
    scenario_id: OptimizationScenarioId
    label: NonEmptyStr
    description: NonEmptyStr

    @model_validator(mode="after")
    def validate_definition(self) -> Self:
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization scenario must not contain sensitive metadata")
        return self


class OptimizationRuleResponse(ContractModel):
    dimension: OptimizationDimension
    label: NonEmptyStr
    description: NonEmptyStr
    limit_by_risk_level: dict[RiskLevel, Decimal]

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        if set(self.limit_by_risk_level) != set(RiskLevel):
            raise ValueError("optimization rule must define every risk level")
        for risk_level, value in self.limit_by_risk_level.items():
            _pct(value, f"limit_by_risk_level[{risk_level.value}]")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization rule must not contain sensitive metadata")
        return self


class PortfolioOptimizationRequest(ContractModel):
    schema_version: Literal["portfolio-optimization-request.v1"] = (
        "portfolio-optimization-request.v1"
    )
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    questionnaire: RiskQuestionnaire
    portfolio: PortfolioImportBundle
    scenario_id: OptimizationScenarioId = OptimizationScenarioId.BASELINE_READY

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if self.questionnaire.owner_id != self.owner_id:
            raise ValueError("questionnaire owner_id does not match request owner_id")
        if self.portfolio.owner_id != self.owner_id:
            raise ValueError("portfolio owner_id does not match request owner_id")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization request must not contain sensitive fields")
        return self


class OptimizationIssue(ContractModel):
    code: OptimizationIssueCode
    safe_message: NonEmptyStr
    dimension: OptimizationDimension | None = None
    target_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        if self.dimension in {
            OptimizationDimension.ASSET,
            OptimizationDimension.SECTOR,
        } and self.target_id is None:
            raise ValueError("asset/sector optimization issue requires target_id")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization issue must not contain sensitive fields")
        return self


class OptimizationConstraint(ContractModel):
    """One current/target view of a deterministic budget constraint."""

    constraint_id: NonEmptyStr
    owner_id: NonEmptyStr
    dimension: OptimizationDimension
    target_id: NonEmptyStr | None = None
    label: NonEmptyStr
    current_weight_pct: Decimal
    target_weight_pct: Decimal
    allowed_max_weight_pct: Decimal
    delta_pct: Decimal
    disposition: OptimizationDisposition
    rationale: NonEmptyStr

    @model_validator(mode="after")
    def validate_constraint(self) -> Self:
        for name, value in (
            ("current_weight_pct", self.current_weight_pct),
            ("target_weight_pct", self.target_weight_pct),
            ("allowed_max_weight_pct", self.allowed_max_weight_pct),
        ):
            _pct(value, name)
        if self.delta_pct != self.target_weight_pct - self.current_weight_pct:
            raise ValueError("optimization constraint delta does not close weights")
        if self.dimension in {
            OptimizationDimension.ASSET,
            OptimizationDimension.SECTOR,
        } and self.target_id is None:
            raise ValueError("asset/sector constraint requires target_id")
        if self.dimension in {
            OptimizationDimension.TECHNOLOGY,
            OptimizationDimension.UNCLASSIFIED,
        } and self.target_id is not None:
            raise ValueError("aggregate constraint must not have target_id")
        if self.disposition in {
            OptimizationDisposition.WITHIN_LIMIT,
            OptimizationDisposition.REPAIRED,
        } and self.target_weight_pct > self.allowed_max_weight_pct:
            raise ValueError("resolved constraint target exceeds its limit")
        if self.disposition == OptimizationDisposition.REPAIRED and (
            self.current_weight_pct <= self.allowed_max_weight_pct
        ):
            raise ValueError("REPAIRED constraint must have exceeded its current limit")
        if self.disposition == OptimizationDisposition.WITHIN_LIMIT and (
            self.current_weight_pct > self.allowed_max_weight_pct
        ):
            raise ValueError("WITHIN_LIMIT constraint must not exceed current limit")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization constraint must not contain sensitive fields")
        return self


class OptimizationTarget(ContractModel):
    """Target percentage for one observed exposure asset."""

    target_id: NonEmptyStr
    owner_id: NonEmptyStr
    asset_name: NonEmptyStr
    sector: NonEmptyStr | None = None
    current_weight_pct: Decimal
    target_weight_pct: Decimal
    delta_pct: Decimal
    allowed_max_weight_pct: Decimal
    constraint_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    rationale: NonEmptyStr

    @model_validator(mode="after")
    def validate_target(self) -> Self:
        for name, value in (
            ("current_weight_pct", self.current_weight_pct),
            ("target_weight_pct", self.target_weight_pct),
            ("allowed_max_weight_pct", self.allowed_max_weight_pct),
        ):
            _pct(value, name)
        if self.delta_pct != self.target_weight_pct - self.current_weight_pct:
            raise ValueError("optimization target delta does not close weights")
        if self.target_weight_pct > self.allowed_max_weight_pct:
            raise ValueError("optimization target exceeds single-asset limit")
        if len(set(self.constraint_ids)) != len(self.constraint_ids):
            raise ValueError("optimization target constraint IDs must be unique")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization target must not contain sensitive fields")
        return self


class OptimizationTrace(ContractModel):
    schema_version: Literal["portfolio-optimization-trace.v1"] = (
        "portfolio-optimization-trace.v1"
    )
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    portfolio_bundle_id: NonEmptyStr
    position_snapshot_id: NonEmptyStr
    exposure_report_id: NonEmptyStr | None = None
    concentration_report_id: NonEmptyStr | None = None
    assessment_id: NonEmptyStr | None = None
    methodology_version: Literal["CAP_AND_REDISTRIBUTE_V1"] = METHODOLOGY_VERSION
    source_contribution_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    calculation_steps: tuple[NonEmptyStr, ...] = Field(min_length=1)
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        if self.exposure_report_id is None and self.source_contribution_ids:
            raise ValueError("trace contributions require an exposure report")
        if len(set(self.source_contribution_ids)) != len(self.source_contribution_ids):
            raise ValueError("trace contribution IDs must be unique")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization trace must not contain sensitive fields")
        return self


class PortfolioOptimizationResponse(ContractModel):
    schema_version: Literal["portfolio-optimization-response.v1"] = (
        "portfolio-optimization-response.v1"
    )
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    scenario: OptimizationScenarioDefinition
    profile_id: NonEmptyStr
    profile_version: int = Field(ge=1)
    risk_level: RiskLevel
    portfolio_bundle_id: NonEmptyStr
    position_snapshot_id: NonEmptyStr
    exposure_report_id: NonEmptyStr | None = None
    concentration_report_id: NonEmptyStr | None = None
    assessment_id: NonEmptyStr | None = None
    assessment_status: BudgetAssessmentStatus | None = None
    methodology_version: Literal["CAP_AND_REDISTRIBUTE_V1"] = METHODOLOGY_VERSION
    status: OptimizationStatus
    summary: NonEmptyStr
    targets: tuple[OptimizationTarget, ...] = Field(default_factory=tuple)
    constraints: tuple[OptimizationConstraint, ...] = Field(default_factory=tuple)
    issues: tuple[OptimizationIssue, ...] = Field(default_factory=tuple)
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    trace: OptimizationTrace

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if self.trace.owner_id != self.owner_id:
            raise ValueError("optimization trace owner does not match response")
        if self.trace.profile_id != self.profile_id:
            raise ValueError("optimization trace profile does not match response")
        if self.trace.portfolio_bundle_id != self.portfolio_bundle_id:
            raise ValueError("optimization trace bundle does not match response")
        if self.trace.position_snapshot_id != self.position_snapshot_id:
            raise ValueError("optimization trace snapshot does not match response")
        if self.trace.exposure_report_id != self.exposure_report_id:
            raise ValueError("optimization trace exposure does not match response")
        if self.trace.concentration_report_id != self.concentration_report_id:
            raise ValueError("optimization trace concentration does not match response")
        if self.trace.assessment_id != self.assessment_id:
            raise ValueError("optimization trace assessment does not match response")
        if tuple(self.invalidation_conditions) != tuple(self.trace.invalidation_conditions):
            raise ValueError("response invalidation conditions do not match trace")

        target_ids = [item.target_id for item in self.targets]
        if target_ids != sorted(target_ids) or len(target_ids) != len(set(target_ids)):
            raise ValueError("optimization targets must be unique and sorted")
        constraint_ids = [item.constraint_id for item in self.constraints]
        if constraint_ids != sorted(constraint_ids) or len(constraint_ids) != len(set(constraint_ids)):
            raise ValueError("optimization constraints must be unique and sorted")
        if any(item.owner_id != self.owner_id for item in (*self.targets, *self.constraints)):
            raise ValueError("optimization row owner does not match response")
        if self.status == OptimizationStatus.READY:
            if not self.targets:
                raise ValueError("READY optimization requires targets")
            if self.issues:
                raise ValueError("READY optimization must not carry issues")
            target_total = sum((item.target_weight_pct for item in self.targets), Decimal("0"))
            if target_total != Decimal("100.00"):
                raise ValueError("READY optimization targets must sum to 100.00 percent")
            if self.exposure_report_id is None or self.concentration_report_id is None or self.assessment_id is None:
                raise ValueError("READY optimization requires closed report identities")
            if self.assessment_status is None:
                raise ValueError("READY optimization requires assessment status")
        else:
            if self.targets:
                raise ValueError("non-ready optimization must not expose targets")
            if not self.issues:
                raise ValueError("non-ready optimization requires an issue")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization response must not contain sensitive fields")
        return self


class PortfolioOptimizationTemplateResponse(ContractModel):
    schema_version: Literal["portfolio-optimization-template.v1"] = (
        "portfolio-optimization-template.v1"
    )
    manifest_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    methodology_version: Literal["CAP_AND_REDISTRIBUTE_V1"] = METHODOLOGY_VERSION
    scope_description: NonEmptyStr
    questionnaire: RiskQuestionnaire
    portfolio: PortfolioImportBundle
    rules: tuple[OptimizationRuleResponse, ...] = Field(min_length=4)
    scenarios: tuple[OptimizationScenarioDefinition, ...] = Field(min_length=3)

    @model_validator(mode="after")
    def validate_template(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if self.questionnaire.owner_id != self.owner_id:
            raise ValueError("optimization template questionnaire owner mismatch")
        if self.portfolio.owner_id != self.owner_id:
            raise ValueError("optimization template portfolio owner mismatch")
        scenario_ids = [item.scenario_id for item in self.scenarios]
        if scenario_ids != sorted(scenario_ids) or len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("optimization template scenarios must be unique and sorted")
        if set(scenario_ids) != set(OptimizationScenarioId):
            raise ValueError("optimization template must cover every scenario")
        dimensions = [item.dimension for item in self.rules]
        if len(set(dimensions)) != len(dimensions):
            raise ValueError("optimization template rules must be unique by dimension")
        if _sensitive(self.model_dump_json()):
            raise ValueError("optimization template must not contain sensitive fields")
        return self


__all__ = [
    "METHODOLOGY_VERSION",
    "OptimizationConstraint",
    "OptimizationDimension",
    "OptimizationDisposition",
    "OptimizationIssue",
    "OptimizationIssueCode",
    "OptimizationRuleResponse",
    "OptimizationScenarioDefinition",
    "OptimizationScenarioId",
    "OptimizationStatus",
    "OptimizationTarget",
    "OptimizationTrace",
    "PortfolioOptimizationRequest",
    "PortfolioOptimizationResponse",
    "PortfolioOptimizationTemplateResponse",
]
