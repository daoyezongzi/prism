"""Deterministic profile-conditioned allocation constraint envelopes."""

from __future__ import annotations

from hashlib import sha256

from app.portfolio.exposure import ExposureResult, ExposureStatus
from app.profile import RiskProfile
from app.risk.contracts import (
    BudgetAssessmentStatus,
    BudgetBreachKind,
    BudgetIssueCode,
    ConcentrationResult,
    ConcentrationStatus,
    RiskBudgetAssessment,
)
from app.allocation.contracts import (
    AllocationBand,
    AllocationBandDimension,
    AllocationBandDisposition,
    AllocationEnvelope,
    AllocationIssue,
    AllocationIssueCode,
    AllocationResult,
    AllocationStatus,
    ConstraintImpact,
)


_DIMENSION_ORDER = {
    AllocationBandDimension.ASSET: 0,
    AllocationBandDimension.SECTOR: 1,
    AllocationBandDimension.TECHNOLOGY: 2,
    AllocationBandDimension.UNCLASSIFIED: 3,
}


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "allocation:" + sha256(payload).hexdigest()[:32]


def _validate_parent_identity(
    profile: RiskProfile,
    exposure_result: ExposureResult,
    concentration_result: ConcentrationResult,
    assessment: RiskBudgetAssessment,
) -> None:
    if profile.owner_id != exposure_result.owner_id:
        raise ValueError("profile owner_id does not match exposure owner_id")
    if profile.owner_id != concentration_result.owner_id:
        raise ValueError("profile owner_id does not match concentration owner_id")
    if profile.owner_id != assessment.owner_id:
        raise ValueError("profile owner_id does not match assessment owner_id")
    if profile.profile_id != assessment.profile_id:
        raise ValueError("profile_id does not match risk-budget assessment")
    if profile.profile_version != assessment.budget.profile_version:
        raise ValueError("profile_version does not match risk budget")
    if profile.risk_level != assessment.budget.risk_level:
        raise ValueError("risk_level does not match risk budget")
    if exposure_result.bundle_id != concentration_result.bundle_id:
        raise ValueError("exposure and concentration bundle IDs do not match")
    if assessment.concentration_report_id is not None and concentration_result.report is not None:
        if assessment.concentration_report_id != concentration_result.report.report_id:
            raise ValueError("assessment concentration_report_id does not match report")
    if assessment.exposure_report_id is not None and exposure_result.report is not None:
        if assessment.exposure_report_id != exposure_result.report.report_id:
            raise ValueError("assessment exposure_report_id does not match report")
    if exposure_result.report is not None and concentration_result.report is not None:
        if concentration_result.report.exposure_report_id != exposure_result.report.report_id:
            raise ValueError("concentration report does not reference exposure report")
    if exposure_result.calculated_at != concentration_result.calculated_at:
        raise ValueError("exposure and concentration timestamps do not match")
    if concentration_result.calculated_at != assessment.assessed_at:
        raise ValueError("concentration and budget timestamps do not match")


def _expected_observation(
    kind: BudgetBreachKind,
    target_id: str | None,
    concentration_result: ConcentrationResult,
) -> tuple[object, object] | None:
    report = concentration_result.report
    if report is None:
        return None
    if kind == BudgetBreachKind.SINGLE_ASSET:
        if target_id is None:
            return None
        group = next((item for item in report.asset_groups if item.key == target_id), None)
        return (group.weight_pct, group.key) if group is not None else None
    if kind == BudgetBreachKind.SECTOR:
        if target_id is None:
            return None
        group = next(
            (
                item
                for item in report.sector_groups
                if item.key == target_id and not item.is_unclassified
            ),
            None,
        )
        return (group.weight_pct, group.key) if group is not None else None
    if kind == BudgetBreachKind.TECHNOLOGY:
        return (report.technology_weight_pct, None)
    return (report.unclassified_weight_pct, None)


