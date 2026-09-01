"""Pure risk eligibility evaluation over already-computed domain results."""

from __future__ import annotations

from hashlib import sha256
from typing import TypeVar

from app.allocation.contracts import (
    AllocationBandDisposition,
    AllocationBandDimension,
    AllocationResult,
    AllocationStatus,
)
from app.contracts.evidence import EvidenceQualityStatus, FactStatus
from app.profile.contracts import RiskProfile
from app.research.pipeline import (
    ResearchEvidencePipelineResult,
    ResearchPipelineStatus,
)
from app.risk.contracts import (
    BudgetAssessmentStatus,
    BudgetBreachKind,
    RiskBudgetAssessment,
    RiskBudgetBreach,
)

from app.gates.contracts import (
    GateStatus,
    RiskGateIssue,
    RiskGateIssueCode,
    RiskGateResult,
)
from app.gates.fingerprint import canonical_model_signature


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


def _revalidate(model: _T) -> _T | None:
    """Rebuild from a mapping so ``model_copy(update=...)`` cannot bypass rules."""

    try:
        model_type = type(model)
        return model_type.model_validate(model.model_dump(mode="python"))
    except Exception:
        return None


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "risk-gate:" + sha256(payload).hexdigest()[:32]


def _issue(code: RiskGateIssueCode, message: str) -> RiskGateIssue:
    return RiskGateIssue(code=code, safe_message=message)


