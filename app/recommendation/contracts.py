"""Immutable Recommendation composition and Decision Receipt contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.allocation.contracts import AllocationBandDimension
from app.contracts.evidence import (
    ActionType,
    ContractModel,
    DecisionTrace,
    NonEmptyStr,
    Recommendation,
)
from app.gates import (
    REQUIRED_DISCLOSURES,
    DecisionGateResult,
    DisclosureCode,
    GateStatus,
)
from app.gates.fingerprint import (
    canonical_model_signature,
    canonical_payload_signature,
)


Digest = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    ),
]


class GenerationMode(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"


class RecommendationIssueCode(StrEnum):
    INVALID_INPUT = "INVALID_INPUT"
    SENSITIVE_INPUT = "SENSITIVE_INPUT"
    GATE_REVIEW_REQUIRED = "GATE_REVIEW_REQUIRED"
    GATE_BLOCKED = "GATE_BLOCKED"
    STALE_GATE = "STALE_GATE"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    PROFILE_MISMATCH = "PROFILE_MISMATCH"
    PORTFOLIO_MISMATCH = "PORTFOLIO_MISMATCH"
    RISK_CLOSURE_MISMATCH = "RISK_CLOSURE_MISMATCH"
    ALLOCATION_MISMATCH = "ALLOCATION_MISMATCH"
    NO_ACTIONABLE_BANDS = "NO_ACTIONABLE_BANDS"
    BREACH_COVERAGE_MISMATCH = "BREACH_COVERAGE_MISMATCH"
    AGGREGATE_BREACH_UNMAPPED = "AGGREGATE_BREACH_UNMAPPED"
    TRACE_INTEGRITY = "TRACE_INTEGRITY"


class RuleVersion(ContractModel):
    component: NonEmptyStr
    version: NonEmptyStr


REQUIRED_RULE_VERSIONS: tuple[RuleVersion, ...] = (
    RuleVersion(component="evidence-contract", version="v1"),
    RuleVersion(component="risk-budget", version="v1"),
    RuleVersion(component="allocation-envelope", version="v1"),
    RuleVersion(component="compliance-policy", version="v1"),
    RuleVersion(component="recommendation-composer", version="v1"),
    RuleVersion(component="decision-receipt", version="v1"),
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


def recommendation_content_id(
    *,
    profile_id: str,
    decision_gate_id: str,
    candidate_id: str,
    band_id: str,
    recommendation: Recommendation,
) -> str:
    """Return the stable ID for a Recommendation's complete material content."""

    payload = {
        "profile_id": profile_id,
        "decision_gate_id": decision_gate_id,
        "candidate_id": candidate_id,
        "band_id": band_id,
        "action_type": recommendation.action_type.value,
        "asset_id": recommendation.asset_id,
        "allocation_range": recommendation.allocation_range.model_dump(mode="json"),
        "rationale": recommendation.rationale,
        "finding_ids": list(recommendation.finding_ids),
        "compliance_status": recommendation.compliance_status.value,
        "invalidation_conditions": list(recommendation.invalidation_conditions),
    }
    return "recommendation:" + canonical_payload_signature(payload)[:32]


class RecommendationIssue(ContractModel):
    code: RecommendationIssueCode
    safe_message: NonEmptyStr

    @model_validator(mode="after")
    def validate_safe_message(self) -> Self:
        _reject_sensitive((self.safe_message,), "recommendation issue")
        return self


class RecommendationBinding(ContractModel):
    recommendation_id: NonEmptyStr
    band_id: NonEmptyStr
    dimension: AllocationBandDimension
    target_id: NonEmptyStr
    current_weight_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    allowed_max_weight_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    target_min_weight_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    target_max_weight_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    breach_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_binding(self) -> Self:
        if len(set(self.breach_ids)) != len(self.breach_ids):
            raise ValueError("binding breach_ids must not contain duplicates")
        if self.target_min_weight_pct > self.target_max_weight_pct:
            raise ValueError("binding target minimum must not exceed maximum")
        if self.breach_ids:
            if self.current_weight_pct <= self.allowed_max_weight_pct:
                raise ValueError("breach binding must exceed its allowed maximum")
            if self.target_min_weight_pct != Decimal("0"):
                raise ValueError("breach binding target minimum must be zero")
            if self.target_max_weight_pct != self.allowed_max_weight_pct:
                raise ValueError("breach binding target maximum must equal its limit")
        elif (
            self.current_weight_pct > self.allowed_max_weight_pct
            or self.target_min_weight_pct != self.current_weight_pct
            or self.target_max_weight_pct != self.current_weight_pct
        ):
            raise ValueError("non-breach binding must hold its current weight")
        _reject_sensitive(
            (
                self.recommendation_id,
                self.band_id,
                self.target_id,
                *self.breach_ids,
            ),
            "recommendation binding",
        )
        return self


