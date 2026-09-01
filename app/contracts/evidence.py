"""Evidence-first domain contracts.

These objects define the minimum auditable chain used by every research,
portfolio, risk, compliance, and recommendation module in Prism. They contain
no provider-specific or presentation-specific behavior.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)


NonEmptyStr = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1),
]


class ContractModel(BaseModel):
    """Strict immutable base for data that crosses module boundaries."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
    )


class EvidenceQualityStatus(StrEnum):
    """Quality of one normalized provider observation."""

    VERIFIED = "VERIFIED"
    STALE = "STALE"
    PARTIAL = "PARTIAL"
    CONFLICTING = "CONFLICTING"
    INVALID = "INVALID"


class FactStatus(StrEnum):
    """Whether a normalized financial fact is safe to consume."""

    VERIFIED = "VERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    INVALID = "INVALID"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class FindingSeverity(StrEnum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ActionType(StrEnum):
    ADD = "ADD"
    REDUCE = "REDUCE"
    HOLD = "HOLD"
    EXIT = "EXIT"
    REVIEW = "REVIEW"


class ComplianceStatus(StrEnum):
    PASSED = "PASSED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class Evidence(ContractModel):
    """One normalized, attributable provider observation."""

    evidence_id: NonEmptyStr
    provider: NonEmptyStr
    source: NonEmptyStr
    field: NonEmptyStr
    value: JsonValue | None = None
    unit: str | None = None
    period: str | None = None
    observed_at: datetime | None = None
    retrieved_at: datetime
    quality_status: EvidenceQualityStatus
    quality_note: str | None = None
    lineage_id: str | None = None

    @model_validator(mode="after")
    def validate_quality(self) -> Self:
        if self.retrieved_at.tzinfo is None or self.retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")

        if self.observed_at is not None and (
            self.observed_at.tzinfo is None or self.observed_at.utcoffset() is None
        ):
            raise ValueError("observed_at must be timezone-aware when provided")

        if self.quality_status == EvidenceQualityStatus.VERIFIED:
            if self.value is None:
                raise ValueError("VERIFIED evidence requires a value")
            if self.quality_note:
                raise ValueError("VERIFIED evidence must not carry a quality_note")
        elif not self.quality_note:
            raise ValueError(
                f"{self.quality_status.value} evidence requires a quality_note"
            )
        return self