def evaluate_risk_gate(
    profile: RiskProfile,
    pipeline: ResearchEvidencePipelineResult,
    assessment: RiskBudgetAssessment,
    allocation: AllocationResult,
) -> RiskGateResult:
    """Return risk eligibility without producing an action or recommendation."""

    owner_id = _safe_text(getattr(profile, "owner_id", None), "unknown-owner")
    profile_id = _safe_text(getattr(profile, "profile_id", None), "unknown-profile")
    run_id = _safe_text(getattr(pipeline, "run_id", None), "unknown-run")
    assessment_id = _safe_text(
        getattr(assessment, "assessment_id", None), "unknown-assessment"
    )
    allocation_id = _safe_text(
        getattr(allocation, "request_id", None), "unknown-allocation"
    )
    input_signatures = (
        canonical_model_signature(profile),
        canonical_model_signature(pipeline),
        canonical_model_signature(assessment),
        canonical_model_signature(allocation),
    )

    normalized_profile = _revalidate(profile)
    normalized_pipeline = _revalidate(pipeline)
    normalized_assessment = _revalidate(assessment)
    normalized_allocation = _revalidate(allocation)
    if not (
        isinstance(normalized_profile, RiskProfile)
        and isinstance(normalized_pipeline, ResearchEvidencePipelineResult)
        and isinstance(normalized_assessment, RiskBudgetAssessment)
        and isinstance(normalized_allocation, AllocationResult)
    ):
        return RiskGateResult(
            gate_id=_stable_id(*input_signatures),
            owner_id=owner_id,
            profile_id=profile_id,
            research_run_id=run_id,
            risk_assessment_id=assessment_id,
            allocation_request_id=allocation_id,
            status=GateStatus.BLOCKED,
            issues=(
                _issue(
                    RiskGateIssueCode.INVALID_INPUT,
                    "gate input failed contract validation",
                ),
            ),
        )

    profile = normalized_profile
    pipeline = normalized_pipeline
    assessment = normalized_assessment
    allocation = normalized_allocation
    actual_owner_id = profile.owner_id
    actual_profile_id = profile.profile_id
    owner_id = _safe_text(actual_owner_id, "unknown-owner")
    profile_id = _safe_text(actual_profile_id, "unknown-profile")
    run_id = _safe_text(pipeline.run_id, "unknown-run")
    assessment_id = _safe_text(assessment.assessment_id, "unknown-assessment")
    allocation_id = _safe_text(allocation.request_id, "unknown-allocation")

    issues: list[RiskGateIssue] = []
    blocked = False
    review = False

    def add(code: RiskGateIssueCode, message: str, *, is_blocked: bool = False) -> None:
        nonlocal blocked, review
        if not any(item.code == code for item in issues):
            issues.append(_issue(code, message))
        if is_blocked:
            blocked = True
        else:
            review = True

    identity_values = (
        actual_owner_id,
        actual_profile_id,
        pipeline.run_id,
        assessment.assessment_id,
        allocation.request_id,
        assessment.budget.budget_id,
    )
    if any(_contains_sensitive(value) for value in identity_values):
        add(
            RiskGateIssueCode.INVALID_INPUT,
            "gate identity contains a disallowed sensitive field",
            is_blocked=True,
        )

    if any(
        value != actual_owner_id
        for value in (
            pipeline.owner_id,
            assessment.owner_id,
            allocation.owner_id,
        )
    ):
        add(
            RiskGateIssueCode.OWNER_MISMATCH,
            "risk inputs do not share one owner",
            is_blocked=True,
        )

    if any(
        value != actual_profile_id
        for value in (assessment.profile_id, allocation.profile_id)
    ):
        add(
            RiskGateIssueCode.PROFILE_MISMATCH,
            "risk inputs do not share one profile",
            is_blocked=True,
        )

    budget = assessment.budget
    if (
        budget.owner_id != actual_owner_id
        or budget.profile_id != actual_profile_id
        or budget.profile_version != profile.profile_version
        or budget.risk_level != profile.risk_level
        or budget.max_drawdown_tolerance_pct
        != profile.max_drawdown_tolerance_pct
    ):
        add(
            RiskGateIssueCode.PROFILE_MISMATCH,
            "risk budget is not bound to the active profile",
            is_blocked=True,
        )

    envelope = allocation.envelope
    if envelope is not None:
        if (
            envelope.owner_id != actual_owner_id
            or envelope.profile_id != actual_profile_id
            or envelope.profile_version != profile.profile_version
            or envelope.risk_level != profile.risk_level
            or envelope.budget_id != budget.budget_id
            or envelope.assessment_id != assessment.assessment_id
            or envelope.concentration_report_id != assessment.concentration_report_id
            or envelope.exposure_report_id != assessment.exposure_report_id
            or envelope.calculated_at != assessment.assessed_at
            or allocation.calculated_at != assessment.assessed_at
        ):
            add(
                RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
                "allocation envelope is not bound to the risk assessment",
                is_blocked=True,
            )

        expected_limits = {
            AllocationBandDimension.ASSET: budget.max_single_asset_weight_pct,
            AllocationBandDimension.SECTOR: budget.max_sector_weight_pct,
            AllocationBandDimension.TECHNOLOGY: budget.max_technology_weight_pct,
            AllocationBandDimension.UNCLASSIFIED: budget.max_unclassified_weight_pct,
        }
        band_keys = [(band.dimension, band.target_id) for band in envelope.bands]
        required_portfolio_bands = {
            (AllocationBandDimension.TECHNOLOGY, "TECHNOLOGY"),
            (AllocationBandDimension.UNCLASSIFIED, "UNCLASSIFIED"),
        }
        if (
            len(set(band_keys)) != len(band_keys)
            or not required_portfolio_bands.issubset(set(band_keys))
            or any(
                band.allowed_max_weight_pct != expected_limits[band.dimension]
                for band in envelope.bands
            )
        ):
            add(
                RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
                "allocation constraints do not match the active risk budget",
                is_blocked=True,
            )

        assessment_breach_ids = {item.breach_id for item in assessment.breaches}
        envelope_breach_ids = {
            breach_id for band in envelope.bands for breach_id in band.breach_ids
        }
        if assessment_breach_ids != envelope_breach_ids:
            add(
                RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
                "allocation breach references do not match the risk assessment",
                is_blocked=True,
            )

        breach_dimensions = {
            BudgetBreachKind.SINGLE_ASSET: AllocationBandDimension.ASSET,
            BudgetBreachKind.SECTOR: AllocationBandDimension.SECTOR,
            BudgetBreachKind.TECHNOLOGY: AllocationBandDimension.TECHNOLOGY,
            BudgetBreachKind.UNCLASSIFIED: AllocationBandDimension.UNCLASSIFIED,
        }
        breaches_by_band: dict[
            tuple[AllocationBandDimension, str], RiskBudgetBreach
        ] = {}
        for breach in assessment.breaches:
            dimension = breach_dimensions[breach.kind]
            target_id = (
                breach.target_id
                if breach.target_id is not None
                else breach.kind.value
            )
            key = (dimension, target_id)
            if key in breaches_by_band:
                add(
                    RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
                    "risk assessment contains duplicate constraint breaches",
                    is_blocked=True,
                )
            breaches_by_band[key] = breach

        for band in envelope.bands:
            breach = breaches_by_band.get((band.dimension, band.target_id))
            expected_ids = (breach.breach_id,) if breach is not None else ()
            if band.breach_ids != expected_ids:
                add(
                    RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
                    "allocation breach is attached to the wrong constraint",
                    is_blocked=True,
                )
                continue
            if breach is not None and (
                band.disposition != AllocationBandDisposition.OVER_LIMIT
                or band.current_weight_pct != breach.observed_weight_pct
                or band.allowed_max_weight_pct != breach.limit_weight_pct
                or band.minimum_reduction_pct != breach.excess_weight_pct
            ):
                add(
                    RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
                    "allocation reduction does not match its risk breach",
                    is_blocked=True,
                )

    expected_allocation_status = {
        BudgetAssessmentStatus.PASS: AllocationStatus.READY,
        BudgetAssessmentStatus.REVIEW_REQUIRED: AllocationStatus.REVIEW_REQUIRED,
        BudgetAssessmentStatus.BLOCKED: AllocationStatus.BLOCKED,
    }[assessment.status]
    if allocation.status != expected_allocation_status:
        add(
            RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
            "allocation status does not match the risk assessment",
            is_blocked=True,
        )

    remediation_ready = (
        assessment.status == BudgetAssessmentStatus.REVIEW_REQUIRED
        and bool(assessment.breaches)
        and not assessment.issues
        and allocation.status == AllocationStatus.REVIEW_REQUIRED
        and envelope is not None
        and any(
            band.disposition == AllocationBandDisposition.OVER_LIMIT
            for band in envelope.bands
        )
        and all(
            band.disposition != AllocationBandDisposition.UNRESOLVED
            for band in envelope.bands
        )
    )

    if pipeline.status == ResearchPipelineStatus.BLOCKED:
        add(
            RiskGateIssueCode.PIPELINE_BLOCKED,
            "research evidence pipeline is blocked",
            is_blocked=True,
        )
    elif pipeline.status == ResearchPipelineStatus.REVIEW_REQUIRED:
        add(
            RiskGateIssueCode.PIPELINE_REVIEW_REQUIRED,
            "research evidence requires human review",
        )
    else:
        trace = pipeline.trace
        evidence_by_id = {item.evidence_id: item for item in trace.evidence}
        fact_by_id = {item.fact_id: item for item in trace.facts}
        finding_by_id = {item.finding_id: item for item in trace.findings}
        if not trace.evidence or not trace.facts or not trace.findings:
            add(
                RiskGateIssueCode.TRACE_INTEGRITY,
                "ready research trace is incomplete",
                is_blocked=True,
            )
        if any(
            evidence.quality_status != EvidenceQualityStatus.VERIFIED
            for evidence in trace.evidence
        ):
            add(
                RiskGateIssueCode.NON_VERIFIED_EVIDENCE,
                "research trace contains non-verified evidence",
                is_blocked=True,
            )
        for fact in trace.facts:
            if fact.status != FactStatus.VERIFIED:
                add(
                    RiskGateIssueCode.NON_VERIFIED_FACT,
                    "research trace contains a non-verified fact",
                    is_blocked=True,
                )
            for evidence_id in fact.evidence_ids:
                evidence = evidence_by_id.get(evidence_id)
                if evidence is None:
                    add(
                        RiskGateIssueCode.TRACE_INTEGRITY,
                        "research trace has an unknown evidence reference",
                        is_blocked=True,
                    )
                elif evidence.quality_status != EvidenceQualityStatus.VERIFIED:
                    add(
                        RiskGateIssueCode.NON_VERIFIED_EVIDENCE,
                        "research trace contains non-verified evidence",
                        is_blocked=True,
                    )
        for finding in trace.findings:
            if not finding.fact_ids or any(
                fact_id not in fact_by_id for fact_id in finding.fact_ids
            ):
                add(
                    RiskGateIssueCode.TRACE_INTEGRITY,
                    "research trace has an unknown fact reference",
                    is_blocked=True,
                )
        for bridge in pipeline.bridges:
            if bridge.fact is None or bridge.finding is None:
                add(
                    RiskGateIssueCode.TRACE_INTEGRITY,
                    "ready research bridge is incomplete",
                    is_blocked=True,
                )
                continue
            if (
                fact_by_id.get(bridge.fact.fact_id) != bridge.fact
                or finding_by_id.get(bridge.finding.finding_id) != bridge.finding
            ):
                add(
                    RiskGateIssueCode.TRACE_INTEGRITY,
                    "research bridge does not match the registered trace",
                    is_blocked=True,
                )
        if pipeline.trace.recommendations:
            add(
                RiskGateIssueCode.TRACE_INTEGRITY,
                "research trace must not contain recommendations",
                is_blocked=True,
            )
    if assessment.status == BudgetAssessmentStatus.BLOCKED:
        add(
            RiskGateIssueCode.RISK_BUDGET_BLOCKED,
            "risk budget assessment is blocked",
            is_blocked=True,
        )
    elif (
        assessment.status == BudgetAssessmentStatus.REVIEW_REQUIRED
        and not remediation_ready
    ):
        add(
            RiskGateIssueCode.RISK_BUDGET_REVIEW_REQUIRED,
            "risk budget assessment requires human review",
        )

    if allocation.status == AllocationStatus.BLOCKED:
        add(
            RiskGateIssueCode.ALLOCATION_BLOCKED,
            "allocation constraint envelope is blocked",
            is_blocked=True,
        )
    elif (
        allocation.status == AllocationStatus.REVIEW_REQUIRED
        and not remediation_ready
    ):
        add(
            RiskGateIssueCode.ALLOCATION_REVIEW_REQUIRED,
            "allocation constraint envelope requires human review",
        )
    elif allocation.envelope is None:
        add(
            RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH,
            "ready allocation has no envelope",
            is_blocked=True,
        )

    checked_evidence_ids = tuple(
        sorted(item.evidence_id for item in pipeline.trace.evidence)
    )
    checked_fact_ids = tuple(sorted(item.fact_id for item in pipeline.trace.facts))
    checked_finding_ids = tuple(sorted(item.finding_id for item in pipeline.trace.findings))
    status = (
        GateStatus.BLOCKED
        if blocked
        else GateStatus.REVIEW_REQUIRED
        if review
        else GateStatus.PASS
    )
    remediation_required = remediation_ready and status == GateStatus.PASS
    return RiskGateResult(
        gate_id=_stable_id(*input_signatures),
        owner_id=owner_id,
        profile_id=profile_id,
        research_run_id=run_id,
        risk_assessment_id=assessment_id,
        allocation_request_id=allocation_id,
        status=status,
        checked_evidence_ids=checked_evidence_ids,
        checked_fact_ids=checked_fact_ids,
        checked_finding_ids=checked_finding_ids,
        remediation_required=remediation_required,
        remediation_breach_ids=(
            tuple(sorted(item.breach_id for item in assessment.breaches))
            if remediation_required
            else ()
        ),
        issues=tuple(sorted(issues, key=lambda item: item.code.value)),
    )