def _verify_breach_alignment(
    assessment: RiskBudgetAssessment,
    concentration_result: ConcentrationResult,
) -> dict[tuple[BudgetBreachKind, str | None], str]:
    """Reject a structurally valid but semantically stale/tampered assessment."""
    budget = assessment.budget
    expected_limits = {
        BudgetBreachKind.SINGLE_ASSET: budget.max_single_asset_weight_pct,
        BudgetBreachKind.SECTOR: budget.max_sector_weight_pct,
        BudgetBreachKind.TECHNOLOGY: budget.max_technology_weight_pct,
        BudgetBreachKind.UNCLASSIFIED: budget.max_unclassified_weight_pct,
    }
    actual_by_key: dict[tuple[BudgetBreachKind, str | None], str] = {}
    for breach in assessment.breaches:
        key = (breach.kind, breach.target_id)
        if key in actual_by_key:
            raise ValueError("assessment contains duplicate breach target")
        observation = _expected_observation(
            breach.kind, breach.target_id, concentration_result
        )
        if observation is None:
            raise ValueError("assessment breach target is absent from concentration report")
        observed, _ = observation
        if breach.owner_id != assessment.owner_id:
            raise ValueError("assessment breach owner does not match assessment")
        if breach.observed_weight_pct != observed:
            raise ValueError("assessment breach observed weight is stale")
        if breach.limit_weight_pct != expected_limits[breach.kind]:
            raise ValueError("assessment breach limit does not match risk budget")
        actual_by_key[key] = breach.breach_id

    report = concentration_result.report
    assert report is not None
    expected_over: set[tuple[BudgetBreachKind, str | None]] = set()
    for group in report.asset_groups:
        if group.weight_pct > budget.max_single_asset_weight_pct:
            expected_over.add((BudgetBreachKind.SINGLE_ASSET, group.key))
    for group in report.sector_groups:
        if (
            not group.is_unclassified
            and group.weight_pct > budget.max_sector_weight_pct
        ):
            expected_over.add((BudgetBreachKind.SECTOR, group.key))
    if report.technology_weight_pct > budget.max_technology_weight_pct:
        expected_over.add((BudgetBreachKind.TECHNOLOGY, None))
    if report.unclassified_weight_pct > budget.max_unclassified_weight_pct:
        expected_over.add((BudgetBreachKind.UNCLASSIFIED, None))

    if set(actual_by_key) != expected_over:
        raise ValueError("assessment breaches do not match concentration observations")
    return actual_by_key


def _band(
    *,
    envelope_seed: str,
    owner_id: str,
    dimension: AllocationBandDimension,
    target_id: str,
    label: str,
    current_weight: object,
    allowed_max: object,
    breach_id: str | None,
    unresolved: bool,
) -> AllocationBand:
    # Values originate from Decimal fields on the parent contracts.  Keeping
    # the helper typed as object prevents accidental conversion through float;
    # Pydantic validates the final Decimal values at the boundary.
    from decimal import Decimal

    current = Decimal(current_weight)
    maximum = Decimal(allowed_max)
    over_limit = current > maximum
    reduction = max(current - maximum, Decimal("0"))
    if unresolved:
        disposition = AllocationBandDisposition.UNRESOLVED
        target_minimum = Decimal("0") if over_limit else current
        target_maximum = min(current, maximum)
    elif over_limit:
        disposition = AllocationBandDisposition.OVER_LIMIT
        target_minimum = Decimal("0")
        target_maximum = maximum
    else:
        disposition = AllocationBandDisposition.WITHIN_LIMIT
        target_minimum = current
        target_maximum = current

    breach_ids = (breach_id,) if breach_id is not None else ()
    return AllocationBand(
        band_id=_stable_id(
            envelope_seed,
            dimension.value,
            target_id,
        ),
        owner_id=owner_id,
        dimension=dimension,
        target_id=target_id,
        label=label,
        current_weight_pct=current,
        allowed_max_weight_pct=maximum,
        target_min_weight_pct=target_minimum,
        target_max_weight_pct=target_maximum,
        minimum_reduction_pct=reduction,
        disposition=disposition,
        breach_ids=breach_ids,
    )


