from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.portfolio import (
    AssetType,
    FundHoldingSnapshot,
    LookThroughHolding,
    PortfolioImportBundle,
    Position,
    PositionImportIssue,
    PositionImportIssueCode,
    PositionImportResult,
    PositionImportStatus,
    PositionSnapshot,
)


NOW = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)


def make_position(**overrides: object) -> Position:
    values: dict[str, object] = {
        "position_id": "position-001",
        "owner_id": "owner-001",
        "asset_id": "FUND_SYNTH_001",
        "asset_type": AssetType.MUTUAL_FUND,
        "asset_name": "Synthetic Technology Fund",
        "quantity": Decimal("100"),
        "market_value": Decimal("10000"),
        "currency": "CNY",
        "as_of": NOW,
        "source": "synthetic-broker-import",
    }
    values.update(overrides)
    return Position.model_validate(values)


def make_snapshot(**overrides: object) -> PositionSnapshot:
    values: dict[str, object] = {
        "snapshot_id": "snapshot-001",
        "owner_id": "owner-001",
        "as_of": NOW,
        "base_currency": "CNY",
        "source": "synthetic-broker-import",
        "positions": (make_position(),),
    }
    values.update(overrides)
    return PositionSnapshot.model_validate(values)


def make_holding(**overrides: object) -> LookThroughHolding:
    values: dict[str, object] = {
        "holding_id": "holding-001",
        "parent_asset_id": "FUND_SYNTH_001",
        "underlying_asset_id": "STOCK_SYNTH_001",
        "underlying_name": "Synthetic Technology Holding",
        "asset_type": AssetType.STOCK,
        "weight_pct": Decimal("35.5"),
        "sector": "Technology",
        "as_of": NOW,
        "source": "synthetic-fund-report",
    }
    values.update(overrides)
    return LookThroughHolding.model_validate(values)


def make_fund_snapshot(**overrides: object) -> FundHoldingSnapshot:
    values: dict[str, object] = {
        "snapshot_id": "fund-snapshot-001",
        "owner_id": "owner-001",
        "parent_asset_id": "FUND_SYNTH_001",
        "parent_asset_type": AssetType.MUTUAL_FUND,
        "as_of": NOW,
        "source": "synthetic-fund-report",
        "coverage_pct": Decimal("80"),
        "holdings": (make_holding(),),
    }
    values.update(overrides)
    return FundHoldingSnapshot.model_validate(values)


def make_issue(**overrides: object) -> PositionImportIssue:
    values: dict[str, object] = {
        "code": PositionImportIssueCode.PARSE_ERROR,
        "safe_message": "One source row could not be parsed",
        "retriable": False,
    }
    values.update(overrides)
    return PositionImportIssue.model_validate(values)


def test_position_rejects_non_positive_quantity_bad_currency_and_naive_time() -> None:
    with pytest.raises(ValidationError):
        make_position(quantity=Decimal("0"))
    with pytest.raises(ValidationError):
        make_position(currency="CN")
    with pytest.raises(ValidationError):
        make_position(as_of=datetime(2026, 8, 31, 16, 0))
    assert make_position(currency="cny").currency == "CNY"


def test_snapshot_and_holdings_reject_duplicate_stable_ids() -> None:
    duplicate_position = make_position(position_id="position-001", asset_id="OTHER")
    with pytest.raises(ValidationError, match="duplicate position_id"):
        make_snapshot(positions=(make_position(), duplicate_position))

    duplicate_holding = make_holding(underlying_asset_id="STOCK_SYNTH_002")
    with pytest.raises(ValidationError, match="duplicate holding_id"):
        make_fund_snapshot(holdings=(make_holding(), duplicate_holding))

    with pytest.raises(ValidationError, match="position owner_id"):
        make_snapshot(
            positions=(make_position(owner_id="owner-002"),),
        )


