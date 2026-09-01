import json
from pathlib import Path

from app.allocation import build_allocation_envelope
from app.contracts import DecisionTrace, Evidence, FindingSeverity
from app.gates import AdvisoryCandidate, evaluate_decision_gates
from app.portfolio import PortfolioImportBundle, calculate_exposure
from app.profile import RiskProfile
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
from app.risk import assess_risk_budget, calculate_concentration


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "gates"
    / "risk_compliance_gate_case.json"
)


def test_fixture_closes_profile_portfolio_research_and_both_gates() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    profile = RiskProfile.model_validate(payload["profile"])
    portfolio = PortfolioImportBundle.model_validate(payload["portfolio"])
    exposure = calculate_exposure(portfolio)
    concentration = calculate_concentration(exposure)
    assessment = assess_risk_budget(profile, concentration)
    allocation = build_allocation_envelope(
        profile, exposure, concentration, assessment
    )

    evidence = tuple(Evidence.model_validate(item) for item in payload["evidence"])
    observations = tuple(
        ResearchObservation.model_validate(item) for item in payload["observations"]
    )
    claim = ValidationClaim.model_validate(payload["claim"])
    validation = validate_claim(claim, observations)
    finding_spec = payload["finding"]
    bridge = bridge_cross_validation(
        validation,
        evidence,
        observations,
        finding_kind=finding_spec["kind"],
        finding_severity=FindingSeverity(finding_spec["severity"]),
        statement=finding_spec["statement"],
    )
    pipeline = ResearchEvidencePipelineResult(
        run_id="gate-research-run-001",
        request_id="gate-research-request-001",
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
            **payload["candidate"],
            "finding_ids": (bridge.finding.finding_id,),
        }
    )

    result = evaluate_decision_gates(
        profile, pipeline, assessment, allocation, candidate
    )

    expected = payload["expected"]
    assert result.risk_gate.status.value == expected["risk_status"]
    assert result.compliance_gate.status.value == expected["compliance_status"]
    assert result.status.value == expected["decision_status"]
    assert (
        result.eligible_for_recommendation
        is expected["eligible_for_recommendation"]
    )
    serialized = result.model_dump_json().casefold()
    for field in expected["forbidden_output_fields"]:
        assert f'"{field.casefold()}"' not in serialized
