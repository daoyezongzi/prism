import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.portfolio import (
    AssetType,
    FundHoldingSnapshot,
    LookThroughHolding,
    PortfolioImportBundle,
    Position,
    PositionSnapshot,
    calculate_exposure,
)
from app.profile import (
    ExperienceLevel,
    InvestmentHorizon,
    LiquidityNeed,
    ReturnExpectation,
    RiskLevel,
    RiskProfile,
)
from app.risk import (
    BudgetAssessmentStatus,
    BudgetBreachKind,
    BudgetIssueCode,
    RiskBudget,
    assess_risk_budget,
    build_risk_budget,
    calculate_concentration,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
EXPOSURE_FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "portfolio"
    / "portfolio_exposure_bundle.json"
)


def make_profile(
    level: RiskLevel,
    *,
    owner_id: str = "fixture-exposure-owner-001",
    profile_id: str | None = None,
) -> RiskProfile:
    score = {
        RiskLevel.CONSERVATIVE: Decimal("25"),
        RiskLevel.BALANCED: Decimal("50"),
        RiskLevel.GROWTH: Decimal("75"),
    }[level]
    return RiskProfile(
        profile_id=profile_id or f"profile-{level.value.lower()}",
        owner_id=owner_id,
        profile_version=1,
        questionnaire_id="questionnaire-risk-budget",
        created_at=NOW,
        risk_score=score,
        risk_level=level,
        investment_horizon=InvestmentHorizon.MEDIUM,
        liquidity_need=LiquidityNeed.MEDIUM,
        experience_level=ExperienceLevel.INTERMEDIATE,
        return_expectation=ReturnExpectation.MODERATE,
        max_drawdown_tolerance_pct=Decimal("20"),
        confidence=Decimal("1"),
    )


def load_concentration():
    bundle = PortfolioImportBundle.model_validate(
        json.loads(EXPOSURE_FIXTURE.read_text())
    )
    return calculate_concentration(calculate_exposure(bundle))


def make_complete_concentration(*, technology_weight: str = "33"):
    positions = Position(
        position_id="position-complete-budget-001",
        owner_id="budget-owner-001",
        asset_id="FUND_COMPLETE_BUDGET",
        asset_type=AssetType.ETF,
        asset_name="Synthetic Complete ETF",
        quantity=Decimal("1"),
        market_value=Decimal("1000"),
        currency="CNY",
        as_of=datetime(2026, 8, 31, 16, 0, tzinfo=UTC),
        source="synthetic",
    )
    tech = Decimal(technology_weight)
    holdings = (
        LookThroughHolding(
            holding_id="holding-complete-tech",
            parent_asset_id="FUND_COMPLETE_BUDGET",
            underlying_asset_id="STOCK_COMPLETE_TECH",
            underlying_name="Synthetic Technology Stock",
            asset_type=AssetType.STOCK,
            weight_pct=tech,
            sector="Technology",
            as_of=positions.as_of,
            source="synthetic",
        ),
        LookThroughHolding(
            holding_id="holding-complete-health",
            parent_asset_id="FUND_COMPLETE_BUDGET",
            underlying_asset_id="STOCK_COMPLETE_HEALTH",
            underlying_name="Synthetic Health Stock",
            asset_type=AssetType.STOCK,
            weight_pct=(Decimal("100") - tech) / Decimal("2"),
            sector="Healthcare",
            as_of=positions.as_of,
            source="synthetic",
        ),
        LookThroughHolding(
            holding_id="holding-complete-finance",
            parent_asset_id="FUND_COMPLETE_BUDGET",
            underlying_asset_id="STOCK_COMPLETE_FINANCE",
            underlying_name="Synthetic Finance Stock",
            asset_type=AssetType.STOCK,
            weight_pct=(Decimal("100") - tech) / Decimal("2"),
            sector="Finance",
            as_of=positions.as_of,
            source="synthetic",
        ),
    )
    bundle = PortfolioImportBundle(
        bundle_id="bundle-complete-budget-001",
        owner_id="budget-owner-001",
        created_at=NOW,
        position_snapshot=PositionSnapshot(
            snapshot_id="snapshot-complete-budget-001",
            owner_id="budget-owner-001",
            as_of=positions.as_of,
            base_currency="CNY",
            source="synthetic",
            positions=(positions,),
        ),
        fund_holdings=(
            FundHoldingSnapshot(
                snapshot_id="holdings-complete-budget-001",
                owner_id="budget-owner-001",
                parent_asset_id=positions.asset_id,
                parent_asset_type=positions.asset_type,
                as_of=positions.as_of,
                source="synthetic",
                coverage_pct=Decimal("100"),
                holdings=holdings,
            ),
        ),
    )
    return calculate_concentration(calculate_exposure(bundle))