def test_import_result_four_states_remain_distinct() -> None:
    complete = PositionImportResult(
        request_id="request-001",
        owner_id="owner-001",
        status=PositionImportStatus.COMPLETE,
        imported_at=NOW,
        snapshot=make_snapshot(),
    )
    partial = PositionImportResult(
        request_id="request-002",
        owner_id="owner-001",
        status=PositionImportStatus.PARTIAL,
        imported_at=NOW,
        snapshot=make_snapshot(snapshot_id="snapshot-partial"),
        missing_fields=("currency",),
    )
    empty = PositionImportResult(
        request_id="request-003",
        owner_id="owner-001",
        status=PositionImportStatus.EMPTY,
        imported_at=NOW,
        scope_description="Broker account owner-001 had no positions at 2026-08-31",
    )
    failed = PositionImportResult(
        request_id="request-004",
        owner_id="owner-001",
        status=PositionImportStatus.FAILED,
        imported_at=NOW,
        issues=(make_issue(code=PositionImportIssueCode.SOURCE_UNAVAILABLE),),
    )
    assert complete.snapshot is not None
    assert partial.snapshot is not None
    assert empty.snapshot is None
    assert failed.snapshot is None
    with pytest.raises(ValidationError, match="COMPLETE import requires"):
        PositionImportResult(
            request_id="bad-complete",
            owner_id="owner-001",
            status=PositionImportStatus.COMPLETE,
            imported_at=NOW,
        )
    with pytest.raises(ValidationError, match="FAILED import requires"):
        PositionImportResult(
            request_id="bad-failed",
            owner_id="owner-001",
            status=PositionImportStatus.FAILED,
            imported_at=NOW,
        )


def test_empty_import_is_not_a_zero_value_position() -> None:
    result = PositionImportResult(
        request_id="request-empty",
        owner_id="owner-001",
        status=PositionImportStatus.EMPTY,
        imported_at=NOW,
        scope_description="The synthetic account was explicitly checked and empty",
    )
    assert result.snapshot is None
    assert "positions" not in result.model_dump(mode="json")


def test_fund_weights_and_coverage_are_raw_bounded_values_without_exposure() -> None:
    snapshot = make_fund_snapshot(
        holdings=(
            make_holding(weight_pct=Decimal("60")),
            make_holding(
                holding_id="holding-002",
                underlying_asset_id="STOCK_SYNTH_002",
                weight_pct=Decimal("40"),
            ),
        ),
        coverage_pct=Decimal("75"),
    )
    assert snapshot.coverage_pct == Decimal("75")
    assert not hasattr(snapshot, "exposure_pct")
    with pytest.raises(ValidationError, match="at most 100"):
        make_fund_snapshot(
            holdings=(
                make_holding(weight_pct=Decimal("60")),
                make_holding(
                    holding_id="holding-002",
                    underlying_asset_id="STOCK_SYNTH_002",
                    weight_pct=Decimal("41"),
                ),
            )
        )


def test_bundle_closes_owner_and_parent_asset_identity() -> None:
    snapshot = make_snapshot()
    fund_snapshot = make_fund_snapshot()
    bundle = PortfolioImportBundle(
        bundle_id="bundle-001",
        owner_id="owner-001",
        created_at=NOW,
        position_snapshot=snapshot,
        fund_holdings=(fund_snapshot,),
    )
    assert bundle.owner_id == bundle.position_snapshot.owner_id
    with pytest.raises(ValidationError, match="owner_id"):
        PortfolioImportBundle(
            bundle_id="bundle-bad-owner",
            owner_id="owner-002",
            created_at=NOW,
            position_snapshot=snapshot,
        )
    with pytest.raises(ValidationError, match="not present"):
        PortfolioImportBundle(
            bundle_id="bundle-bad-parent",
            owner_id="owner-001",
            created_at=NOW,
            position_snapshot=snapshot,
            fund_holdings=(
                make_fund_snapshot(
                    parent_asset_id="UNKNOWN_FUND",
                    holdings=(make_holding(parent_asset_id="UNKNOWN_FUND"),),
                ),
            ),
        )
    with pytest.raises(ValidationError, match="duplicate snapshot_id"):
        PortfolioImportBundle(
            bundle_id="bundle-duplicate-snapshot",
            owner_id="owner-001",
            created_at=NOW,
            position_snapshot=make_snapshot(
                positions=(
                    make_position(),
                    make_position(
                        position_id="position-002",
                        asset_id="ETF_SYNTH_001",
                        asset_type=AssetType.ETF,
                        asset_name="Synthetic ETF",
                    ),
                )
            ),
            fund_holdings=(
                fund_snapshot,
                make_fund_snapshot(
                    parent_asset_id="ETF_SYNTH_001",
                    parent_asset_type=AssetType.ETF,
                    holdings=(make_holding(parent_asset_id="ETF_SYNTH_001"),),
                ),
            ),
        )