class DecisionReceipt(ContractModel):
    """Content-addressed replay metadata without raw private holdings."""

    schema_version: Literal["decision-receipt.v1"] = "decision-receipt.v1"
    receipt_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    profile_version: int = Field(ge=1)
    portfolio_bundle_id: NonEmptyStr
    position_snapshot_id: NonEmptyStr
    exposure_report_id: NonEmptyStr
    concentration_report_id: NonEmptyStr
    risk_assessment_id: NonEmptyStr
    allocation_request_id: NonEmptyStr
    allocation_envelope_id: NonEmptyStr
    research_run_id: NonEmptyStr
    candidate_id: NonEmptyStr
    risk_gate_id: NonEmptyStr
    compliance_gate_id: NonEmptyStr
    decision_gate_id: NonEmptyStr
    evidence_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    fact_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    finding_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    recommendation_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    recommendation_bindings: tuple[RecommendationBinding, ...] = Field(min_length=1)
    rule_versions: tuple[RuleVersion, ...] = REQUIRED_RULE_VERSIONS
    generation_mode: Literal[GenerationMode.DETERMINISTIC] = (
        GenerationMode.DETERMINISTIC
    )
    model_versions: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    generated_at: datetime
    decision_trace_hash: Digest
    content_hash: Digest

    @model_validator(mode="after")
    def validate_receipt(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        for name in (
            "evidence_ids",
            "fact_ids",
            "finding_ids",
            "recommendation_ids",
            "model_versions",
        ):
            values = getattr(self, name)
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")
        if self.model_versions:
            raise ValueError("deterministic receipt must not claim model versions")
        if self.rule_versions != REQUIRED_RULE_VERSIONS:
            raise ValueError("rule_versions must match recommendation policy v1")
        components = [item.component for item in self.rule_versions]
        if len(set(components)) != len(components):
            raise ValueError("rule_versions must not contain duplicate components")
        binding_ids = tuple(
            binding.recommendation_id for binding in self.recommendation_bindings
        )
        if binding_ids != self.recommendation_ids:
            raise ValueError("receipt bindings must match recommendation_ids in order")
        binding_band_ids = tuple(
            binding.band_id for binding in self.recommendation_bindings
        )
        if len(set(binding_band_ids)) != len(binding_band_ids):
            raise ValueError("receipt bindings must not reuse an allocation band")

        expected_receipt_id = _receipt_id(
            self.owner_id,
            self.profile_id,
            self.decision_gate_id,
            self.recommendation_ids,
        )
        if self.receipt_id != expected_receipt_id:
            raise ValueError("receipt_id does not match decision identities")

        sensitive_values = (
            self.receipt_id,
            self.owner_id,
            self.profile_id,
            self.portfolio_bundle_id,
            self.position_snapshot_id,
            self.exposure_report_id,
            self.concentration_report_id,
            self.risk_assessment_id,
            self.allocation_request_id,
            self.allocation_envelope_id,
            self.research_run_id,
            self.candidate_id,
            self.risk_gate_id,
            self.compliance_gate_id,
            self.decision_gate_id,
            *self.evidence_ids,
            *self.fact_ids,
            *self.finding_ids,
            *self.recommendation_ids,
        )
        _reject_sensitive(sensitive_values, "decision receipt")

        payload = self.model_dump(mode="json", exclude={"content_hash"})
        if self.content_hash != canonical_payload_signature(payload):
            raise ValueError("content_hash does not match receipt content")
        return self


class RecommendationCompositionResult(ContractModel):
    """Final deterministic decision output or an explicit safe refusal."""

    schema_version: Literal["recommendation-composition-result.v1"] = (
        "recommendation-composition-result.v1"
    )
    composition_id: NonEmptyStr
    owner_id: NonEmptyStr
    status: GateStatus
    decision_gate: DecisionGateResult | None = None
    summary: NonEmptyStr | None = None
    disclosures: tuple[DisclosureCode, ...] = Field(default_factory=tuple)
    trace: DecisionTrace = Field(default_factory=DecisionTrace)
    receipt: DecisionReceipt | None = None
    issues: tuple[RecommendationIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("recommendation issues must not contain duplicate codes")
        if self.decision_gate is not None and self.decision_gate.owner_id != self.owner_id:
            raise ValueError("decision gate owner does not match result owner")
        _reject_sensitive((self.composition_id, self.owner_id), "composition result")

        if self.status == GateStatus.PASS:
            if self.decision_gate is None:
                raise ValueError("PASS composition requires a decision gate")
            if self.decision_gate.status != GateStatus.PASS:
                raise ValueError("PASS composition requires a PASS decision gate")
            if not self.decision_gate.eligible_for_recommendation:
                raise ValueError("PASS composition requires recommendation eligibility")
            if self.summary is None or self.disclosures != REQUIRED_DISCLOSURES:
                raise ValueError("PASS composition requires summary and disclosures")
            if not self.trace.recommendations or self.receipt is None or self.issues:
                raise ValueError(
                    "PASS composition requires recommendations, receipt, and no issues"
                )
            if self.receipt.owner_id != self.owner_id:
                raise ValueError("receipt owner does not match composition owner")
            if self.receipt.profile_id != self.decision_gate.profile_id:
                raise ValueError("receipt profile does not match decision gate")
            if (
                self.receipt.candidate_id
                != self.decision_gate.compliance_gate.candidate_id
            ):
                raise ValueError("receipt candidate does not match compliance gate")
            if self.receipt.research_run_id != self.decision_gate.research_run_id:
                raise ValueError("receipt research run does not match decision gate")
            if (
                self.receipt.risk_assessment_id
                != self.decision_gate.risk_gate.risk_assessment_id
            ):
                raise ValueError("receipt risk assessment does not match risk gate")
            if (
                self.receipt.allocation_request_id
                != self.decision_gate.risk_gate.allocation_request_id
            ):
                raise ValueError("receipt allocation request does not match risk gate")
            if self.receipt.decision_gate_id != self.decision_gate.gate_id:
                raise ValueError("receipt decision gate does not match composition")
            if self.receipt.risk_gate_id != self.decision_gate.risk_gate.gate_id:
                raise ValueError("receipt risk gate does not match composition")
            if (
                self.receipt.compliance_gate_id
                != self.decision_gate.compliance_gate.gate_id
            ):
                raise ValueError("receipt compliance gate does not match composition")
            if self.receipt.decision_trace_hash != canonical_model_signature(self.trace):
                raise ValueError("receipt decision_trace_hash does not match trace")
            if self.receipt.evidence_ids != tuple(
                sorted(item.evidence_id for item in self.trace.evidence)
            ):
                raise ValueError("receipt evidence IDs do not match trace")
            if self.receipt.evidence_ids != tuple(
                sorted(self.decision_gate.risk_gate.checked_evidence_ids)
            ):
                raise ValueError("receipt evidence IDs do not match risk gate")
            if self.receipt.fact_ids != tuple(
                sorted(item.fact_id for item in self.trace.facts)
            ):
                raise ValueError("receipt fact IDs do not match trace")
            if self.receipt.fact_ids != tuple(
                sorted(self.decision_gate.risk_gate.checked_fact_ids)
            ):
                raise ValueError("receipt fact IDs do not match risk gate")
            if self.receipt.finding_ids != tuple(
                sorted(item.finding_id for item in self.trace.findings)
            ):
                raise ValueError("receipt finding IDs do not match trace")
            if self.receipt.finding_ids != tuple(
                sorted(self.decision_gate.risk_gate.checked_finding_ids)
            ):
                raise ValueError("receipt finding IDs do not match risk gate")
            recommendation_ids = tuple(
                item.recommendation_id for item in self.trace.recommendations
            )
            if recommendation_ids != self.receipt.recommendation_ids:
                raise ValueError("receipt recommendation IDs do not match trace")
            bindings_by_id = {
                item.recommendation_id: item
                for item in self.receipt.recommendation_bindings
            }
            for recommendation in self.trace.recommendations:
                binding = bindings_by_id[recommendation.recommendation_id]
                expected_id = recommendation_content_id(
                    profile_id=self.receipt.profile_id,
                    decision_gate_id=self.receipt.decision_gate_id,
                    candidate_id=self.receipt.candidate_id,
                    band_id=binding.band_id,
                    recommendation=recommendation,
                )
                if recommendation.recommendation_id != expected_id:
                    raise ValueError("recommendation_id does not match material content")
                if recommendation.asset_id != binding.target_id:
                    raise ValueError("recommendation asset does not match binding target")
                if (
                    recommendation.allocation_range.minimum_pct
                    != binding.target_min_weight_pct
                    or recommendation.allocation_range.maximum_pct
                    != binding.target_max_weight_pct
                ):
                    raise ValueError(
                        "recommendation allocation range does not match binding"
                    )
                if recommendation.action_type == ActionType.REDUCE and not binding.breach_ids:
                    raise ValueError("REDUCE recommendation requires breach binding")
                if (
                    recommendation.action_type == ActionType.REDUCE
                    and binding.dimension != AllocationBandDimension.ASSET
                ):
                    raise ValueError(
                        "REDUCE recommendation must bind an ASSET band"
                    )
                if recommendation.action_type == ActionType.HOLD and binding.breach_ids:
                    raise ValueError("HOLD recommendation must not bind breaches")
                if recommendation.action_type not in {ActionType.REDUCE, ActionType.HOLD}:
                    raise ValueError("composer v1 supports only REDUCE and HOLD")
                if (
                    recommendation.action_type == ActionType.REDUCE
                    and binding.current_weight_pct
                    <= recommendation.allocation_range.maximum_pct
                ):
                    raise ValueError("REDUCE recommendation must lower current weight")
                if (
                    recommendation.action_type == ActionType.HOLD
                    and binding.dimension != AllocationBandDimension.ASSET
                ):
                    raise ValueError("HOLD recommendation must bind an ASSET band")
                if (
                    self.decision_gate.risk_gate.remediation_required
                    and recommendation.action_type != ActionType.REDUCE
                ):
                    raise ValueError(
                        "remediation composition must contain only REDUCE recommendations"
                    )
                if (
                    not self.decision_gate.risk_gate.remediation_required
                    and recommendation.action_type != ActionType.HOLD
                ):
                    raise ValueError(
                        "non-remediation composition must contain only HOLD recommendations"
                    )
            bound_breaches = {
                breach_id
                for binding in self.receipt.recommendation_bindings
                for breach_id in binding.breach_ids
            }
            expected_breaches = set(
                self.decision_gate.risk_gate.remediation_breach_ids
            )
            if bound_breaches != expected_breaches:
                raise ValueError("receipt bindings do not close remediation breaches")
            if self.decision_gate.risk_gate.remediation_required != bool(
                bound_breaches
            ):
                raise ValueError("recommendation actions do not match remediation mode")
        else:
            if self.summary is not None or self.disclosures:
                raise ValueError("non-PASS composition must not expose candidate prose")
            if self.trace != DecisionTrace():
                raise ValueError("non-PASS composition must expose an empty trace")
            if self.receipt is not None:
                raise ValueError("non-PASS composition must not carry a receipt")
            if not self.issues:
                raise ValueError("non-PASS composition requires an issue")
        return self


def _receipt_id(
    owner_id: str,
    profile_id: str,
    decision_gate_id: str,
    recommendation_ids: tuple[str, ...],
) -> str:
    payload = "\x1f".join(
        (owner_id, profile_id, decision_gate_id, *sorted(recommendation_ids))
    ).encode("utf-8")
    return "receipt:" + sha256(payload).hexdigest()[:32]


__all__ = [
    "DecisionReceipt",
    "GenerationMode",
    "REQUIRED_RULE_VERSIONS",
    "RecommendationBinding",
    "RecommendationCompositionResult",
    "RecommendationIssue",
    "RecommendationIssueCode",
    "RuleVersion",
    "recommendation_content_id",
]
