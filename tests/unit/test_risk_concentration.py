import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.portfolio import (
    AssetType,
    ExposureResult,
    ExposureStatus,
    PortfolioImportBundle,
    Position,
    PositionSnapshot,
    calculate_exposure,
)
from app.risk import (
    ConcentrationDimension,
    ConcentrationIssue,
    ConcentrationIssueCode,
    ConcentrationReport,
    ConcentrationResult,
    ConcentrationStatus,
    calculate_concentration,
)


NOW = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)
FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "portfolio"
    / "portfolio_exposure_bundle.json"
)


def load_fixture_exposure():
    bundle = PortfolioImportBundle.model_validate(json.loads(FIXTURE.read_text()))
    return calculate_exposure(bundle)


def make_direct_exposure() -> ExposureResult:
    positions = tuple(
        Position(
            position_id=f"position-direct-{idx}",
            owner_id="owner-concentration-001",
            asset_id=f"STOCK_DIRECT_{idx}",
            asset_type=AssetType.STOCK,
            asset_name=f"Synthetic Direct {idx}",
            quantity=Decimal("1"),
            market_value=Decimal(value),
            currency="CNY",
            as_of=NOW,
            source="synthetic",
        )
        for idx, value in (("001", "50"), ("002", "50"))
    )
    bundle = PortfolioImportBundle(
        bundle_id="bundle-concentration-001",
        owner_id="owner-concentration-001",
        created_at=NOW,
        position_snapshot=PositionSnapshot(
            snapshot_id="snapshot-concentration-001",
            owner_id="owner-concentration-001",
            as_of=NOW,
            base_currency="CNY",
            source="synthetic",
            positions=positions,
        ),
    )
    return calculate_exposure(bundle)


def test_partial_exposure_propagates_and_groups_close_to_total() -> None:
    result = calculate_concentration(load_fixture_exposure())
    assert result.status == ConcentrationStatus.PARTIAL
    assert result.report is not None
    report = result.report
    assert sum(group.market_value for group in report.asset_groups) == report.total_market_value
    assert sum(group.market_value for group in report.sector_groups) == report.total_market_value
    assert any(
        group.key == "UNCLASSIFIED" and group.is_unclassified
        for group in report.sector_groups
    )
    assert report.asset_hhi >= Decimal("0")
    assert report.sector_hhi >= Decimal("0")
    assert any(issue.code == ConcentrationIssueCode.UPSTREAM_PARTIAL for issue in result.issues)


def test_complete_direct_exposure_has_deterministic_groups_and_hhi() -> None:
    exposure = make_direct_exposure()
    first = calculate_concentration(exposure)
    second = calculate_concentration(exposure)
    assert first.status == ConcentrationStatus.COMPLETE
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert first.report is not None
    assert first.report.asset_hhi == Decimal("5000.00")
    assert first.report.sector_hhi == Decimal("10000.00")
    tied = [group for group in first.report.asset_groups if group.market_value == Decimal("50")]
    assert first.report.top_asset_group_id == min(group.group_id for group in tied)


def test_failed_exposure_is_blocked_without_a_concentration_report() -> None:
    from app.portfolio import ExposureIssue, ExposureIssueCode

    failed = ExposureResult(
        request_id="exposure-failed",
        owner_id="owner-failed",
        bundle_id="bundle-failed",
        status=ExposureStatus.FAILED,
        calculated_at=NOW,
        issues=(
            ExposureIssue(
                code=ExposureIssueCode.ZERO_PORTFOLIO_VALUE,
                safe_message="no value",
            ),
        ),
    )
    result = calculate_concentration(failed)
    assert result.status == ConcentrationStatus.FAILED
    assert result.report is None
    assert result.issues[0].code == ConcentrationIssueCode.UPSTREAM_FAILED


def test_report_contract_rejects_tampered_group_weight_and_status() -> None:
    result = calculate_concentration(make_direct_exposure())
    assert result.report is not None
    payload = result.report.model_dump(mode="python")
    payload["top_asset_weight_pct"] = Decimal("1")
    with pytest.raises(ValidationError):
        ConcentrationReport.model_validate(payload)
    with pytest.raises(ValidationError, match="COMPLETE concentration"):
        ConcentrationResult(
            request_id="bad",
            owner_id=result.owner_id,
            bundle_id=result.bundle_id,
            status=ConcentrationStatus.COMPLETE,
            calculated_at=NOW,
            issues=(
                ConcentrationIssue(
                    code=ConcentrationIssueCode.UPSTREAM_PARTIAL,
                    safe_message="bad",
                ),
            ),
        )


def test_unrecognised_sector_is_kept_as_its_own_group_not_technology() -> None:
    payload = json.loads(FIXTURE.read_text())
    payload["fund_holdings"][0]["holdings"][1]["sector"] = "Semiconductors"
    bundle = PortfolioImportBundle.model_validate(payload)
    result = calculate_concentration(calculate_exposure(bundle))
    assert result.report is not None
    unknown = [
        group
        for group in result.report.sector_groups
        if group.key == "semiconductors"
    ]
    assert len(unknown) == 1
    assert not unknown[0].is_unclassified
    assert result.report.technology_weight_pct == Decimal("20.88")
