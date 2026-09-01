"""Immutable contracts for deterministic user risk profiles."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr


Digest = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    ),
]


class InvestmentHorizon(StrEnum):
    SHORT = "SHORT"
    MEDIUM = "MEDIUM"
    LONG = "LONG"


class LiquidityNeed(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ExperienceLevel(StrEnum):
    NOVICE = "NOVICE"
    INTERMEDIATE = "INTERMEDIATE"
    EXPERIENCED = "EXPERIENCED"


class ReturnExpectation(StrEnum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class RiskLevel(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    GROWTH = "GROWTH"


class ProfileStatus(StrEnum):
    READY = "READY"
    REQUIRES_CONFIRMATION = "REQUIRES_CONFIRMATION"


class ProfileDimension(StrEnum):
    INVESTMENT_HORIZON = "investment_horizon"
    LIQUIDITY_NEED = "liquidity_need"
    EXPERIENCE_LEVEL = "experience_level"
    RETURN_EXPECTATION = "return_expectation"
    MAX_DRAWDOWN_TOLERANCE_PCT = "max_drawdown_tolerance_pct"
    EXPECTED_RETURN_RANGE = "expected_return_range"


class ConflictResolution(StrEnum):
    UNRESOLVED = "UNRESOLVED"
    USE_QUESTIONNAIRE = "USE_QUESTIONNAIRE"
    USE_EXTRACTION = "USE_EXTRACTION"


class PercentageRange(ContractModel):
    minimum_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    maximum_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))

    @model_validator(mode="after")
    def validate_order(self) -> Self:
        if self.minimum_pct > self.maximum_pct:
            raise ValueError("minimum_pct must not exceed maximum_pct")
        return self


def _display_value(value: object) -> str:
    """Return the stable text form used when a conflict is persisted."""
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, PercentageRange):
        return f"{value.minimum_pct}:{value.maximum_pct}"
    return str(value)


class RiskQuestionnaire(ContractModel):
    schema_version: Literal["risk-questionnaire.v1"] = "risk-questionnaire.v1"
    questionnaire_id: NonEmptyStr
    owner_id: NonEmptyStr
    answered_at: datetime
    loss_tolerance_score: int = Field(ge=1, le=5)
    investment_horizon: InvestmentHorizon
    liquidity_need: LiquidityNeed
    experience_level: ExperienceLevel
    return_expectation: ReturnExpectation
    max_drawdown_tolerance_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    expected_return_range: PercentageRange | None = None

    @model_validator(mode="after")
    def validate_timestamp(self) -> Self:
        if self.answered_at.tzinfo is None or self.answered_at.utcoffset() is None:
            raise ValueError("answered_at must be timezone-aware")
        return self


class ProfileExtractionProposal(ContractModel):
    schema_version: Literal["profile-extraction.v1"] = "profile-extraction.v1"
    extraction_id: NonEmptyStr
    owner_id: NonEmptyStr
    input_digest: Digest
    extracted_at: datetime
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    investment_horizon: InvestmentHorizon | None = None
    liquidity_need: LiquidityNeed | None = None
    experience_level: ExperienceLevel | None = None
    return_expectation: ReturnExpectation | None = None
    max_drawdown_tolerance_pct: Decimal | None = Field(
        default=None, ge=Decimal("0"), le=Decimal("100")
    )
    expected_return_range: PercentageRange | None = None
    asset_preferences: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    sector_preferences: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    exclusions: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_extraction(self) -> Self:
        if self.extracted_at.tzinfo is None or self.extracted_at.utcoffset() is None:
            raise ValueError("extracted_at must be timezone-aware")
        for field_name in ("asset_preferences", "sector_preferences", "exclusions"):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicates")
        serialized = self.model_dump_json().casefold().replace("-", "_")
        for forbidden in (
            "api_key",
            "apikey",
            "authorization",
            "password",
            "private_key",
            "privatekey",
            "secret",
            "token",
            "credential",
            "cookie",
        ):
            if forbidden in serialized:
                raise ValueError("profile extraction must not contain sensitive fields")
        return self


class ProfileConflict(ContractModel):
    conflict_id: NonEmptyStr
    owner_id: NonEmptyStr
    dimension: ProfileDimension
    questionnaire_value: NonEmptyStr
    extracted_value: NonEmptyStr
    resolution: ConflictResolution = ConflictResolution.UNRESOLVED
    resolved_value: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_resolution(self) -> Self:
        if self.resolution == ConflictResolution.UNRESOLVED:
            if self.resolved_value is not None:
                raise ValueError("unresolved conflict must not have resolved_value")
        elif self.resolved_value not in {
            self.questionnaire_value,
            self.extracted_value,
        }:
            raise ValueError(
                "resolved_value must match questionnaire_value or extracted_value"
            )
        return self


class ProfileDraft(ContractModel):
    draft_id: NonEmptyStr
    owner_id: NonEmptyStr
    questionnaire: RiskQuestionnaire
    extraction: ProfileExtractionProposal | None = None
    conflicts: tuple[ProfileConflict, ...] = Field(default_factory=tuple)
    status: ProfileStatus

    @model_validator(mode="after")
    def validate_draft(self) -> Self:
        if self.questionnaire.owner_id != self.owner_id:
            raise ValueError("questionnaire owner_id does not match draft owner_id")
        if self.extraction is not None and self.extraction.owner_id != self.owner_id:
            raise ValueError("extraction owner_id does not match draft owner_id")
        if len({conflict.conflict_id for conflict in self.conflicts}) != len(self.conflicts):
            raise ValueError("conflicts must not contain duplicate conflict_id")
        if any(conflict.owner_id != self.owner_id for conflict in self.conflicts):
            raise ValueError("conflict owner_id does not match draft owner_id")
        conflict_dimensions = [conflict.dimension for conflict in self.conflicts]
        if len(set(conflict_dimensions)) != len(conflict_dimensions):
            raise ValueError("conflicts must not contain duplicate dimensions")
        if self.extraction is None and self.conflicts:
            raise ValueError("conflicts require an extraction proposal")
        if self.extraction is not None:
            for conflict in self.conflicts:
                questionnaire_value = getattr(
                    self.questionnaire, conflict.dimension.value
                )
                extracted_value = getattr(self.extraction, conflict.dimension.value)
                if extracted_value is None:
                    raise ValueError(
                        "conflict dimension must have an extracted candidate value"
                    )
                if _display_value(questionnaire_value) != conflict.questionnaire_value:
                    raise ValueError("conflict questionnaire_value is not current")
                if _display_value(extracted_value) != conflict.extracted_value:
                    raise ValueError("conflict extracted_value is not current")
                if questionnaire_value == extracted_value:
                    raise ValueError("conflict values must actually differ")
        has_unresolved = any(
            conflict.resolution == ConflictResolution.UNRESOLVED
            for conflict in self.conflicts
        )
        expected_status = (
            ProfileStatus.REQUIRES_CONFIRMATION
            if has_unresolved
            else ProfileStatus.READY
        )
        if self.status != expected_status:
            raise ValueError(
                f"draft status must be {expected_status.value} for its conflicts"
            )
        return self


class RiskProfile(ContractModel):
    schema_version: Literal["risk-profile.v1"] = "risk-profile.v1"
    profile_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_version: int = Field(ge=1)
    questionnaire_id: NonEmptyStr
    extraction_id: NonEmptyStr | None = None
    created_at: datetime
    risk_score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    risk_level: RiskLevel
    investment_horizon: InvestmentHorizon
    liquidity_need: LiquidityNeed
    experience_level: ExperienceLevel
    return_expectation: ReturnExpectation
    max_drawdown_tolerance_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    expected_return_range: PercentageRange | None = None
    asset_preferences: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    sector_preferences: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    exclusions: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))
    conflicts: tuple[ProfileConflict, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_profile(self) -> Self:
        if self.created_at.tzinfo is None or self.created_at.utcoffset() is None:
            raise ValueError("created_at must be timezone-aware")
        if any(
            conflict.owner_id != self.owner_id
            for conflict in self.conflicts
        ):
            raise ValueError("conflict owner_id does not match profile owner_id")
        if any(
            conflict.resolution == ConflictResolution.UNRESOLVED
            for conflict in self.conflicts
        ):
            raise ValueError("RiskProfile must not contain unresolved conflicts")
        conflict_ids = [conflict.conflict_id for conflict in self.conflicts]
        if len(set(conflict_ids)) != len(conflict_ids):
            raise ValueError("conflicts must not contain duplicate conflict_id")
        conflict_dimensions = [conflict.dimension for conflict in self.conflicts]
        if len(set(conflict_dimensions)) != len(conflict_dimensions):
            raise ValueError("conflicts must not contain duplicate dimensions")
        expected_level = (
            RiskLevel.CONSERVATIVE
            if self.risk_score <= Decimal("33")
            else RiskLevel.BALANCED
            if self.risk_score <= Decimal("66")
            else RiskLevel.GROWTH
        )
        if self.risk_level != expected_level:
            raise ValueError("risk_level does not match risk_score thresholds")
        for field_name in ("asset_preferences", "sector_preferences", "exclusions"):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must not contain duplicates")
        return self
