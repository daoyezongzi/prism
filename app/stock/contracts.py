"""Immutable, owner-scoped contracts for the Demo F stock research card."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import (
    ContractModel,
    DecisionTrace,
    Fact,
    Finding,
    FindingSeverity,
    NonEmptyStr,
)
from app.orchestration.contracts import ResearchRunStatus
from app.providers import FrozenDict
from app.research.contracts import CrossValidationResult
from app.research.pipeline import ResearchPipelineStatus
from app.research.specialists import ResearchIdentifier


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


def _contains_sensitive(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return any(item in normalized for item in _SENSITIVE_SUBSTRINGS)


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


class StockResearchScenarioId(StrEnum):
    """Fixed, offline scenarios used to demonstrate stock-data boundaries."""

    BASELINE_READY = "BASELINE_READY"
    SOURCE_DISAGREEMENT = "SOURCE_DISAGREEMENT"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    SOURCE_EMPTY = "SOURCE_EMPTY"
    SOURCE_FAILED = "SOURCE_FAILED"


class StockRiskStatus(StrEnum):
    """A descriptive risk state, never a trade instruction."""

    NOT_ASSESSED = "NOT_ASSESSED"
    CLEAR = "CLEAR"
    WATCH = "WATCH"
    HIGH_RISK = "HIGH_RISK"


class StockResearchScenarioDefinition(ContractModel):
    """Safe catalog metadata for a deterministic stock replay."""

    scenario_id: StockResearchScenarioId
    label: NonEmptyStr
    description: NonEmptyStr

    @model_validator(mode="after")
    def validate_safety(self) -> Self:
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("stock scenario definition must not contain sensitive metadata")
        return self


class StockMetricResponse(ContractModel):
    """Presentation-safe metadata for one raw financial metric."""

    metric: ResearchIdentifier
    label: NonEmptyStr
    unit: NonEmptyStr

    @model_validator(mode="after")
    def validate_safety(self) -> Self:
        if any(_contains_sensitive(value) for value in (self.metric, self.label, self.unit)):
            raise ValueError("stock metric metadata must not contain sensitive fields")
        return self


class StockRiskRuleResponse(ContractModel):
    """Public explanation of a fixed deterministic risk threshold."""

    rule_id: ResearchIdentifier
    label: NonEmptyStr
    operator: Literal["LT", "GT"]
    threshold: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    unit: NonEmptyStr

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        _finite(self.threshold, "threshold")
        if any(_contains_sensitive(value) for value in (self.rule_id, self.label, self.unit)):
            raise ValueError("stock risk rule must not contain sensitive fields")
        return self


class StockResearchManifestNode(ContractModel):
    """Private manifest metadata binding one request to one source lineage."""

    node_id: ResearchIdentifier
    request_id: ResearchIdentifier
    source: ResearchIdentifier
    record_id: ResearchIdentifier
    lineage_id: ResearchIdentifier
    source_slot: Literal["a", "b"]
    required_fields: tuple[ResearchIdentifier, ...] = Field(min_length=1)
    parameters: FrozenDict = Field(default_factory=FrozenDict)
    timeout_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_node(self) -> Self:
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("stock manifest required_fields must be unique")
        if any(_contains_sensitive(value) for value in (
            self.node_id,
            self.request_id,
            self.source,
            self.record_id,
            self.lineage_id,
            *self.required_fields,
        )):
            raise ValueError("stock manifest node contains sensitive metadata")
        return self


class StockResearchMetricSpec(ContractModel):
    """Private claim metadata used to build the existing pipeline specs."""

    metric: ResearchIdentifier
    label: NonEmptyStr
    unit: NonEmptyStr
    expected_value: Decimal
    finding_kind: ResearchIdentifier
    finding_severity: FindingSeverity
    finding_statement: NonEmptyStr

    @model_validator(mode="after")
    def validate_metric(self) -> Self:
        _finite(self.expected_value, "expected_value")
        if any(_contains_sensitive(value) for value in (
            self.metric,
            self.label,
            self.unit,
            self.finding_kind,
            self.finding_statement,
        )):
            raise ValueError("stock metric spec contains sensitive metadata")
        return self


class StockResearchManifest(ContractModel):
    """Versioned, fixture-only input recipe for Demo F."""

    schema_version: Literal["stock-research-manifest.v1"] = "stock-research-manifest.v1"
    manifest_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    budget_ms: int = Field(gt=0)
    scope_description: NonEmptyStr
    metrics: tuple[StockResearchMetricSpec, ...] = Field(min_length=1)
    nodes: tuple[StockResearchManifestNode, ...] = Field(min_length=2, max_length=2)
    cashflow_quality_min_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    receivable_ratio_max_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    debt_ratio_max_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        _aware(self.generated_at, "generated_at")
        for name, value in (
            ("cashflow_quality_min_pct", self.cashflow_quality_min_pct),
            ("receivable_ratio_max_pct", self.receivable_ratio_max_pct),
            ("debt_ratio_max_pct", self.debt_ratio_max_pct),
        ):
            _finite(value, name)
        if tuple(item.metric for item in self.metrics) != tuple(
            sorted(item.metric for item in self.metrics)
        ):
            raise ValueError("stock manifest metrics must be in deterministic order")
        metric_ids = [item.metric for item in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("stock manifest metrics must be unique")
        if tuple(item.node_id for item in self.nodes) != tuple(
            sorted(item.node_id for item in self.nodes)
        ):
            raise ValueError("stock manifest nodes must be in deterministic order")
        for attr in ("node_id", "request_id", "source", "record_id", "lineage_id", "source_slot"):
            values = [getattr(item, attr) for item in self.nodes]
            if len(values) != len(set(values)):
                raise ValueError(f"stock manifest {attr} values must be unique")
        expected_fields = tuple(metric_ids)
        for node in self.nodes:
            if tuple(sorted(node.required_fields)) != expected_fields:
                raise ValueError("each stock manifest node must request every metric")
            if node.parameters.get("period") != self.period:
                raise ValueError("stock manifest node period must match manifest period")
            if node.parameters.get("source_slot") != node.source_slot:
                raise ValueError("stock manifest source_slot must match node parameters")
            if node.timeout_ms > self.budget_ms:
                raise ValueError("stock manifest node timeout exceeds budget")
        if {node.source_slot for node in self.nodes} != {"a", "b"}:
            raise ValueError("stock manifest must contain source slots a and b")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("stock manifest must not contain sensitive metadata")
        return self


class StockResearchRequest(ContractModel):
    """Owner/request envelope for one fixed stock replay."""

    schema_version: Literal["stock-research-request.v1"] = "stock-research-request.v1"
    request_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    scenario_id: StockResearchScenarioId = StockResearchScenarioId.BASELINE_READY

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _aware(self.generated_at, "generated_at")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("stock research request must not contain sensitive metadata")
        return self


class StockResearchScenarioResponse(StockResearchScenarioDefinition):
    """Public alias retaining a response-specific schema version."""

    schema_version: Literal["stock-research-scenario-response.v1"] = (
        "stock-research-scenario-response.v1"
    )


class StockResearchIssue(ContractModel):
    code: ResearchIdentifier
    safe_message: NonEmptyStr
    claim_id: ResearchIdentifier | None = None

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        values = (self.code, self.safe_message, self.claim_id)
        if any(value is not None and _contains_sensitive(value) for value in values):
            raise ValueError("stock issue must not contain sensitive fields")
        return self


class StockRiskSummary(ContractModel):
    """Descriptive risk state bound to the card's Finding IDs."""

    status: StockRiskStatus
    summary: NonEmptyStr
    finding_ids: tuple[ResearchIdentifier, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.finding_ids != tuple(sorted(self.finding_ids)):
            raise ValueError("stock risk finding_ids must be sorted")
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("stock risk finding_ids must be unique")
        if self.status == StockRiskStatus.NOT_ASSESSED and self.finding_ids:
            raise ValueError("NOT_ASSESSED risk must not contain finding IDs")
        if self.status == StockRiskStatus.CLEAR and self.finding_ids:
            raise ValueError("CLEAR risk must not contain finding IDs")
        if self.status in {StockRiskStatus.WATCH, StockRiskStatus.HIGH_RISK} and not self.finding_ids:
            raise ValueError("non-clear risk must reference a Finding")
        if _contains_sensitive(self.summary):
            raise ValueError("stock risk summary must not contain sensitive fields")
        return self


class StockResearchTemplateResponse(ContractModel):
    schema_version: Literal["stock-research-template.v1"] = "stock-research-template.v1"
    manifest_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    budget_ms: int = Field(gt=0)
    metrics: tuple[StockMetricResponse, ...] = Field(min_length=1)
    risk_rules: tuple[StockRiskRuleResponse, ...] = Field(min_length=3)
    scenarios: tuple[StockResearchScenarioResponse, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def validate_template(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if tuple(item.metric for item in self.metrics) != tuple(
            sorted(item.metric for item in self.metrics)
        ):
            raise ValueError("stock template metrics must be sorted")
        if len(set(item.metric for item in self.metrics)) != len(self.metrics):
            raise ValueError("stock template metrics must be unique")
        if tuple(item.scenario_id for item in self.scenarios) != tuple(
            sorted((item.scenario_id for item in self.scenarios), key=lambda item: item.value)
        ):
            raise ValueError("stock template scenarios must be sorted")
        if len({item.scenario_id for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("stock template scenarios must be unique")
        if StockResearchScenarioId.BASELINE_READY not in {item.scenario_id for item in self.scenarios}:
            raise ValueError("stock template must include baseline scenario")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("stock template must not contain sensitive metadata")
        return self


class StockResearchResponse(ContractModel):
    schema_version: Literal["stock-research-response.v1"] = "stock-research-response.v1"
    manifest_id: ResearchIdentifier
    request_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    scenario: StockResearchScenarioResponse
    run_id: NonEmptyStr
    run_status: ResearchRunStatus
    pipeline_status: ResearchPipelineStatus
    validations: tuple[CrossValidationResult, ...] = Field(default_factory=tuple)
    facts: tuple[Fact, ...] = Field(default_factory=tuple)
    findings: tuple[Finding, ...] = Field(default_factory=tuple)
    risk: StockRiskSummary
    issues: tuple[StockResearchIssue, ...] = Field(default_factory=tuple)
    trace: DecisionTrace

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if tuple(item.fact_id for item in self.facts) != tuple(
            sorted(item.fact_id for item in self.facts)
        ):
            raise ValueError("stock response facts must be sorted")
        if tuple(item.finding_id for item in self.findings) != tuple(
            sorted(item.finding_id for item in self.findings)
        ):
            raise ValueError("stock response findings must be sorted")
        if len({item.fact_id for item in self.facts}) != len(self.facts):
            raise ValueError("stock response facts must be unique")
        if len({item.finding_id for item in self.findings}) != len(self.findings):
            raise ValueError("stock response findings must be unique")
        if any(item.owner_id != self.owner_id for item in self.validations):
            raise ValueError("stock response validation owner does not match")
        if self.trace.recommendations:
            raise ValueError("stock research response must not contain recommendations")
        if self.trace.facts != self.facts:
            raise ValueError("stock response facts must equal trace facts")
        if self.trace.findings != self.findings:
            raise ValueError("stock response findings must equal trace findings")
        if self.pipeline_status == ResearchPipelineStatus.READY:
            if self.run_status != ResearchRunStatus.COMPLETED:
                raise ValueError("READY stock response requires completed run")
            if not self.facts or not self.findings:
                raise ValueError("READY stock response requires facts and findings")
            if self.issues:
                raise ValueError("READY stock response must not carry issues")
            if self.risk.status == StockRiskStatus.NOT_ASSESSED:
                raise ValueError("READY stock response requires an assessed risk")
        else:
            if self.facts or self.findings:
                raise ValueError("non-ready stock response must not expose facts/findings")
            if self.risk.status != StockRiskStatus.NOT_ASSESSED:
                raise ValueError("non-ready stock response risk must be NOT_ASSESSED")
            if not self.issues:
                raise ValueError("non-ready stock response requires an issue")
        known_finding_ids = {item.finding_id for item in self.findings}
        if not set(self.risk.finding_ids).issubset(known_finding_ids):
            raise ValueError("stock risk references an unknown finding")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("stock response must not contain sensitive fields")
        return self


__all__ = [
    "StockMetricResponse",
    "StockResearchIssue",
    "StockResearchManifest",
    "StockResearchManifestNode",
    "StockResearchMetricSpec",
    "StockResearchRequest",
    "StockResearchResponse",
    "StockResearchScenarioDefinition",
    "StockResearchScenarioId",
    "StockResearchScenarioResponse",
    "StockResearchTemplateResponse",
    "StockRiskRuleResponse",
    "StockRiskStatus",
    "StockRiskSummary",
]
