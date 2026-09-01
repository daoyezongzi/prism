from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.profile import (
    ExperienceLevel,
    InvestmentHorizon,
    LiquidityNeed,
    PercentageRange,
    ProfileConflict,
    ProfileDimension,
    ProfileExtractionProposal,
    ProfileStatus,
    ReturnExpectation,
    RiskQuestionnaire,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
DIGEST = "a" * 64


def make_questionnaire(**overrides: object) -> RiskQuestionnaire:
    values: dict[str, object] = {
        "questionnaire_id": "questionnaire-001",
        "owner_id": "owner-001",
        "answered_at": NOW,
        "loss_tolerance_score": 3,
        "investment_horizon": InvestmentHorizon.MEDIUM,
        "liquidity_need": LiquidityNeed.MEDIUM,
        "experience_level": ExperienceLevel.INTERMEDIATE,
        "return_expectation": ReturnExpectation.MODERATE,
        "max_drawdown_tolerance_pct": Decimal("20"),
        "expected_return_range": PercentageRange(
            minimum_pct=Decimal("4"), maximum_pct=Decimal("8")
        ),
    }
    values.update(overrides)
    return RiskQuestionnaire.model_validate(values)


def make_extraction(**overrides: object) -> ProfileExtractionProposal:
    values: dict[str, object] = {
        "extraction_id": "extraction-001",
        "owner_id": "owner-001",
        "input_digest": DIGEST,
        "extracted_at": NOW,
        "confidence": Decimal("0.8"),
        "investment_horizon": InvestmentHorizon.LONG,
        "liquidity_need": LiquidityNeed.MEDIUM,
        "experience_level": ExperienceLevel.INTERMEDIATE,
        "return_expectation": ReturnExpectation.HIGH,
        "max_drawdown_tolerance_pct": Decimal("25"),
        "expected_return_range": PercentageRange(
            minimum_pct=Decimal("6"), maximum_pct=Decimal("12")
        ),
        "asset_preferences": ("ETF_SYNTH_001",),
        "sector_preferences": ("Technology",),
        "exclusions": ("Leveraged",),
    }
    values.update(overrides)
    return ProfileExtractionProposal.model_validate(values)


def test_questionnaire_rejects_bad_range_and_naive_timestamp() -> None:
    with pytest.raises(ValidationError):
        make_questionnaire(
            answered_at=datetime(2026, 9, 1, 12, 0),
        )
    with pytest.raises(ValidationError):
        PercentageRange(minimum_pct=Decimal("9"), maximum_pct=Decimal("8"))
    with pytest.raises(ValidationError):
        make_questionnaire(loss_tolerance_score=6)


def test_profile_models_are_immutable_and_extra_fields_are_forbidden() -> None:
    questionnaire = make_questionnaire()
    with pytest.raises(ValidationError):
        make_questionnaire(unexpected="value")
    with pytest.raises(ValidationError):
        questionnaire.owner_id = "owner-002"  # type: ignore[misc]


def test_extraction_requires_digest_and_deduplicated_structured_values() -> None:
    with pytest.raises(ValidationError):
        make_extraction(input_digest="not-a-digest")
    with pytest.raises(ValidationError):
        make_extraction(asset_preferences=("ETF_SYNTH_001", "ETF_SYNTH_001"))


def test_profile_conflict_requires_a_valid_explicit_resolution() -> None:
    with pytest.raises(ValidationError):
        ProfileConflict(
            conflict_id="conflict-001",
            owner_id="owner-001",
            dimension=ProfileDimension.INVESTMENT_HORIZON,
            questionnaire_value="MEDIUM",
            extracted_value="LONG",
            resolution="USE_QUESTIONNAIRE",
        )
