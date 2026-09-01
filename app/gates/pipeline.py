"""Composition of independent risk and compliance gate outcomes."""

from __future__ import annotations

from hashlib import sha256

from app.allocation.contracts import AllocationResult
from app.profile.contracts import RiskProfile
from app.research.pipeline import ResearchEvidencePipelineResult
from app.risk.contracts import RiskBudgetAssessment

from app.gates.compliance import evaluate_compliance_gate
from app.gates.contracts import (
    AdvisoryCandidate,
    DecisionGateResult,
    GateStatus,
)
from app.gates.risk import evaluate_risk_gate


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "decision-gate:" + sha256(payload).hexdigest()[:32]


def evaluate_decision_gates(
    profile: RiskProfile,
    pipeline: ResearchEvidencePipelineResult,
    assessment: RiskBudgetAssessment,
    allocation: AllocationResult,
    candidate: AdvisoryCandidate,
) -> DecisionGateResult:
    """Run both independent gates and expose only recommendation eligibility."""

    risk = evaluate_risk_gate(profile, pipeline, assessment, allocation)
    compliance = evaluate_compliance_gate(profile, pipeline, candidate)
    statuses = {risk.status, compliance.status}
    status = (
        GateStatus.BLOCKED
        if GateStatus.BLOCKED in statuses
        else GateStatus.REVIEW_REQUIRED
        if GateStatus.REVIEW_REQUIRED in statuses
        else GateStatus.PASS
    )
    owner_id = risk.owner_id
    profile_id = risk.profile_id
    run_id = risk.research_run_id
    return DecisionGateResult(
        gate_id=_stable_id(risk.gate_id, compliance.gate_id),
        owner_id=owner_id,
        profile_id=profile_id,
        research_run_id=run_id,
        risk_gate=risk,
        compliance_gate=compliance,
        status=status,
        eligible_for_recommendation=status == GateStatus.PASS,
    )
