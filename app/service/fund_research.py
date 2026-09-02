"""Fixture-first execution of the Demo G ETF/Fund research Evidence Card."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path

from app.contracts.evidence import DecisionTrace, Fact, Finding, FindingSeverity
from app.fund.contracts import (
    FundMetricResponse,
    FundResearchIssue,
    FundResearchManifest,
    FundResearchNodeResponse,
    FundResearchRequest,
    FundResearchResponse,
    FundResearchScenarioDefinition,
    FundResearchScenarioId,
    FundResearchScenarioResponse,
    FundResearchTemplateResponse,
    FundRiskRuleResponse,
    FundRiskStatus,
    FundRiskSummary,
)
from app.orchestration import (
    ResearchNodeRequest,
    ResearchNodeSpec,
    build_research_plan,
    create_research_run,
    execute_research_run,
)
from app.providers import (
    FixtureFinancialProvider,
    ProviderOperation,
    ProviderRecord,
    ProviderRequest,
    ProviderResult,
    ProviderServingMode,
    ProviderStatus,
)
from app.research import (
    ResearchClaimSpec,
    ResearchPipelineStatus,
    ValidationClaim,
    build_research_evidence_pipeline,
)


_DEFAULT_MANIFEST = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "fund"
    / "fund_research_manifest.json"
)
_DEFAULT_PROVIDER_DIR = (
    Path(__file__).resolve().parent.parent / "fixtures" / "fund" / "providers"
)

_SCENARIOS: tuple[FundResearchScenarioDefinition, ...] = (
    FundResearchScenarioDefinition(
        scenario_id=FundResearchScenarioId.BASELINE_READY,
        label="基线：双源一致",
        description="两条独立合成来源在同一报告期一致，允许生成可追溯基金事实与资产风险摘要。",
    ),
    FundResearchScenarioDefinition(
        scenario_id=FundResearchScenarioId.SOURCE_DISAGREEMENT,
        label="来源分歧：科技暴露冲突",
        description="来源 B 对科技行业权重给出不同数值，冲突保持待复核，不升级为事实。",
    ),
    FundResearchScenarioDefinition(
        scenario_id=FundResearchScenarioId.SOURCE_PARTIAL,
        label="来源部分缺失",
        description="来源 B 缺少最大回撤字段，保留可用证据但阻止完整资产结论。",
    ),
    FundResearchScenarioDefinition(
        scenario_id=FundResearchScenarioId.SOURCE_EMPTY,
        label="来源无结果",
        description="来源 B 在声明范围内没有记录，不能将无结果当作零值。",
    ),
    FundResearchScenarioDefinition(
        scenario_id=FundResearchScenarioId.SOURCE_FAILED,
        label="来源失败",
        description="来源 B 安全失败，失败状态不转换为 EMPTY 或可用事实。",
    ),
)
_SCENARIO_BY_ID = {item.scenario_id: item for item in _SCENARIOS}


class FundResearchError(RuntimeError):
    """Safe boundary for invalid or unavailable fund research requests."""


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None or isinstance(value, (Mapping, list, tuple)):
        raise ValueError("fund value is not a scalar")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("fund value is not decimal") from exc
    if not parsed.is_finite():
        raise ValueError("fund value must be finite")
    return parsed


def _result_with_record(
    result: ProviderResult,
    record: ProviderRecord,
    *,
    status: ProviderStatus,
    missing_fields: tuple[str, ...] = (),
    issues: tuple[object, ...] = (),
    scope_description: str | None = None,
) -> ProviderResult:
    return ProviderResult.model_validate(
        {
            **result.model_dump(mode="python"),
            "status": status,
            "records": (record,),
            "missing_fields": missing_fields,
            "issues": issues,
            "scope_description": scope_description,
        }
    )


class _FundScenarioFixtureProvider:
    """Read-only deterministic overlay over the fund fixture provider."""

    def __init__(self, base: FixtureFinancialProvider, scenario: FundResearchScenarioId):
        self._base = base
        self._scenario = scenario

    @property
    def name(self) -> str:
        return self._base.name

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        result = await self._base.execute(request)
        if request.parameters.get("source_slot") != "b":
            return result
        if self._scenario == FundResearchScenarioId.BASELINE_READY:
            return result

        if self._scenario == FundResearchScenarioId.SOURCE_DISAGREEMENT:
            if result.status != ProviderStatus.SUCCESS or not result.records:
                return result
            original = result.records[0]
            fields = dict(original.fields)
            fields["technology_weight_pct"] = "58.00"
            record = ProviderRecord.model_validate(
                {**original.model_dump(mode="python"), "fields": fields}
            )
            return _result_with_record(result, record, status=ProviderStatus.SUCCESS)

        if self._scenario == FundResearchScenarioId.SOURCE_PARTIAL:
            if result.status != ProviderStatus.SUCCESS or not result.records:
                return result
            original = result.records[0]
            fields = {
                key: value
                for key, value in original.fields.items()
                if key != "max_drawdown_pct"
            }
            units = {key: value for key, value in original.units.items() if key in fields}
            record = ProviderRecord.model_validate(
                {
                    **original.model_dump(mode="python"),
                    "fields": fields,
                    "units": units,
                }
            )
            return _result_with_record(
                result,
                record,
                status=ProviderStatus.PARTIAL,
                missing_fields=("max_drawdown_pct",),
            )

        if self._scenario == FundResearchScenarioId.SOURCE_EMPTY:
            return ProviderResult.model_validate(
                {
                    **result.model_dump(mode="python"),
                    "status": ProviderStatus.EMPTY,
                    "records": (),
                    "missing_fields": (),
                    "issues": (),
                    "scope_description": "source B returned no fund record for the requested period",
                }
            )

        if self._scenario == FundResearchScenarioId.SOURCE_FAILED:
            return ProviderResult.model_validate(
                {
                    **result.model_dump(mode="python"),
                    "status": ProviderStatus.FAILED,
                    "records": (),
                    "missing_fields": (),
                    "issues": (
                        {
                            "code": "TRANSPORT_ERROR",
                            "stage": "fund-source",
                            "safe_message": "source B was unavailable in this offline replay",
                            "retriable": False,
                            "diagnostics": {},
                        },
                    ),
                    "scope_description": None,
                }
            )

        raise FundResearchError("unsupported fund research scenario")


class FixtureFundResearchService:
    """Run the fixed Demo G fund card through Prism's existing research chain."""

    def __init__(
        self,
        *,
        manifest_path: str | Path = _DEFAULT_MANIFEST,
        provider_dir: str | Path = _DEFAULT_PROVIDER_DIR,
    ) -> None:
        self._manifest_path = Path(manifest_path)
        self._provider_dir = Path(provider_dir)
        try:
            payload = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            self._manifest = FundResearchManifest.model_validate(payload)
        except Exception as exc:
            raise FundResearchError("fund research manifest could not be loaded") from exc
        if not self._provider_dir.exists() or not self._provider_dir.is_dir():
            raise FundResearchError("fund research provider fixtures are unavailable")

    @property
    def manifest_id(self) -> str:
        return self._manifest.manifest_id

    @property
    def scenarios(self) -> tuple[FundResearchScenarioDefinition, ...]:
        return tuple(sorted(_SCENARIOS, key=lambda item: item.scenario_id.value))

    def template(self, owner_id: str) -> FundResearchTemplateResponse:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise FundResearchError("fund research owner is required")
        if any(
            token in owner_id.casefold().replace("-", "_")
            for token in ("api_key", "token", "secret", "password")
        ):
            raise FundResearchError("fund research owner is not allowed")
        metrics = tuple(
            FundMetricResponse(metric=item.metric, label=item.label, unit=item.unit)
            for item in self._manifest.metrics
        )
        risk_rules = (
            FundRiskRuleResponse(
                rule_id="fund-technology-weight",
                label="科技行业权重超过阈值",
                operator="GT",
                threshold=self._manifest.technology_weight_max_pct,
                unit="pct",
            ),
            FundRiskRuleResponse(
                rule_id="fund-top10-weight",
                label="前十大持仓权重超过阈值",
                operator="GT",
                threshold=self._manifest.top10_weight_max_pct,
                unit="pct",
            ),
            FundRiskRuleResponse(
                rule_id="fund-volatility",
                label="年化波动超过阈值",
                operator="GT",
                threshold=self._manifest.volatility_max_pct,
                unit="pct",
            ),
            FundRiskRuleResponse(
                rule_id="fund-drawdown",
                label="最大回撤超过阈值",
                operator="GT",
                threshold=self._manifest.drawdown_max_pct,
                unit="pct",
            ),
            FundRiskRuleResponse(
                rule_id="fund-expense-ratio",
                label="费率超过阈值",
                operator="GT",
                threshold=self._manifest.expense_ratio_max_pct,
                unit="pct",
            ),
        )
        scenarios = tuple(
            FundResearchScenarioResponse(
                schema_version="fund-research-scenario-response.v1",
                scenario_id=item.scenario_id,
                label=item.label,
                description=item.description,
            )
            for item in self.scenarios
        )
        return FundResearchTemplateResponse(
            manifest_id=self._manifest.manifest_id,
            subject=self._manifest.subject,
            period=self._manifest.period,
            generated_at=self._manifest.generated_at,
            budget_ms=self._manifest.budget_ms,
            metrics=metrics,
            risk_rules=risk_rules,
            scenarios=scenarios,
        )

    def _plan(self, owner_id: str, scenario: FundResearchScenarioId):
        scope = f"{self._manifest.scope_description} · replay {scenario.value}"
        nodes = tuple(
            ResearchNodeSpec(
                node_id=node.node_id,
                owner_id=owner_id,
                node_kind="FUND",
                required=True,
                dependencies=(),
                timeout_ms=min(node.timeout_ms, self._manifest.budget_ms),
            )
            for node in self._manifest.nodes
        )
        return build_research_plan(owner_id, scope, nodes)

    def _requests(self) -> tuple[ResearchNodeRequest, ...]:
        return tuple(
            ResearchNodeRequest(
                node_id=node.node_id,
                request=ProviderRequest(
                    request_id=node.request_id,
                    operation=ProviderOperation.FUND_DATA,
                    subject=self._manifest.subject,
                    required_fields=node.required_fields,
                    parameters=node.parameters,
                    timeout_ms=min(node.timeout_ms, self._manifest.budget_ms),
                ),
            )
            for node in self._manifest.nodes
        )

    def _claim_specs(self, owner_id: str, execution):
        specs: list[ResearchClaimSpec] = []
        for item in self._manifest.metrics:
            observation_ids = tuple(
                sorted(
                    observation.observation_id
                    for observation in execution.observations
                    if observation.metric == item.metric
                    and observation.subject == self._manifest.subject
                    and observation.unit == item.unit
                    and observation.period == self._manifest.period
                )
            )
            claim = ValidationClaim(
                claim_id=f"claim-fund-{item.metric}",
                owner_id=owner_id,
                subject=self._manifest.subject,
                metric=item.metric,
                unit=item.unit,
                period=self._manifest.period,
                expected_value=item.expected_value,
            )
            specs.append(
                ResearchClaimSpec(
                    claim=claim,
                    finding_kind=item.finding_kind,
                    finding_severity=item.finding_severity,
                    statement=item.finding_statement,
                    observation_ids=observation_ids,
                )
            )
        return tuple(specs)

    @staticmethod
    def _node_responses(execution) -> tuple[FundResearchNodeResponse, ...]:
        responses: list[FundResearchNodeResponse] = []
        for node in sorted(execution.state.nodes, key=lambda item: item.node_id):
            issue_by_code: dict[str, FundResearchIssue] = {}
            for issue in node.issues:
                code = issue.code.value
                issue_by_code.setdefault(
                    code,
                    FundResearchIssue(code=code, safe_message=issue.safe_message),
                )
            missing_fields: tuple[str, ...] = ()
            scope_description: str | None = None
            if node.result is not None:
                missing_fields = tuple(sorted(node.result.missing_fields))
                scope_description = node.result.scope_description
                for issue in node.result.issues:
                    code = issue.code.value
                    issue_by_code.setdefault(
                        code,
                        FundResearchIssue(code=code, safe_message=issue.safe_message),
                    )
            provider = node.result.provider if node.result is not None else None
            serving_mode = (
                node.result.provider_serving_mode
                if node.result is not None
                else ProviderServingMode.DIRECT
            )
            cache_age_ms = (
                node.result.provider_cache_age_ms
                if node.result is not None
                else None
            )
            responses.append(
                FundResearchNodeResponse(
                    node_id=node.node_id,
                    required=node.required,
                    status=node.status,
                    started_at=node.started_at,
                    finished_at=node.finished_at,
                    missing_fields=missing_fields,
                    scope_description=scope_description,
                    issues=tuple(issue_by_code[key] for key in sorted(issue_by_code)),
                    provider=provider,
                    provider_serving_mode=serving_mode,
                    provider_cache_age_ms=cache_age_ms,
                )
            )
        return tuple(responses)

    @staticmethod
    def _derived_findings(owner_id: str, facts: tuple[Fact, ...], manifest: FundResearchManifest) -> tuple[Finding, ...]:
        by_metric = {fact.metric: fact for fact in facts}
        required = {
            "technology_weight_pct",
            "top10_weight_pct",
            "annualized_volatility_pct",
            "max_drawdown_pct",
            "expense_ratio_pct",
        }
        if not required.issubset(by_metric):
            raise FundResearchError("fund deterministic risk inputs are incomplete")
        values = {metric: _decimal(by_metric[metric].value) for metric in required}
        facts_for = lambda *metrics: tuple(sorted(by_metric[metric].fact_id for metric in metrics))
        checks = (
            (
                "technology_weight_pct",
                manifest.technology_weight_max_pct,
                "GT",
                "FUND_TECHNOLOGY_CONCENTRATION",
                FindingSeverity.WARNING,
                "科技行业权重为 {value:.2f}%，高于 {threshold:.2f}% 阈值。",
                "technology weight threshold",
            ),
            (
                "top10_weight_pct",
                manifest.top10_weight_max_pct,
                "GT",
                "FUND_TOP10_CONCENTRATION",
                FindingSeverity.WARNING,
                "前十大持仓权重为 {value:.2f}%，高于 {threshold:.2f}% 阈值。",
                "top10 concentration threshold",
            ),
            (
                "annualized_volatility_pct",
                manifest.volatility_max_pct,
                "GT",
                "FUND_VOLATILITY_RISK",
                FindingSeverity.WARNING,
                "年化波动为 {value:.2f}%，高于 {threshold:.2f}% 阈值。",
                "annualized volatility threshold",
            ),
            (
                "max_drawdown_pct",
                manifest.drawdown_max_pct,
                "GT",
                "FUND_DRAWDOWN_RISK",
                FindingSeverity.CRITICAL,
                "最大回撤为 {value:.2f}%，高于 {threshold:.2f}% 阈值，需人工复核。",
                "maximum drawdown threshold",
            ),
            (
                "expense_ratio_pct",
                manifest.expense_ratio_max_pct,
                "GT",
                "FUND_COST_WARNING",
                FindingSeverity.WARNING,
                "费率为 {value:.2f}%，高于 {threshold:.2f}% 阈值。",
                "expense ratio threshold",
            ),
        )
        findings: list[Finding] = []
        for metric, threshold, operator, kind, severity, statement_template, method_label in checks:
            value = values[metric]
            triggered = value > threshold if operator == "GT" else value < threshold
            if not triggered:
                continue
            statement = statement_template.format(value=value, threshold=threshold)
            methodology = f"deterministic Decimal threshold: {metric} {operator} configured fund-risk.v1 limit ({method_label})"
            findings.append(
                Finding(
                    finding_id=_stable_id("finding", owner_id, kind, statement, methodology),
                    kind=kind,
                    severity=severity,
                    statement=statement,
                    fact_ids=facts_for(metric),
                    confidence=1.0,
                    methodology=methodology,
                )
            )
        return tuple(sorted(findings, key=lambda item: item.finding_id))

    @staticmethod
    def _risk(findings: tuple[Finding, ...]) -> FundRiskSummary:
        critical = tuple(sorted(item.finding_id for item in findings if item.severity == FindingSeverity.CRITICAL))
        warning = tuple(sorted(item.finding_id for item in findings if item.severity == FindingSeverity.WARNING))
        if critical:
            return FundRiskSummary(
                status=FundRiskStatus.HIGH_RISK,
                summary=f"检测到 {len(critical)} 项 CRITICAL 基金风险，需人工复核；这不是交易建议。",
                finding_ids=tuple(sorted(set(critical) | set(warning))),
            )
        if warning:
            return FundRiskSummary(
                status=FundRiskStatus.WATCH,
                summary=f"检测到 {len(warning)} 项 WARNING 基金异常，需人工复核；这不是交易建议。",
                finding_ids=warning,
            )
        return FundRiskSummary(
            status=FundRiskStatus.CLEAR,
            summary="固定基金风险规则未触发；这不是交易建议。",
            finding_ids=(),
        )

    async def run(self, request: FundResearchRequest) -> FundResearchResponse:
        try:
            request = FundResearchRequest.model_validate(
                request.model_dump(mode="python") if isinstance(request, FundResearchRequest) else request
            )
        except Exception as exc:
            raise FundResearchError("fund research request was refused") from exc
        if request.subject != self._manifest.subject or request.period != self._manifest.period:
            raise FundResearchError("requested fund research scope is unavailable")
        scenario = _SCENARIO_BY_ID.get(request.scenario_id)
        if scenario is None:
            raise FundResearchError("requested fund research scenario is unavailable")

        try:
            plan = self._plan(request.owner_id, request.scenario_id)
            state = create_research_run(
                plan,
                request.request_id,
                self._manifest.budget_ms,
                request.generated_at,
            )
            clock = lambda: request.generated_at
            execution = await execute_research_run(
                state,
                _FundScenarioFixtureProvider(
                    FixtureFinancialProvider(fixture_dir=self._provider_dir, clock=clock),
                    request.scenario_id,
                ),
                self._requests(),
                started_at=request.generated_at,
                clock=clock,
            )
            pipeline = build_research_evidence_pipeline(
                execution,
                self._claim_specs(request.owner_id, execution),
            )
            issues = tuple(
                FundResearchIssue(
                    code=issue.code.value,
                    safe_message=issue.safe_message,
                    claim_id=issue.claim_id,
                )
                for issue in pipeline.issues
            )
            response_scenario = FundResearchScenarioResponse(
                schema_version="fund-research-scenario-response.v1",
                scenario_id=scenario.scenario_id,
                label=scenario.label,
                description=scenario.description,
            )
            if pipeline.status != ResearchPipelineStatus.READY:
                return FundResearchResponse(
                    manifest_id=self._manifest.manifest_id,
                    request_id=request.request_id,
                    owner_id=request.owner_id,
                    subject=self._manifest.subject,
                    period=self._manifest.period,
                    scenario=response_scenario,
                    run_id=execution.state.run_id,
                    run_status=execution.state.status,
                    pipeline_status=pipeline.status,
                    nodes=self._node_responses(execution),
                    validations=pipeline.validations,
                    facts=(),
                    findings=(),
                    risk=FundRiskSummary(
                        status=FundRiskStatus.NOT_ASSESSED,
                        summary="证据链未闭合，基金风险未评估。",
                        finding_ids=(),
                    ),
                    issues=issues,
                    trace=pipeline.trace,
                )

            facts = tuple(sorted(pipeline.trace.facts, key=lambda item: item.fact_id))
            derived = self._derived_findings(request.owner_id, facts, self._manifest)
            findings = tuple(sorted((*pipeline.trace.findings, *derived), key=lambda item: item.finding_id))
            trace = DecisionTrace(
                evidence=execution.evidence,
                facts=facts,
                findings=findings,
                recommendations=(),
            )
            return FundResearchResponse(
                manifest_id=self._manifest.manifest_id,
                request_id=request.request_id,
                owner_id=request.owner_id,
                subject=self._manifest.subject,
                period=self._manifest.period,
                scenario=response_scenario,
                run_id=execution.state.run_id,
                run_status=execution.state.status,
                pipeline_status=pipeline.status,
                nodes=self._node_responses(execution),
                validations=pipeline.validations,
                facts=facts,
                findings=findings,
                risk=self._risk(derived),
                issues=issues,
                trace=trace,
            )
        except FundResearchError:
            raise
        except Exception as exc:
            raise FundResearchError("fund research execution was refused") from exc


__all__ = ["FixtureFundResearchService", "FundResearchError"]
