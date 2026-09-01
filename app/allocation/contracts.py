"""Immutable contracts for deterministic allocation envelopes.

The envelope is a constraint view over the Phase 4 risk-budget result.  It is
deliberately not a trade order or a recommendation: it records what the
current observations permit under a selected profile and what would have to
change to get back below a limit.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.risk.contracts import RiskLevel


Percentage = Decimal


class AllocationBandDimension(StrEnum):
    """The concentration dimension represented by one envelope row."""

    ASSET = "ASSET"
    SECTOR = "SECTOR"
    TECHNOLOGY = "TECHNOLOGY"
    UNCLASSIFIED = "UNCLASSIFIED"


class AllocationBandDisposition(StrEnum):
    """Constraint state, not an executable action."""

    WITHIN_LIMIT = "WITHIN_LIMIT"
    OVER_LIMIT = "OVER_LIMIT"
    UNRESOLVED = "UNRESOLVED"


class AllocationStatus(StrEnum):
    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class AllocationIssueCode(StrEnum):
    BUDGET_REVIEW_REQUIRED = "BUDGET_REVIEW_REQUIRED"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"


def _percentage(value: Decimal, field_name: str) -> None:
    if value < Decimal("0") or value > Decimal("100"):
        raise ValueError(f"{field_name} must be between 0 and 100")


class AllocationBand(ContractModel):
    """One profile-conditioned constraint envelope row.

    ``target_min_weight_pct`` and ``target_max_weight_pct`` are a permitted
    constraint interval, not a promise that the portfolio will be rebalanced
    to that value.  A row can only be marked ``OVER_LIMIT`` when the observed
    weight exceeds its budget cap.
    """

    schema_version: Literal["allocation-band.v1"] = "allocation-band.v1"
    band_id: NonEmptyStr
    owner_id: NonEmptyStr
    dimension: AllocationBandDimension
    target_id: NonEmptyStr
    label: NonEmptyStr
    current_weight_pct: Percentage = Field(ge=Decimal("0"), le=Decimal("100"))
    allowed_max_weight_pct: Percentage = Field(
        ge=Decimal("0"), le=Decimal("100")
    )
    target_min_weight_pct: Percentage = Field(
        ge=Decimal("0"), le=Decimal("100")
    )
    target_max_weight_pct: Percentage = Field(
        ge=Decimal("0"), le=Decimal("100")
    )
    minimum_reduction_pct: Percentage = Field(
        ge=Decimal("0"), le=Decimal("100")
    )
    disposition: AllocationBandDisposition
    breach_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_band(self) -> Self:
        if self.target_min_weight_pct > self.target_max_weight_pct:
            raise ValueError("target_min_weight_pct must not exceed target_max_weight_pct")
        expected_reduction = max(
            self.current_weight_pct - self.allowed_max_weight_pct,
            Decimal("0"),
        )
        if self.minimum_reduction_pct != expected_reduction:
            raise ValueError(
                "minimum_reduction_pct must equal current minus allowed maximum"
            )
        if len(set(self.breach_ids)) != len(self.breach_ids):
            raise ValueError("breach_ids must not contain duplicates")

        over_limit = self.current_weight_pct > self.allowed_max_weight_pct
        if not over_limit and self.breach_ids:
            raise ValueError("a within-limit band must not reference breach_ids")
        if over_limit and not self.breach_ids:
            raise ValueError("an over-limit band requires at least one breach_id")

        if self.disposition == AllocationBandDisposition.WITHIN_LIMIT:
            if over_limit:
                raise ValueError("WITHIN_LIMIT band must not exceed its allowed maximum")
            if (
                self.target_min_weight_pct != self.current_weight_pct
                or self.target_max_weight_pct != self.current_weight_pct
            ):
                raise ValueError("WITHIN_LIMIT band target must equal current weight")
        elif self.disposition == AllocationBandDisposition.OVER_LIMIT:
            if not over_limit:
                raise ValueError("OVER_LIMIT band must exceed its allowed maximum")
            if self.target_min_weight_pct != Decimal("0"):
                raise ValueError("OVER_LIMIT band target minimum must be zero")
            if self.target_max_weight_pct != self.allowed_max_weight_pct:
                raise ValueError("OVER_LIMIT band target maximum must equal its limit")
        elif self.disposition == AllocationBandDisposition.UNRESOLVED:
            expected_max = min(self.current_weight_pct, self.allowed_max_weight_pct)
            expected_min = Decimal("0") if over_limit else self.current_weight_pct
            if (
                self.target_min_weight_pct != expected_min
                or self.target_max_weight_pct != expected_max
            ):
                raise ValueError(
                    "UNRESOLVED band target must expose the bounded review interval"
                )
        return self


class ConstraintImpact(ContractModel):
    """A before/after comparison for one constraint, without redistribution."""

    schema_version: Literal["constraint-impact.v1"] = "constraint-impact.v1"
    impact_id: NonEmptyStr
    band_id: NonEmptyStr
    owner_id: NonEmptyStr
    dimension: AllocationBandDimension
    target_id: NonEmptyStr
    before_weight_pct: Percentage = Field(ge=Decimal("0"), le=Decimal("100"))
    after_weight_pct: Percentage = Field(ge=Decimal("0"), le=Decimal("100"))
    reduction_pct_points: Percentage = Field(
        ge=Decimal("0"), le=Decimal("100")
    )
    breach_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_impact(self) -> Self:
        if self.after_weight_pct > self.before_weight_pct:
            raise ValueError("after_weight_pct must not exceed before_weight_pct")
        expected_reduction = self.before_weight_pct - self.after_weight_pct
        if self.reduction_pct_points != expected_reduction:
            raise ValueError(
                "reduction_pct_points must equal before minus after weight"
            )
        if len(set(self.breach_ids)) != len(self.breach_ids):
            raise ValueError("impact breach_ids must not contain duplicates")
        return self


class AllocationEnvelope(ContractModel):
    """Closed allocation constraint view for one profile and snapshot."""

    schema_version: Literal["allocation-envelope.v1"] = "allocation-envelope.v1"
    envelope_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    profile_version: int = Field(ge=1)
    risk_level: RiskLevel
    budget_id: NonEmptyStr
    assessment_id: NonEmptyStr
    concentration_report_id: NonEmptyStr
    exposure_report_id: NonEmptyStr
    calculated_at: datetime
    status: AllocationStatus
    bands: tuple[AllocationBand, ...] = Field(min_length=1)
    impacts: tuple[ConstraintImpact, ...] = Field(min_length=1)
    invalidation_conditions: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_envelope(self) -> Self:
        if self.calculated_at.tzinfo is None or self.calculated_at.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")
        band_ids = [band.band_id for band in self.bands]
        if len(set(band_ids)) != len(band_ids):
            raise ValueError("bands must not contain duplicate band_id")
        impact_ids = [impact.impact_id for impact in self.impacts]
        if len(set(impact_ids)) != len(impact_ids):
            raise ValueError("impacts must not contain duplicate impact_id")
        bands_by_id = {band.band_id: band for band in self.bands}
        impact_band_ids = [impact.band_id for impact in self.impacts]
        if len(set(impact_band_ids)) != len(impact_band_ids):
            raise ValueError("each band must have at most one impact")
        if set(impact_band_ids) != set(band_ids):
            raise ValueError("impacts must close over all envelope bands")
        if any(band.owner_id != self.owner_id for band in self.bands):
            raise ValueError("band owner_id does not match envelope owner_id")
        for impact in self.impacts:
            if impact.owner_id != self.owner_id:
                raise ValueError("impact owner_id does not match envelope owner_id")
            band = bands_by_id.get(impact.band_id)
            if band is None:
                raise ValueError("impact references unknown band_id")
            if impact.dimension != band.dimension or impact.target_id != band.target_id:
                raise ValueError("impact target does not match its band")
            if impact.before_weight_pct != band.current_weight_pct:
                raise ValueError("impact before weight does not match its band")
            if impact.after_weight_pct != band.target_max_weight_pct:
                raise ValueError("impact after weight does not match its band")
            if impact.reduction_pct_points != band.minimum_reduction_pct:
                raise ValueError("impact reduction does not match its band")
            if impact.breach_ids != band.breach_ids:
                raise ValueError("impact breach IDs do not match its band")

        if self.status == AllocationStatus.READY:
            if any(
                band.disposition != AllocationBandDisposition.WITHIN_LIMIT
                for band in self.bands
            ):
                raise ValueError("READY envelope must contain only within-limit bands")
            if any(impact.reduction_pct_points != Decimal("0") for impact in self.impacts):
                raise ValueError("READY envelope must not contain reductions")
        elif self.status == AllocationStatus.REVIEW_REQUIRED:
            if not any(
                band.disposition
                in {
                    AllocationBandDisposition.OVER_LIMIT,
                    AllocationBandDisposition.UNRESOLVED,
                }
                for band in self.bands
            ):
                raise ValueError("review envelope must expose an over-limit or unresolved band")
        elif self.status == AllocationStatus.BLOCKED:
            raise ValueError("BLOCKED envelopes must be represented by AllocationResult")
        return self


class AllocationIssue(ContractModel):
    code: AllocationIssueCode
    safe_message: NonEmptyStr


class AllocationResult(ContractModel):
    """Three-state result for a constraint envelope calculation."""

    schema_version: Literal["allocation-result.v1"] = "allocation-result.v1"
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    calculated_at: datetime
    status: AllocationStatus
    envelope: AllocationEnvelope | None = None
    issues: tuple[AllocationIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.calculated_at.tzinfo is None or self.calculated_at.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")
        if self.envelope is not None:
            if self.envelope.owner_id != self.owner_id:
                raise ValueError("envelope owner_id does not match result owner_id")
            if self.envelope.profile_id != self.profile_id:
                raise ValueError("envelope profile_id does not match result profile_id")
            if self.envelope.calculated_at != self.calculated_at:
                raise ValueError("envelope calculated_at does not match result")
            if self.envelope.status != self.status:
                raise ValueError("envelope status does not match result status")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("issues must not contain duplicate code")

        if self.status == AllocationStatus.READY:
            if self.envelope is None or self.issues:
                raise ValueError("READY allocation requires an envelope and no issues")
        elif self.status == AllocationStatus.REVIEW_REQUIRED:
            if self.envelope is None or not self.issues:
                raise ValueError(
                    "REVIEW_REQUIRED allocation requires an envelope and issue"
                )
        elif self.status == AllocationStatus.BLOCKED:
            if self.envelope is not None or not self.issues:
                raise ValueError("BLOCKED allocation requires issues and no envelope")
        return self
