from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.portfolio import (
    AssetType,
    ExposureBasis,
    ExposureContribution,
    ExposureIssue,
    ExposureIssueCode,
    ExposureReport,
    ExposureResult,
    ExposureStatus,
    FundHoldingSnapshot,
    LookThroughHolding,
    PortfolioImportBundle,
    Position,
    PositionImportStatus,
    PositionSnapshot,
    calculate_exposure,
)


NOW = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)


def make_position(**overrides: object) -> Position:
    values: dict[str, object] = {
        "position_id": "position-exposure-001",
        "owner_id": "owner-exposure-001",
        "asset_id": "FUND_EXPOSURE_001",
        "asset_type": AssetType.MUTUAL_FUND,
        "asset_name": "Synthetic Fund",
        "quantity": Decimal("100"),
        "market_value": Decimal("10000"),
        "currency": "CNY",
        "as_of": NOW,
        "source": "synthetic",
    }
    values.update(overrides)
    return Position.model_validate(values)


def make_holding(**overrides: object) -> LookThroughHolding:
    values: dict[str, object] = {
        "holding_id": "holding-exposure-001",
        "parent_asset_id": "FUND_EXPOSURE_001",
        "underlying_asset_id": "STOCK_TECH_001",
        "underlying_name": "Synthetic Tech Holding",
        "asset_type": AssetType.STOCK,
        "weight_pct": Decimal("35.5"),
        "sector": "Technology",
        "as_of": NOW,
        "source": "synthetic-fund",
    }
    values.update(overrides)
    return LookThroughHolding.model_validate(values)


def make_bundle(
    *,
    position: Position | None = None,
    holdings: FundHoldingSnapshot | None = None,
    include_holdings: bool = True,
    created_at: datetime = datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
) -> PortfolioImportBundle:
    position = position or make_position()
    snapshot = PositionSnapshot(
        snapshot_id="snapshot-exposure-001",
        owner_id=position.owner_id,
        as_of=NOW,
        base_currency="CNY",
        source="synthetic",
        positions=(position,),
    )
    if include_holdings and holdings is None and position.asset_type in {
        AssetType.ETF,
        AssetType.MUTUAL_FUND,
    }:
        holdings = FundHoldingSnapshot(
            snapshot_id="holdings-exposure-001",
            owner_id=position.owner_id,
            parent_asset_id=position.asset_id,
            parent_asset_type=position.asset_type,
            as_of=NOW,
            source="synthetic-fund",
            coverage_pct=Decimal("80"),
            holdings=(make_holding(),),
        )
    return PortfolioImportBundle(
        bundle_id="bundle-exposure-001",
        owner_id=position.owner_id,
        created_at=created_at,
        position_snapshot=snapshot,
        fund_holdings=(holdings,) if include_holdings and holdings is not None else (),
    )


def test_direct_and_lookthrough_values_use_decimal_and_close_residual() -> None:
    position = make_position()
    bundle = make_bundle(position=position)
    result = calculate_exposure(bundle)
    assert result.status == ExposureStatus.PARTIAL
    assert result.report is not None
    assert result.report.total_market_value == Decimal("10000")
    lookthrough = [
        c for c in result.report.contributions if c.basis == ExposureBasis.LOOK_THROUGH
    ]
    residual = [
        c
        for c in result.report.contributions
        if c.basis == ExposureBasis.UNLOOKED_THROUGH
    ]
    assert lookthrough[0].market_value == Decimal("3550.00")
    assert residual[0].market_value == Decimal("6450.00")
    assert result.report.attributed_market_value == Decimal("3550.00")
    assert result.report.unclassified_market_value == Decimal("6450.00")
    assert result.issues[0].code == ExposureIssueCode.INCOMPLETE_LOOK_THROUGH
    assert sum(c.market_value for c in result.report.contributions) == Decimal("10000")


def test_fully_covered_direct_position_can_be_complete() -> None:
    position = make_position(
        asset_id="STOCK_DIRECT_001",
        asset_type=AssetType.STOCK,
        asset_name="Synthetic Direct Stock",
        market_value=Decimal("100"),
    )
    result = calculate_exposure(make_bundle(position=position, include_holdings=False))
    assert result.status == ExposureStatus.COMPLETE
    assert result.issues == ()
    assert result.report is not None
    assert result.report.unclassified_market_value == Decimal("0")


def test_missing_lookthrough_keeps_parent_as_partial_residual() -> None:
    result = calculate_exposure(make_bundle(include_holdings=False))
    assert result.status == ExposureStatus.PARTIAL
    assert result.report is not None
    assert result.report.contributions[0].basis == ExposureBasis.UNLOOKED_THROUGH
    assert result.report.contributions[0].market_value == Decimal("10000")
    assert result.issues[0].code == ExposureIssueCode.MISSING_LOOK_THROUGH


