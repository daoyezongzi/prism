import json
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.allocation import AllocationStatus, build_allocation_envelope
from app.contracts import (
    DecisionTrace,
    Evidence,
    EvidenceQualityStatus,
    FindingSeverity,
)
from app.gates import (
    REQUIRED_DISCLOSURES,
    AdvisoryCandidate,
    ComplianceGateIssue,
    ComplianceGateIssueCode,
    ComplianceGateResult,
    GateStatus,
    RiskGateIssueCode,
    evaluate_compliance_gate,
    evaluate_decision_gates,
    evaluate_risk_gate,
)
from app.portfolio import (
    ExposureIssue,
    ExposureIssueCode,
    ExposureResult,
    ExposureStatus,
    PortfolioImportBundle,
    calculate_exposure,
)
from app.profile import RiskLevel, RiskProfile
from app.research import (
    EvidenceBridgeStatus,
    ResearchObservation,
    ValidationClaim,
    ValidationStatus,
    bridge_cross_validation,
    validate_claim,
)
from app.research.pipeline import (
    ResearchEvidencePipelineResult,
    ResearchPipelineIssue,
    ResearchPipelineIssueCode,
    ResearchPipelineStatus,
)
from app.risk import BudgetAssessmentStatus, assess_risk_budget, calculate_concentration


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "gates"
    / "risk_compliance_gate_case.json"
)


def _load_payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _build_pipeline(payload: dict, *, lineage_count: int = 2):
    evidence = tuple(
        Evidence.model_validate(item) for item in payload["evidence"][:lineage_count]
    )
    observations = tuple(
        ResearchObservation.model_validate(item)
        for item in payload["observations"][:lineage_count]
    )
    claim = ValidationClaim.model_validate(payload["claim"])
    validation = validate_claim(claim, observations)
    finding = payload["finding"]
    bridge = bridge_cross_validation(
        validation,
        evidence,
        observations,
        finding_kind=finding["kind"],
        finding_severity=FindingSeverity(finding["severity"]),
        statement=finding["statement"],
    )
    if bridge.status == EvidenceBridgeStatus.READY:
        trace = DecisionTrace(
            evidence=evidence,
            facts=(bridge.fact,),
            findings=(bridge.finding,),
        )
        status = ResearchPipelineStatus.READY
        issues = ()
    else:
        trace = DecisionTrace(evidence=evidence)
        status = ResearchPipelineStatus.REVIEW_REQUIRED
        issues = (
            ResearchPipelineIssue(
                code=ResearchPipelineIssueCode.CLAIM_REVIEW_REQUIRED,
                safe_message="research claim requires human review",
                claim_id=claim.claim_id,
            ),
        )
    pipeline = ResearchEvidencePipelineResult(
        run_id="gate-research-run-001",
        request_id="gate-research-request-001",
        owner_id=claim.owner_id,
        status=status,
        validations=(validation,),
        bridges=(bridge,),
        trace=trace,
        issues=issues,
    )
    return pipeline, claim, evidence, observations


def _build_case(*, level: RiskLevel = RiskLevel.BALANCED):
    payload = _load_payload()
    profile = RiskProfile.model_validate(payload["profile"])
    if level != RiskLevel.BALANCED:
        score = {
            RiskLevel.CONSERVATIVE: "25",
            RiskLevel.GROWTH: "75",
        }[level]
        profile = RiskProfile.model_validate(
            {
                **profile.model_dump(mode="python"),
                "profile_id": f"gate-profile-{level.value.lower()}-001",
                "risk_score": score,
                "risk_level": level,
            }
        )
    bundle = PortfolioImportBundle.model_validate(payload["portfolio"])
    exposure = calculate_exposure(bundle)
    concentration = calculate_concentration(exposure)
    assessment = assess_risk_budget(profile, concentration)
    allocation = build_allocation_envelope(
        profile, exposure, concentration, assessment
    )
    pipeline, claim, evidence, observations = _build_pipeline(payload)
    candidate = AdvisoryCandidate.model_validate(
        {
            **payload["candidate"],
            "finding_ids": (pipeline.trace.findings[0].finding_id,),
        }
    )
    return (
        payload,
        profile,
        bundle,
        exposure,
        concentration,
        assessment,
        allocation,
        pipeline,
        candidate,
        claim,
        evidence,
        observations,
    )


