"""Deterministic Decision Receipt construction."""

from __future__ import annotations

from datetime import datetime

from app.allocation.contracts import AllocationResult
from app.contracts.evidence import DecisionTrace
from app.gates import AdvisoryCandidate, DecisionGateResult
from app.gates.fingerprint import (
    canonical_model_signature,
    canonical_payload_signature,
)
from app.portfolio.contracts import PortfolioImportBundle
from app.portfolio.exposure import ExposureResult
from app.profile.contracts import RiskProfile
from app.research.pipeline import ResearchEvidencePipelineResult
from app.risk.contracts import ConcentrationResult, RiskBudgetAssessment

from app.recommendation.contracts import (
    REQUIRED_RULE_VERSIONS,
    DecisionReceipt,
    GenerationMode,
    RecommendationBinding,
    _receipt_id,
)


def build_decision_receipt(
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
    trace: DecisionTrace,
    bindings: tuple[RecommendationBinding, ...],
    generated_at: datetime,
) -> DecisionReceipt:
    """Build a self-validating receipt from an already closed PASS decision."""

    if exposure.report is None or concentration.report is None:
        raise ValueError("receipt requires exposure and concentration reports")
    if allocation.envelope is None:
        raise ValueError("receipt requires an allocation envelope")

    recommendation_ids = tuple(
        recommendation.recommendation_id for recommendation in trace.recommendations
    )
    payload = {
        "receipt_id": _receipt_id(
            profile.owner_id,
            profile.profile_id,
            decision_gate.gate_id,
            recommendation_ids,
        ),
        "owner_id": profile.owner_id,
        "profile_id": profile.profile_id,
        "profile_version": profile.profile_version,
        "portfolio_bundle_id": portfolio.bundle_id,
        "position_snapshot_id": portfolio.position_snapshot.snapshot_id,
        "exposure_report_id": exposure.report.report_id,
        "concentration_report_id": concentration.report.report_id,
        "risk_assessment_id": assessment.assessment_id,
        "allocation_request_id": allocation.request_id,
        "allocation_envelope_id": allocation.envelope.envelope_id,
        "research_run_id": pipeline.run_id,
        "candidate_id": candidate.candidate_id,
        "risk_gate_id": decision_gate.risk_gate.gate_id,
        "compliance_gate_id": decision_gate.compliance_gate.gate_id,
        "decision_gate_id": decision_gate.gate_id,
        "evidence_ids": tuple(sorted(item.evidence_id for item in trace.evidence)),
        "fact_ids": tuple(sorted(item.fact_id for item in trace.facts)),
        "finding_ids": tuple(sorted(item.finding_id for item in trace.findings)),
        "recommendation_ids": recommendation_ids,
        "recommendation_bindings": bindings,
        "rule_versions": REQUIRED_RULE_VERSIONS,
        "generation_mode": GenerationMode.DETERMINISTIC,
        "model_versions": (),
        "generated_at": generated_at,
        "decision_trace_hash": canonical_model_signature(trace),
    }
    content_hash = canonical_payload_signature(
        DecisionReceipt.model_construct(**payload, content_hash="0" * 64).model_dump(
            mode="json", exclude={"content_hash"}
        )
    )
    return DecisionReceipt(**payload, content_hash=content_hash)


__all__ = ["build_decision_receipt"]
