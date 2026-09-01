"""Strict contracts for the fixture-first ETF/Fund research card (Demo G)."""

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
    FactStatus,
    Finding,
    FindingSeverity,
    NonEmptyStr,
)
from app.orchestration.contracts import ResearchNodeRunStatus, ResearchRunStatus
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


class FundResearchScenarioId(StrEnum):
    """Fixed, offline scenarios used to demonstrate fund-data boundaries."""

    BASELINE_READY = "BASELINE_READY"
    SOURCE_DISAGREEMENT = "SOURCE_DISAGREEMENT"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    SOURCE_EMPTY = "SOURCE_EMPTY"
    SOURCE_FAILED = "SOURCE_FAILED"


class FundRiskStatus(StrEnum):
    """A descriptive asset-risk state, never a trade instruction."""

    NOT_ASSESSED = "NOT_ASSESSED"
    CLEAR = "CLEAR"
    WATCH = "WATCH"
    HIGH_RISK = "HIGH_RISK"


class FundResearchScenarioDefinition(ContractModel):
    """Safe catalog metadata for one deterministic ETF/Fund replay."""

    scenario_id: FundResearchScenarioId
    label: NonEmptyStr
    description: NonEmptyStr

    @model_validator(mode="after")
    def validate_safety(self) -> Self:
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("fund scenario definition must not contain sensitive metadata")
        return self


class FundMetricResponse(ContractModel):
    """Presentation-safe metadata for one raw fund metric."""

    metric: ResearchIdentifier
    label: NonEmptyStr
    unit: NonEmptyStr

    @model_validator(mode="after")
    def validate_safety(self) -> Self:
        if any(_contains_sensitive(value) for value in (self.metric, self.label, self.unit)):
            raise ValueError("fund metric metadata must not contain sensitive fields")
        return self


class FundRiskRuleResponse(ContractModel):
    """Public explanation of one deterministic asset-risk threshold."""

    rule_id: ResearchIdentifier
    label: NonEmptyStr
    operator: Literal["LT", "GT"]
    threshold: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    unit: NonEmptyStr

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        _finite(self.threshold, "threshold")
        if any(_contains_sensitive(value) for value in (self.rule_id, self.label, self.unit)):
            raise ValueError("fund risk rule must not contain sensitive fields")
        return self


class FundResearchManifestNode(ContractModel):
    """Private manifest metadata binding one request to one fund lineage."""

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
            raise ValueError("fund manifest required_fields must be unique")
        if any(
            _contains_sensitive(value)
            for value in (
                self.node_id,
                self.request_id,
                self.source,
                self.record_id,
                self.lineage_id,
                *self.required_fields,
            )
        ):
            raise ValueError("fund manifest node contains sensitive metadata")
        return self


class FundResearchMetricSpec(ContractModel):
    """Private claim metadata used to build the existing evidence pipeline."""

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
        if any(
            _contains_sensitive(value)
            for value in (
                self.metric,
                self.label,
                self.unit,
                self.finding_kind,
                self.finding_statement,
            )
        ):
            raise ValueError("fund metric spec contains sensitive metadata")
        return self