def test_complete_case_passes_both_gates_without_recommendation() -> None:
    payload, profile, _, _, _, assessment, allocation, pipeline, candidate, *_ = (
        _build_case()
    )
    result = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )

    assert assessment.status == BudgetAssessmentStatus.PASS
    assert allocation.status == AllocationStatus.READY
    assert result.risk_gate.status == GateStatus.PASS
    assert result.compliance_gate.status == GateStatus.PASS
    assert result.status == GateStatus.PASS
    assert result.eligible_for_recommendation is True
    assert pipeline.trace.recommendations == ()
    serialized = result.model_dump_json().casefold()
    for field in payload["expected"]["forbidden_output_fields"]:
        assert f'"{field.casefold()}"' not in serialized
    assert candidate.statement not in serialized
    assert candidate.rationale not in serialized


def test_closed_breaches_allow_only_explicit_remediation_eligibility() -> None:
    (
        _,
        profile,
        _,
        _,
        _,
        assessment,
        allocation,
        pipeline,
        candidate,
        *_,
    ) = _build_case(level=RiskLevel.CONSERVATIVE)
    remediation = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )
    assert assessment.status == BudgetAssessmentStatus.REVIEW_REQUIRED
    assert allocation.status == AllocationStatus.REVIEW_REQUIRED
    assert remediation.risk_gate.status == GateStatus.PASS
    assert remediation.risk_gate.remediation_required is True
    assert set(remediation.risk_gate.remediation_breach_ids) == {
        breach.breach_id for breach in assessment.breaches
    }
    assert remediation.status == GateStatus.PASS
    assert remediation.eligible_for_recommendation is True


def test_partial_risk_inputs_require_review_and_blocked_states_propagate() -> None:
    (
        _,
        profile,
        bundle,
        _,
        _,
        _,
        _,
        pipeline,
        candidate,
        *_,
    ) = _build_case()
    fund_snapshot = bundle.fund_holdings[0].model_copy(
        update={"coverage_pct": Decimal("80")}
    )
    partial_bundle = bundle.model_copy(update={"fund_holdings": (fund_snapshot,)})
    partial_exposure = calculate_exposure(partial_bundle)
    partial_concentration = calculate_concentration(partial_exposure)
    partial_assessment = assess_risk_budget(profile, partial_concentration)
    partial_allocation = build_allocation_envelope(
        profile,
        partial_exposure,
        partial_concentration,
        partial_assessment,
    )
    review = evaluate_decision_gates(
        profile, pipeline, partial_assessment, partial_allocation, candidate
    )
    assert partial_exposure.status == ExposureStatus.PARTIAL
    assert review.risk_gate.status == GateStatus.REVIEW_REQUIRED
    assert review.risk_gate.remediation_required is False
    assert review.status == GateStatus.REVIEW_REQUIRED
    assert review.eligible_for_recommendation is False

    failed_exposure = ExposureResult(
        request_id="gate-failed-exposure",
        owner_id=profile.owner_id,
        bundle_id="gate-failed-bundle",
        status=ExposureStatus.FAILED,
        calculated_at=partial_assessment.assessed_at,
        issues=(
            ExposureIssue(
                code=ExposureIssueCode.ZERO_PORTFOLIO_VALUE,
                safe_message="portfolio value is unavailable",
            ),
        ),
    )
    failed_concentration = calculate_concentration(failed_exposure)
    blocked_assessment = assess_risk_budget(profile, failed_concentration)
    blocked_allocation = build_allocation_envelope(
        profile, failed_exposure, failed_concentration, blocked_assessment
    )
    blocked = evaluate_decision_gates(
        profile, pipeline, blocked_assessment, blocked_allocation, candidate
    )
    assert blocked.risk_gate.status == GateStatus.BLOCKED
    assert blocked.status == GateStatus.BLOCKED
    assert blocked.eligible_for_recommendation is False


def test_research_review_and_blocked_states_cannot_pass() -> None:
    payload, profile, _, _, _, assessment, allocation, _, candidate, *_ = _build_case()
    review_pipeline, *_ = _build_pipeline(payload, lineage_count=1)
    assert review_pipeline.validations[0].status == ValidationStatus.INSUFFICIENT
    review_candidate = candidate.model_copy(
        update={"finding_ids": ("review-finding-placeholder",)}
    )
    review = evaluate_decision_gates(
        profile, review_pipeline, assessment, allocation, review_candidate
    )
    assert review.risk_gate.status == GateStatus.REVIEW_REQUIRED
    assert review.compliance_gate.status == GateStatus.REVIEW_REQUIRED
    assert review.status == GateStatus.REVIEW_REQUIRED

    blocked_pipeline = ResearchEvidencePipelineResult(
        run_id="gate-blocked-run",
        request_id="gate-blocked-request",
        owner_id=profile.owner_id,
        status=ResearchPipelineStatus.BLOCKED,
        trace=DecisionTrace(),
        issues=(
            ResearchPipelineIssue(
                code=ResearchPipelineIssueCode.EMPTY_CLAIMS,
                safe_message="claim set is empty",
            ),
        ),
    )
    blocked = evaluate_decision_gates(
        profile, blocked_pipeline, assessment, allocation, review_candidate
    )
    assert blocked.risk_gate.status == GateStatus.BLOCKED
    assert blocked.compliance_gate.status == GateStatus.BLOCKED
    assert blocked.status == GateStatus.BLOCKED


