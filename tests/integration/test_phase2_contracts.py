import json
from decimal import Decimal
from pathlib import Path

from app.portfolio import PortfolioImportBundle
from app.profile import (
    ConflictResolution,
    RiskProfile,
    RiskQuestionnaire,
    ProfileExtractionProposal,
    build_profile_draft,
    finalize_profile,
)


FIXTURES = Path(__file__).parents[1] / "fixtures"


def test_synthetic_profile_fixture_can_be_confirmed_without_network_or_raw_text() -> None:
    payload = json.loads((FIXTURES / "profile" / "profile_case.json").read_text())
    questionnaire = RiskQuestionnaire.model_validate(payload["questionnaire"])
    extraction = ProfileExtractionProposal.model_validate(payload["extraction"])
    draft = build_profile_draft(questionnaire, extraction)
    resolutions = {
        conflict.conflict_id: ConflictResolution.USE_QUESTIONNAIRE
        for conflict in draft.conflicts
    }
    profile = finalize_profile(
        draft,
        resolutions,
        profile_id="fixture-profile-001",
        created_at=questionnaire.answered_at,
    )
    assert isinstance(profile, RiskProfile)
    assert profile.owner_id == questionnaire.owner_id
    assert profile.extraction_id == extraction.extraction_id
    assert profile.risk_score >= 0


def test_synthetic_portfolio_fixture_is_owner_closed_and_phase3_ready() -> None:
    payload = json.loads((FIXTURES / "portfolio" / "portfolio_bundle.json").read_text())
    bundle = PortfolioImportBundle.model_validate(payload)
    assert bundle.position_snapshot.positions
    assert bundle.fund_holdings[0].parent_asset_id == "FUND_SYNTH_001"
    assert bundle.fund_holdings[0].holdings[0].weight_pct == Decimal("35.5")
    assert all(
        snapshot.owner_id == bundle.owner_id for snapshot in bundle.fund_holdings
    )
