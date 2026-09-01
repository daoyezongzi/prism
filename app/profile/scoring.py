"""Deterministic scoring and explicit conflict resolution for profiles."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Any

from app.profile.contracts import (
    ConflictResolution,
    ProfileConflict,
    ProfileDimension,
    ProfileDraft,
    ProfileExtractionProposal,
    ProfileStatus,
    RiskLevel,
    RiskProfile,
    RiskQuestionnaire,
)


_WEIGHTS = {
    "loss_tolerance_score": Decimal("0.30"),
    "investment_horizon": Decimal("0.25"),
    "liquidity_need": Decimal("0.20"),
    "experience_level": Decimal("0.10"),
    "return_expectation": Decimal("0.15"),
}
_HORIZON_SCORE = {"SHORT": 1, "MEDIUM": 3, "LONG": 5}
_LIQUIDITY_SCORE = {"LOW": 5, "MEDIUM": 3, "HIGH": 1}
_EXPERIENCE_SCORE = {"NOVICE": 1, "INTERMEDIATE": 3, "EXPERIENCED": 5}
_RETURN_SCORE = {"LOW": 1, "MODERATE": 3, "HIGH": 5}


def _normalise_five_point(value: int) -> Decimal:
    return (Decimal(value) - Decimal("1")) / Decimal("4")


def score_questionnaire(questionnaire: RiskQuestionnaire) -> Decimal:
    """Return a deterministic 0-100 score rounded to two decimal places."""
    components = {
        "loss_tolerance_score": questionnaire.loss_tolerance_score,
        "investment_horizon": _HORIZON_SCORE[questionnaire.investment_horizon.value],
        "liquidity_need": _LIQUIDITY_SCORE[questionnaire.liquidity_need.value],
        "experience_level": _EXPERIENCE_SCORE[questionnaire.experience_level.value],
        "return_expectation": _RETURN_SCORE[questionnaire.return_expectation.value],
    }
    weighted = sum(
        (_WEIGHTS[name] * _normalise_five_point(value) for name, value in components.items()),
        Decimal("0"),
    )
    return (weighted * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def risk_level_for_score(score: Decimal) -> RiskLevel:
    if score <= Decimal("33"):
        return RiskLevel.CONSERVATIVE
    if score <= Decimal("66"):
        return RiskLevel.BALANCED
    return RiskLevel.GROWTH


def _display_value(value: Any) -> str:
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "minimum_pct") and hasattr(value, "maximum_pct"):
        return f"{value.minimum_pct}:{value.maximum_pct}"
    return str(value)


def _conflict_values(
    questionnaire: RiskQuestionnaire,
    extraction: ProfileExtractionProposal,
) -> list[tuple[ProfileDimension, Any, Any]]:
    values: list[tuple[ProfileDimension, Any, Any]] = []
    for dimension in ProfileDimension:
        questionnaire_value = getattr(questionnaire, dimension.value)
        extraction_value = getattr(extraction, dimension.value)
        if extraction_value is not None and extraction_value != questionnaire_value:
            values.append((dimension, questionnaire_value, extraction_value))
    return values


def build_profile_draft(
    questionnaire: RiskQuestionnaire,
    extraction: ProfileExtractionProposal | None = None,
) -> ProfileDraft:
    if extraction is not None and extraction.owner_id != questionnaire.owner_id:
        raise ValueError("extraction owner_id does not match questionnaire owner_id")

    draft_id = "profile-draft:" + questionnaire.questionnaire_id
    if extraction is not None:
        draft_id += ":" + extraction.extraction_id

    conflicts = tuple(
        ProfileConflict(
            conflict_id=f"{draft_id}:{dimension.value}",
            owner_id=questionnaire.owner_id,
            dimension=dimension,
            questionnaire_value=_display_value(questionnaire_value),
            extracted_value=_display_value(extraction_value),
        )
        for dimension, questionnaire_value, extraction_value in (
            _conflict_values(questionnaire, extraction)
            if extraction is not None
            else []
        )
    )
    return ProfileDraft(
        draft_id=draft_id,
        owner_id=questionnaire.owner_id,
        questionnaire=questionnaire,
        extraction=extraction,
        conflicts=conflicts,
        status=(
            ProfileStatus.REQUIRES_CONFIRMATION
            if conflicts
            else ProfileStatus.READY
        ),
    )


def _typed_value(dimension: ProfileDimension, value: Any) -> Any:
    if dimension == ProfileDimension.INVESTMENT_HORIZON:
        from app.profile.contracts import InvestmentHorizon

        return InvestmentHorizon(value)
    if dimension == ProfileDimension.LIQUIDITY_NEED:
        from app.profile.contracts import LiquidityNeed

        return LiquidityNeed(value)
    if dimension == ProfileDimension.EXPERIENCE_LEVEL:
        from app.profile.contracts import ExperienceLevel

        return ExperienceLevel(value)
    if dimension == ProfileDimension.RETURN_EXPECTATION:
        from app.profile.contracts import ReturnExpectation

        return ReturnExpectation(value)
    if dimension == ProfileDimension.MAX_DRAWDOWN_TOLERANCE_PCT:
        return Decimal(value)
    return value


def finalize_profile(
    draft: ProfileDraft,
    resolutions: Mapping[str, ConflictResolution | str] | None = None,
    *,
    profile_id: str,
    profile_version: int = 1,
    created_at: datetime,
) -> RiskProfile:
    choices = dict(resolutions or {})
    known_ids = {conflict.conflict_id for conflict in draft.conflicts}
    unknown_ids = set(choices) - known_ids
    if unknown_ids:
        raise ValueError("resolutions contains unknown conflict IDs")

    questionnaire = draft.questionnaire
    extraction = draft.extraction
    selected: dict[ProfileDimension, Any] = {
        dimension: getattr(questionnaire, dimension.value)
        for dimension in ProfileDimension
    }
    updated_conflicts: list[ProfileConflict] = []
    for conflict in draft.conflicts:
        raw_choice = choices.get(conflict.conflict_id, conflict.resolution)
        choice = ConflictResolution(raw_choice)
        if choice == ConflictResolution.UNRESOLVED:
            raise ValueError(
                f"conflict {conflict.conflict_id!r} requires explicit confirmation"
            )
        chosen_text = (
            conflict.questionnaire_value
            if choice == ConflictResolution.USE_QUESTIONNAIRE
            else conflict.extracted_value
        )
        updated_conflicts.append(
            ProfileConflict(
                conflict_id=conflict.conflict_id,
                owner_id=conflict.owner_id,
                dimension=conflict.dimension,
                questionnaire_value=conflict.questionnaire_value,
                extracted_value=conflict.extracted_value,
                resolution=choice,
                resolved_value=chosen_text,
            )
        )
        if choice == ConflictResolution.USE_EXTRACTION:
            if extraction is None:
                raise ValueError("cannot use extraction without an extraction proposal")
            selected[conflict.dimension] = _typed_value(
                conflict.dimension,
                getattr(extraction, conflict.dimension.value),
            )

    if extraction is not None:
        for dimension in ProfileDimension:
            extraction_value = getattr(extraction, dimension.value)
            if extraction_value is not None and not any(
                conflict.dimension == dimension for conflict in draft.conflicts
            ):
                selected[dimension] = extraction_value

    effective_questionnaire = questionnaire.model_copy(
        update={dimension.value: value for dimension, value in selected.items()}
    )
    score = score_questionnaire(effective_questionnaire)
    return RiskProfile(
        profile_id=profile_id,
        owner_id=draft.owner_id,
        profile_version=profile_version,
        questionnaire_id=questionnaire.questionnaire_id,
        extraction_id=extraction.extraction_id if extraction is not None else None,
        created_at=created_at,
        risk_score=score,
        risk_level=risk_level_for_score(score),
        investment_horizon=selected[ProfileDimension.INVESTMENT_HORIZON],
        liquidity_need=selected[ProfileDimension.LIQUIDITY_NEED],
        experience_level=selected[ProfileDimension.EXPERIENCE_LEVEL],
        return_expectation=selected[ProfileDimension.RETURN_EXPECTATION],
        max_drawdown_tolerance_pct=selected[
            ProfileDimension.MAX_DRAWDOWN_TOLERANCE_PCT
        ],
        expected_return_range=selected[ProfileDimension.EXPECTED_RETURN_RANGE],
        asset_preferences=extraction.asset_preferences if extraction else (),
        sector_preferences=extraction.sector_preferences if extraction else (),
        exclusions=extraction.exclusions if extraction else (),
        confidence=extraction.confidence if extraction else Decimal("1"),
        conflicts=tuple(updated_conflicts),
    )