def test_owner_mismatch_and_allocation_budget_tampering_are_blocked() -> None:
    _, profile, _, _, _, assessment, allocation, pipeline, candidate, *_ = _build_case()
    foreign_pipeline = pipeline.model_copy(update={"owner_id": "foreign-owner"})
    owner_result = evaluate_decision_gates(
        profile, foreign_pipeline, assessment, allocation, candidate
    )
    assert owner_result.status == GateStatus.BLOCKED
    assert owner_result.risk_gate.issues[0].code == RiskGateIssueCode.INVALID_INPUT

    assert allocation.envelope is not None
    first_band = allocation.envelope.bands[0]
    tampered_band = first_band.model_copy(
        update={"allowed_max_weight_pct": Decimal("99")}
    )
    tampered_envelope = allocation.envelope.model_copy(
        update={"bands": (tampered_band,) + allocation.envelope.bands[1:]}
    )
    tampered_allocation = allocation.model_copy(update={"envelope": tampered_envelope})
    risk = evaluate_risk_gate(profile, pipeline, assessment, tampered_allocation)
    assert risk.status == GateStatus.BLOCKED
    assert any(
        issue.code == RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH
        for issue in risk.issues
    )


def test_breach_values_and_profile_drawdown_must_close_allocation() -> None:
    (
        _,
        profile,
        _,
        _,
        _,
        assessment,
        allocation,
        pipeline,
        _,
        *_,
    ) = _build_case(level=RiskLevel.CONSERVATIVE)
    breach = assessment.breaches[0]
    observed = Decimal("99")
    tampered_breach = breach.model_copy(
        update={
            "observed_weight_pct": observed,
            "excess_weight_pct": observed - breach.limit_weight_pct,
        }
    )
    tampered_assessment = assessment.model_copy(
        update={"breaches": (tampered_breach,) + assessment.breaches[1:]}
    )
    mismatch = evaluate_risk_gate(
        profile, pipeline, tampered_assessment, allocation
    )
    assert mismatch.status == GateStatus.BLOCKED
    assert any(
        issue.code == RiskGateIssueCode.ALLOCATION_IDENTITY_MISMATCH
        for issue in mismatch.issues
    )

    changed_profile = profile.model_copy(
        update={"max_drawdown_tolerance_pct": Decimal("30")}
    )
    profile_mismatch = evaluate_risk_gate(
        changed_profile, pipeline, assessment, allocation
    )
    assert profile_mismatch.status == GateStatus.BLOCKED
    assert any(
        issue.code == RiskGateIssueCode.PROFILE_MISMATCH
        for issue in profile_mismatch.issues
    )


def test_stale_evidence_is_independently_blocked_by_both_gates() -> None:
    _, profile, _, _, _, assessment, allocation, pipeline, candidate, *_ = _build_case()
    stale = pipeline.trace.evidence[0].model_copy(
        update={
            "quality_status": EvidenceQualityStatus.STALE,
            "quality_note": "source is stale",
        }
    )
    stale_trace = pipeline.trace.model_copy(
        update={"evidence": (stale,) + pipeline.trace.evidence[1:]}
    )
    stale_pipeline = pipeline.model_copy(update={"trace": stale_trace})

    risk = evaluate_risk_gate(profile, stale_pipeline, assessment, allocation)
    compliance = evaluate_compliance_gate(profile, stale_pipeline, candidate)
    assert risk.status == GateStatus.BLOCKED
    assert compliance.status == GateStatus.BLOCKED
    assert any(
        issue.code == RiskGateIssueCode.NON_VERIFIED_EVIDENCE
        for issue in risk.issues
    )
    assert any(
        issue.code == ComplianceGateIssueCode.NON_VERIFIED_EVIDENCE
        for issue in compliance.issues
    )

    unreferenced = stale.model_copy(
        update={"evidence_id": "gate-evidence-unreferenced"}
    )
    extra_trace = pipeline.trace.model_copy(
        update={"evidence": pipeline.trace.evidence + (unreferenced,)}
    )
    extra_pipeline = pipeline.model_copy(update={"trace": extra_trace})
    extra_risk = evaluate_risk_gate(
        profile, extra_pipeline, assessment, allocation
    )
    assert extra_risk.status == GateStatus.BLOCKED
    assert any(
        issue.code == RiskGateIssueCode.NON_VERIFIED_EVIDENCE
        for issue in extra_risk.issues
    )


