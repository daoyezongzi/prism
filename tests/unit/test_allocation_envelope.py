import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.allocation import (
    AllocationBand,
    AllocationBandDimension,
    AllocationBandDisposition,
    AllocationIssueCode,
    AllocationStatus,
    build_allocation_envelope,
)
from app.portfolio import (
    AssetType,
    ExposureIssue,
    ExposureIssueCode,
    ExposureResult,
    ExposureStatus,
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
    assess_risk_budget,
    calculate_concentration,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
FIXTURES = Path(__file__).parents[1] / "fixtures"


def make_profile(
    level: RiskLevel,
    *,
    owner_id: str = "allocation-owner-001",
    profile_id: str | None = None,
) -> RiskProfile:
    score = {
        RiskLevel.CONSERVATIVE: Decimal("25"),
        RiskLevel.BALANCED: Decimal("50"),
        RiskLevel.GROWTH: Decimal("75"),
    }[level]
    return RiskProfile(
        profile_id=profile_id or f"allocation-profile-{level.value.lower()}",
        owner_id=owner_id,
        profile_version=1,
        questionnaire_id="allocation-questionnaire-001",
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


def make_complete_bundle() -> PortfolioImportBundle:
    position = Position(
        position_id="allocation-position-fund-001",
        owner_id="allocation-owner-001",
        asset_id="allocation-fund-001",
        asset_type=AssetType.ETF,
        asset_name="Synthetic Allocation ETF",
        quantity=Decimal("1"),
        market_value=Decimal("1000"),
        currency="CNY",
        as_of=datetime(2026, 8, 31, 16, 0, tzinfo=UTC),
        source="synthetic-allocation",
    )
    holdings = tuple(
        LookThroughHolding(
            holding_id=f"allocation-holding-{sector.lower()}",
            parent_asset_id=position.asset_id,
            underlying_asset_id=f"allocation-{sector.lower()}-asset",
            underlying_name=f"Synthetic {sector} Asset",
            asset_type=AssetType.STOCK,
            weight_pct=Decimal(weight),
            sector=sector,
            as_of=position.as_of,
            source="synthetic-allocation",
        )
        for sector, weight in (
            ("Technology", "30"),
            ("Healthcare", "35"),
            ("Finance", "35"),
        )
    )
    return PortfolioImportBundle(
        bundle_id="allocation-bundle-complete-001",
        owner_id=position.owner_id,
        created_at=NOW,
        position_snapshot=PositionSnapshot(
            snapshot_id="allocation-position-snapshot-001",
            owner_id=position.owner_id,
            as_of=position.as_of,
            base_currency="CNY",
            source="synthetic-allocation",
            positions=(position,),
        ),
        fund_holdings=(
            FundHoldingSnapshot(
                snapshot_id="allocation-holdings-snapshot-001",
                owner_id=position.owner_id,
                parent_asset_id=position.asset_id,
                parent_asset_type=position.asset_type,
                as_of=position.as_of,
                source="synthetic-allocation",
                coverage_pct=Decimal("100"),
                holdings=holdings,
            ),
        ),
    )


def load_partial_pipeline():
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
    return profile, exposure, concentration, assessment


def run_pipeline(profile: RiskProfile, bundle: PortfolioImportBundle):
    exposure = calculate_exposure(bundle)
    concentration = calculate_concentration(exposure)
    assessment = assess_risk_budget(profile, concentration)
    result = build_allocation_envelope(profile, exposure, concentration, assessment)
    return exposure, concentration, assessment, result


def test_complete_balanced_envelope_is_ready_and_zero_impact() -> None:
    _, _, assessment, result = run_pipeline(
        make_profile(RiskLevel.BALANCED), make_complete_bundle()
    )
    assert assessment.status == BudgetAssessmentStatus.PASS
    assert result.status == AllocationStatus.READY
    assert result.envelope is not None
    assert all(
        band.disposition == AllocationBandDisposition.WITHIN_LIMIT
        for band in result.envelope.bands
    )
    assert all(
        impact.reduction_pct_points == Decimal("0")
        for impact in result.envelope.impacts
    )
    assert not hasattr(result.envelope, "recommendation")


def test_complete_conservative_envelope_exposes_over_limit_constraints() -> None:
    _, _, assessment, result = run_pipeline(
        make_profile(RiskLevel.CONSERVATIVE), make_complete_bundle()
    )
    assert assessment.status == BudgetAssessmentStatus.REVIEW_REQUIRED
    assert result.status == AllocationStatus.REVIEW_REQUIRED
    assert result.envelope is not None
    over_limit = [
        band
        for band in result.envelope.bands
        if band.disposition == AllocationBandDisposition.OVER_LIMIT
    ]
    assert over_limit
    for band in over_limit:
        assert band.target_max_weight_pct == band.allowed_max_weight_pct
        assert band.minimum_reduction_pct > Decimal("0")
    assert any(
        band.dimension == AllocationBandDimension.TECHNOLOGY for band in over_limit
    )


def test_same_exposure_changes_with_profile_limits() -> None:
    _, _, _, conservative = run_pipeline(
        make_profile(RiskLevel.CONSERVATIVE), make_complete_bundle()
    )
    _, _, _, growth = run_pipeline(
        make_profile(RiskLevel.GROWTH), make_complete_bundle()
    )
    assert conservative.envelope is not None
    assert growth.status == AllocationStatus.READY
    conservative_asset = next(
        band
        for band in conservative.envelope.bands
        if band.dimension == AllocationBandDimension.ASSET
        and band.target_id == "allocation-technology-asset"
    )
    growth_asset = next(
        band
        for band in growth.envelope.bands
        if band.dimension == AllocationBandDimension.ASSET
        and band.target_id == "allocation-technology-asset"
    )
    assert conservative_asset.allowed_max_weight_pct == Decimal("20")
    assert growth_asset.allowed_max_weight_pct == Decimal("50")
    assert conservative_asset.disposition == AllocationBandDisposition.OVER_LIMIT
    assert growth_asset.disposition == AllocationBandDisposition.WITHIN_LIMIT


def test_partial_input_is_unresolved_and_never_ready() -> None:
    profile, exposure, concentration, assessment = load_partial_pipeline()
    result = build_allocation_envelope(profile, exposure, concentration, assessment)
    assert result.status == AllocationStatus.REVIEW_REQUIRED
    assert result.issues[0].code == AllocationIssueCode.BUDGET_REVIEW_REQUIRED
    assert result.envelope is not None
    assert all(
        band.disposition == AllocationBandDisposition.UNRESOLVED
        for band in result.envelope.bands
    )


def test_failed_upstream_is_blocked_without_zero_value_envelope() -> None:
    failed = ExposureResult(
        request_id="allocation-failed-request",
        owner_id="allocation-owner-001",
        bundle_id="allocation-failed-bundle",
        status=ExposureStatus.FAILED,
        calculated_at=NOW,
        issues=(
            ExposureIssue(
                code=ExposureIssueCode.NON_BASE_CURRENCY,
                safe_message="base-currency value unavailable",
            ),
        ),
    )
    concentration = calculate_concentration(failed)
    assessment = assess_risk_budget(make_profile(RiskLevel.BALANCED), concentration)
    result = build_allocation_envelope(
        make_profile(RiskLevel.BALANCED), failed, concentration, assessment
    )
    assert result.status == AllocationStatus.BLOCKED
    assert result.envelope is None
    assert result.issues[0].code == AllocationIssueCode.BUDGET_BLOCKED


def test_input_order_does_not_change_envelope() -> None:
    profile = make_profile(RiskLevel.BALANCED)
    bundle = make_complete_bundle()
    first = run_pipeline(profile, bundle)[-1]
    snapshot = bundle.fund_holdings[0]
    reordered_snapshot = snapshot.model_copy(
        update={"holdings": tuple(reversed(snapshot.holdings))}
    )
    reordered_bundle = bundle.model_copy(
        update={"fund_holdings": (reordered_snapshot,)}
    )
    second = run_pipeline(profile, reordered_bundle)[-1]
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_tampered_assessment_breach_is_rejected() -> None:
    _, _, assessment, _ = run_pipeline(
        make_profile(RiskLevel.CONSERVATIVE), make_complete_bundle()
    )
    assert assessment.breaches
    tampered_breach = assessment.breaches[0].model_copy(
        update={"observed_weight_pct": Decimal("99")}
    )
    tampered_assessment = assessment.model_copy(
        update={"breaches": (tampered_breach,) + assessment.breaches[1:]}
    )
    profile = make_profile(RiskLevel.CONSERVATIVE)
    exposure = calculate_exposure(make_complete_bundle())
    concentration = calculate_concentration(exposure)
    with pytest.raises(ValueError, match="stale"):
        build_allocation_envelope(profile, exposure, concentration, tampered_assessment)


def test_pass_assessment_cannot_hide_observed_breach() -> None:
    profile = make_profile(RiskLevel.CONSERVATIVE)
    exposure, concentration, assessment, _ = run_pipeline(profile, make_complete_bundle())
    tampered = assessment.model_copy(update={"status": BudgetAssessmentStatus.PASS, "breaches": (), "issues": ()})
    with pytest.raises(ValueError, match="breaches do not match"):
        build_allocation_envelope(profile, exposure, concentration, tampered)


def test_owner_mismatch_and_contract_tampering_are_rejected() -> None:
    profile = make_profile(RiskLevel.BALANCED)
    exposure, concentration, assessment, result = run_pipeline(
        profile, make_complete_bundle()
    )
    assert result.envelope is not None
    band = result.envelope.bands[0]
    with pytest.raises(ValueError, match="profile owner_id"):
        build_allocation_envelope(
            make_profile(RiskLevel.BALANCED, owner_id="other-owner"),
            exposure,
            concentration,
            assessment,
        )
    payload = band.model_dump(mode="python")
    payload["target_max_weight_pct"] = Decimal("99")
    with pytest.raises(ValidationError, match="target"):
        AllocationBand.model_validate(payload)
    with pytest.raises((TypeError, ValidationError)):
        band.current_weight_pct = Decimal("1")


def test_envelope_requires_one_impact_for_every_band() -> None:
    profile = make_profile(RiskLevel.BALANCED)
    _, _, _, result = run_pipeline(profile, make_complete_bundle())
    assert result.envelope is not None
    payload = result.envelope.model_dump(mode="python")
    payload["impacts"] = payload["impacts"][:-1]
    with pytest.raises(ValidationError, match="close over all envelope bands"):
        type(result.envelope).model_validate(payload)