def build_allocation_envelope(
    profile: RiskProfile,
    exposure_result: ExposureResult,
    concentration_result: ConcentrationResult,
    assessment: RiskBudgetAssessment,
) -> AllocationResult:
    """Build a constraint envelope without rebalancing or recommendation text."""
    _validate_parent_identity(
        profile, exposure_result, concentration_result, assessment
    )

    source_blocked = (
        exposure_result.status == ExposureStatus.FAILED
        or concentration_result.status == ConcentrationStatus.FAILED
    )
    if source_blocked and assessment.status != BudgetAssessmentStatus.BLOCKED:
        raise ValueError("failed upstream data requires a blocked budget assessment")
    if assessment.status == BudgetAssessmentStatus.BLOCKED:
        if not source_blocked:
            raise ValueError("blocked budget assessment has usable upstream data")
        return AllocationResult(
            request_id=f"allocation-request:{assessment.assessment_id}",
            owner_id=profile.owner_id,
            profile_id=profile.profile_id,
            calculated_at=assessment.assessed_at,
            status=AllocationStatus.BLOCKED,
            issues=(
                AllocationIssue(
                    code=AllocationIssueCode.BUDGET_BLOCKED,
                    safe_message="risk-budget assessment is blocked; no allocation envelope was produced",
                ),
            ),
        )

    if exposure_result.report is None or concentration_result.report is None:
        raise ValueError("usable allocation requires exposure and concentration reports")
    if concentration_result.status == ConcentrationStatus.PARTIAL:
        if exposure_result.status != ExposureStatus.PARTIAL:
            raise ValueError("partial concentration requires partial exposure")
    if exposure_result.status == ExposureStatus.PARTIAL and concentration_result.status != ConcentrationStatus.PARTIAL:
        raise ValueError("partial exposure requires partial concentration")
    if assessment.status == BudgetAssessmentStatus.PASS and (
        exposure_result.status != ExposureStatus.COMPLETE
        or concentration_result.status != ConcentrationStatus.COMPLETE
    ):
        raise ValueError("PASS budget assessment requires complete upstream data")

    breach_ids = _verify_breach_alignment(assessment, concentration_result)
    budget = assessment.budget
    report = concentration_result.report
    envelope_seed = "|".join(
        (
            profile.profile_id,
            str(profile.profile_version),
            budget.budget_id,
            assessment.assessment_id,
            report.report_id,
        )
    )
    unresolved = (
        exposure_result.status == ExposureStatus.PARTIAL
        or concentration_result.status == ConcentrationStatus.PARTIAL
        or any(
            issue.code == BudgetIssueCode.CONCENTRATION_PARTIAL
            for issue in assessment.issues
        )
    )

    bands: list[AllocationBand] = []
    for group in report.asset_groups:
        bands.append(
            _band(
                envelope_seed=envelope_seed,
                owner_id=profile.owner_id,
                dimension=AllocationBandDimension.ASSET,
                target_id=group.key,
                label=group.label,
                current_weight=group.weight_pct,
                allowed_max=budget.max_single_asset_weight_pct,
                breach_id=breach_ids.get((BudgetBreachKind.SINGLE_ASSET, group.key)),
                unresolved=unresolved,
            )
        )
    for group in report.sector_groups:
        if group.is_unclassified:
            continue
        bands.append(
            _band(
                envelope_seed=envelope_seed,
                owner_id=profile.owner_id,
                dimension=AllocationBandDimension.SECTOR,
                target_id=group.key,
                label=group.label,
                current_weight=group.weight_pct,
                allowed_max=budget.max_sector_weight_pct,
                breach_id=breach_ids.get((BudgetBreachKind.SECTOR, group.key)),
                unresolved=unresolved,
            )
        )
    bands.extend(
        (
            _band(
                envelope_seed=envelope_seed,
                owner_id=profile.owner_id,
                dimension=AllocationBandDimension.TECHNOLOGY,
                target_id="TECHNOLOGY",
                label="Technology aggregate",
                current_weight=report.technology_weight_pct,
                allowed_max=budget.max_technology_weight_pct,
                breach_id=breach_ids.get((BudgetBreachKind.TECHNOLOGY, None)),
                unresolved=unresolved,
            ),
            _band(
                envelope_seed=envelope_seed,
                owner_id=profile.owner_id,
                dimension=AllocationBandDimension.UNCLASSIFIED,
                target_id="UNCLASSIFIED",
                label="Unclassified exposure",
                current_weight=report.unclassified_weight_pct,
                allowed_max=budget.max_unclassified_weight_pct,
                breach_id=breach_ids.get((BudgetBreachKind.UNCLASSIFIED, None)),
                unresolved=unresolved,
            ),
        )
    )
    bands.sort(
        key=lambda item: (
            _DIMENSION_ORDER[item.dimension],
            -item.current_weight_pct,
            item.band_id,
        )
    )

    impacts = tuple(
        ConstraintImpact(
            impact_id=_stable_id(band.band_id, "impact"),
            band_id=band.band_id,
            owner_id=band.owner_id,
            dimension=band.dimension,
            target_id=band.target_id,
            before_weight_pct=band.current_weight_pct,
            after_weight_pct=band.target_max_weight_pct,
            reduction_pct_points=band.minimum_reduction_pct,
            breach_ids=band.breach_ids,
        )
        for band in bands
    )
    envelope_status = (
        AllocationStatus.READY
        if assessment.status == BudgetAssessmentStatus.PASS
        else AllocationStatus.REVIEW_REQUIRED
    )
    envelope = AllocationEnvelope(
        envelope_id=_stable_id(envelope_seed, "envelope"),
        owner_id=profile.owner_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        risk_level=profile.risk_level,
        budget_id=budget.budget_id,
        assessment_id=assessment.assessment_id,
        concentration_report_id=report.report_id,
        exposure_report_id=report.exposure_report_id,
        calculated_at=assessment.assessed_at,
        status=envelope_status,
        bands=tuple(bands),
        impacts=impacts,
        invalidation_conditions=(
            "风险画像版本变化",
            "持仓或基金成分快照变化",
            "穿透覆盖率或基准币种变化",
        ),
    )
    if envelope_status == AllocationStatus.READY:
        return AllocationResult(
            request_id=f"allocation-request:{assessment.assessment_id}",
            owner_id=profile.owner_id,
            profile_id=profile.profile_id,
            calculated_at=assessment.assessed_at,
            status=AllocationStatus.READY,
            envelope=envelope,
        )
    return AllocationResult(
        request_id=f"allocation-request:{assessment.assessment_id}",
        owner_id=profile.owner_id,
        profile_id=profile.profile_id,
        calculated_at=assessment.assessed_at,
        status=AllocationStatus.REVIEW_REQUIRED,
        envelope=envelope,
        issues=(
            AllocationIssue(
                code=AllocationIssueCode.BUDGET_REVIEW_REQUIRED,
                    safe_message="budget limits or input coverage require human review; no executable instruction was produced",
            ),
        ),
    )