def test_missing_disclosure_requires_review_and_order_is_canonical() -> None:
    _, profile, _, _, _, _, _, pipeline, candidate, *_ = _build_case()
    incomplete = candidate.model_copy(
        update={"disclosure_codes": REQUIRED_DISCLOSURES[:-1]}
    )
    result = evaluate_compliance_gate(profile, pipeline, incomplete)
    assert result.status == GateStatus.REVIEW_REQUIRED
    assert result.issues[0].code == ComplianceGateIssueCode.MISSING_DISCLOSURE

    reordered = candidate.model_copy(
        update={"disclosure_codes": tuple(reversed(REQUIRED_DISCLOSURES))}
    )
    passed = evaluate_compliance_gate(profile, pipeline, reordered)
    original = evaluate_compliance_gate(profile, pipeline, candidate)
    assert passed.status == GateStatus.PASS
    assert passed.present_disclosures == REQUIRED_DISCLOSURES
    assert passed.gate_id == original.gate_id


@pytest.mark.parametrize(
    ("statement", "issue_code"),
    (
        ("这项配置保证收益并且无风险。", ComplianceGateIssueCode.GUARANTEE_LANGUAGE),
        ("预计收益率达到12%。", ComplianceGateIssueCode.TARGET_RETURN_LANGUAGE),
        ("预期年化10%。", ComplianceGateIssueCode.TARGET_RETURN_LANGUAGE),
        ("该资产必涨。", ComplianceGateIssueCode.GUARANTEE_LANGUAGE),
    ),
)
def test_prohibited_promises_are_blocked_without_echoing_text(
    statement: str, issue_code: ComplianceGateIssueCode
) -> None:
    _, profile, _, _, _, _, _, pipeline, candidate, *_ = _build_case()
    unsafe = candidate.model_copy(update={"statement": statement})
    result = evaluate_compliance_gate(profile, pipeline, unsafe)

    assert result.status == GateStatus.BLOCKED
    assert any(issue.code == issue_code for issue in result.issues)
    assert statement not in result.model_dump_json()


def test_plain_risk_disclaimer_is_not_misclassified_as_a_guarantee() -> None:
    _, profile, _, _, _, _, _, pipeline, candidate, *_ = _build_case()
    disclosed = candidate.model_copy(
        update={"statement": "该方案不保证收益，且可能发生本金损失。"}
    )
    result = evaluate_compliance_gate(profile, pipeline, disclosed)
    assert result.status == GateStatus.PASS


def test_prohibited_language_in_referenced_finding_is_also_blocked() -> None:
    _, profile, _, _, _, _, _, pipeline, candidate, *_ = _build_case()
    finding = pipeline.trace.findings[0].model_copy(
        update={"statement": "该研究结论保证收益。"}
    )
    bridge = pipeline.bridges[0].model_copy(update={"finding": finding})
    trace = pipeline.trace.model_copy(update={"findings": (finding,)})
    unsafe_pipeline = pipeline.model_copy(
        update={"bridges": (bridge,), "trace": trace}
    )

    result = evaluate_compliance_gate(profile, unsafe_pipeline, candidate)
    assert result.status == GateStatus.BLOCKED
    assert any(
        issue.code == ComplianceGateIssueCode.GUARANTEE_LANGUAGE
        for issue in result.issues
    )
    assert "保证收益" not in result.model_dump_json()


