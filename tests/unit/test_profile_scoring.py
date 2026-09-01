from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.profile import (
    ConflictResolution,
    ExperienceLevel,
    InvestmentHorizon,
    LiquidityNeed,
    ProfileStatus,
    ReturnExpectation,
    RiskLevel,
    RiskQuestionnaire,
    build_profile_draft,
    finalize_profile,
    risk_level_for_score,
    score_questionnaire,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
DIGEST = "b" * 64


def make_questionnaire(**overrides: object) -> RiskQuestionnaire:
    values: dict[str, object] = {
        "questionnaire_id": "questionnaire-score-001",
        "owner_id": "owner-score-001",
        "answered_at": NOW,
        "loss_tolerance_score": 3,
        "investment_horizon": InvestmentHorizon.MEDIUM,
        "liquidity_need": LiquidityNeed.MEDIUM,
        "experience_level": ExperienceLevel.INTERMEDIATE,
        "return_expectation": ReturnExpectation.MODERATE,
        "max_drawdown_tolerance_pct": Decimal("20"),
    }
    values.update(overrides)
    return RiskQuestionnaire.model_validate(values)


def make_extraction(**overrides: object):
    from app.profile import ProfileExtractionProposal

    values: dict[str, object] = {
        "extraction_id": "extraction-score-001",
        "owner_id": "owner-score-001",
        "input_digest": DIGEST,
        "extracted_at": NOW,
        "confidence": Decimal("0.75"),
        "investment_horizon": InvestmentHorizon.LONG,
        "return_expectation": ReturnExpectation.HIGH,
        "max_drawdown_tolerance_pct": Decimal("30"),
    }
    values.update(overrides)
    return ProfileExtractionProposal.model_validate(values)


def test_score_is_deterministic_and_serializable() -> None:
    questionnaire = make_questionnaire()
    first = score_questionnaire(questionnaire)
    second = score_questionnaire(
        RiskQuestionnaire.model_validate(questionnaire.model_dump(mode="json"))
    )
    assert first == second == Decimal("50.00")
    assert questionnaire.model_dump(mode="json") == RiskQuestionnaire.model_validate(
        questionnaire.model_dump(mode="json")
    ).model_dump(mode="json")


def test_low_and_high_questionnaires_get_different_levels() -> None:
    low = make_questionnaire(
        loss_tolerance_score=1,
        investment_horizon=InvestmentHorizon.SHORT,
        liquidity_need=LiquidityNeed.HIGH,
        experience_level=ExperienceLevel.NOVICE,
        return_expectation=ReturnExpectation.LOW,
    )
    high = make_questionnaire(
        loss_tolerance_score=5,
        investment_horizon=InvestmentHorizon.LONG,
        liquidity_need=LiquidityNeed.LOW,
        experience_level=ExperienceLevel.EXPERIENCED,
        return_expectation=ReturnExpectation.HIGH,
    )
    low_score = score_questionnaire(low)
    high_score = score_questionnaire(high)
    assert low_score == Decimal("0.00")
    assert high_score == Decimal("100.00")
    assert risk_level_for_score(low_score) == RiskLevel.CONSERVATIVE
    assert risk_level_for_score(high_score) == RiskLevel.GROWTH


def test_score_does_not_consume_free_text_or_random_state() -> None:
    questionnaire = make_questionnaire()
    assert "free_text" not in RiskQuestionnaire.model_fields
    assert score_questionnaire(questionnaire) == score_questionnaire(questionnaire)


def test_conflicting_extraction_creates_confirmation_draft() -> None:
    draft = build_profile_draft(make_questionnaire(), make_extraction())
    assert draft.status == ProfileStatus.REQUIRES_CONFIRMATION
    assert {
        conflict.dimension.value for conflict in draft.conflicts
    } == {
        "investment_horizon",
        "return_expectation",
        "max_drawdown_tolerance_pct",
    }


def test_unresolved_conflict_cannot_be_finalized() -> None:
    draft = build_profile_draft(make_questionnaire(), make_extraction())
    with pytest.raises(ValueError, match="requires explicit confirmation"):
        finalize_profile(
            draft,
            profile_id="profile-001",
            created_at=NOW,
        )


def test_explicit_conflict_choices_finalize_and_preserve_audit_record() -> None:
    draft = build_profile_draft(make_questionnaire(), make_extraction())
    resolutions = {
        conflict.conflict_id: (
            ConflictResolution.USE_EXTRACTION
            if conflict.dimension.value == "investment_horizon"
            else ConflictResolution.USE_QUESTIONNAIRE
        )
        for conflict in draft.conflicts
    }
    profile = finalize_profile(
        draft,
        resolutions,
        profile_id="profile-001",
        created_at=NOW,
    )
    assert profile.investment_horizon == InvestmentHorizon.LONG
    assert profile.return_expectation == ReturnExpectation.MODERATE
    assert profile.max_drawdown_tolerance_pct == Decimal("20")
    assert profile.conflicts
    assert all(
        conflict.resolution != ConflictResolution.UNRESOLVED
        for conflict in profile.conflicts
    )


def test_profile_serialization_has_digest_not_raw_natural_language() -> None:
    extraction = make_extraction()
    draft = build_profile_draft(make_questionnaire(), extraction)
    raw = "I am worried about a sudden crash and need cash next month"
    serialized = str(draft.model_dump(mode="json"))
    assert extraction.input_digest in serialized
    assert raw not in serialized
    assert "api_key" not in serialized.lower()
