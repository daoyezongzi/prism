"""Synthetic end-to-end inputs shared by Phase 12 tests."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
import json

from app.allocation import AllocationResult, build_allocation_envelope
from app.contracts import DecisionTrace, Evidence, FindingSeverity
from app.gates import AdvisoryCandidate, DecisionGateResult, evaluate_decision_gates
from app.portfolio import (
    ExposureResult,
    PortfolioImportBundle,
    calculate_exposure,
)
from app.profile import RiskLevel, RiskProfile
from app.research import (
    ResearchObservation,
    ValidationClaim,
    bridge_cross_validation,
    validate_claim,
)
from app.research.pipeline import (
    ResearchEvidencePipelineResult,
    ResearchPipelineStatus,
)
from app.risk import (
    ConcentrationResult,
    RiskBudgetAssessment,
    assess_risk_budget,
    calculate_concentration,
)


FIXTURES = Path(__file__).parent / "fixtures"
GATE_FIXTURE = FIXTURES / "gates" / "risk_compliance_gate_case.json"
RECOMMENDATION_FIXTURE = (
    FIXTURES / "recommendation" / "recommendation_receipt_case.json"
)


@dataclass(frozen=True)
class RecommendationCase:
    fixture: dict
    gate_fixture: dict
    profile: RiskProfile
    portfolio: PortfolioImportBundle
    exposure: ExposureResult
    concentration: ConcentrationResult
    assessment: RiskBudgetAssessment
    allocation: AllocationResult
    pipeline: ResearchEvidencePipelineResult
    candidate: AdvisoryCandidate
    decision_gate: DecisionGateResult
    generated_at: datetime


def build_recommendation_case(
    level: RiskLevel = RiskLevel.BALANCED,
) -> RecommendationCase:
    fixture = json.loads(RECOMMENDATION_FIXTURE.read_text(encoding="utf-8"))
    gate_fixture = json.loads(GATE_FIXTURE.read_text(encoding="utf-8"))
    profile = RiskProfile.model_validate(gate_fixture["profile"])
    if level != RiskLevel.BALANCED:
        score = {
            RiskLevel.CONSERVATIVE: "25",
            RiskLevel.GROWTH: "75",
        }[level]
        profile = RiskProfile.model_validate(
            {
                **profile.model_dump(mode="python"),
                "profile_id": f"receipt-profile-{level.value.lower()}-001",
                "risk_score": score,
                "risk_level": level,
            }
        )

    portfolio = PortfolioImportBundle.model_validate(gate_fixture["portfolio"])
    exposure = calculate_exposure(portfolio)
    concentration = calculate_concentration(exposure)
    assessment = assess_risk_budget(profile, concentration)
    allocation = build_allocation_envelope(
        profile, exposure, concentration, assessment
    )

    evidence = tuple(
        Evidence.model_validate(item) for item in gate_fixture["evidence"]
    )
    observations = tuple(
        ResearchObservation.model_validate(item)
        for item in gate_fixture["observations"]
    )
    claim = ValidationClaim.model_validate(gate_fixture["claim"])
    validation = validate_claim(claim, observations)
    finding = gate_fixture["finding"]
    bridge = bridge_cross_validation(
        validation,
        evidence,
        observations,
        finding_kind=finding["kind"],
        finding_severity=FindingSeverity(finding["severity"]),
        statement=finding["statement"],
    )
    assert bridge.fact is not None and bridge.finding is not None
    pipeline = ResearchEvidencePipelineResult(
        run_id="receipt-research-run-001",
        request_id="receipt-research-request-001",
        owner_id=profile.owner_id,
        status=ResearchPipelineStatus.READY,
        validations=(validation,),
        bridges=(bridge,),
        trace=DecisionTrace(
            evidence=evidence,
            facts=(bridge.fact,),
            findings=(bridge.finding,),
        ),
    )
    candidate = AdvisoryCandidate.model_validate(
        {
            **gate_fixture["candidate"],
            "finding_ids": (bridge.finding.finding_id,),
        }
    )
    decision_gate = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )
    generated_at = datetime.fromisoformat(
        fixture["generated_at"].replace("Z", "+00:00")
    )
    return RecommendationCase(
        fixture=fixture,
        gate_fixture=gate_fixture,
        profile=profile,
        portfolio=portfolio,
        exposure=exposure,
        concentration=concentration,
        assessment=assessment,
        allocation=allocation,
        pipeline=pipeline,
        candidate=candidate,
        decision_gate=decision_gate,
        generated_at=generated_at,
    )


__all__ = ["RecommendationCase", "build_recommendation_case"]