def test_bridge_trace_divergence_and_oversized_policy_input_are_blocked() -> None:
    _, profile, _, _, _, _, _, pipeline, candidate, *_ = _build_case()
    changed_finding = pipeline.trace.findings[0].model_copy(
        update={"statement": "内容已改变但未同步 bridge。"}
    )
    changed_trace = pipeline.trace.model_copy(update={"findings": (changed_finding,)})
    divergent = pipeline.model_copy(update={"trace": changed_trace})
    result = evaluate_compliance_gate(profile, divergent, candidate)
    assert result.status == GateStatus.BLOCKED
    assert any(
        issue.code == ComplianceGateIssueCode.TRACE_INTEGRITY
        for issue in result.issues
    )

    oversized = candidate.model_copy(update={"statement": "x" * 5000})
    oversized_result = evaluate_compliance_gate(profile, pipeline, oversized)
    assert oversized_result.status == GateStatus.BLOCKED
    assert oversized_result.issues[0].code == ComplianceGateIssueCode.INVALID_INPUT


def test_unknown_finding_and_sensitive_input_are_blocked_without_leakage() -> None:
    _, profile, _, _, _, _, _, pipeline, candidate, *_ = _build_case()
    unknown = candidate.model_copy(update={"finding_ids": ("unknown-finding",)})
    unknown_result = evaluate_compliance_gate(profile, pipeline, unknown)
    assert unknown_result.status == GateStatus.BLOCKED
    assert unknown_result.checked_finding_ids == ()
    assert unknown_result.issues[-1].code == ComplianceGateIssueCode.UNKNOWN_FINDING

    raw_secret = "authorization=bearer-do-not-emit"
    sensitive = candidate.model_copy(update={"rationale": raw_secret})
    sensitive_result = evaluate_compliance_gate(profile, pipeline, sensitive)
    serialized = sensitive_result.model_dump_json().casefold()
    assert sensitive_result.status == GateStatus.BLOCKED
    assert sensitive_result.issues[0].code == ComplianceGateIssueCode.SENSITIVE_INPUT
    assert "authorization" not in serialized
    assert "do-not-emit" not in serialized


def test_model_copy_tampering_is_revalidated_and_inputs_remain_immutable() -> None:
    _, profile, _, _, _, assessment, allocation, pipeline, candidate, *_ = _build_case()
    originals = tuple(
        item.model_dump_json()
        for item in (profile, pipeline, assessment, allocation, candidate)
    )
    first = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )
    second = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )
    assert first == second
    assert originals == tuple(
        item.model_dump_json()
        for item in (profile, pipeline, assessment, allocation, candidate)
    )

    invalid_ready = pipeline.model_copy(update={"trace": DecisionTrace()})
    blocked = evaluate_risk_gate(profile, invalid_ready, assessment, allocation)
    assert blocked.status == GateStatus.BLOCKED
    assert blocked.issues[0].code == RiskGateIssueCode.INVALID_INPUT

    with pytest.raises((TypeError, ValidationError)):
        candidate.statement = "mutated"


def test_gate_ids_bind_content_and_result_contract_rejects_sensitive_output() -> None:
    _, profile, _, _, _, assessment, allocation, pipeline, candidate, *_ = _build_case()
    first = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )
    changed_candidate = candidate.model_copy(
        update={"rationale": "同一候选标识下的另一份合规理由。"}
    )
    second = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, changed_candidate
    )
    assert first.compliance_gate.gate_id != second.compliance_gate.gate_id
    assert first.gate_id != second.gate_id

    reversed_trace = pipeline.trace.model_copy(
        update={"evidence": tuple(reversed(pipeline.trace.evidence))}
    )
    reordered_pipeline = pipeline.model_copy(update={"trace": reversed_trace})
    reordered = evaluate_decision_gates(
        profile, reordered_pipeline, assessment, allocation, candidate
    )
    assert reordered.risk_gate.gate_id == first.risk_gate.gate_id
    assert reordered.compliance_gate.gate_id == first.compliance_gate.gate_id
    assert reordered.gate_id == first.gate_id

    with pytest.raises(ValidationError, match="sensitive"):
        ComplianceGateResult(
            gate_id="compliance-gate:unsafe",
            candidate_id="candidate-secret-token",
            owner_id=profile.owner_id,
            research_run_id=pipeline.run_id,
            status=GateStatus.BLOCKED,
            issues=(
                ComplianceGateIssue(
                    code=ComplianceGateIssueCode.INVALID_INPUT,
                    safe_message="gate input failed contract validation",
                ),
            ),
        )


def test_candidate_contract_rejects_duplicate_references() -> None:
    _, _, _, _, _, _, _, _, candidate, *_ = _build_case()
    payload = candidate.model_dump(mode="python")
    payload["finding_ids"] = candidate.finding_ids * 2
    with pytest.raises(ValidationError, match="duplicates"):
        AdvisoryCandidate.model_validate(payload)
