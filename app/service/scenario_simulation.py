"""Fixture-first deterministic hypothetical scenario simulation service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256

from app.contracts.evidence import NonEmptyStr
from app.optimization import (
    OptimizationStatus,
    PortfolioOptimizationResponse,
)
from app.portfolio import (
    ExposureBasis,
    ExposureResult,
    ExposureStatus,
    PortfolioImportBundle,
    calculate_exposure,
)
from app.profile import RiskProfile, RiskQuestionnaire
from app.risk import (
    BudgetAssessmentStatus,
    ConcentrationResult,
    ConcentrationStatus,
    RiskBudgetAssessment,
    assess_risk_budget,
    calculate_concentration,
)
from app.service.portfolio_optimization import (
    FixturePortfolioOptimizationService,
    PortfolioOptimizationError,
)
from app.service.profile_confirmation import (
    ProfileConfirmationError,
    confirm_questionnaire,
)
from app.simulation import (
    SCENARIO_SIMULATION_METHODOLOGY_VERSION,
    BuiltScenarioOverlay,
    ScenarioAssumption,
    ScenarioDefinition,
    ScenarioDiffDimension,
    ScenarioMetricDiff,
    ScenarioOverlayError,
    ScenarioRunSide,
    ScenarioRunSummary,
    ScenarioSimulationId,
    ScenarioSimulationIssue,
    ScenarioSimulationRequest,
    ScenarioSimulationResponse,
    ScenarioSimulationStatus,
    ScenarioSimulationTemplateResponse,
    ScenarioSimulationTrace,
    ScenarioTargetDiff,
    build_overlay,
    scenario_definitions,
)


_CENT = Decimal("0.01")
_INVALIDATION_CONDITIONS: tuple[str, ...] = (
    "Risk Profile version or risk budget rule changes",
    "Portfolio positions or fund look-through snapshot changes",
    "Observed market data or provider evidence updates",
    "Hypothetical scenario parameters or overlay definitions change",
)
_CALCULATION_STEPS: tuple[str, ...] = (
    "1. Confirm owner risk profile and validate input boundary",
    "2. Compute baseline exposure, concentration, budget assessment and target optimization",
    "3. Build deterministic immutable scenario overlay",
    "4. Compute simulated exposure, concentration, budget assessment and target optimization",
    "5. Compute verified metric and target diffs without fabricating missing values",
    "6. Validate complete closed response trace and safety invariants",
)


class ScenarioSimulationError(RuntimeError):
    """A safe domain refusal while constructing or executing a simulation."""


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


class FixtureScenarioSimulationService:
    """Deterministic, owner-scoped scenario simulation engine."""

    def __init__(
        self,
        optimization_service: FixturePortfolioOptimizationService | None = None,
    ) -> None:
        self._optimization_service = (
            optimization_service
            if optimization_service is not None
            else FixturePortfolioOptimizationService()
        )

    def template(
        self,
        owner_id: str,
        generated_at: datetime | None = None,
    ) -> ScenarioSimulationTemplateResponse:
        now = (
            generated_at
            if generated_at is not None
            else datetime.now(tz=UTC)
        )
        return ScenarioSimulationTemplateResponse(
            owner_id=owner_id,
            generated_at=now,
            scenarios=scenario_definitions(),
            supported_dimensions=tuple(ScenarioDiffDimension),
        )

    def execute(self, request: ScenarioSimulationRequest) -> ScenarioSimulationResponse:
        try:
            profile: RiskProfile = confirm_questionnaire(request.questionnaire)
        except ProfileConfirmationError as err:
            raise ScenarioSimulationError(f"risk profile confirmation failed: {err}") from err

        if profile.owner_id != request.owner_id:
            raise ScenarioSimulationError("profile owner does not match request owner")
        if request.portfolio.owner_id != request.owner_id:
            raise ScenarioSimulationError("portfolio owner does not match request owner")

        # 1. Baseline calculation
        baseline_exposure = calculate_exposure(request.portfolio)
        baseline_concentration = calculate_concentration(baseline_exposure)
        baseline_assessment = assess_risk_budget(profile, baseline_concentration)
        try:
            baseline_optimization = self._optimization_service.propose(
                request.portfolio,
                profile,
                baseline_exposure,
                baseline_concentration,
                baseline_assessment,
            )
        except PortfolioOptimizationError as err:
            raise ScenarioSimulationError(f"baseline optimization failed: {err}") from err

        # 2. Build scenario overlay
        base_tech_cap = baseline_assessment.budget.max_technology_weight_pct
        try:
            overlay: BuiltScenarioOverlay = build_overlay(
                request.portfolio,
                request.scenario_id,
                base_technology_cap=base_tech_cap,
            )
        except ScenarioOverlayError as err:
            raise ScenarioSimulationError(f"scenario overlay construction failed: {err}") from err

        # 3. Simulated calculation
        simulated_exposure = calculate_exposure(overlay.portfolio)
        simulated_concentration = calculate_concentration(simulated_exposure)
        simulated_assessment = assess_risk_budget(profile, simulated_concentration)
        try:
            simulated_optimization = self._optimization_service.propose(
                overlay.portfolio,
                profile,
                simulated_exposure,
                simulated_concentration,
                simulated_assessment,
                technology_cap_override=overlay.technology_cap_override,
            )
        except PortfolioOptimizationError as err:
            raise ScenarioSimulationError(f"simulated optimization failed: {err}") from err

        # 4. Summaries
        baseline_summary = self._build_summary(
            side=ScenarioRunSide.BASELINE,
            owner_id=request.owner_id,
            profile=profile,
            portfolio=request.portfolio,
            exposure=baseline_exposure,
            concentration=baseline_concentration,
            assessment=baseline_assessment,
            optimization=baseline_optimization,
        )
        simulated_summary = self._build_summary(
            side=ScenarioRunSide.SCENARIO,
            owner_id=request.owner_id,
            profile=profile,
            portfolio=overlay.portfolio,
            exposure=simulated_exposure,
            concentration=simulated_concentration,
            assessment=simulated_assessment,
            optimization=simulated_optimization,
        )

        overall_status = (
            ScenarioSimulationStatus.BLOCKED
            if ScenarioSimulationStatus.BLOCKED in (baseline_summary.status, simulated_summary.status)
            else ScenarioSimulationStatus.REVIEW_REQUIRED
            if ScenarioSimulationStatus.REVIEW_REQUIRED in (baseline_summary.status, simulated_summary.status)
            else ScenarioSimulationStatus.READY
        )

        # 5. Diffs (only emitted when READY)
        metric_diffs: tuple[ScenarioMetricDiff, ...] = ()
        target_diffs: tuple[ScenarioTargetDiff, ...] = ()
        response_issues: tuple[ScenarioSimulationIssue, ...] = ()

        if overall_status == ScenarioSimulationStatus.READY:
            metric_diffs = self._compute_metric_diffs(
                baseline_exposure=baseline_exposure,
                baseline_concentration=baseline_concentration,
                baseline_assessment=baseline_assessment,
                simulated_exposure=simulated_exposure,
                simulated_concentration=simulated_concentration,
                simulated_assessment=simulated_assessment,
                technology_cap_override=overlay.technology_cap_override,
            )
            target_diffs = self._compute_target_diffs(
                baseline_optimization=baseline_optimization,
                simulated_optimization=simulated_optimization,
            )
        else:
            all_issues: list[ScenarioSimulationIssue] = []
            seen_issue_keys: set[tuple[str, str]] = set()
            for issue in baseline_summary.issues + simulated_summary.issues:
                key = (issue.code, issue.safe_message)
                if key not in seen_issue_keys:
                    seen_issue_keys.add(key)
                    all_issues.append(issue)
            response_issues = tuple(all_issues)

        # 6. Definition & Trace
        definition = next(
            item for item in scenario_definitions() if item.scenario_id == request.scenario_id
        )

        input_fingerprint = _stable_id(
            "scenario-simulation-fingerprint",
            request.owner_id,
            profile.profile_id,
            str(profile.profile_version),
            request.portfolio.bundle_id,
            request.portfolio.position_snapshot.snapshot_id,
            request.scenario_id.value,
            overlay.overlay_digest,
            SCENARIO_SIMULATION_METHODOLOGY_VERSION,
        )

        all_contributions = sorted(
            set(baseline_summary.source_contribution_ids + simulated_summary.source_contribution_ids)
        )

        trace = ScenarioSimulationTrace(
            owner_id=request.owner_id,
            profile_id=profile.profile_id,
            scenario_id=request.scenario_id,
            input_fingerprint=input_fingerprint,
            baseline_run_id=baseline_optimization.request_id,
            simulated_run_id=simulated_optimization.request_id,
            baseline_bundle_id=request.portfolio.bundle_id,
            simulated_bundle_id=overlay.portfolio.bundle_id,
            baseline_snapshot_id=request.portfolio.position_snapshot.snapshot_id,
            simulated_snapshot_id=overlay.portfolio.position_snapshot.snapshot_id,
            methodology_version=SCENARIO_SIMULATION_METHODOLOGY_VERSION,
            source_contribution_ids=tuple(all_contributions),
            calculation_steps=_CALCULATION_STEPS,
            invalidation_conditions=_INVALIDATION_CONDITIONS,
            derived_values_are_hypothetical=True,
        )

        simulation_id = _stable_id(
            "scenario-simulation",
            request.owner_id,
            request.scenario_id.value,
            input_fingerprint,
        )

        return ScenarioSimulationResponse(
            simulation_id=simulation_id,
            request_id=request.request_id,
            owner_id=request.owner_id,
            generated_at=request.generated_at,
            scenario=definition,
            assumption=overlay.assumption,
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            baseline=baseline_summary,
            simulated=simulated_summary,
            metric_diffs=metric_diffs,
            target_diffs=target_diffs,
            status=overall_status,
            issues=response_issues,
            invalidation_conditions=_INVALIDATION_CONDITIONS,
            trace=trace,
        )

    def _build_summary(
        self,
        side: ScenarioRunSide,
        owner_id: str,
        profile: RiskProfile,
        portfolio: PortfolioImportBundle,
        exposure: ExposureResult,
        concentration: ConcentrationResult,
        assessment: RiskBudgetAssessment,
        optimization: PortfolioOptimizationResponse,
    ) -> ScenarioRunSummary:
        if (
            optimization.status == OptimizationStatus.BLOCKED
            or exposure.status == ExposureStatus.FAILED
            or concentration.status == ConcentrationStatus.FAILED
        ):
            status = ScenarioSimulationStatus.BLOCKED
        elif (
            optimization.status == OptimizationStatus.REVIEW_REQUIRED
            or exposure.status == ExposureStatus.PARTIAL
            or concentration.status == ConcentrationStatus.PARTIAL
        ):
            status = ScenarioSimulationStatus.REVIEW_REQUIRED
        else:
            status = ScenarioSimulationStatus.READY

        issues: list[ScenarioSimulationIssue] = []
        if status != ScenarioSimulationStatus.READY:
            for exp_issue in exposure.issues:
                issues.append(
                    ScenarioSimulationIssue(
                        code=f"EXPOSURE_{exp_issue.code.value if hasattr(exp_issue.code, 'value') else exp_issue.code}",
                        safe_message=exp_issue.safe_message,
                        dimension=ScenarioDiffDimension.EXPOSURE,
                    )
                )
            for conc_issue in concentration.issues:
                issues.append(
                    ScenarioSimulationIssue(
                        code=f"CONCENTRATION_{conc_issue.code.value if hasattr(conc_issue.code, 'value') else conc_issue.code}",
                        safe_message=conc_issue.safe_message,
                        dimension=ScenarioDiffDimension.CONCENTRATION,
                    )
                )
            for asst_issue in assessment.issues:
                issues.append(
                    ScenarioSimulationIssue(
                        code=f"RISK_BUDGET_{asst_issue.code.value if hasattr(asst_issue.code, 'value') else asst_issue.code}",
                        safe_message=asst_issue.safe_message,
                        dimension=ScenarioDiffDimension.RISK_BUDGET,
                    )
                )
            for opt_issue in optimization.issues:
                issues.append(
                    ScenarioSimulationIssue(
                        code=f"OPTIMIZATION_{opt_issue.code.value if hasattr(opt_issue.code, 'value') else opt_issue.code}",
                        safe_message=opt_issue.safe_message,
                        dimension=ScenarioDiffDimension.OPTIMIZATION,
                    )
                )

        target_diffs: list[ScenarioTargetDiff] = []
        if optimization.status == OptimizationStatus.READY:
            for target in optimization.targets:
                target_diffs.append(
                    ScenarioTargetDiff(
                        target_id=target.target_id,
                        asset_name=target.asset_name,
                        baseline_value=_quantize(target.target_weight_pct),
                        scenario_value=_quantize(target.target_weight_pct),
                        delta=Decimal("0.00"),
                        unit="PCT",
                    )
                )
            target_diffs.sort(key=lambda item: item.target_id)

        source_ids_list: list[str] = [
            assessment.assessment_id,
            optimization.request_id,
        ]
        if exposure.report is not None:
            source_ids_list.append(exposure.report.report_id)
        if concentration.report is not None:
            source_ids_list.append(concentration.report.report_id)
        source_ids = sorted(set(source_ids_list))

        tech_pct = (
            _quantize(exposure.report.technology_weight_pct)
            if exposure.report is not None
            else None
        )
        top_pct = (
            _quantize(concentration.report.top_asset_weight_pct)
            if concentration.report is not None
            else None
        )
        asset_hhi = (
            _quantize(concentration.report.asset_hhi)
            if concentration.report is not None
            else None
        )
        sector_hhi = (
            _quantize(concentration.report.sector_hhi)
            if concentration.report is not None
            else None
        )

        return ScenarioRunSummary(
            side=side,
            status=status,
            owner_id=owner_id,
            profile_id=profile.profile_id,
            profile_version=profile.profile_version,
            risk_level=profile.risk_level,
            portfolio_bundle_id=portfolio.bundle_id,
            position_snapshot_id=portfolio.position_snapshot.snapshot_id,
            exposure_report_id=exposure.report.report_id if exposure.report is not None else None,
            concentration_report_id=concentration.report.report_id if concentration.report is not None else None,
            assessment_id=assessment.assessment_id,
            assessment_status=assessment.status,
            optimization_status=optimization.status,
            technology_weight_pct=tech_pct,
            top_asset_weight_pct=top_pct,
            asset_hhi=asset_hhi,
            sector_hhi=sector_hhi,
            targets=tuple(target_diffs),
            issues=tuple(issues),
            source_contribution_ids=tuple(source_ids),
        )

    def _compute_metric_diffs(
        self,
        baseline_exposure: ExposureResult,
        baseline_concentration: ConcentrationResult,
        baseline_assessment: RiskBudgetAssessment,
        simulated_exposure: ExposureResult,
        simulated_concentration: ConcentrationResult,
        simulated_assessment: RiskBudgetAssessment,
        technology_cap_override: Decimal | None,
    ) -> tuple[ScenarioMetricDiff, ...]:
        diffs: list[ScenarioMetricDiff] = []

        # 1. Total portfolio value
        if (
            baseline_exposure.report is not None
            and simulated_exposure.report is not None
        ):
            b_val = _quantize(baseline_exposure.report.total_market_value)
            s_val = _quantize(simulated_exposure.report.total_market_value)
            diffs.append(
                ScenarioMetricDiff(
                    metric_id="metric:01:total_portfolio_value_cny",
                    dimension=ScenarioDiffDimension.INPUT,
                    label="组合总市值（CNY）",
                    baseline_value=b_val,
                    scenario_value=s_val,
                    delta=_quantize(s_val - b_val),
                    unit="CNY",
                )
            )

        # 2. Technology weight
        if (
            baseline_exposure.report is not None
            and simulated_exposure.report is not None
        ):
            b_val = _quantize(baseline_exposure.report.technology_weight_pct)
            s_val = _quantize(simulated_exposure.report.technology_weight_pct)
            diffs.append(
                ScenarioMetricDiff(
                    metric_id="metric:02:technology_weight_pct",
                    dimension=ScenarioDiffDimension.EXPOSURE,
                    label="科技行业总暴露（%）",
                    baseline_value=b_val,
                    scenario_value=s_val,
                    delta=_quantize(s_val - b_val),
                    unit="PCT",
                )
            )

        # 3. Top asset weight
        if (
            baseline_concentration.report is not None
            and simulated_concentration.report is not None
        ):
            b_val = _quantize(baseline_concentration.report.top_asset_weight_pct)
            s_val = _quantize(simulated_concentration.report.top_asset_weight_pct)
            diffs.append(
                ScenarioMetricDiff(
                    metric_id="metric:03:top_asset_weight_pct",
                    dimension=ScenarioDiffDimension.CONCENTRATION,
                    label="单一最大资产权重（%）",
                    baseline_value=b_val,
                    scenario_value=s_val,
                    delta=_quantize(s_val - b_val),
                    unit="PCT",
                )
            )

        # 4. Asset HHI
        if (
            baseline_concentration.report is not None
            and simulated_concentration.report is not None
        ):
            b_val = _quantize(baseline_concentration.report.asset_hhi)
            s_val = _quantize(simulated_concentration.report.asset_hhi)
            diffs.append(
                ScenarioMetricDiff(
                    metric_id="metric:04:asset_hhi",
                    dimension=ScenarioDiffDimension.CONCENTRATION,
                    label="资产集中度 HHI 指数",
                    baseline_value=b_val,
                    scenario_value=s_val,
                    delta=_quantize(s_val - b_val),
                    unit="INDEX",
                )
            )

        # 5. Technology cap
        b_cap = _quantize(baseline_assessment.budget.max_technology_weight_pct)
        s_cap = (
            _quantize(technology_cap_override)
            if technology_cap_override is not None
            else b_cap
        )
        diffs.append(
            ScenarioMetricDiff(
                metric_id="metric:05:max_technology_cap_pct",
                dimension=ScenarioDiffDimension.RISK_BUDGET,
                label="科技行业限额（%）",
                baseline_value=b_cap,
                scenario_value=s_cap,
                delta=_quantize(s_cap - b_cap),
                unit="PCT",
            )
        )

        diffs.sort(key=lambda item: item.metric_id)
        return tuple(diffs)

        diffs.sort(key=lambda item: item.metric_id)
        return tuple(diffs)

    def _compute_target_diffs(
        self,
        baseline_optimization: PortfolioOptimizationResponse,
        simulated_optimization: PortfolioOptimizationResponse,
    ) -> tuple[ScenarioTargetDiff, ...]:
        base_targets = {t.target_id: t for t in baseline_optimization.targets}
        sim_targets = {t.target_id: t for t in simulated_optimization.targets}
        all_ids = sorted(set(base_targets.keys()) | set(sim_targets.keys()))

        diffs: list[ScenarioTargetDiff] = []
        for tid in all_ids:
            b = base_targets.get(tid)
            s = sim_targets.get(tid)
            if b is not None and s is not None:
                b_val = _quantize(b.target_weight_pct)
                s_val = _quantize(s.target_weight_pct)
                diffs.append(
                    ScenarioTargetDiff(
                        target_id=tid,
                        asset_name=b.asset_name,
                        baseline_value=b_val,
                        scenario_value=s_val,
                        delta=_quantize(s_val - b_val),
                        unit="PCT",
                    )
                )
            elif b is not None:
                b_val = _quantize(b.target_weight_pct)
                s_val = Decimal("0.00")
                diffs.append(
                    ScenarioTargetDiff(
                        target_id=tid,
                        asset_name=b.asset_name,
                        baseline_value=b_val,
                        scenario_value=s_val,
                        delta=_quantize(s_val - b_val),
                        unit="PCT",
                    )
                )
            elif s is not None:
                b_val = Decimal("0.00")
                s_val = _quantize(s.target_weight_pct)
                diffs.append(
                    ScenarioTargetDiff(
                        target_id=tid,
                        asset_name=s.asset_name,
                        baseline_value=b_val,
                        scenario_value=s_val,
                        delta=_quantize(s_val - b_val),
                        unit="PCT",
                    )
                )
        diffs.sort(key=lambda item: item.target_id)
        return tuple(diffs)


__all__ = [
    "FixtureScenarioSimulationService",
    "ScenarioSimulationError",
]
