"""Deterministic concentration aggregation over Phase 3 exposures."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256

from app.portfolio.exposure import ExposureReport, ExposureResult, ExposureStatus
from app.risk.contracts import (
    ConcentrationDimension,
    ConcentrationGroup,
    ConcentrationIssue,
    ConcentrationIssueCode,
    ConcentrationReport,
    ConcentrationResult,
    ConcentrationStatus,
)


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "concentration:" + sha256(payload).hexdigest()[:32]


def _percentage_of(value: Decimal, total: Decimal) -> Decimal:
    return (value / total * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _hhi(values: Iterable[Decimal], total: Decimal) -> Decimal:
    raw = sum(((value / total) ** 2 for value in values), Decimal("0"))
    return (raw * Decimal("10000")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _ordered_groups(
    groups: tuple[ConcentrationGroup, ...],
) -> tuple[ConcentrationGroup, ...]:
    return tuple(sorted(groups, key=lambda group: (-group.market_value, group.group_id)))


def _build_groups(
    exposure_report: ExposureReport,
    dimension: ConcentrationDimension,
) -> tuple[ConcentrationGroup, ...]:
    # The report is typed by the public function; keeping this helper narrow
    # avoids exposing mutable aggregation state across the contract boundary.
    contributions = exposure_report.contributions
    buckets: dict[str, dict[str, object]] = {}
    for contribution in contributions:
        if dimension == ConcentrationDimension.ASSET:
            key = contribution.asset_id
            label = contribution.asset_name
        else:
            key = (
                contribution.sector.strip().casefold()
                if contribution.sector is not None
                else "UNCLASSIFIED"
            )
            label = key
        bucket = buckets.setdefault(
            key,
            {"market_value": Decimal("0"), "labels": set(), "contribution_ids": []},
        )
        bucket["market_value"] = bucket["market_value"] + contribution.market_value
        bucket["labels"].add(label)
        bucket["contribution_ids"].append(contribution.exposure_id)

    groups = []
    for key in sorted(buckets):
        bucket = buckets[key]
        market_value = bucket["market_value"]
        labels = sorted(bucket["labels"])
        groups.append(
            ConcentrationGroup(
                group_id=_stable_id(
                    exposure_report.report_id,
                    dimension.value,
                    key,
                ),
                owner_id=exposure_report.owner_id,
                dimension=dimension,
                key=key,
                label=labels[0],
                market_value=market_value,
                weight_pct=_percentage_of(
                    market_value, exposure_report.total_market_value
                ),
                contribution_ids=tuple(sorted(bucket["contribution_ids"])),
                is_unclassified=(
                    dimension == ConcentrationDimension.SECTOR
                    and key == "UNCLASSIFIED"
                ),
            )
        )
    return tuple(groups)


def _build_report(exposure_result: ExposureResult) -> ConcentrationReport:
    exposure_report = exposure_result.report
    assert exposure_report is not None
    asset_groups = _build_groups(exposure_report, ConcentrationDimension.ASSET)
    sector_groups = _build_groups(exposure_report, ConcentrationDimension.SECTOR)
    ordered_assets = _ordered_groups(asset_groups)
    ordered_sectors = _ordered_groups(sector_groups)
    unclassified_value = sum(
        (group.market_value for group in sector_groups if group.is_unclassified),
        Decimal("0"),
    )
    return ConcentrationReport(
        report_id=_stable_id(exposure_report.report_id, "report"),
        exposure_report_id=exposure_report.report_id,
        owner_id=exposure_report.owner_id,
        bundle_id=exposure_report.bundle_id,
        calculated_at=exposure_report.calculated_at,
        base_currency=exposure_report.base_currency,
        total_market_value=exposure_report.total_market_value,
        asset_groups=asset_groups,
        sector_groups=sector_groups,
        top_asset_group_id=ordered_assets[0].group_id,
        top_asset_weight_pct=ordered_assets[0].weight_pct,
        top_sector_group_id=ordered_sectors[0].group_id,
        top_sector_weight_pct=ordered_sectors[0].weight_pct,
        asset_hhi=_hhi(
            (group.market_value for group in asset_groups),
            exposure_report.total_market_value,
        ),
        sector_hhi=_hhi(
            (group.market_value for group in sector_groups),
            exposure_report.total_market_value,
        ),
        unclassified_market_value=unclassified_value,
        unclassified_weight_pct=_percentage_of(
            unclassified_value, exposure_report.total_market_value
        ),
        technology_market_value=exposure_report.technology_market_value,
        technology_weight_pct=exposure_report.technology_weight_pct,
        source_exposure_status=exposure_result.status.value,
    )


def calculate_concentration(exposure_result: ExposureResult) -> ConcentrationResult:
    """Aggregate a usable exposure report while preserving its data status."""
    if exposure_result.status == ExposureStatus.FAILED or exposure_result.report is None:
        return ConcentrationResult(
            request_id=f"concentration-request:{exposure_result.request_id}",
            owner_id=exposure_result.owner_id,
            bundle_id=exposure_result.bundle_id,
            status=ConcentrationStatus.FAILED,
            calculated_at=exposure_result.calculated_at,
            issues=(
                ConcentrationIssue(
                    code=ConcentrationIssueCode.UPSTREAM_FAILED,
                    safe_message="exposure report is unavailable; concentration was blocked",
                ),
            ),
        )

    issue = None
    if exposure_result.status == ExposureStatus.PARTIAL:
        issue = ConcentrationIssue(
            code=ConcentrationIssueCode.UPSTREAM_PARTIAL,
            safe_message="exposure data is partial; concentration requires review",
        )
    report = _build_report(exposure_result)
    return ConcentrationResult(
        request_id=f"concentration-request:{exposure_result.request_id}",
        owner_id=exposure_result.owner_id,
        bundle_id=exposure_result.bundle_id,
        status=(ConcentrationStatus.PARTIAL if issue is not None else ConcentrationStatus.COMPLETE),
        calculated_at=exposure_result.calculated_at,
        report=report,
        issues=(issue,) if issue is not None else (),
    )