class Fact(ContractModel):
    """A normalized financial statement derived from registered evidence."""

    fact_id: NonEmptyStr
    subject: NonEmptyStr
    metric: NonEmptyStr
    value: JsonValue | None = None
    unit: str | None = None
    period: str | None = None
    status: FactStatus
    evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    reason: str | None = None

    @model_validator(mode="after")
    def validate_status(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must not contain duplicates")

        if self.status == FactStatus.VERIFIED:
            if self.value is None:
                raise ValueError("VERIFIED fact requires a value")
            if not self.evidence_ids:
                raise ValueError("VERIFIED fact requires at least one evidence_id")
            if self.reason:
                raise ValueError("VERIFIED fact must not carry a reason")
        else:
            if self.value is not None:
                raise ValueError(f"{self.status.value} fact must not carry a value")
            if not self.reason:
                raise ValueError(f"{self.status.value} fact requires a reason")
        return self


class Finding(ContractModel):
    """A deterministic or structured interpretation of one or more facts."""

    finding_id: NonEmptyStr
    kind: NonEmptyStr
    severity: FindingSeverity
    statement: NonEmptyStr
    fact_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    methodology: NonEmptyStr

    @model_validator(mode="after")
    def validate_fact_ids(self) -> Self:
        if len(set(self.fact_ids)) != len(self.fact_ids):
            raise ValueError("fact_ids must not contain duplicates")
        return self


class AllocationRange(ContractModel):
    """Target portfolio weight range expressed in percentage points."""

    minimum_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    maximum_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.minimum_pct > self.maximum_pct:
            raise ValueError("minimum_pct must not exceed maximum_pct")
        return self


class Recommendation(ContractModel):
    """A profile-conditioned action justified by registered findings."""

    recommendation_id: NonEmptyStr
    action_type: ActionType
    asset_id: NonEmptyStr
    allocation_range: AllocationRange
    rationale: NonEmptyStr
    finding_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    compliance_status: ComplianceStatus
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_finding_ids(self) -> Self:
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("finding_ids must not contain duplicates")
        return self


class DecisionTrace(ContractModel):
    """Closed, auditable object graph for one decision response."""

    evidence: tuple[Evidence, ...] = Field(default_factory=tuple)
    facts: tuple[Fact, ...] = Field(default_factory=tuple)
    findings: tuple[Finding, ...] = Field(default_factory=tuple)
    recommendations: tuple[Recommendation, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_trace(self) -> Self:
        evidence_by_id = self._index_unique(self.evidence, "evidence_id")
        facts_by_id = self._index_unique(self.facts, "fact_id")
        findings_by_id = self._index_unique(self.findings, "finding_id")
        self._index_unique(self.recommendations, "recommendation_id")

        for fact in self.facts:
            referenced_evidence = []
            for evidence_id in fact.evidence_ids:
                item = evidence_by_id.get(evidence_id)
                if item is None:
                    raise ValueError(
                        f"fact {fact.fact_id!r} references unknown evidence {evidence_id!r}"
                    )
                referenced_evidence.append(item)

            if fact.status == FactStatus.VERIFIED:
                for item in referenced_evidence:
                    if item.quality_status == EvidenceQualityStatus.INVALID:
                        raise ValueError(
                            f"VERIFIED fact {fact.fact_id!r} references INVALID evidence"
                        )
                    if item.value != fact.value:
                        raise ValueError(
                            f"VERIFIED fact {fact.fact_id!r} does not match evidence value"
                        )
                    if fact.period and item.period and fact.period != item.period:
                        raise ValueError(
                            f"VERIFIED fact {fact.fact_id!r} does not match evidence period"
                        )

        for finding in self.findings:
            for fact_id in finding.fact_ids:
                if fact_id not in facts_by_id:
                    raise ValueError(
                        f"finding {finding.finding_id!r} references unknown fact {fact_id!r}"
                    )

        for recommendation in self.recommendations:
            referenced_findings = []
            for finding_id in recommendation.finding_ids:
                item = findings_by_id.get(finding_id)
                if item is None:
                    raise ValueError(
                        "recommendation "
                        f"{recommendation.recommendation_id!r} references unknown "
                        f"finding {finding_id!r}"
                    )
                referenced_findings.append(item)

            referenced_facts = {
                facts_by_id[fact_id]
                for finding in referenced_findings
                for fact_id in finding.fact_ids
            }

            if recommendation.compliance_status != ComplianceStatus.BLOCKED:
                non_verified = sorted(
                    fact.fact_id
                    for fact in referenced_facts
                    if fact.status != FactStatus.VERIFIED
                )
                if non_verified:
                    raise ValueError(
                        "actionable recommendation references non-VERIFIED facts: "
                        + ", ".join(non_verified)
                    )

            if recommendation.compliance_status == ComplianceStatus.PASSED:
                non_verified_evidence = sorted(
                    evidence_id
                    for fact in referenced_facts
                    for evidence_id in fact.evidence_ids
                    if evidence_by_id[evidence_id].quality_status
                    != EvidenceQualityStatus.VERIFIED
                )
                if non_verified_evidence:
                    raise ValueError(
                        "PASSED recommendation references non-VERIFIED evidence: "
                        + ", ".join(non_verified_evidence)
                    )

        return self

    @staticmethod
    def _index_unique(items: tuple[ContractModel, ...], id_field: str) -> dict[str, ContractModel]:
        indexed: dict[str, ContractModel] = {}
        for item in items:
            item_id = getattr(item, id_field)
            if item_id in indexed:
                raise ValueError(f"duplicate {id_field}: {item_id!r}")
            indexed[item_id] = item
        return indexed
