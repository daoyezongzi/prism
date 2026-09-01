"""Immutable contracts for the fixture-first convertible-bond asset card."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
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

CONVERTIBLE_BOND_RAW_METRICS = (
    "bond_floor",
    "bond_price",
    "conversion_price",
    "credit_rating_rank",
    "liquidity_score",
    "underlying_stock_price",
    "yield_to_maturity_pct",
)

CONVERTIBLE_BOND_DERIVED_METRICS = (
    "conversion_premium_pct",
    "conversion_value",
)

CONVERTIBLE_BOND_METRIC_UNITS = {
    "bond_floor": "CNY",
    "bond_price": "CNY",
    "conversion_price": "CNY",
    "conversion_value": "CNY",
    "conversion_premium_pct": "pct",
    "credit_rating_rank": "rating_rank",
    "liquidity_score": "score",
    "underlying_stock_price": "CNY",
    "yield_to_maturity_pct": "pct",
}


def _contains_sensitive(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return any(item in normalized for item in _SENSITIVE_SUBSTRINGS)


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


def _decimal_value(value: object, field_name: str) -> Decimal:
    if isinstance(value, bool) or value is None or isinstance(value, (dict, list, tuple)):
        raise ValueError(f"{field_name} must be a finite scalar")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a finite scalar") from exc
    _finite(parsed, field_name)
    return parsed


class ConvertibleBondResearchScenarioId(StrEnum):
    """Fixed, offline scenarios used to demonstrate convertible-bond boundaries."""

    BASELINE_READY = "BASELINE_READY"
    SOURCE_DISAGREEMENT = "SOURCE_DISAGREEMENT"
    SOURCE_PARTIAL = "SOURCE_PARTIAL"
    SOURCE_EMPTY = "SOURCE_EMPTY"
    SOURCE_FAILED = "SOURCE_FAILED"


class ConvertibleBondRiskStatus(StrEnum):
    """Descriptive asset-risk state, never a trade instruction."""

    NOT_ASSESSED = "NOT_ASSESSED"
    CLEAR = "CLEAR"
    WATCH = "WATCH"
    HIGH_RISK = "HIGH_RISK"


class ConvertibleBondResearchScenarioDefinition(ContractModel):
    scenario_id: ConvertibleBondResearchScenarioId
    label: NonEmptyStr
    description: NonEmptyStr

    @model_validator(mode="after")
    def validate_safety(self) -> Self:
        if any(token in self.model_dump_json().casefold() for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("convertible scenario definition must not contain sensitive metadata")
        return self


class ConvertibleBondMetricResponse(ContractModel):
    """Presentation-safe metadata for one raw or deterministic metric."""

    metric: ResearchIdentifier
    label: NonEmptyStr
    unit: NonEmptyStr
    derived: bool = False
    formula: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_metric(self) -> Self:
        if self.metric not in CONVERTIBLE_BOND_METRIC_UNITS:
            raise ValueError("unknown convertible-bond metric")
        if self.unit != CONVERTIBLE_BOND_METRIC_UNITS[self.metric]:
            raise ValueError("convertible-bond metric unit does not match")
        if self.derived and not self.formula:
            raise ValueError("derived convertible-bond metric requires a formula")
        if not self.derived and self.formula is not None:
            raise ValueError("raw convertible-bond metric must not expose a formula")
        if any(_contains_sensitive(value) for value in (self.metric, self.label, self.unit, self.formula or "")):
            raise ValueError("convertible metric metadata must not contain sensitive fields")
        return self


class ConvertibleBondRiskRuleResponse(ContractModel):
    rule_id: ResearchIdentifier
    label: NonEmptyStr
    operator: Literal["LT", "LTE", "GT", "GTE"]
    threshold: Decimal
    unit: NonEmptyStr

    @model_validator(mode="after")
    def validate_rule(self) -> Self:
        _finite(self.threshold, "threshold")
        if any(_contains_sensitive(value) for value in (self.rule_id, self.label, self.unit)):
            raise ValueError("convertible risk rule must not contain sensitive fields")
        return self


class ConvertibleBondResearchManifestNode(ContractModel):
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
            raise ValueError("convertible manifest required_fields must be unique")
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
            raise ValueError("convertible manifest node contains sensitive metadata")
        return self


class ConvertibleBondResearchMetricSpec(ContractModel):
    metric: ResearchIdentifier
    label: NonEmptyStr
    unit: NonEmptyStr
    expected_value: Decimal | None = None
    derived: bool = False
    formula: NonEmptyStr | None = None
    finding_kind: ResearchIdentifier
    finding_severity: FindingSeverity
    finding_statement: NonEmptyStr

    @model_validator(mode="after")
    def validate_metric(self) -> Self:
        _finite(self.expected_value, "expected_value") if self.expected_value is not None else None
        if self.metric not in CONVERTIBLE_BOND_METRIC_UNITS:
            raise ValueError("unknown convertible-bond metric")
        if self.unit != CONVERTIBLE_BOND_METRIC_UNITS[self.metric]:
            raise ValueError("convertible metric unit does not match")
        if self.derived and not self.formula:
            raise ValueError("derived convertible metric requires formula")
        if not self.derived and self.formula is not None:
            raise ValueError("raw convertible metric must not contain formula")
        if not self.derived and self.expected_value is None:
            raise ValueError("raw convertible metric requires expected value")
        if self.derived and self.expected_value is not None:
            raise ValueError("derived convertible metric must not contain fixture expected value")
        values = (
            self.metric,
            self.label,
            self.unit,
            self.formula or "",
            self.finding_kind,
            self.finding_statement,
        )
        if any(_contains_sensitive(value) for value in values):
            raise ValueError("convertible metric spec contains sensitive fields")
        return self


class ConvertibleBondResearchManifest(ContractModel):
    schema_version: Literal["convertible-bond-research-manifest.v1"] = (
        "convertible-bond-research-manifest.v1"
    )
    manifest_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    budget_ms: int = Field(gt=0)
    scope_description: NonEmptyStr
    metrics: tuple[ConvertibleBondResearchMetricSpec, ...] = Field(min_length=1)
    nodes: tuple[ConvertibleBondResearchManifestNode, ...] = Field(min_length=2, max_length=2)
    bond_par_value: Decimal = Field(gt=0)
    conversion_premium_max_pct: Decimal
    bond_floor_min: Decimal
    negative_yield_min_pct: Decimal
    credit_rating_min_risk_rank: Decimal = Field(gt=0)
    liquidity_min_risk_score: Decimal = Field(gt=0)
    credit_rating_labels: FrozenDict = Field(default_factory=FrozenDict)
    liquidity_labels: FrozenDict = Field(default_factory=FrozenDict)

    @model_validator(mode="after")
    def validate_manifest(self) -> Self:
        _aware(self.generated_at, "generated_at")
        for name, value in (
            ("bond_par_value", self.bond_par_value),
            ("conversion_premium_max_pct", self.conversion_premium_max_pct),
            ("bond_floor_min", self.bond_floor_min),
            ("negative_yield_min_pct", self.negative_yield_min_pct),
            ("credit_rating_min_risk_rank", self.credit_rating_min_risk_rank),
            ("liquidity_min_risk_score", self.liquidity_min_risk_score),
        ):
            _finite(value, name)
        if tuple(item.metric for item in self.metrics) != tuple(
            sorted(item.metric for item in self.metrics)
        ):
            raise ValueError("convertible manifest metrics must be in deterministic order")
        metric_ids = [item.metric for item in self.metrics]
        if len(metric_ids) != len(set(metric_ids)):
            raise ValueError("convertible manifest metrics must be unique")
        if set(metric_ids) != set(CONVERTIBLE_BOND_METRIC_UNITS):
            raise ValueError("convertible manifest must define every minimum metric")
        derived_metrics = {item.metric for item in self.metrics if item.derived}
        if derived_metrics != set(CONVERTIBLE_BOND_DERIVED_METRICS):
            raise ValueError("convertible manifest derived metrics are incomplete")
        raw_metrics = tuple(item.metric for item in self.metrics if not item.derived)
        if set(raw_metrics) != set(CONVERTIBLE_BOND_RAW_METRICS):
            raise ValueError("convertible manifest raw metrics are incomplete")
        if tuple(item.node_id for item in self.nodes) != tuple(
            sorted(item.node_id for item in self.nodes)
        ):
            raise ValueError("convertible manifest nodes must be in deterministic order")
        for attr in ("node_id", "request_id", "source", "record_id", "lineage_id", "source_slot"):
            values = [getattr(item, attr) for item in self.nodes]
            if len(values) != len(set(values)):
                raise ValueError(f"convertible manifest {attr} values must be unique")
        expected_fields = tuple(sorted(raw_metrics))
        for node in self.nodes:
            if tuple(sorted(node.required_fields)) != expected_fields:
                raise ValueError("each convertible manifest node must request every raw metric")
            if node.parameters.get("period") != self.period:
                raise ValueError("convertible manifest node period must match manifest period")
            if node.parameters.get("source_slot") != node.source_slot:
                raise ValueError("convertible manifest source_slot must match node parameters")
            if node.timeout_ms > self.budget_ms:
                raise ValueError("convertible manifest node timeout exceeds budget")
        if {node.source_slot for node in self.nodes} != {"a", "b"}:
            raise ValueError("convertible manifest must contain source slots a and b")
        if not self.credit_rating_labels or not self.liquidity_labels:
            raise ValueError("convertible manifest must define safe rating labels")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("convertible manifest must not contain sensitive metadata")
        return self


class ConvertibleBondResearchRequest(ContractModel):
    schema_version: Literal["convertible-bond-research-request.v1"] = (
        "convertible-bond-research-request.v1"
    )
    request_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    scenario_id: ConvertibleBondResearchScenarioId = ConvertibleBondResearchScenarioId.BASELINE_READY

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if any(token in self.model_dump_json().casefold() for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("convertible research request must not contain sensitive metadata")
        return self


class ConvertibleBondResearchScenarioResponse(ConvertibleBondResearchScenarioDefinition):
    schema_version: Literal["convertible-bond-research-scenario-response.v1"] = (
        "convertible-bond-research-scenario-response.v1"
    )


class ConvertibleBondResearchIssue(ContractModel):
    code: ResearchIdentifier
    safe_message: NonEmptyStr
    claim_id: ResearchIdentifier | None = None

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        if any(
            value is not None and _contains_sensitive(value)
            for value in (self.code, self.safe_message, self.claim_id)
        ):
            raise ValueError("convertible research issue must not contain sensitive fields")
        return self


class ConvertibleBondRiskSummary(ContractModel):
    status: ConvertibleBondRiskStatus
    summary: NonEmptyStr
    finding_ids: tuple[ResearchIdentifier, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.finding_ids != tuple(sorted(self.finding_ids)):
            raise ValueError("convertible risk finding_ids must be sorted")
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("convertible risk finding_ids must be unique")
        if self.status in {ConvertibleBondRiskStatus.NOT_ASSESSED, ConvertibleBondRiskStatus.CLEAR} and self.finding_ids:
            raise ValueError(f"{self.status.value} convertible risk must not contain finding IDs")
        if self.status in {ConvertibleBondRiskStatus.WATCH, ConvertibleBondRiskStatus.HIGH_RISK} and not self.finding_ids:
            raise ValueError("non-clear convertible risk must reference a Finding")
        if _contains_sensitive(self.summary):
            raise ValueError("convertible risk summary must not contain sensitive fields")
        return self


class ConvertibleBondResearchNodeResponse(ContractModel):
    node_id: ResearchIdentifier
    required: bool
    status: ResearchNodeRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    missing_fields: tuple[ResearchIdentifier, ...] = Field(default_factory=tuple)
    scope_description: NonEmptyStr | None = None
    issues: tuple[ConvertibleBondResearchIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_node(self) -> Self:
        if self.missing_fields != tuple(sorted(self.missing_fields)):
            raise ValueError("convertible node missing_fields must be sorted")
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("convertible node missing_fields must be unique")
        issue_codes = [item.code for item in self.issues]
        if len(issue_codes) != len(set(issue_codes)):
            raise ValueError("convertible node issues must be unique")
        for name, value in (("started_at", self.started_at), ("finished_at", self.finished_at)):
            if value is not None:
                _aware(value, f"convertible node {name}")
        if self.started_at is None and self.finished_at is not None and self.status not in {ResearchNodeRunStatus.FAILED, ResearchNodeRunStatus.CANCELLED}:
            raise ValueError("convertible node finished_at requires started_at")
        if self.started_at is not None and self.finished_at is not None and self.finished_at < self.started_at:
            raise ValueError("convertible node finished_at must not precede started_at")
        if self.status == ResearchNodeRunStatus.PENDING:
            if self.started_at is not None or self.finished_at is not None or self.missing_fields or self.scope_description or self.issues:
                raise ValueError("PENDING convertible node must not carry runtime data")
        elif self.status == ResearchNodeRunStatus.RUNNING:
            if self.started_at is None or self.finished_at is not None or self.missing_fields or self.scope_description or self.issues:
                raise ValueError("RUNNING convertible node requires only started_at")
        elif self.status == ResearchNodeRunStatus.COMPLETE:
            if self.started_at is None or self.finished_at is None:
                raise ValueError("COMPLETE convertible node requires timestamps")
            if self.missing_fields or self.issues:
                raise ValueError("COMPLETE convertible node must not carry missing/issues")
        elif self.status == ResearchNodeRunStatus.PARTIAL:
            if self.started_at is None or self.finished_at is None:
                raise ValueError("PARTIAL convertible node requires timestamps")
            if not self.missing_fields and not self.issues:
                raise ValueError("PARTIAL convertible node requires missing_fields or issues")
        elif self.status == ResearchNodeRunStatus.EMPTY:
            if self.started_at is None or self.finished_at is None:
                raise ValueError("EMPTY convertible node requires timestamps")
            if self.missing_fields or self.issues:
                raise ValueError("EMPTY convertible node must not carry missing/issues")
            if not self.scope_description:
                raise ValueError("EMPTY convertible node requires scope_description")
        elif self.status == ResearchNodeRunStatus.FAILED:
            if self.finished_at is None:
                raise ValueError("FAILED convertible node requires finished_at")
            if self.missing_fields:
                raise ValueError("FAILED convertible node must not carry missing_fields")
            if not self.issues:
                raise ValueError("FAILED convertible node requires an issue")
        elif self.status == ResearchNodeRunStatus.CANCELLED:
            if self.finished_at is None:
                raise ValueError("CANCELLED convertible node requires finished_at")
            if self.missing_fields:
                raise ValueError("CANCELLED convertible node must not carry missing_fields")
            if not self.issues:
                raise ValueError("CANCELLED convertible node requires an issue")
        return self


class ConvertibleBondResearchTemplateResponse(ContractModel):
    schema_version: Literal["convertible-bond-research-template.v1"] = (
        "convertible-bond-research-template.v1"
    )
    manifest_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    generated_at: datetime
    budget_ms: int = Field(gt=0)
    bond_par_value: Decimal = Field(gt=0)
    metrics: tuple[ConvertibleBondMetricResponse, ...] = Field(min_length=1)
    risk_rules: tuple[ConvertibleBondRiskRuleResponse, ...] = Field(min_length=5)
    credit_rating_labels: FrozenDict = Field(default_factory=FrozenDict)
    liquidity_labels: FrozenDict = Field(default_factory=FrozenDict)
    scenarios: tuple[ConvertibleBondResearchScenarioResponse, ...] = Field(min_length=5)

    @model_validator(mode="after")
    def validate_template(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if tuple(item.metric for item in self.metrics) != tuple(sorted(item.metric for item in self.metrics)):
            raise ValueError("convertible template metrics must be sorted")
        if len({item.metric for item in self.metrics}) != len(self.metrics):
            raise ValueError("convertible template metrics must be unique")
        if set(item.metric for item in self.metrics) != set(CONVERTIBLE_BOND_METRIC_UNITS):
            raise ValueError("convertible template must include every minimum metric")
        if tuple(item.scenario_id for item in self.scenarios) != tuple(sorted((item.scenario_id for item in self.scenarios), key=lambda item: item.value)):
            raise ValueError("convertible template scenarios must be sorted")
        if len({item.scenario_id for item in self.scenarios}) != len(self.scenarios):
            raise ValueError("convertible template scenarios must be unique")
        if ConvertibleBondResearchScenarioId.BASELINE_READY not in {item.scenario_id for item in self.scenarios}:
            raise ValueError("convertible template must include baseline scenario")
        if not self.credit_rating_labels or not self.liquidity_labels:
            raise ValueError("convertible template must include level labels")
        if any(token in self.model_dump_json().casefold() for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("convertible template must not contain sensitive metadata")
        return self


class ConvertibleBondResearchResponse(ContractModel):
    schema_version: Literal["convertible-bond-research-response.v1"] = (
        "convertible-bond-research-response.v1"
    )
    manifest_id: ResearchIdentifier
    request_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    subject: ResearchIdentifier
    period: ResearchIdentifier
    scenario: ConvertibleBondResearchScenarioResponse
    bond_par_value: Decimal = Field(gt=0)
    run_id: NonEmptyStr
    run_status: ResearchRunStatus
    pipeline_status: ResearchPipelineStatus
    nodes: tuple[ConvertibleBondResearchNodeResponse, ...] = Field(min_length=2)
    validations: tuple[CrossValidationResult, ...] = Field(default_factory=tuple)
    facts: tuple[Fact, ...] = Field(default_factory=tuple)
    findings: tuple[Finding, ...] = Field(default_factory=tuple)
    risk: ConvertibleBondRiskSummary
    issues: tuple[ConvertibleBondResearchIssue, ...] = Field(default_factory=tuple)
    trace: DecisionTrace

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if tuple(item.fact_id for item in self.facts) != tuple(sorted(item.fact_id for item in self.facts)):
            raise ValueError("convertible response facts must be sorted")
        if tuple(item.finding_id for item in self.findings) != tuple(sorted(item.finding_id for item in self.findings)):
            raise ValueError("convertible response findings must be sorted")
        if len({item.fact_id for item in self.facts}) != len(self.facts):
            raise ValueError("convertible response facts must be unique")
        fact_metrics = [item.metric for item in self.facts]
        if len(fact_metrics) != len(set(fact_metrics)):
            raise ValueError("convertible response facts must contain one row per metric")
        if len({item.finding_id for item in self.findings}) != len(self.findings):
            raise ValueError("convertible response findings must be unique")
        node_ids = [item.node_id for item in self.nodes]
        if node_ids != sorted(node_ids) or len(node_ids) != len(set(node_ids)):
            raise ValueError("convertible response nodes must be unique and sorted")
        validation_ids = [item.validation_id for item in self.validations]
        if len(validation_ids) != len(set(validation_ids)):
            raise ValueError("convertible response validations must be unique")
        validation_metrics = [item.metric for item in self.validations]
        if len(validation_metrics) != len(set(validation_metrics)):
            raise ValueError("convertible response validations must contain one row per raw metric")
        raw_metrics = set(CONVERTIBLE_BOND_RAW_METRICS)
        all_metrics = set(CONVERTIBLE_BOND_METRIC_UNITS)
        if any(item.owner_id != self.owner_id for item in self.validations):
            raise ValueError("convertible response validation owner does not match")
        if any(item.subject != self.subject or item.period != self.period or item.metric not in raw_metrics or item.unit != CONVERTIBLE_BOND_METRIC_UNITS[item.metric] for item in self.validations):
            raise ValueError("convertible response validation scope does not match")
        if any(item.subject != self.subject or item.period != self.period or item.metric not in all_metrics or item.unit != CONVERTIBLE_BOND_METRIC_UNITS[item.metric] for item in self.facts):
            raise ValueError("convertible response fact scope does not match")
        if self.bond_par_value != Decimal("100"):
            raise ValueError("convertible response must use the fixed 100 CNY par value")
        if self.trace.recommendations:
            raise ValueError("convertible response must not contain recommendations")
        if self.trace.facts != self.facts:
            raise ValueError("convertible response facts must equal trace facts")
        if self.trace.findings != self.findings:
            raise ValueError("convertible response findings must equal trace findings")
        if self.pipeline_status == ResearchPipelineStatus.READY:
            if self.run_status != ResearchRunStatus.COMPLETED:
                raise ValueError("READY convertible response requires completed run")
            if any(item.status != ResearchNodeRunStatus.COMPLETE for item in self.nodes):
                raise ValueError("READY convertible response requires every node to be COMPLETE")
            if {item.metric for item in self.facts} != all_metrics:
                raise ValueError("READY convertible response requires every minimum fact")
            if not self.findings or any(item.status != FactStatus.VERIFIED for item in self.facts):
                raise ValueError("READY convertible response requires verified facts/findings")
            if self.issues:
                raise ValueError("READY convertible response must not carry issues")
            if self.risk.status == ConvertibleBondRiskStatus.NOT_ASSESSED:
                raise ValueError("READY convertible response requires an assessed risk")
            values = {
                fact.metric: _decimal_value(fact.value, f"fact {fact.metric}")
                for fact in self.facts
            }
            if values["underlying_stock_price"] <= 0 or values["conversion_price"] <= 0 or values["bond_price"] <= 0:
                raise ValueError("convertible response price inputs must be positive")
            for metric, maximum in (("credit_rating_rank", Decimal("5")), ("liquidity_score", Decimal("3"))):
                level = values[metric]
                if level != level.to_integral_value() or level < Decimal("1") or level > maximum:
                    raise ValueError(f"convertible response {metric} is outside the fixed rank range")
            expected_conversion_value = (
                values["underlying_stock_price"] / values["conversion_price"] * self.bond_par_value
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            expected_premium = (
                (values["bond_price"] / expected_conversion_value - Decimal("1")) * Decimal("100")
            ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if values["conversion_value"] != expected_conversion_value:
                raise ValueError("convertible response conversion value does not match formula")
            if values["conversion_premium_pct"] != expected_premium:
                raise ValueError("convertible response conversion premium does not match formula")
        else:
            if self.facts or self.findings:
                raise ValueError("non-ready convertible response must not expose facts/findings")
            if self.risk.status != ConvertibleBondRiskStatus.NOT_ASSESSED:
                raise ValueError("non-ready convertible response risk must be NOT_ASSESSED")
            if not self.issues:
                raise ValueError("non-ready convertible response requires an issue")
        known_finding_ids = {item.finding_id for item in self.findings}
        if not set(self.risk.finding_ids).issubset(known_finding_ids):
            raise ValueError("convertible risk references an unknown finding")
        non_info = {item.finding_id: item for item in self.findings if item.severity in {FindingSeverity.WARNING, FindingSeverity.CRITICAL}}
        non_info_ids = set(non_info)
        risk_ids = set(self.risk.finding_ids)
        if self.pipeline_status == ResearchPipelineStatus.READY:
            if self.risk.status == ConvertibleBondRiskStatus.CLEAR and non_info:
                raise ValueError("CLEAR convertible risk must not hide warning or critical findings")
            if self.risk.status == ConvertibleBondRiskStatus.WATCH:
                if any(item.severity == FindingSeverity.CRITICAL for item in non_info.values()) or risk_ids != non_info_ids:
                    raise ValueError("WATCH convertible risk must reference all non-info findings without critical findings")
            if self.risk.status == ConvertibleBondRiskStatus.HIGH_RISK:
                if not any(item.severity == FindingSeverity.CRITICAL for item in non_info.values()) or risk_ids != non_info_ids:
                    raise ValueError("HIGH_RISK convertible risk must reference every non-info finding")
        if any(token in self.model_dump_json().casefold() for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("convertible response must not contain sensitive fields")
        return self


__all__ = [
    "CONVERTIBLE_BOND_DERIVED_METRICS",
    "CONVERTIBLE_BOND_METRIC_UNITS",
    "CONVERTIBLE_BOND_RAW_METRICS",
    "ConvertibleBondMetricResponse",
    "ConvertibleBondResearchIssue",
    "ConvertibleBondResearchManifest",
    "ConvertibleBondResearchManifestNode",
    "ConvertibleBondResearchMetricSpec",
    "ConvertibleBondResearchNodeResponse",
    "ConvertibleBondResearchRequest",
    "ConvertibleBondResearchResponse",
    "ConvertibleBondResearchScenarioDefinition",
    "ConvertibleBondResearchScenarioId",
    "ConvertibleBondResearchScenarioResponse",
    "ConvertibleBondResearchTemplateResponse",
    "ConvertibleBondRiskRuleResponse",
    "ConvertibleBondRiskStatus",
    "ConvertibleBondRiskSummary",
]