class FundResearchManifest(ContractModel):
    """Versioned, fixture-only input recipe for Demo G."""

    schema_version: Literal["fund-research-manifest.v1"] = "fund-research-manifest.v1"
    manifest_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    budget_ms: int = Field(gt=0)
    scope_description: NonEmptyStr
    metrics: tuple[FundResearchMetricSpec, ...] = Field(min_length=1)
    nodes: tuple[FundResearchManifestNode, ...] = Field(min_length=2, max_length=2)
    technology_weight_max_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    top10_weight_max_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    volatility_max_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    drawdown_max_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    expense_ratio_max_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        _aware(self.generated_at, "generated_at")
        for name, value in (
            ("technology_weight_max_pct", self.technology_weight_max_pct),
            ("top10_weight_max_pct", self.top10_weight_max_pct),
            ("volatility_max_pct", self.volatility_max_pct),
            ("drawdown_max_pct", self.drawdown_max_pct),
            ("expense_ratio_max_pct", self.expense_ratio_max_pct),
        ):
            _finite(value, name)
        if tuple(item.metric for item in self.metrics) != tuple(
            sorted(item.metric for item in self.metrics)
        ):
            raise ValueError("fund manifest metrics must be in deterministic order")
        metric_ids = [item.metric for item in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("fund manifest metrics must be unique")
        if tuple(item.node_id for item in self.nodes) != tuple(
            sorted(item.node_id for item in self.nodes)
        ):
            raise ValueError("fund manifest nodes must be in deterministic order")
        for attr in (
            "node_id",
            "request_id",
            "source",
            "record_id",
            "lineage_id",
            "source_slot",
        ):
            values = [getattr(item, attr) for item in self.nodes]
            if len(values) != len(set(values)):
                raise ValueError(f"fund manifest {attr} values must be unique")
        expected_fields = tuple(metric_ids)
        for node in self.nodes:
            if tuple(sorted(node.required_fields)) != expected_fields:
                raise ValueError("each fund manifest node must request every metric")
            if node.parameters.get("period") != self.period:
                raise ValueError("fund manifest node period must match manifest period")
            if node.parameters.get("source_slot") != node.source_slot:
                raise ValueError("fund manifest source_slot must match node parameters")
            if node.timeout_ms > self.budget_ms:
                raise ValueError("fund manifest node timeout exceeds budget")
        if {node.source_slot for node in self.nodes} != {"a", "b"}:
            raise ValueError("fund manifest must contain source slots a and b")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("fund manifest must not contain sensitive metadata")
        return self


class FundResearchRequest(ContractModel):
    """Owner/request envelope for one fixed fund replay."""

    schema_version: Literal["fund-research-request.v1"] = "fund-research-request.v1"
    request_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    scenario_id: FundResearchScenarioId = FundResearchScenarioId.BASELINE_READY

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _aware(self.generated_at, "generated_at")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("fund research request must not contain sensitive metadata")
        return self


class FundResearchScenarioResponse(FundResearchScenarioDefinition):
    """Public alias retaining a response-specific schema version."""

    schema_version: Literal["fund-research-scenario-response.v1"] = (
        "fund-research-scenario-response.v1"
    )


class FundResearchIssue(ContractModel):
    code: ResearchIdentifier
    safe_message: NonEmptyStr
    claim_id: ResearchIdentifier | None = None

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        values = (self.code, self.safe_message, self.claim_id)
        if any(value is not None and _contains_sensitive(value) for value in values):
            raise ValueError("fund issue must not contain sensitive fields")
        return self


class FundRiskSummary(ContractModel):
    """Descriptive fund-risk state bound to Finding IDs."""

    status: FundRiskStatus
    summary: NonEmptyStr
    finding_ids: tuple[ResearchIdentifier, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.finding_ids != tuple(sorted(self.finding_ids)):
            raise ValueError("fund risk finding_ids must be sorted")
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("fund risk finding_ids must be unique")
        if self.status in {FundRiskStatus.NOT_ASSESSED, FundRiskStatus.CLEAR} and self.finding_ids:
            raise ValueError(f"{self.status.value} fund risk must not contain finding IDs")
        if self.status in {FundRiskStatus.WATCH, FundRiskStatus.HIGH_RISK} and not self.finding_ids:
            raise ValueError("non-clear fund risk must reference a Finding")
        if _contains_sensitive(self.summary):
            raise ValueError("fund risk summary must not contain sensitive fields")
        return self


class FundResearchNodeResponse(ContractModel):
    """Safe run state for one fund source node."""

    node_id: ResearchIdentifier
    required: bool
    status: ResearchNodeRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    missing_fields: tuple[ResearchIdentifier, ...] = Field(default_factory=tuple)
    scope_description: NonEmptyStr | None = None
    issues: tuple[FundResearchIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_node(self) -> Self:
        if self.missing_fields != tuple(sorted(self.missing_fields)):
            raise ValueError("fund node missing_fields must be sorted")
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("fund node missing_fields must be unique")
        issue_codes = [item.code for item in self.issues]
        if len(issue_codes) != len(set(issue_codes)):
            raise ValueError("fund node issues must be unique")
        for name, value in (("started_at", self.started_at), ("finished_at", self.finished_at)):
            if value is not None:
                _aware(value, f"fund node {name}")
        if self.started_at is None and self.finished_at is not None:
            raise ValueError("fund node finished_at requires started_at")
        if self.started_at is not None and self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("fund node finished_at must not precede started_at")
        if self.status == ResearchNodeRunStatus.EMPTY and not self.scope_description:
            raise ValueError("EMPTY fund node requires scope_description")
        return self


class FundResearchTemplateResponse(ContractModel):
    schema_version: Literal["fund-research-template.v1"] = "fund-research-template.v1"
    manifest_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    budget_ms: int = Field(gt=0)
    metrics: tuple[FundMetricResponse, ...] = Field(min_length=1)
    risk_rules: tuple[FundRiskRuleResponse, ...] = Field(min_length=5)
    scenarios: tuple[FundResearchScenarioResponse, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def validate_template(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if tuple(item.metric for item in self.metrics) != tuple(
            sorted(item.metric for item in self.metrics)
        ):
            raise ValueError("fund template metrics must be sorted")
        if len(set(item.metric for item in self.metrics)) != len(self.metrics):
            raise ValueError("fund template metrics must be unique")
        if tuple(item.scenario_id for item in self.scenarios) != tuple(
            sorted((item.scenario_id for item in self.scenarios), key=lambda item: item.value)
        ):
            raise ValueError("fund template scenarios must be sorted")
        if len({item.scenario_id for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("fund template scenarios must be unique")
        if FundResearchScenarioId.BASELINE_READY not in {item.scenario_id for item in self.scenarios}:
            raise ValueError("fund template must include baseline scenario")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("fund template must not contain sensitive metadata")
        return self


class FundResearchResponse(ContractModel):
    schema_version: Literal["fund-research-response.v1"] = "fund-research-response.v1"
    manifest_id: ResearchIdentifier
    request_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    scenario: FundResearchScenarioResponse
    run_id: NonEmptyStr
    run_status: ResearchRunStatus
    pipeline_status: ResearchPipelineStatus
    nodes: tuple[FundResearchNodeResponse, ...] = Field(min_length=2)
    validations: tuple[CrossValidationResult, ...] = Field(default_factory=tuple)
    facts: tuple[Fact, ...] = Field(default_factory=tuple)
    findings: tuple[Finding, ...] = Field(default_factory=tuple)
    risk: FundRiskSummary
    issues: tuple[FundResearchIssue, ...] = Field(default_factory=tuple)
    trace: DecisionTrace

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if tuple(item.fact_id for item in self.facts) != tuple(sorted(item.fact_id for item in self.facts)):
            raise ValueError("fund response facts must be sorted")
        if tuple(item.finding_id for item in self.findings) != tuple(
            sorted(item.finding_id for item in self.findings)
        ):
            raise ValueError("fund response findings must be sorted")
        if len({item.fact_id for item in self.facts}) != len(self.facts):
            raise ValueError("fund response facts must be unique")
        if len({item.finding_id for item in self.findings}) != len(self.findings):
            raise ValueError("fund response findings must be unique")
        node_ids = [item.node_id for item in self.nodes]
        if node_ids != sorted(node_ids) or len(node_ids) != len(set(node_ids)):
            raise ValueError("fund response nodes must be unique and sorted")
        validation_ids = [item.validation_id for item in self.validations]
        if len(validation_ids) != len(set(validation_ids)):
            raise ValueError("fund response validations must be unique")
        if any(item.owner_id != self.owner_id for item in self.validations):
            raise ValueError("fund response validation owner does not match")
        if any(item.subject != self.subject or item.unit != "pct" or item.period != self.period for item in self.validations):
            raise ValueError("fund response validation scope does not match")
        if any(fact.subject != self.subject or fact.period != self.period for fact in self.facts):
            raise ValueError("fund response fact scope does not match")
        if self.trace.recommendations:
            raise ValueError("fund research response must not contain recommendations")
        if self.trace.facts != self.facts:
            raise ValueError("fund response facts must equal trace facts")
        if self.trace.findings != self.findings:
            raise ValueError("fund response findings must equal trace findings")
        if self.pipeline_status == ResearchPipelineStatus.READY:
            if self.run_status != ResearchRunStatus.COMPLETED:
                raise ValueError("READY fund response requires completed run")
            if not self.facts or not self.findings:
                raise ValueError("READY fund response requires facts and findings")
            if any(fact.status != FactStatus.VERIFIED for fact in self.facts):
                raise ValueError("READY fund response requires VERIFIED facts")
            if self.issues:
                raise ValueError("READY fund response must not carry issues")
            if self.risk.status == FundRiskStatus.NOT_ASSESSED:
                raise ValueError("READY fund response requires an assessed risk")
            finding_by_id = {item.finding_id: item for item in self.findings}
            risk_findings = [finding_by_id[item] for item in self.risk.finding_ids]
            if self.risk.status == FundRiskStatus.HIGH_RISK and not any(
                item.severity == FindingSeverity.CRITICAL for item in risk_findings
            ):
                raise ValueError("HIGH_RISK fund response requires a CRITICAL finding")
            if self.risk.status == FundRiskStatus.WATCH and not any(
                item.severity in {FindingSeverity.WARNING, FindingSeverity.CRITICAL}
                for item in risk_findings
            ):
                raise ValueError("WATCH fund response requires a warning finding")
        else:
            if self.facts or self.findings:
                raise ValueError("non-ready fund response must not expose facts/findings")
            if self.risk.status != FundRiskStatus.NOT_ASSESSED:
                raise ValueError("non-ready fund response risk must be NOT_ASSESSED")
            if not self.issues:
                raise ValueError("non-ready fund response requires an issue")
        known_finding_ids = {item.finding_id for item in self.findings}
        if not set(self.risk.finding_ids).issubset(known_finding_ids):
            raise ValueError("fund risk references an unknown finding")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("fund response must not contain sensitive fields")
        return self


__all__ = [
    "FundMetricResponse",
    "FundResearchIssue",
    "FundResearchManifest",
    "FundResearchManifestNode",
    "FundResearchMetricSpec",
    "FundResearchNodeResponse",
    "FundResearchRequest",
    "FundResearchResponse",
    "FundResearchScenarioDefinition",
    "FundResearchScenarioId",
    "FundResearchScenarioResponse",
    "FundResearchTemplateResponse",
    "FundRiskRuleResponse",
    "FundRiskStatus",
    "FundRiskSummary",
]
