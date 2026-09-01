"""Immutable concentration and profile-conditioned risk-budget contracts."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.profile.contracts import RiskLevel


Percentage = Annotated[
    Decimal,
    Field(ge=Decimal("0"), le=Decimal("100")),
]
NonNegativeDecimal = Annotated[
    Decimal,
    Field(ge=Decimal("0")),
]


class ConcentrationDimension(StrEnum):
    ASSET = "ASSET"
    SECTOR = "SECTOR"


class ConcentrationStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class ConcentrationIssueCode(StrEnum):
    UPSTREAM_PARTIAL = "UPSTREAM_PARTIAL"
    UPSTREAM_FAILED = "UPSTREAM_FAILED"


class ConcentrationGroup(ContractModel):
    """One deterministic asset or sector aggregation group."""

    group_id: NonEmptyStr
    owner_id: NonEmptyStr
    dimension: ConcentrationDimension
    key: NonEmptyStr
    label: NonEmptyStr
    market_value: NonNegativeDecimal
    weight_pct: Percentage
    contribution_ids: tuple[NonEmptyStr, ...] = Field(min_length=1)
    is_unclassified: bool = False

    @model_validator(mode="after")
    def validate_group(self) -> Self:
        if len(set(self.contribution_ids)) != len(self.contribution_ids):
            raise ValueError("contribution_ids must not contain duplicates")
        expected_unclassified = (
            self.dimension == ConcentrationDimension.SECTOR
            and self.key == "UNCLASSIFIED"
        )
        if self.is_unclassified != expected_unclassified:
            raise ValueError("is_unclassified does not match group dimension/key")
        return self


class ConcentrationReport(ContractModel):
    """Closed asset/sector concentration view of one exposure report."""

    schema_version: Literal["concentration-report.v1"] = "concentration-report.v1"
    report_id: NonEmptyStr
    exposure_report_id: NonEmptyStr
    owner_id: NonEmptyStr
    bundle_id: NonEmptyStr
    calculated_at: datetime
    base_currency: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            to_upper=True,
            min_length=3,
            max_length=3,
            pattern=r"^[A-Za-z]{3}$",
        ),
    ]
    total_market_value: Decimal = Field(gt=Decimal("0"))
    asset_groups: tuple[ConcentrationGroup, ...] = Field(min_length=1)
    sector_groups: tuple[ConcentrationGroup, ...] = Field(min_length=1)
    top_asset_group_id: NonEmptyStr
    top_asset_weight_pct: Percentage
    top_sector_group_id: NonEmptyStr
    top_sector_weight_pct: Percentage
    asset_hhi: Decimal = Field(ge=Decimal("0"), le=Decimal("10000"))
    sector_hhi: Decimal = Field(ge=Decimal("0"), le=Decimal("10000"))
    unclassified_market_value: Decimal = Field(ge=Decimal("0"))
    unclassified_weight_pct: Percentage
    technology_market_value: Decimal = Field(ge=Decimal("0"))
    technology_weight_pct: Percentage
    source_exposure_status: Literal["COMPLETE", "PARTIAL"]

    @model_validator(mode="after")
    def validate_report(self) -> Self:
        if self.calculated_at.tzinfo is None or self.calculated_at.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")

        groups = self.asset_groups + self.sector_groups
        if any(group.owner_id != self.owner_id for group in groups):
            raise ValueError("group owner_id does not match report owner_id")
        group_ids = [group.group_id for group in groups]
        if len(set(group_ids)) != len(group_ids):
            raise ValueError("groups must not contain duplicate group_id")
        for name, dimension_groups in (
            ("asset", self.asset_groups),
            ("sector", self.sector_groups),
        ):
            group_keys = [group.key for group in dimension_groups]
            if len(set(group_keys)) != len(group_keys):
                raise ValueError(f"{name} groups must not contain duplicate keys")
        if any(
            group.dimension != ConcentrationDimension.ASSET
            for group in self.asset_groups
        ):
            raise ValueError("asset_groups must contain only ASSET groups")
        if any(
            group.dimension != ConcentrationDimension.SECTOR
            for group in self.sector_groups
        ):
            raise ValueError("sector_groups must contain only SECTOR groups")

        for name, dimension_groups in (
            ("asset", self.asset_groups),
            ("sector", self.sector_groups),
        ):
            group_total = sum(
                (group.market_value for group in dimension_groups),
                Decimal("0"),
            )
            if group_total != self.total_market_value:
                raise ValueError(
                    f"{name} group market values must close total_market_value"
                )
            for group in dimension_groups:
                expected_weight = _percentage_of(
                    group.market_value, self.total_market_value
                )
                if group.weight_pct != expected_weight:
                    raise ValueError(
                        f"group {group.group_id!r} has an invalid weight_pct"
                    )

        ordered_assets = _order_groups(self.asset_groups)
        ordered_sectors = _order_groups(self.sector_groups)
        if self.top_asset_group_id != ordered_assets[0].group_id:
            raise ValueError("top_asset_group_id does not match deterministic ordering")
        if self.top_asset_weight_pct != ordered_assets[0].weight_pct:
            raise ValueError("top_asset_weight_pct does not match top asset group")
        if self.top_sector_group_id != ordered_sectors[0].group_id:
            raise ValueError("top_sector_group_id does not match deterministic ordering")
        if self.top_sector_weight_pct != ordered_sectors[0].weight_pct:
            raise ValueError("top_sector_weight_pct does not match top sector group")

        expected_asset_hhi = _hhi(self.asset_groups, self.total_market_value)
        expected_sector_hhi = _hhi(self.sector_groups, self.total_market_value)
        if self.asset_hhi != expected_asset_hhi:
            raise ValueError("asset_hhi does not match group market values")
        if self.sector_hhi != expected_sector_hhi:
            raise ValueError("sector_hhi does not match group market values")

        unclassified = sum(
            (
                group.market_value
                for group in self.sector_groups
                if group.is_unclassified
            ),
            Decimal("0"),
        )
        if unclassified != self.unclassified_market_value:
            raise ValueError("unclassified_market_value does not match sector groups")
        if self.unclassified_weight_pct != _percentage_of(
            self.unclassified_market_value, self.total_market_value
        ):
            raise ValueError("unclassified_weight_pct does not match market values")
        if self.technology_weight_pct != _percentage_of(
            self.technology_market_value, self.total_market_value
        ):
            raise ValueError("technology_weight_pct does not match market values")
        return self


class ConcentrationIssue(ContractModel):
    """Safe explanation for incomplete or unavailable concentration data."""

    code: ConcentrationIssueCode
    safe_message: NonEmptyStr


class ConcentrationResult(ContractModel):
    """Three-state concentration result preserving upstream data quality."""

    schema_version: Literal["concentration-result.v1"] = "concentration-result.v1"
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    bundle_id: NonEmptyStr
    status: ConcentrationStatus
    calculated_at: datetime
    report: ConcentrationReport | None = None
    issues: tuple[ConcentrationIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result(self) -> Self:
        if self.calculated_at.tzinfo is None or self.calculated_at.utcoffset() is None:
            raise ValueError("calculated_at must be timezone-aware")
        if self.report is not None:
            if self.report.owner_id != self.owner_id:
                raise ValueError("report owner_id does not match result owner_id")
            if self.report.bundle_id != self.bundle_id:
                raise ValueError("report bundle_id does not match result bundle_id")
        if self.status == ConcentrationStatus.COMPLETE:
            if self.report is None:
                raise ValueError("COMPLETE concentration requires a report")
            if self.issues:
                raise ValueError("COMPLETE concentration must not carry issues")
            if self.report.source_exposure_status != "COMPLETE":
                raise ValueError("COMPLETE concentration requires complete exposure")
        elif self.status == ConcentrationStatus.PARTIAL:
            if self.report is None:
                raise ValueError("PARTIAL concentration requires a report")
            if not self.issues:
                raise ValueError("PARTIAL concentration requires at least one issue")
        elif self.status == ConcentrationStatus.FAILED:
            if self.report is not None:
                raise ValueError("FAILED concentration must not carry a report")
            if not self.issues:
                raise ValueError("FAILED concentration requires at least one issue")
        return self


class BudgetBreachKind(StrEnum):
    SINGLE_ASSET = "SINGLE_ASSET"
    SECTOR = "SECTOR"
    TECHNOLOGY = "TECHNOLOGY"
    UNCLASSIFIED = "UNCLASSIFIED"


class BudgetAssessmentStatus(StrEnum):
    PASS = "PASS"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class BudgetIssueCode(StrEnum):
    CONCENTRATION_PARTIAL = "CONCENTRATION_PARTIAL"
    CONCENTRATION_FAILED = "CONCENTRATION_FAILED"


class RiskBudget(ContractModel):
    """Versioned fixed limits selected from a confirmed risk profile."""

    schema_version: Literal["risk-budget.v1"] = "risk-budget.v1"
    budget_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    profile_version: int = Field(ge=1)
    risk_level: RiskLevel
    max_single_asset_weight_pct: Percentage
    max_sector_weight_pct: Percentage
    max_technology_weight_pct: Percentage
    max_unclassified_weight_pct: Percentage
    max_drawdown_tolerance_pct: Percentage

    @model_validator(mode="after")
    def validate_rules(self) -> Self:
        expected = _RISK_BUDGET_RULES[self.risk_level]
        actual = (
            self.max_single_asset_weight_pct,
            self.max_sector_weight_pct,
            self.max_technology_weight_pct,
            self.max_unclassified_weight_pct,
        )
        if actual != expected:
            raise ValueError("risk budget limits do not match risk-budget.v1 rules")
        return self


class RiskBudgetBreach(ContractModel):
    """One explicit budget exceedance, never an implied trade instruction."""

    breach_id: NonEmptyStr
    owner_id: NonEmptyStr
    kind: BudgetBreachKind
    target_id: NonEmptyStr | None = None
    observed_weight_pct: Percentage
    limit_weight_pct: Percentage
    excess_weight_pct: Percentage

    @model_validator(mode="after")
    def validate_breach(self) -> Self:
        if self.kind in {BudgetBreachKind.SINGLE_ASSET, BudgetBreachKind.SECTOR}:
            if self.target_id is None:
                raise ValueError("asset/sector breach requires target_id")
        elif self.target_id is not None:
            raise ValueError("technology/unclassified breach must not have target_id")
        expected_excess = self.observed_weight_pct - self.limit_weight_pct
        if expected_excess <= Decimal("0"):
            raise ValueError("breach must exceed its limit")
        if self.excess_weight_pct != expected_excess:
            raise ValueError("excess_weight_pct does not match observed and limit")
        return self


class RiskBudgetIssue(ContractModel):
    code: BudgetIssueCode
    safe_message: NonEmptyStr


class RiskBudgetAssessment(ContractModel):
    """Profile-conditioned constraint assessment without optimization."""

    schema_version: Literal["risk-budget-assessment.v1"] = (
        "risk-budget-assessment.v1"
    )
    assessment_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    exposure_report_id: NonEmptyStr | None = None
    concentration_report_id: NonEmptyStr | None = None
    assessed_at: datetime
    status: BudgetAssessmentStatus
    budget: RiskBudget
    breaches: tuple[RiskBudgetBreach, ...] = Field(default_factory=tuple)
    issues: tuple[RiskBudgetIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_assessment(self) -> Self:
        if self.assessed_at.tzinfo is None or self.assessed_at.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware")
        if self.budget.owner_id != self.owner_id:
            raise ValueError("budget owner_id does not match assessment owner_id")
        if self.budget.profile_id != self.profile_id:
            raise ValueError("budget profile_id does not match assessment profile_id")
        if any(breach.owner_id != self.owner_id for breach in self.breaches):
            raise ValueError("breach owner_id does not match assessment owner_id")
        breach_ids = [breach.breach_id for breach in self.breaches]
        if len(set(breach_ids)) != len(breach_ids):
            raise ValueError("breaches must not contain duplicate breach_id")

        if self.status == BudgetAssessmentStatus.PASS:
            if self.exposure_report_id is None or self.concentration_report_id is None:
                raise ValueError("PASS assessment requires report identities")
            if self.breaches or self.issues:
                raise ValueError("PASS assessment must not carry breaches or issues")
        elif self.status == BudgetAssessmentStatus.REVIEW_REQUIRED:
            if self.exposure_report_id is None or self.concentration_report_id is None:
                raise ValueError("REVIEW_REQUIRED assessment requires report identities")
            if not self.breaches and not self.issues:
                raise ValueError("REVIEW_REQUIRED assessment requires a breach or issue")
        elif self.status == BudgetAssessmentStatus.BLOCKED:
            if self.exposure_report_id is not None or self.concentration_report_id is not None:
                raise ValueError("BLOCKED assessment must not carry usable report identities")
            if self.breaches or not self.issues:
                raise ValueError("BLOCKED assessment requires issues and no breaches")
        return self


def _percentage_of(value: Decimal, total: Decimal) -> Decimal:
    if total <= Decimal("0"):
        return Decimal("0.00")
    return (value / total * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _hhi(groups: tuple[ConcentrationGroup, ...], total: Decimal) -> Decimal:
    raw = sum(
        ((group.market_value / total) ** 2 for group in groups),
        Decimal("0"),
    ) * Decimal("10000")
    return raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _order_groups(
    groups: tuple[ConcentrationGroup, ...],
) -> tuple[ConcentrationGroup, ...]:
    return tuple(sorted(groups, key=lambda group: (-group.market_value, group.group_id)))


_RISK_BUDGET_RULES = {
    RiskLevel.CONSERVATIVE: (
        Decimal("20"),
        Decimal("30"),
        Decimal("25"),
        Decimal("10"),
    ),
    RiskLevel.BALANCED: (
        Decimal("35"),
        Decimal("45"),
        Decimal("40"),
        Decimal("20"),
    ),
    RiskLevel.GROWTH: (
        Decimal("50"),
        Decimal("60"),
        Decimal("60"),
        Decimal("35"),
    ),
}