def test_future_holdings_are_not_used() -> None:
    future = FundHoldingSnapshot(
        snapshot_id="holdings-future-001",
        owner_id="owner-exposure-001",
        parent_asset_id="FUND_EXPOSURE_001",
        parent_asset_type=AssetType.MUTUAL_FUND,
        as_of=datetime(2026, 9, 2, 16, 0, tzinfo=UTC),
        source="synthetic-fund",
        coverage_pct=Decimal("100"),
        holdings=(make_holding(),),
    )
    result = calculate_exposure(make_bundle(holdings=future))
    assert result.status == ExposureStatus.PARTIAL
    assert result.report is not None
    assert all(c.basis != ExposureBasis.LOOK_THROUGH for c in result.report.contributions)
    assert result.issues[0].code == ExposureIssueCode.FUTURE_HOLDINGS


def test_non_base_currency_is_not_converted_or_zero_filled() -> None:
    usd_position = make_position(
        position_id="position-usd-001",
        asset_id="STOCK_USD_001",
        asset_type=AssetType.STOCK,
        asset_name="Synthetic USD Stock",
        market_value=Decimal("1000"),
        currency="USD",
    )
    result = calculate_exposure(make_bundle(position=usd_position, include_holdings=False))
    assert result.status == ExposureStatus.FAILED
    assert result.report is None
    assert result.issues[0].code == ExposureIssueCode.NON_BASE_CURRENCY


def test_technology_classification_is_fixed_and_unknown_sector_stays_unknown() -> None:
    bundle = make_bundle(
        holdings=FundHoldingSnapshot(
            snapshot_id="holdings-tech-rule-001",
            owner_id="owner-exposure-001",
            parent_asset_id="FUND_EXPOSURE_001",
            parent_asset_type=AssetType.MUTUAL_FUND,
            as_of=NOW,
            source="synthetic-fund",
            coverage_pct=Decimal("100"),
            holdings=(
                make_holding(sector=" information technology "),
                make_holding(
                    holding_id="holding-unknown",
                    underlying_asset_id="STOCK_UNKNOWN_001",
                    weight_pct=Decimal("10"),
                    sector="Semiconductors",
                ),
            ),
        )
    )
    result = calculate_exposure(bundle)
    assert result.report is not None
    assert result.report.technology_market_value == Decimal("3550.0")
    technology_rows = [c for c in result.report.contributions if c.is_technology]
    assert len(technology_rows) == 1
    assert result.report.technology_weight_pct == Decimal("35.50")


def test_zero_base_value_fails_without_a_fake_zero_percent_report() -> None:
    position = make_position(market_value=Decimal("0"))
    result = calculate_exposure(make_bundle(position=position))
    assert result.status == ExposureStatus.FAILED
    assert result.report is None
    assert any(issue.code == ExposureIssueCode.ZERO_PORTFOLIO_VALUE for issue in result.issues)


def test_result_and_contribution_contracts_reject_tampering_and_are_immutable() -> None:
    bundle = make_bundle()
    result = calculate_exposure(bundle)
    assert result.report is not None
    with pytest.raises(ValidationError):
        result.status = ExposureStatus.FAILED  # type: ignore[misc]
    tampered_report = result.report.model_dump(mode="python")
    tampered_report["total_market_value"] = Decimal("1")
    with pytest.raises(ValidationError):
        ExposureReport.model_validate(tampered_report)
    with pytest.raises(ValidationError):
        ExposureContribution(
            exposure_id="bad",
            owner_id="owner-exposure-001",
            asset_id="STOCK",
            asset_name="Synthetic",
            asset_type=AssetType.STOCK,
            basis=ExposureBasis.DIRECT,
            market_value=Decimal("1"),
            portfolio_weight_pct=Decimal("100"),
            source_position_ids=("position-exposure-001",),
            is_attributed=False,
            is_technology=False,
            unexpected="value",
        )


def test_result_status_invariants_are_separate() -> None:
    now = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
    issue = ExposureIssue(
        code=ExposureIssueCode.MISSING_LOOK_THROUGH,
        safe_message="missing",
    )
    with pytest.raises(ValidationError, match="COMPLETE exposure"):
        ExposureResult(
            request_id="request",
            owner_id="owner",
            bundle_id="bundle",
            status=ExposureStatus.COMPLETE,
            calculated_at=now,
            issues=(issue,),
        )
    with pytest.raises(ValidationError, match="FAILED exposure"):
        ExposureResult(
            request_id="request",
            owner_id="owner",
            bundle_id="bundle",
            status=ExposureStatus.FAILED,
            calculated_at=now,
        )
