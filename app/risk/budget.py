"""Fixed profile-conditioned risk-budget rules and assessments."""

from __future__ import annotations

from decimal import Decimal
from hashlib import sha256

from app.profile import RiskProfile
from app.risk.contracts import (
    BudgetAssessmentStatus,
    BudgetBreachKind,
    BudgetIssueCode,
    ConcentrationResult,
    ConcentrationStatus,
    RiskBudget,
    RiskBudgetAssessment,
    RiskBudgetBreach,
    RiskBudgetIssue,
)


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "risk-budget:" + sha256(payload).hexdigest()[:32]


def build_risk_budget(profile: RiskProfile) -> RiskBudget:
    """Build the frozen v1 limits selected by a confirmed profile."""
    from app.risk.contracts import _RISK_BUDGET_RULES

    single, sector, technology, unclassified = _RISK_BUDGET_RULES[
        profile.risk_level
    ]
    return RiskBudget(
        budget_id=f"risk-budget:{profile.profile_id}:v{profile.profile_version}",
        owner_id=profile.owner_id,
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        risk_level=profile.risk_level,
        max_single_asset_weight_pct=single,
        max_sector_weight_pct=sector,
        max_technology_weight_pct=technology,
        max_unclassified_weight_pct=unclassified,
        max_drawdown_tolerance_pct=profile.max_drawdown_tolerance_pct,
    )


def _breach(
    budget: RiskBudget,
    kind: BudgetBreachKind,
    observed: Decimal,
    limit: Decimal,
    target_id: str | None,
) -> RiskBudgetBreach | None:
    if observed <= limit:
        return None
    return RiskBudgetBreach(
        breach_id=_stable_id(
            budget.budget_id,
            kind.value,
            target_id or "portfolio",
        ),
        owner_id=budget.owner_id,
        kind=kind,
        target_id=target_id,
        observed_weight_pct=observed,
        limit_weight_pct=limit,
        excess_weight_pct=observed - limit,
    )


def assess_risk_budget(
    profile: RiskProfile,
    concentration_result: ConcentrationResult,
) -> RiskBudgetAssessment:
    """Compare concentration observations to profile limits without advising trades."""
    if profile.owner_id != concentration_result.owner_id:
        raise ValueError("profile owner_id does not match concentration owner_id")
    budget = build_risk_budget(profile)
    assessed_at = concentration_result.calculated_at

    if (
        concentration_result.status == ConcentrationStatus.FAILED
        or concentration_result.report is None
    ):
        return RiskBudgetAssessment(
            assessment_id=_stable_id(budget.budget_id, "blocked"),
            owner_id=profile.owner_id,
            profile_id=profile.profile_id,
            assessed_at=assessed_at,
            status=BudgetAssessmentStatus.BLOCKED,
            budget=budget,
            issues=(
                RiskBudgetIssue(
                    code=BudgetIssueCode.CONCENTRATION_FAILED,
                    safe_message="concentration report is unavailable; budget assessment was blocked",
                ),
            ),
        )

    report = concentration_result.report
    breaches: list[RiskBudgetBreach] = []
    for group in report.asset_groups:
        item = _breach(
            budget,
            BudgetBreachKind.SINGLE_ASSET,
            group.weight_pct,
            budget.max_single_asset_weight_pct,
            group.key,
        )
        if item is not None:
            breaches.append(item)
    for group in report.sector_groups:
        if group.is_unclassified:
            continue
        item = _breach(
            budget,
            BudgetBreachKind.SECTOR,
            group.weight_pct,
            budget.max_sector_weight_pct,
            group.key,
        )
        if item is not None:
            breaches.append(item)

    technology_breach = _breach(
        budget,
        BudgetBreachKind.TECHNOLOGY,
        report.technology_weight_pct,
        budget.max_technology_weight_pct,
        None,
    )
    if technology_breach is not None:
        breaches.append(technology_breach)
    unclassified_breach = _breach(
        budget,
        BudgetBreachKind.UNCLASSIFIED,
        report.unclassified_weight_pct,
        budget.max_unclassified_weight_pct,
        None,
    )
    if unclassified_breach is not None:
        breaches.append(unclassified_breach)

    issues: tuple[RiskBudgetIssue, ...] = ()
    if concentration_result.status == ConcentrationStatus.PARTIAL:
        issues = (
            RiskBudgetIssue(
                code=BudgetIssueCode.CONCENTRATION_PARTIAL,
                safe_message="concentration data is partial; assessment requires review",
            ),
        )

    return RiskBudgetAssessment(
        assessment_id=_stable_id(budget.budget_id, report.report_id),
        owner_id=profile.owner_id,
        profile_id=profile.profile_id,
        exposure_report_id=report.exposure_report_id,
        concentration_report_id=report.report_id,
        assessed_at=assessed_at,
        status=(
            BudgetAssessmentStatus.REVIEW_REQUIRED
            if issues or breaches
            else BudgetAssessmentStatus.PASS
        ),
        budget=budget,
        breaches=tuple(breaches),
        issues=issues,
    )