def test_budget_rules_are_fixed_and_differ_by_risk_level() -> None:
    conservative = build_risk_budget(make_profile(RiskLevel.CONSERVATIVE))
    balanced = build_risk_budget(make_profile(RiskLevel.BALANCED))
    growth = build_risk_budget(make_profile(RiskLevel.GROWTH))
    assert conservative.max_single_asset_weight_pct == Decimal("20")
    assert balanced.max_single_asset_weight_pct == Decimal("35")
    assert growth.max_single_asset_weight_pct == Decimal("50")
    assert conservative.max_unclassified_weight_pct < growth.max_unclassified_weight_pct
    assert conservative.max_drawdown_tolerance_pct == Decimal("20")


def test_partial_concentration_never_passes_budget_assessment() -> None:
    concentration = load_concentration()
    assessment = assess_risk_budget(make_profile(RiskLevel.GROWTH), concentration)
    assert assessment.status == BudgetAssessmentStatus.REVIEW_REQUIRED
    assert any(
        issue.code == BudgetIssueCode.CONCENTRATION_PARTIAL
        for issue in assessment.issues
    )
    assert assessment.exposure_report_id is not None
    assert assessment.concentration_report_id is not None


def test_complete_concentration_within_limits_can_pass() -> None:
    concentration = make_complete_concentration()
    assert concentration.status.value == "COMPLETE"
    assessment = assess_risk_budget(
        make_profile(RiskLevel.BALANCED, owner_id="budget-owner-001"),
        concentration,
    )
    assert assessment.status == BudgetAssessmentStatus.PASS
    assert assessment.breaches == ()
    assert assessment.issues == ()


def test_technology_and_known_sector_breaches_are_explicit() -> None:
    concentration = make_complete_concentration(technology_weight="70")
    assessment = assess_risk_budget(
        make_profile(RiskLevel.CONSERVATIVE, owner_id="budget-owner-001"),
        concentration,
    )
    kinds = {breach.kind for breach in assessment.breaches}
    assert BudgetBreachKind.TECHNOLOGY in kinds
    assert BudgetBreachKind.SECTOR in kinds
    assert BudgetBreachKind.SINGLE_ASSET in kinds


def test_same_exposure_has_profile_conditioned_breach_differences() -> None:
    concentration = load_concentration()
    conservative = assess_risk_budget(make_profile(RiskLevel.CONSERVATIVE), concentration)
    growth = assess_risk_budget(make_profile(RiskLevel.GROWTH), concentration)
    conservative_kinds = {breach.kind for breach in conservative.breaches}
    growth_kinds = {breach.kind for breach in growth.breaches}
    assert BudgetBreachKind.UNCLASSIFIED in conservative_kinds
    assert len(conservative.breaches) > len(growth.breaches)
    assert growth_kinds.issubset(conservative_kinds)
    assert conservative.budget.max_unclassified_weight_pct < growth.budget.max_unclassified_weight_pct


def test_owner_mismatch_and_tampered_budget_are_rejected() -> None:
    concentration = load_concentration()
    with pytest.raises(ValueError, match="owner_id"):
        assess_risk_budget(
            make_profile(RiskLevel.BALANCED, owner_id="other-owner"), concentration
        )
    budget = build_risk_budget(make_profile(RiskLevel.BALANCED))
    payload = budget.model_dump(mode="python")
    payload["max_single_asset_weight_pct"] = Decimal("99")
    with pytest.raises(ValidationError, match="risk-budget.v1"):
        RiskBudget.model_validate(payload)


def test_blocked_assessment_has_no_recommendation_or_report_identity() -> None:
    from app.portfolio import ExposureIssue, ExposureIssueCode, ExposureResult, ExposureStatus

    failed = ExposureResult(
        request_id="failed",
        owner_id="fixture-exposure-owner-001",
        bundle_id="failed-bundle",
        status=ExposureStatus.FAILED,
        calculated_at=NOW,
        issues=(
            ExposureIssue(
                code=ExposureIssueCode.NON_BASE_CURRENCY,
                safe_message="no base currency value",
            ),
        ),
    )
    blocked = assess_risk_budget(
        make_profile(RiskLevel.CONSERVATIVE),
        calculate_concentration(failed),
    )
    assert blocked.status == BudgetAssessmentStatus.BLOCKED
    assert blocked.exposure_report_id is None
    assert blocked.concentration_report_id is None
    assert not hasattr(blocked, "recommendations")
