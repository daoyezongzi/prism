"""Deterministic bridge from validated research claims to Evidence/Finding closure.

This module deliberately does not execute providers or compose recommendations.  It
only registers a supported scalar claim as a verified :class:`Fact` when the
cross-validation result, its observations, and the normalized Evidence objects all
agree on ownership, scope, value, period, unit, quality, and lineage.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from hashlib import sha256
from math import isfinite
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import (
    ContractModel,
    Evidence,
    EvidenceQualityStatus,
    Fact,
    FactStatus,
    Finding,
    FindingSeverity,
    NonEmptyStr,
)
from app.research.contracts import (
    CrossValidationResult,
    ResearchObservation,
    ValidationStatus,
)


class EvidenceBridgeStatus(StrEnum):
    """Whether a validated research claim can be consumed downstream."""

    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class EvidenceBridgeIssueCode(StrEnum):
    """Stable, safe issue categories emitted by the bridge."""

    VALIDATION_CONTRADICTED = "VALIDATION_CONTRADICTED"
    VALIDATION_UNRESOLVED = "VALIDATION_UNRESOLVED"
    INSUFFICIENT_SOURCES = "INSUFFICIENT_SOURCES"
    VALIDATION_ISSUES = "VALIDATION_ISSUES"
    UNKNOWN_EVIDENCE = "UNKNOWN_EVIDENCE"
    DUPLICATE_EVIDENCE = "DUPLICATE_EVIDENCE"
    MISSING_OBSERVATION = "MISSING_OBSERVATION"
    DUPLICATE_OBSERVATION = "DUPLICATE_OBSERVATION"
    NON_VERIFIED_EVIDENCE = "NON_VERIFIED_EVIDENCE"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"
    VALUE_MISMATCH = "VALUE_MISMATCH"
    PERIOD_MISMATCH = "PERIOD_MISMATCH"
    UNIT_MISMATCH = "UNIT_MISMATCH"
    LINEAGE_MISMATCH = "LINEAGE_MISMATCH"
    PROVENANCE_MISMATCH = "PROVENANCE_MISMATCH"
    INVALID_INPUT = "INVALID_INPUT"
    SENSITIVE_INPUT = "SENSITIVE_INPUT"


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


def _safe_ids(values: Iterable[str], known_ids: set[str]) -> tuple[str, ...]:
    """Return bounded, non-sensitive IDs so issues never echo raw payloads."""

    return tuple(
        sorted(
            {
                value
                for value in values
                if isinstance(value, str)
                and 0 < len(value) <= 128
                and all(
                    character.isalnum() or character in "_.:/-"
                    for character in value
                )
                and not _contains_sensitive(value)
            }
        )
    )


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


def _safe_validation_id(value: str) -> str:
    if _contains_sensitive(value):
        return _stable_id("validation", "redacted", value)
    return value


def _issue(
    code: EvidenceBridgeIssueCode,
    message: str,
    evidence_ids: Iterable[str] = (),
    *,
    known_ids: set[str] | None = None,
) -> "EvidenceBridgeIssue":
    return EvidenceBridgeIssue(
        code=code,
        safe_message=message,
        evidence_ids=_safe_ids(
            evidence_ids,
            known_ids if known_ids is not None else set(),
        ),
    )


class EvidenceBridgeIssue(ContractModel):
    """Safe issue metadata; no upstream payload or exception is retained."""

    code: EvidenceBridgeIssueCode
    safe_message: NonEmptyStr
    evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_issue(self) -> Self:
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must not contain duplicates")
        if _contains_sensitive(self.safe_message):
            raise ValueError("safe_message must not contain sensitive fields")
        if any(_contains_sensitive(item) for item in self.evidence_ids):
            raise ValueError("evidence_ids must not contain sensitive fields")
        return self


class EvidenceFindingBridgeResult(ContractModel):
    """Result of registering one cross-validated claim in the domain graph."""

    schema_version: Literal["evidence-finding-bridge.v1"] = (
        "evidence-finding-bridge.v1"
    )
    validation_id: NonEmptyStr
    status: EvidenceBridgeStatus
    fact: Fact | None = None
    finding: Finding | None = None
    supporting_evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    issues: tuple[EvidenceBridgeIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if _contains_sensitive(self.validation_id):
            raise ValueError("validation_id must not contain sensitive fields")
        if any(_contains_sensitive(item) for item in self.supporting_evidence_ids):
            raise ValueError("supporting_evidence_ids must not contain sensitive fields")
        if len(set(self.supporting_evidence_ids)) != len(
            self.supporting_evidence_ids
        ):
            raise ValueError("supporting_evidence_ids must not contain duplicates")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("issues must not contain duplicate code")

        if self.status == EvidenceBridgeStatus.READY:
            if self.fact is None or self.finding is None:
                raise ValueError("READY bridge result requires fact and finding")
            if self.fact.status != FactStatus.VERIFIED:
                raise ValueError("READY bridge result requires a VERIFIED fact")
            if self.finding.fact_ids != (self.fact.fact_id,):
                raise ValueError("finding must reference the bridge fact")
            if self.fact.evidence_ids != self.supporting_evidence_ids:
                raise ValueError("fact evidence IDs must match bridge evidence IDs")
            if self.issues:
                raise ValueError("READY bridge result must not carry issues")
        else:
            if self.fact is not None or self.finding is not None:
                raise ValueError(
                    "non-ready bridge result must not expose Fact or Finding"
                )
            if not self.issues:
                raise ValueError("non-ready bridge result requires an issue")
        return self


def _decimal_value(value: object) -> Decimal | None:
    """Parse only finite scalar JSON-like numeric values."""

    if isinstance(value, bool) or value is None or isinstance(value, (list, tuple, dict)):
        return None
    if not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if not parsed.is_finite():
        return None
    if isinstance(value, float) and not isfinite(value):
        return None
    return parsed


def _review_result(
    validation: CrossValidationResult,
    code: EvidenceBridgeIssueCode,
    message: str,
) -> EvidenceFindingBridgeResult:
    return EvidenceFindingBridgeResult(
        validation_id=_safe_validation_id(validation.validation_id),
        status=EvidenceBridgeStatus.REVIEW_REQUIRED,
        issues=(EvidenceBridgeIssue(code=code, safe_message=message),),
    )


def _blocked_result(
    validation: CrossValidationResult,
    code: EvidenceBridgeIssueCode,
    message: str,
    evidence_ids: Iterable[str] = (),
    *,
    known_ids: set[str] | None = None,
) -> EvidenceFindingBridgeResult:
    return EvidenceFindingBridgeResult(
        validation_id=_safe_validation_id(validation.validation_id),
        status=EvidenceBridgeStatus.BLOCKED,
        issues=(
            _issue(
                code,
                message,
                evidence_ids,
                known_ids=known_ids,
            ),
        ),
    )


def bridge_cross_validation(
    validation: CrossValidationResult,
    evidence: Iterable[Evidence],
    observations: Iterable[ResearchObservation],
    *,
    finding_kind: str,
    finding_severity: FindingSeverity,
    statement: str,
) -> EvidenceFindingBridgeResult:
    """Build a verified Fact/Finding only from a fully closed supported claim.

    The observations are retained as the owner/subject/lineage binding because the
    shared Evidence contract intentionally carries provider provenance but not
    user ownership.  Every selected observation must match its registered Evidence
    row field-for-field before a Fact is emitted.
    """

    if not isinstance(validation, CrossValidationResult):
        raise TypeError("validation must be a CrossValidationResult")

    safe_texts = (
        validation.owner_id,
        validation.claim_id,
        validation.subject,
        validation.metric,
        validation.unit,
        validation.period,
        validation.methodology,
        finding_kind if isinstance(finding_kind, str) else "",
        statement if isinstance(statement, str) else "",
    )
    if any(not isinstance(value, str) or not value.strip() for value in safe_texts):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.INVALID_INPUT,
            "bridge input contains an empty required field",
        )
    if any(_contains_sensitive(value) for value in safe_texts):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.SENSITIVE_INPUT,
            "bridge input contains a disallowed sensitive field",
        )
    if not isinstance(finding_severity, FindingSeverity):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.INVALID_INPUT,
            "bridge input contains an invalid finding severity",
        )

    if validation.status == ValidationStatus.CONTRADICTED:
        return _review_result(
            validation,
            EvidenceBridgeIssueCode.VALIDATION_CONTRADICTED,
            "independent evidence contradicts the claim; human review is required",
        )
    if validation.status == ValidationStatus.UNRESOLVED:
        return _review_result(
            validation,
            EvidenceBridgeIssueCode.VALIDATION_UNRESOLVED,
            "independent evidence does not resolve the claim; human review is required",
        )
    if validation.status == ValidationStatus.INSUFFICIENT:
        return _review_result(
            validation,
            EvidenceBridgeIssueCode.INSUFFICIENT_SOURCES,
            "fewer than two independent sources support the claim",
        )

    # SUPPORTED is the only status that may reach Fact creation.  A forged or
    # manually edited result carrying any ambiguity is blocked rather than
    # silently trusting its status label.
    if validation.issues:
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.VALIDATION_ISSUES,
            "supported validation carries unresolved issue metadata",
        )
    if (
        not validation.supporting_evidence_ids
        or validation.contradicting_evidence_ids
        or validation.duplicate_lineage_evidence_ids
        or validation.unresolved_evidence_ids
        or validation.independent_lineage_count < 2
    ):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.VALIDATION_ISSUES,
            "supported validation does not satisfy the independent-source invariant",
        )

    if validation.status != ValidationStatus.SUPPORTED:
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.INVALID_INPUT,
            "bridge input contains an unknown validation status",
        )

    evidence_items = tuple(evidence)
    observation_items = tuple(observations)
    if not all(isinstance(item, Evidence) for item in evidence_items):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.INVALID_INPUT,
            "evidence registry contains an invalid record",
        )
    if not all(isinstance(item, ResearchObservation) for item in observation_items):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.INVALID_INPUT,
            "observation registry contains an invalid record",
        )
    evidence_ids = [item.evidence_id for item in evidence_items]
    observation_ids = [item.evidence_id for item in observation_items]
    known_evidence_ids = set(evidence_ids)
    if len(evidence_ids) != len(known_evidence_ids):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.DUPLICATE_EVIDENCE,
            "the evidence registry contains duplicate identifiers",
            known_ids=known_evidence_ids,
        )
    if len(validation.supporting_evidence_ids) != len(
        set(validation.supporting_evidence_ids)
    ):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.DUPLICATE_EVIDENCE,
            "supported validation contains duplicate evidence identifiers",
            validation.supporting_evidence_ids,
            known_ids=known_evidence_ids,
        )
    if set(validation.supporting_evidence_ids) & set(
        validation.contradicting_evidence_ids
    ):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.VALIDATION_ISSUES,
            "supported validation reuses an evidence identifier across outcomes",
            validation.supporting_evidence_ids,
            known_ids=known_evidence_ids,
        )
    if len(observation_ids) != len(set(observation_ids)):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.DUPLICATE_OBSERVATION,
            "the observation registry contains duplicate identifiers",
            known_ids=known_evidence_ids,
        )

    requested_ids = tuple(sorted(validation.supporting_evidence_ids))
    missing_evidence = [item for item in requested_ids if item not in known_evidence_ids]
    if missing_evidence:
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.UNKNOWN_EVIDENCE,
            "a supporting evidence record is not registered",
            missing_evidence,
            known_ids=known_evidence_ids,
        )

    evidence_by_id = {item.evidence_id: item for item in evidence_items}
    observation_by_id = {item.evidence_id: item for item in observation_items}
    missing_observations = [item for item in requested_ids if item not in observation_by_id]
    if missing_observations:
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.MISSING_OBSERVATION,
            "a supporting evidence record has no owner and lineage binding",
            missing_observations,
            known_ids=known_evidence_ids,
        )

    selected_evidence = tuple(evidence_by_id[item] for item in requested_ids)
    selected_observations = tuple(observation_by_id[item] for item in requested_ids)

    if any(item.quality_status != EvidenceQualityStatus.VERIFIED for item in selected_evidence):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.NON_VERIFIED_EVIDENCE,
            "supporting evidence is not VERIFIED",
            (item.evidence_id for item in selected_evidence),
            known_ids=known_evidence_ids,
        )
    if any(item.quality_status != EvidenceQualityStatus.VERIFIED for item in selected_observations):
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.NON_VERIFIED_EVIDENCE,
            "supporting observation is not VERIFIED",
            (item.evidence_id for item in selected_observations),
            known_ids=known_evidence_ids,
        )

    for item in selected_observations:
        if item.owner_id != validation.owner_id:
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.OWNER_MISMATCH,
                "supporting observation belongs to a different owner",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )
        if (
            item.subject != validation.subject
            or item.metric != validation.metric
            or item.unit != validation.unit
            or item.period != validation.period
        ):
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.SCOPE_MISMATCH,
                "supporting observation scope does not match the validated claim",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )
        if item.lineage_id is None:
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.LINEAGE_MISMATCH,
                "supporting observation has no independent lineage",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )
        observed_value = _decimal_value(item.value)
        if observed_value is None or observed_value != validation.expected_value:
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.VALUE_MISMATCH,
                "supporting observation value does not match the validated claim",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )

    lineages = {item.lineage_id for item in selected_observations}
    if len(lineages) != validation.independent_lineage_count:
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.LINEAGE_MISMATCH,
            "registered lineages do not match the validation result",
            requested_ids,
            known_ids=known_evidence_ids,
        )

    first_value = selected_evidence[0].value
    expected_value = _decimal_value(first_value)
    if expected_value is None or expected_value != validation.expected_value:
        return _blocked_result(
            validation,
            EvidenceBridgeIssueCode.VALUE_MISMATCH,
            "registered evidence value does not match the validated claim",
            requested_ids,
            known_ids=known_evidence_ids,
        )

    for item, observation_item in zip(selected_evidence, selected_observations):
        if item.value != first_value:
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.VALUE_MISMATCH,
                "supporting evidence values use inconsistent representations",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )
        if item.field != validation.metric:
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.SCOPE_MISMATCH,
                "registered evidence field does not match the claim",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )
        if item.unit != validation.unit:
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.UNIT_MISMATCH,
                "registered evidence field or unit does not match the claim",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )
        if item.period != validation.period:
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.PERIOD_MISMATCH,
                "registered evidence period does not match the claim",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )
        if (
            item.provider != observation_item.provider
            or item.source != observation_item.source
            or item.lineage_id != observation_item.lineage_id
            or item.observed_at != observation_item.observed_at
            or item.retrieved_at != observation_item.retrieved_at
        ):
            return _blocked_result(
                validation,
                EvidenceBridgeIssueCode.PROVENANCE_MISMATCH,
                "registered evidence provenance does not match its observation",
                (item.evidence_id,),
                known_ids=known_evidence_ids,
            )

    fact_id = _stable_id(
        "fact",
        validation.owner_id,
        validation.claim_id,
        validation.subject,
        validation.metric,
        validation.unit,
        validation.period,
        str(validation.expected_value),
        *requested_ids,
    )
    finding_kind_value = finding_kind.strip()
    statement_value = statement.strip()
    methodology_value = validation.methodology.strip()
    finding_id = _stable_id(
        "finding",
        fact_id,
        finding_kind_value,
        finding_severity.value,
        statement_value,
        methodology_value,
    )
    fact = Fact(
        fact_id=fact_id,
        subject=validation.subject,
        metric=validation.metric,
        value=first_value,
        unit=validation.unit,
        period=validation.period,
        status=FactStatus.VERIFIED,
        evidence_ids=requested_ids,
    )
    finding = Finding(
        finding_id=finding_id,
        kind=finding_kind_value,
        severity=finding_severity,
        statement=statement_value,
        fact_ids=(fact.fact_id,),
        confidence=float(validation.confidence),
        methodology=methodology_value,
    )
    return EvidenceFindingBridgeResult(
        validation_id=_safe_validation_id(validation.validation_id),
        status=EvidenceBridgeStatus.READY,
        fact=fact,
        finding=finding,
        supporting_evidence_ids=requested_ids,
    )


def build_evidence_grounded_finding(
    validation: CrossValidationResult,
    evidence: Iterable[Evidence],
    observations: Iterable[ResearchObservation],
    *,
    finding_kind: str,
    finding_severity: FindingSeverity,
    statement: str,
) -> EvidenceFindingBridgeResult:
    """Descriptive alias for callers that prefer the product-layer vocabulary."""

    return bridge_cross_validation(
        validation,
        evidence,
        observations,
        finding_kind=finding_kind,
        finding_severity=finding_severity,
        statement=statement,
    )


__all__ = [
    "EvidenceBridgeIssue",
    "EvidenceBridgeIssueCode",
    "EvidenceBridgeStatus",
    "EvidenceFindingBridgeResult",
    "bridge_cross_validation",
    "build_evidence_grounded_finding",
]
