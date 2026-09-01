"""Deterministic Recommendation composition from a dual-PASS decision gate."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from typing import TypeVar

from app.allocation.contracts import (
    AllocationBand,
    AllocationBandDimension,
    AllocationBandDisposition,
    AllocationResult,
)
from app.contracts.evidence import (
    ActionType,
    AllocationRange,
    ComplianceStatus,
    DecisionTrace,
    Recommendation,
)
from app.gates import (
    REQUIRED_DISCLOSURES,
    AdvisoryCandidate,
    DecisionGateResult,
    GateStatus,
    evaluate_decision_gates,
)
from app.gates.fingerprint import canonical_model_signature
from app.portfolio.contracts import PortfolioImportBundle
from app.portfolio.exposure import ExposureResult, ExposureStatus
from app.profile.contracts import RiskProfile
from app.research.pipeline import ResearchEvidencePipelineResult
from app.risk.contracts import (
    ConcentrationResult,
    ConcentrationStatus,
    RiskBudgetAssessment,
)

from app.recommendation.contracts import (
    RecommendationBinding,
    RecommendationCompositionResult,
    RecommendationIssue,
    RecommendationIssueCode,
    recommendation_content_id,
)
from app.recommendation.receipt import build_decision_receipt


_T = TypeVar("_T")
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


def _safe_text(value: object, fallback: str) -> str:
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if not value or _contains_sensitive(value):
        return fallback
    return value


def _revalidate(model: _T, expected_type: type[_T]) -> _T | None:
    if not isinstance(model, expected_type):
        return None
    try:
        return expected_type.model_validate(model.model_dump(mode="python"))
    except Exception:
        return None


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


def _issue(
    code: RecommendationIssueCode, message: str
) -> RecommendationIssue:
    return RecommendationIssue(code=code, safe_message=message)


def _blocked_result(
    *,
    composition_id: str,
    owner_id: str,
    code: RecommendationIssueCode,
    message: str,
    decision_gate: DecisionGateResult | None = None,
    status: GateStatus = GateStatus.BLOCKED,
) -> RecommendationCompositionResult:
    if decision_gate is not None and decision_gate.owner_id != owner_id:
        decision_gate = None
    return RecommendationCompositionResult(
        composition_id=composition_id,
        owner_id=owner_id,
        status=status,
        decision_gate=decision_gate,
        issues=(_issue(code, message),),
    )


def _invalidation_conditions(
    candidate: AdvisoryCandidate, allocation: AllocationResult
) -> tuple[str, ...]:
    if allocation.envelope is None:
        return ()
    return tuple(
        sorted(
            set(candidate.invalidation_conditions)
            | set(allocation.envelope.invalidation_conditions)
        )
    )


def _actionable_bands(
    allocation: AllocationResult,
    decision_gate: DecisionGateResult,
) -> tuple[AllocationBand, ...]:
    if allocation.envelope is None:
        return ()
    risk_gate = decision_gate.risk_gate
    if risk_gate.remediation_required:
        remediation_ids = set(risk_gate.remediation_breach_ids)
        return tuple(
            sorted(
                (
                    band
                    for band in allocation.envelope.bands
                    if band.dimension == AllocationBandDimension.ASSET
                    and set(band.breach_ids) & remediation_ids
                ),
                key=lambda item: item.band_id,
            )
        )
    return tuple(
        sorted(
            (
                band
                for band in allocation.envelope.bands
                if band.dimension == AllocationBandDimension.ASSET
            ),
            key=lambda item: item.band_id,
        )
    )


def _build_recommendation(
    *,
    profile: RiskProfile,
    candidate: AdvisoryCandidate,
    decision_gate: DecisionGateResult,
    band: AllocationBand,
    invalidation_conditions: tuple[str, ...],
) -> tuple[Recommendation, RecommendationBinding]:
    remediation = decision_gate.risk_gate.remediation_required
    action_type = ActionType.REDUCE if remediation else ActionType.HOLD
    allocation_range = (
        AllocationRange(
            minimum_pct=band.target_min_weight_pct,
            maximum_pct=band.target_max_weight_pct,
        )
        if remediation
        else AllocationRange(
            minimum_pct=band.current_weight_pct,
            maximum_pct=band.current_weight_pct,
        )
    )
    placeholder = Recommendation(
        recommendation_id="recommendation:pending",
        action_type=action_type,
        asset_id=band.target_id,
        allocation_range=allocation_range,
        rationale=candidate.rationale,
        finding_ids=tuple(sorted(candidate.finding_ids)),
        compliance_status=ComplianceStatus.PASSED,
        invalidation_conditions=invalidation_conditions,
    )
    recommendation_id = recommendation_content_id(
        profile_id=profile.profile_id,
        decision_gate_id=decision_gate.gate_id,
        candidate_id=candidate.candidate_id,
        band_id=band.band_id,
        recommendation=placeholder,
    )
    recommendation = placeholder.model_copy(
        update={"recommendation_id": recommendation_id}
    )
    binding = RecommendationBinding(
        recommendation_id=recommendation_id,
        band_id=band.band_id,
        dimension=band.dimension,
        target_id=band.target_id,
        current_weight_pct=band.current_weight_pct,
        allowed_max_weight_pct=band.allowed_max_weight_pct,
        target_min_weight_pct=allocation_range.minimum_pct,
        target_max_weight_pct=allocation_range.maximum_pct,
        breach_ids=tuple(sorted(band.breach_ids)),
    )
    return recommendation, binding


def compose_recommendations(
    *,
    profile: RiskProfile,
    portfolio: PortfolioImportBundle,
    exposure: ExposureResult,
    concentration: ConcentrationResult,
    assessment: RiskBudgetAssessment,
    allocation: AllocationResult,
    pipeline: ResearchEvidencePipelineResult,
    candidate: AdvisoryCandidate,
    decision_gate: DecisionGateResult,
    generated_at: datetime,
) -> RecommendationCompositionResult:
    """Compose HOLD/REDUCE only after exact, independently re-run gate closure."""

    signatures = tuple(
        canonical_model_signature(item)
        for item in (
            profile,
            portfolio,
            exposure,
            concentration,
            assessment,
            allocation,
            pipeline,
            candidate,
            decision_gate,
        )
    ) + (str(generated_at),)
    composition_id = _stable_id("composition", *signatures)
    owner_id = _safe_text(getattr(profile, "owner_id", None), "unknown-owner")

    normalized = (
        _revalidate(profile, RiskProfile),
        _revalidate(portfolio, PortfolioImportBundle),
        _revalidate(exposure, ExposureResult),
        _revalidate(concentration, ConcentrationResult),
        _revalidate(assessment, RiskBudgetAssessment),
        _revalidate(allocation, AllocationResult),
        _revalidate(pipeline, ResearchEvidencePipelineResult),
        _revalidate(candidate, AdvisoryCandidate),
        _revalidate(decision_gate, DecisionGateResult),
    )
    if any(item is None for item in normalized):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.INVALID_INPUT,
            message="recommendation input failed contract validation",
        )

    (
        profile,
        portfolio,
        exposure,
        concentration,
        assessment,
        allocation,
        pipeline,
        candidate,
        decision_gate,
    ) = normalized
    owner_id = _safe_text(profile.owner_id, "unknown-owner")
    if _contains_sensitive(profile.owner_id):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.SENSITIVE_INPUT,
            message="recommendation identity contains a sensitive field",
        )

    owner_values = (
        portfolio.owner_id,
        exposure.owner_id,
        concentration.owner_id,
        assessment.owner_id,
        allocation.owner_id,
        pipeline.owner_id,
        candidate.owner_id,
        decision_gate.owner_id,
    )
    if any(value != profile.owner_id for value in owner_values):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.OWNER_MISMATCH,
            message="recommendation inputs do not share one owner",
            decision_gate=decision_gate,
        )
    if (
        assessment.profile_id != profile.profile_id
        or allocation.profile_id != profile.profile_id
        or decision_gate.profile_id != profile.profile_id
        or assessment.budget.profile_version != profile.profile_version
        or assessment.budget.risk_level != profile.risk_level
    ):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.PROFILE_MISMATCH,
            message="recommendation inputs do not share one profile version",
            decision_gate=decision_gate,
        )

    if (
        exposure.bundle_id != portfolio.bundle_id
        or exposure.status == ExposureStatus.FAILED
        or exposure.report is None
        or exposure.report.bundle_id != portfolio.bundle_id
    ):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.PORTFOLIO_MISMATCH,
            message="portfolio and exposure inputs do not close one snapshot",
            decision_gate=decision_gate,
        )
    if (
        concentration.status == ConcentrationStatus.FAILED
        or concentration.report is None
        or concentration.bundle_id != portfolio.bundle_id
        or concentration.report.exposure_report_id != exposure.report.report_id
        or assessment.exposure_report_id != exposure.report.report_id
        or assessment.concentration_report_id != concentration.report.report_id
    ):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.RISK_CLOSURE_MISMATCH,
            message="risk assessment does not close the portfolio reports",
            decision_gate=decision_gate,
        )
    envelope = allocation.envelope
    if (
        envelope is None
        or envelope.exposure_report_id != exposure.report.report_id
        or envelope.concentration_report_id != concentration.report.report_id
        or envelope.assessment_id != assessment.assessment_id
        or envelope.profile_version != profile.profile_version
    ):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.ALLOCATION_MISMATCH,
            message="allocation envelope does not close the risk assessment",
            decision_gate=decision_gate,
        )

    recomputed_gate = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )
    if recomputed_gate != decision_gate:
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.STALE_GATE,
            message="decision gate does not match the current inputs",
            decision_gate=decision_gate,
        )
    if decision_gate.status != GateStatus.PASS:
        status = decision_gate.status
        code = (
            RecommendationIssueCode.GATE_BLOCKED
            if status == GateStatus.BLOCKED
            else RecommendationIssueCode.GATE_REVIEW_REQUIRED
        )
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=code,
            message=(
                "decision gate is blocked"
                if status == GateStatus.BLOCKED
                else "decision gate requires human review"
            ),
            decision_gate=decision_gate,
            status=status,
        )
    if (
        exposure.status != ExposureStatus.COMPLETE
        or concentration.status != ConcentrationStatus.COMPLETE
    ):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.RISK_CLOSURE_MISMATCH,
            message="PASS recommendation requires complete portfolio risk inputs",
            decision_gate=decision_gate,
        )
    if (
        not isinstance(generated_at, datetime)
        or generated_at.tzinfo is None
        or generated_at.utcoffset() is None
    ):
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.INVALID_INPUT,
            message="recommendation generated_at must be timezone-aware",
            decision_gate=decision_gate,
        )

    if decision_gate.risk_gate.remediation_required:
        expected_breaches = set(decision_gate.risk_gate.remediation_breach_ids)
        all_bands_by_breach = {
            breach_id: band
            for band in envelope.bands
            for breach_id in band.breach_ids
        }
        non_asset_breaches = {
            breach_id
            for breach_id in expected_breaches
            if all_bands_by_breach.get(breach_id) is not None
            and all_bands_by_breach[breach_id].dimension
            != AllocationBandDimension.ASSET
        }
        if non_asset_breaches:
            return _blocked_result(
                composition_id=composition_id,
                owner_id=owner_id,
                code=RecommendationIssueCode.AGGREGATE_BREACH_UNMAPPED,
                message="aggregate risk breach has no executable asset mapping",
                decision_gate=decision_gate,
            )
    bands = _actionable_bands(allocation, decision_gate)
    if not bands:
        return _blocked_result(
            composition_id=composition_id,
            owner_id=owner_id,
            code=RecommendationIssueCode.NO_ACTIONABLE_BANDS,
            message="allocation envelope has no deterministic actionable bands",
            decision_gate=decision_gate,
        )
    if decision_gate.risk_gate.remediation_required:
        actual_breaches = {
            breach_id for band in bands for breach_id in band.breach_ids
        }
        if (
            actual_breaches != expected_breaches
            or any(
                band.disposition != AllocationBandDisposition.OVER_LIMIT
                for band in bands
            )
        ):
            return _blocked_result(
                composition_id=composition_id,
                owner_id=owner_id,
                code=RecommendationIssueCode.BREACH_COVERAGE_MISMATCH,
                message="actionable bands do not close remediation breaches",
                decision_gate=decision_gate,
            )

    invalidation_conditions = _invalidation_conditions(candidate, allocation)
    recommendations: list[Recommendation] = []
    bindings: list[RecommendationBinding] = []
    for band in bands:
        recommendation, binding = _build_recommendation(
            profile=profile,
            candidate=candidate,
            decision_gate=decision_gate,
            band=band,
            invalidation_conditions=invalidation_conditions,
        )
        recommendations.append(recommendation)
        bindings.append(binding)
    pairs = sorted(
        zip(recommendations, bindings), key=lambda pair: pair[0].recommendation_id
    )
    recommendation_tuple = tuple(pair[0] for pair in pairs)
    binding_tuple = tuple(pair[1] for pair in pairs)

    trace = DecisionTrace(
        evidence=tuple(sorted(pipeline.trace.evidence, key=lambda item: item.evidence_id)),
        facts=tuple(sorted(pipeline.trace.facts, key=lambda item: item.fact_id)),
        findings=tuple(sorted(pipeline.trace.findings, key=lambda item: item.finding_id)),
        recommendations=recommendation_tuple,
    )
    receipt = build_decision_receipt(
        profile=profile,
        portfolio=portfolio,
        exposure=exposure,
        concentration=concentration,
        assessment=assessment,
        allocation=allocation,
        pipeline=pipeline,
        candidate=candidate,
        decision_gate=decision_gate,
        trace=trace,
        bindings=binding_tuple,
        generated_at=generated_at,
    )
    return RecommendationCompositionResult(
        composition_id=composition_id,
        owner_id=owner_id,
        status=GateStatus.PASS,
        decision_gate=decision_gate,
        summary=candidate.statement,
        disclosures=REQUIRED_DISCLOSURES,
        trace=trace,
        receipt=receipt,
    )


compose_recommendation_receipt = compose_recommendations


__all__ = ["compose_recommendation_receipt", "compose_recommendations"]
