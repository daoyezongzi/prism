"""Immutable contracts for the independent risk and compliance gates."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr


class GateStatus(StrEnum):
    """A gate outcome, ordered as BLOCKED > REVIEW_REQUIRED > PASS."""

    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class RiskGateIssueCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    PROFILE_MISMATCH = "PROFILE_MISMATCH"
    PIPELINE_REVIEW_REQUIRED = "PIPELINE_REVIEW_REQUIRED"
    PIPELINE_BLOCKED = "PIPELINE_BLOCKED"
    TRACE_INTEGRITY = "TRACE_INTEGRITY"
    NON_VERIFIED_FACT = "NON_VERIFIED_FACT"
    NON_VERIFIED_EVIDENCE = "NON_VERIFIED_EVIDENCE"
    RISK_BUDGET_REVIEW_REQUIRED = "RISK_BUDGET_REVIEW_REQUIRED"
    RISK_BUDGET_BLOCKED = "RISK_BUDGET_BLOCKED"
    ALLOCATION_REVIEW_REQUIRED = "ALLOCATION_REVIEW_REQUIRED"
    ALLOCATION_BLOCKED = "ALLOCATION_BLOCKED"
    ALLOCATION_IDENTITY_MISMATCH = "ALLOCATION_IDENTITY_MISMATCH"


class ComplianceGateIssueCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    SENSITIVE_INPUT = "SENSITIVE_INPUT"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    PIPELINE_REVIEW_REQUIRED = "PIPELINE_REVIEW_REQUIRED"
    PIPELINE_BLOCKED = "PIPELINE_BLOCKED"
    TRACE_INTEGRITY = "TRACE_INTEGRITY"
    UNKNOWN_FINDING = "UNKNOWN_FINDING"
    NON_VERIFIED_FACT = "NON_VERIFIED_FACT"
    NON_VERIFIED_EVIDENCE = "NON_VERIFIED_EVIDENCE"
    MISSING_DISCLOSURE = "MISSING_DISCLOSURE"
    GUARANTEE_LANGUAGE = "GUARANTEE_LANGUAGE"
    TARGET_RETURN_LANGUAGE = "TARGET_RETURN_LANGUAGE"


class DisclosureCode(StrEnum):
    """Machine-readable disclosures required before advice composition."""

    NO_GUARANTEE = "NO_GUARANTEE"
    LOSS_RISK = "LOSS_RISK"
    EVIDENCE_SCOPE = "EVIDENCE_SCOPE"
    INVALIDATION_CONDITIONS = "INVALIDATION_CONDITIONS"


REQUIRED_DISCLOSURES: tuple[DisclosureCode, ...] = (
    DisclosureCode.NO_GUARANTEE,
    DisclosureCode.LOSS_RISK,
    DisclosureCode.EVIDENCE_SCOPE,
    DisclosureCode.INVALIDATION_CONDITIONS,
)

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


def _reject_sensitive(values: tuple[str, ...], field_name: str) -> None:
    if any(_contains_sensitive(value) for value in values):
        raise ValueError(f"{field_name} must not contain sensitive fields")


class AdvisoryCandidate(ContractModel):
    """A non-persistent preflight input, not a Recommendation.

    Phase 11 checks this candidate but never stores it in a decision trace or
    converts it to the public ``Recommendation`` contract.  Text is retained
    only on the call boundary and is deliberately absent from gate results.
    """

    schema_version: Literal["advisory-candidate.v1"] = "advisory-candidate.v1"
    candidate_id: NonEmptyStr
    owner_id: NonEmptyStr
    statement: NonEmptyStr
    rationale: NonEmptyStr
    finding_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)
    disclosure_codes: tuple[DisclosureCode, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_collections(self) -> Self:
        if len(set(self.finding_ids)) != len(self.finding_ids):
            raise ValueError("finding_ids must not contain duplicates")
        if len(set(self.invalidation_conditions)) != len(self.invalidation_conditions):
            raise ValueError("invalidation_conditions must not contain duplicates")
        if len(set(self.disclosure_codes)) != len(self.disclosure_codes):
            raise ValueError("disclosure_codes must not contain duplicates")
        return self


class RiskGateIssue(ContractModel):
    code: RiskGateIssueCode
    safe_message: NonEmptyStr

    @model_validator(mode="after")
    def validate_safe_message(self) -> Self:
        _reject_sensitive((self.safe_message,), "risk gate issue")
        return self


class ComplianceGateIssue(ContractModel):
    code: ComplianceGateIssueCode
    safe_message: NonEmptyStr

    @model_validator(mode="after")
    def validate_safe_message(self) -> Self:
        _reject_sensitive((self.safe_message,), "compliance gate issue")
        return self


class RiskGateResult(ContractModel):
    """Closed risk eligibility result with no action or recommendation."""

    schema_version: Literal["risk-gate-result.v1"] = "risk-gate-result.v1"
    gate_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    research_run_id: NonEmptyStr
    risk_assessment_id: NonEmptyStr
    allocation_request_id: NonEmptyStr
    status: GateStatus
    checked_evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    checked_fact_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    checked_finding_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    remediation_required: bool = False
    remediation_breach_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    issues: tuple[RiskGateIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        _reject_sensitive(
            (
                self.gate_id,
                self.owner_id,
                self.profile_id,
                self.research_run_id,
                self.risk_assessment_id,
                self.allocation_request_id,
                *self.checked_evidence_ids,
                *self.checked_fact_ids,
                *self.checked_finding_ids,
                *self.remediation_breach_ids,
            ),
            "risk gate result",
        )
        for name in (
            "checked_evidence_ids",
            "checked_fact_ids",
            "checked_finding_ids",
            "remediation_breach_ids",
        ):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("risk gate issues must not contain duplicate codes")
        if self.status == GateStatus.PASS:
            if self.issues:
                raise ValueError("PASS risk gate must not carry issues")
            if not self.checked_evidence_ids:
                raise ValueError("PASS risk gate requires checked evidence")
            if not self.checked_fact_ids or not self.checked_finding_ids:
                raise ValueError("PASS risk gate requires checked facts and findings")
        elif not self.issues:
            raise ValueError("non-PASS risk gate requires an issue")
        if self.remediation_required != bool(self.remediation_breach_ids):
            raise ValueError(
                "remediation_required must match remediation_breach_ids"
            )
        if self.remediation_required and self.status != GateStatus.PASS:
            raise ValueError("only a PASS risk gate may approve remediation")
        return self


class ComplianceGateResult(ContractModel):
    """Closed compliance preflight result; candidate prose is never echoed."""

    schema_version: Literal["compliance-gate-result.v1"] = "compliance-gate-result.v1"
    gate_id: NonEmptyStr
    candidate_id: NonEmptyStr
    owner_id: NonEmptyStr
    research_run_id: NonEmptyStr
    status: GateStatus
    required_disclosures: tuple[DisclosureCode, ...] = REQUIRED_DISCLOSURES
    present_disclosures: tuple[DisclosureCode, ...] = Field(default_factory=tuple)
    checked_finding_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    issues: tuple[ComplianceGateIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        _reject_sensitive(
            (
                self.gate_id,
                self.candidate_id,
                self.owner_id,
                self.research_run_id,
                *self.checked_finding_ids,
            ),
            "compliance gate result",
        )
        if self.required_disclosures != REQUIRED_DISCLOSURES:
            raise ValueError("required_disclosures must match compliance policy v1")
        if any(item not in self.required_disclosures for item in self.present_disclosures):
            raise ValueError("present_disclosures must be required disclosure codes")
        if len(set(self.present_disclosures)) != len(self.present_disclosures):
            raise ValueError("present_disclosures must not contain duplicates")
        if len(set(self.checked_finding_ids)) != len(self.checked_finding_ids):
            raise ValueError("checked_finding_ids must not contain duplicates")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("compliance gate issues must not contain duplicate codes")
        if self.status == GateStatus.PASS:
            if self.issues or self.present_disclosures != REQUIRED_DISCLOSURES:
                raise ValueError(
                    "PASS compliance gate requires all disclosures and no issues"
                )
            if not self.checked_finding_ids:
                raise ValueError("PASS compliance gate requires checked findings")
        elif not self.issues:
            raise ValueError("non-PASS compliance gate requires an issue")
        return self


class DecisionGateResult(ContractModel):
    """Aggregate eligibility for the next Recommendation-only phase."""

    schema_version: Literal["decision-gate-result.v1"] = "decision-gate-result.v1"
    gate_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    research_run_id: NonEmptyStr
    risk_gate: RiskGateResult
    compliance_gate: ComplianceGateResult
    status: GateStatus
    eligible_for_recommendation: bool

    @model_validator(mode="after")
    def validate_aggregate(self) -> Self:
        _reject_sensitive(
            (self.gate_id, self.owner_id, self.profile_id, self.research_run_id),
            "decision gate result",
        )
        if self.risk_gate.owner_id != self.owner_id:
            raise ValueError("risk gate owner does not match aggregate owner")
        if self.compliance_gate.owner_id != self.owner_id:
            raise ValueError("compliance gate owner does not match aggregate owner")
        if self.risk_gate.profile_id != self.profile_id:
            raise ValueError("risk gate profile does not match aggregate profile")
        if self.risk_gate.research_run_id != self.research_run_id:
            raise ValueError("risk gate run does not match aggregate run")
        if self.compliance_gate.research_run_id != self.research_run_id:
            raise ValueError("compliance gate run does not match aggregate run")

        statuses = {self.risk_gate.status, self.compliance_gate.status}
        expected = (
            GateStatus.BLOCKED
            if GateStatus.BLOCKED in statuses
            else GateStatus.REVIEW_REQUIRED
            if GateStatus.REVIEW_REQUIRED in statuses
            else GateStatus.PASS
        )
        if self.status != expected:
            raise ValueError("aggregate status does not match child gate statuses")
        if self.eligible_for_recommendation != (expected == GateStatus.PASS):
            raise ValueError("recommendation eligibility does not match aggregate status")
        return self
