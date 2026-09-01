import json
from pathlib import Path

from app.allocation import AllocationStatus, build_allocation_envelope
from app.portfolio import PortfolioImportBundle, calculate_exposure
from app.profile import RiskProfile
from app.risk import assess_risk_budget, calculate_concentration


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_fixture_pipeline_keeps_profile_and_snapshot_closure() -> None:
    fixture = json.loads(
        (FIXTURES / "allocation" / "allocation_envelope_case.json").read_text(
            encoding="utf-8"
        )
    )
    profile = RiskProfile.model_validate(
        json.loads((FIXTURES / "risk" / "risk_budget_case.json").read_text())["profile"]
    )
    bundle = PortfolioImportBundle.model_validate(
        json.loads(
            (FIXTURES / "portfolio" / "portfolio_exposure_bundle.json").read_text()
        )
    )
    exposure = calculate_exposure(bundle)
    concentration = calculate_concentration(exposure)
    assessment = assess_risk_budget(profile, concentration)
    result = build_allocation_envelope(profile, exposure, concentration, assessment)

    assert fixture["source"] == "offline-test-only"
    assert result.status == AllocationStatus.REVIEW_REQUIRED
    assert result.envelope is not None
    assert result.envelope.profile_id == profile.profile_id
    assert result.envelope.exposure_report_id == exposure.report.report_id
    assert result.envelope.concentration_report_id == concentration.report.report_id
    assert result.envelope.invalidation_conditions == tuple(
        fixture["expected_invalidation_conditions"]
    )
    serialized = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    for field in fixture["forbidden_fields"]:
        assert field not in serialized.lower()
    assert "api_key" not in serialized.lower()
