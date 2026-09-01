import json
from pathlib import Path

from app.portfolio import PortfolioImportBundle, calculate_exposure
from app.profile import RiskProfile
from app.risk import BudgetAssessmentStatus, assess_risk_budget, calculate_concentration


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_synthetic_profile_and_exposure_produce_auditable_budget_assessment() -> None:
    profile_payload = json.loads(
        (FIXTURES / "risk" / "risk_budget_case.json").read_text()
    )
    profile = RiskProfile.model_validate(profile_payload["profile"])
    bundle = PortfolioImportBundle.model_validate(
        json.loads(
            (FIXTURES / "portfolio" / "portfolio_exposure_bundle.json").read_text()
        )
    )
    concentration = calculate_concentration(calculate_exposure(bundle))
    assessment = assess_risk_budget(profile, concentration)
    assert assessment.status == BudgetAssessmentStatus.REVIEW_REQUIRED
    assert assessment.owner_id == profile.owner_id
    assert assessment.budget.profile_id == profile.profile_id
    assert assessment.breaches or assessment.issues
    serialized = str(assessment.model_dump(mode="json"))
    assert "recommendation" not in serialized.lower()
    assert "api_key" not in serialized.lower()
