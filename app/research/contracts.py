"""Frozen contracts for structured research observations and validation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, EvidenceQualityStatus, NonEmptyStr


class ResearchNodeKind(StrEnum):
    MACRO = "MACRO"
    INDUSTRY = "INDUSTRY"
    STOCK = "STOCK"
    FUND = "FUND"
    CONVERTIBLE_BOND = "CONVERTIBLE_BOND"


class ResearchNodeStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    FAILED = "FAILED"


class ResearchNodeIssueCode(StrEnum):
    INVALID_OBSERVATION = "INVALID_OBSERVATION"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    MISSING_FIELDS = "MISSING_FIELDS"
    CONFLICTING_LINEAGE = "CONFLICTING_LINEAGE"


class ValidationStatus(StrEnum):
    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNRESOLVED = "UNRESOLVED"
    INSUFFICIENT = "INSUFFICIENT"


class ValidationIssueCode(StrEnum):
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    NON_VERIFIED_EVIDENCE = "NON_VERIFIED_EVIDENCE"
    DUPLICATE_LINEAGE = "DUPLICATE_LINEAGE"
    LINEAGE_CONFLICT = "LINEAGE_CONFLICT"
    INSUFFICIENT_INDEPENDENT_SOURCES = "INSUFFICIENT_INDEPENDENT_SOURCES"
    CONFLICTING_VALUES = "CONFLICTING_VALUES"
    NODE_PARTIAL = "NODE_PARTIAL"
    NODE_UNAVAILABLE = "NODE_UNAVAILABLE"


def _validate_finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


def _validate_timestamp(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class ResearchObservation(ContractModel):
    """One scalar observation carrying the source identity needed for review."""

    schema_version: Literal["research-observation.v1"] = "research-observation.v1"
    observation_id: NonEmptyStr
    owner_id: NonEmptyStr
    evidence_id: NonEmptyStr
    subject: NonEmptyStr
    metric: NonEmptyStr
    value: Decimal
    unit: NonEmptyStr
    period: NonEmptyStr
    provider: NonEmptyStr
    source: NonEmptyStr
    lineage_id: NonEmptyStr | None = None
    quality_status: EvidenceQualityStatus
    observed_at: datetime | None = None
    retrieved_at: datetime

    @model_validator(mode="after")
    def validate_observation(self) -> Self:
        _validate_finite(self.value, "value")
        _validate_timestamp(self.retrieved_at, "retrieved_at")
        if self.observed_at is not None:
            _validate_timestamp(self.observed_at, "observed_at")
        if self.quality_status == EvidenceQualityStatus.VERIFIED:
            # A verified observation is the only kind allowed to participate in
            # numeric cross-validation.  The value itself is always present by
            # type, so no sentinel zero can stand in for missing data.
            return self
        return self


class ResearchNodeIssue(ContractModel):
    code: ResearchNodeIssueCode
    safe_message: NonEmptyStr
    field_name: NonEmptyStr | None = None


class ResearchNodeResult(ContractModel):
    """Four-state result for one future structured research node."""

    schema_version: Literal["research-node-result.v1"] = "research-node-result.v1"
    request_id: NonEmptyStr
    node_id: NonEmptyStr
    owner_id: NonEmptyStr
    node_kind: ResearchNodeKind
    subject: NonEmptyStr
    completed_at: datetime
    status: ResearchNodeStatus
    observations: tuple[ResearchObservation, ...] = Field(default_factory=tuple)
    missing_fields: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    issues: tuple[ResearchNodeIssue, ...] = Field(default_factory=tuple)
    scope_description: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        _validate_timestamp(self.completed_at, "completed_at")
        observation_ids = [item.observation_id for item in self.observations]
        evidence_ids = [item.evidence_id for item in self.observations]
        if len(set(observation_ids)) != len(observation_ids):
            raise ValueError("observations must not contain duplicate observation_id")
        if len(set(evidence_ids)) != len(evidence_ids):
            raise ValueError("observations must not contain duplicate evidence_id")
        if any(item.owner_id != self.owner_id for item in self.observations):
            raise ValueError("observation owner_id does not match node owner_id")
        if any(item.subject != self.subject for item in self.observations):
            raise ValueError("observation subject does not match node subject")
        if len(set(self.missing_fields)) != len(self.missing_fields):
            raise ValueError("missing_fields must not contain duplicates")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("issues must not contain duplicate code")

        if self.status == ResearchNodeStatus.COMPLETE:
            if not self.observations:
                raise ValueError("COMPLETE research node requires observations")
            if self.missing_fields or self.issues:
                raise ValueError("COMPLETE research node must not carry missing/issues")
        elif self.status == ResearchNodeStatus.PARTIAL:
            if not self.observations:
                raise ValueError("PARTIAL research node requires usable observations")
            if not self.missing_fields and not self.issues:
                raise ValueError("PARTIAL research node requires missing_fields or issues")
        elif self.status == ResearchNodeStatus.EMPTY:
            if self.observations or self.missing_fields or self.issues:
                raise ValueError("EMPTY research node must not carry observations/issues")
            if self.scope_description is None:
                raise ValueError("EMPTY research node requires scope_description")
        elif self.status == ResearchNodeStatus.FAILED:
            if self.observations:
                raise ValueError("FAILED research node must not carry observations")
            if not self.issues:
                raise ValueError("FAILED research node requires at least one issue")
        return self


class ValidationClaim(ContractModel):
    """A scalar claim to compare against independent observations."""

    schema_version: Literal["validation-claim.v1"] = "validation-claim.v1"
    claim_id: NonEmptyStr
    owner_id: NonEmptyStr
    subject: NonEmptyStr
    metric: NonEmptyStr
    unit: NonEmptyStr
    period: NonEmptyStr
    expected_value: Decimal

    @model_validator(mode="after")
    def validate_claim(self) -> Self:
        _validate_finite(self.expected_value, "expected_value")
        return self


class ValidationIssue(ContractModel):
    code: ValidationIssueCode
    safe_message: NonEmptyStr
    evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("validation issue evidence_ids must not contain duplicates")
        return self


class CrossValidationResult(ContractModel):
    """Closed deterministic support/contradiction result for one claim."""

    schema_version: Literal["cross-validation-result.v1"] = (
        "cross-validation-result.v1"
    )
    validation_id: NonEmptyStr
    owner_id: NonEmptyStr
    claim_id: NonEmptyStr
    subject: NonEmptyStr
    metric: NonEmptyStr
    unit: NonEmptyStr
    period: NonEmptyStr
    expected_value: Decimal
    status: ValidationStatus
    supporting_evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    contradicting_evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    duplicate_lineage_evidence_ids: tuple[NonEmptyStr, ...] = Field(
        default_factory=tuple
    )
    unlinked_evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    unresolved_evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    independent_lineage_count: int = Field(ge=0)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    methodology: NonEmptyStr
    issues: tuple[ValidationIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        _validate_finite(self.expected_value, "expected_value")
        _validate_finite(self.confidence, "confidence")
        fields = (
            self.supporting_evidence_ids,
            self.contradicting_evidence_ids,
            self.duplicate_lineage_evidence_ids,
            self.unlinked_evidence_ids,
            self.unresolved_evidence_ids,
        )
        for values in fields:
            if len(set(values)) != len(values):
                raise ValueError("validation evidence ID lists must not contain duplicates")
        if set(self.supporting_evidence_ids) & set(self.contradicting_evidence_ids):
            raise ValueError("an evidence ID cannot both support and contradict")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("validation issues must not contain duplicate code")

        if self.status == ValidationStatus.SUPPORTED:
            if self.independent_lineage_count < 2:
                raise ValueError("SUPPORTED validation requires two independent lineages")
            if not self.supporting_evidence_ids or self.contradicting_evidence_ids:
                raise ValueError("SUPPORTED validation requires support and no contradiction")
        elif self.status == ValidationStatus.CONTRADICTED:
            if self.independent_lineage_count < 2:
                raise ValueError("CONTRADICTED validation requires two independent lineages")
            if not self.contradicting_evidence_ids or self.supporting_evidence_ids:
                raise ValueError("CONTRADICTED validation requires contradiction and no support")
        elif self.status == ValidationStatus.INSUFFICIENT:
            if self.independent_lineage_count >= 2:
                raise ValueError("INSUFFICIENT validation has enough independent lineages")
        elif self.status == ValidationStatus.UNRESOLVED:
            if (
                not self.issues
                and not self.unresolved_evidence_ids
                and not (
                    self.supporting_evidence_ids
                    and self.contradicting_evidence_ids
                )
            ):
                raise ValueError("UNRESOLVED validation requires an explicit conflict")
        return self
