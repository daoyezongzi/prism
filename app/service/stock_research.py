"""Fixture-first execution of the Demo F stock research Evidence Card."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path

from app.contracts.evidence import Finding, FindingSeverity, Fact
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
    ProviderStatus,
)
from app.research import (
    ResearchClaimSpec,
    ResearchPipelineStatus,
    ValidationClaim,
    build_research_evidence_pipeline,
)
from app.stock.contracts import (
    StockMetricResponse,
    StockResearchIssue,
    StockResearchManifest,
    StockResearchManifestNode,
    StockResearchMetricSpec,
    StockResearchRequest,
    StockResearchResponse,
    StockResearchScenarioDefinition,
    StockResearchScenarioId,
    StockResearchScenarioResponse,
    StockResearchTemplateResponse,
    StockRiskRuleResponse,
    StockRiskStatus,
    StockRiskSummary,
)


_DEFAULT_MANIFEST = Path(__file__).resolve().parent.parent / "fixtures" / "stock" / "stock_research_manifest.json"
_DEFAULT_PROVIDER_DIR = Path(__file__).resolve().parent.parent / "fixtures" / "stock" / "providers"

_SCENARIOS: tuple[StockResearchScenarioDefinition, ...] = (
    StockResearchScenarioDefinition(
        scenario_id=StockResearchScenarioId.BASELINE_READY,
        label="基线：双源一致",
        description="两条独立合成来源在同一报告期一致，允许生成可追溯事实与风险摘要。",
    ),
    StockResearchScenarioDefinition(
        scenario_id=StockResearchScenarioId.SOURCE_DISAGREEMENT,
        label="来源分歧：债务率冲突",
        description="来源 B 对资产负债率给出不同数值，冲突保持待复核，不升级为事实。",
    ),
    StockResearchScenarioDefinition(
        scenario_id=StockResearchScenarioId.SOURCE_PARTIAL,
        label="来源部分缺失",
        description="来源 B 缺少一个必需财务字段，保留可用证据但阻止完整结论。",
    ),
    StockResearchScenarioDefinition(
        scenario_id=StockResearchScenarioId.SOURCE_EMPTY,
        label="来源无结果",
        description="来源 B 在声明范围内没有记录，不能将无结果当作零值。",
    ),
    StockResearchScenarioDefinition(
        scenario_id=StockResearchScenarioId.SOURCE_FAILED,
        label="来源失败",
        description="来源 B 安全失败，失败状态不转换为 EMPTY 或可用事实。",
    ),
)
_SCENARIO_BY_ID = {item.scenario_id: item for item in _SCENARIOS}


class StockResearchError(RuntimeError):
    """Safe boundary for invalid or unavailable stock research requests."""


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None or isinstance(value, (Mapping, list, tuple)):
        raise ValueError("stock value is not a scalar")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("stock value is not decimal") from exc
    if not parsed.is_finite():
        raise ValueError("stock value must be finite")
    return parsed


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if denominator <= Decimal("0"):
        raise ValueError("stock ratio denominator must be positive")
    return (numerator / denominator * Decimal("100")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )


def _node_result_with_record(
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


class _StockScenarioFixtureProvider:
    """Read-only deterministic overlay over the stock fixture provider."""

    def __init__(self, base: FixtureFinancialProvider, scenario: StockResearchScenarioId):
        self._base = base
        self._scenario = scenario

    @property
    def name(self) -> str:
        return self._base.name

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        result = await self._base.execute(request)
        if self._scenario == StockResearchScenarioId.BASELINE_READY:
            return result
        if request.parameters.get("source_slot") != "b":
            return result

        if self._scenario == StockResearchScenarioId.SOURCE_DISAGREEMENT:
            if result.status != ProviderStatus.SUCCESS or not result.records:
                return result
            original = result.records[0]
            fields = dict(original.fields)
            fields["debt_ratio_pct"] = "62.00"
            record = ProviderRecord.model_validate(
                {
                    **original.model_dump(mode="python"),
                    "fields": fields,
                }
            )
            return _node_result_with_record(result, record, status=ProviderStatus.SUCCESS)

        if self._scenario == StockResearchScenarioId.SOURCE_PARTIAL:
            if result.status != ProviderStatus.SUCCESS or not result.records:
                return result
            original = result.records[0]
            fields = {
                key: value
                for key, value in original.fields.items()
                if key != "debt_ratio_pct"
            }
            units = {
                key: value
                for key, value in original.units.items()
                if key in fields
            }
            record = ProviderRecord.model_validate(
                {
                    **original.model_dump(mode="python"),
                    "fields": fields,
                    "units": units,
                }
            )
            return _node_result_with_record(
                result,
                record,
                status=ProviderStatus.PARTIAL,
                missing_fields=("debt_ratio_pct",),
            )

        if self._scenario == StockResearchScenarioId.SOURCE_EMPTY:
            return ProviderResult.model_validate(
                {
                    **result.model_dump(mode="python"),
                    "status": ProviderStatus.EMPTY,
                    "records": (),
                    "missing_fields": (),
                    "issues": (),
                    "scope_description": "source B returned no stock record for the requested period",
                }
            )

        if self._scenario == StockResearchScenarioId.SOURCE_FAILED:
            return ProviderResult.model_validate(
                {
                    **result.model_dump(mode="python"),
                    "status": ProviderStatus.FAILED,
                    "records": (),
                    "missing_fields": (),
                    "issues": (
                        {
                            "code": "TRANSPORT_ERROR",
                            "stage": "stock-source",
                            "safe_message": "source B was unavailable in this offline replay",
                            "retriable": False,
                            "diagnostics": {},
                        },
                    ),
                    "scope_description": None,
                }
            )

        raise StockResearchError("unsupported stock research scenario")


class FixtureStockResearchService:
    """Run the fixed Demo F stock card through Prism's existing research chain."""

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
            self._manifest = StockResearchManifest.model_validate(payload)
        except Exception as exc:
            raise StockResearchError("stock research manifest could not be loaded") from exc
        if not self._provider_dir.exists() or not self._provider_dir.is_dir():
            raise StockResearchError("stock research provider fixtures are unavailable")

    @property
    def manifest_id(self) -> str:
        return self._manifest.manifest_id

    @property
    def scenarios(self) -> tuple[StockResearchScenarioDefinition, ...]:
        return tuple(sorted(_SCENARIOS, key=lambda item: item.scenario_id.value))

    def template(self, owner_id: str) -> StockResearchTemplateResponse:
        """Return only safe presentation metadata; owner is checked at the API boundary."""

        if not isinstance(owner_id, str) or not owner_id.strip():
            raise StockResearchError("stock research owner is required")
        if any(token in owner_id.casefold().replace("-", "_") for token in ("api_key", "token", "secret", "password")):
            raise StockResearchError("stock research owner is not allowed")
        metrics = tuple(
            StockMetricResponse(metric=item.metric, label=item.label, unit=item.unit)
            for item in self._manifest.metrics
        )
        risk_rules = (
            StockRiskRuleResponse(
                rule_id="stock-cashflow-quality",
                label="现金流质量低于阈值",
                operator="LT",
                threshold=self._manifest.cashflow_quality_min_pct,
                unit="pct",
            ),
            StockRiskRuleResponse(
                rule_id="stock-receivable-ratio",
                label="应收账款占收入超过阈值",
                operator="GT",
                threshold=self._manifest.receivable_ratio_max_pct,
                unit="pct",
            ),
            StockRiskRuleResponse(
                rule_id="stock-debt-ratio",
                label="资产负债率超过阈值",
                operator="GT",
                threshold=self._manifest.debt_ratio_max_pct,
                unit="pct",
            ),
        )
        scenarios = tuple(
            StockResearchScenarioResponse(
                schema_version="stock-research-scenario-response.v1",
                scenario_id=item.scenario_id,
                label=item.label,
                description=item.description,
            )
            for item in self.scenarios
        )
        return StockResearchTemplateResponse(
            manifest_id=self._manifest.manifest_id,
            subject=self._manifest.subject,
            period=self._manifest.period,
            generated_at=self._manifest.generated_at,
            budget_ms=self._manifest.budget_ms,
            metrics=metrics,
            risk_rules=risk_rules,
            scenarios=scenarios,
        )

    def _plan(self, owner_id: str, scenario: StockResearchScenarioId):
        scope = f"{self._manifest.scope_description} · replay {scenario.value}"
        nodes = tuple(
            ResearchNodeSpec(
                node_id=node.node_id,
                owner_id=owner_id,
                node_kind="STOCK",
                required=True,
                dependencies=(),
                timeout_ms=min(node.timeout_ms, self._manifest.budget_ms),
            )
            for node in self._manifest.nodes
        )
        return build_research_plan(owner_id, scope, nodes)

    def _requests(self, owner_id: str) -> tuple[ResearchNodeRequest, ...]:
        return tuple(
            ResearchNodeRequest(
                node_id=node.node_id,
                request=ProviderRequest(
                    request_id=node.request_id,
                    operation=ProviderOperation.COMPANY_DATA,
                    subject=self._manifest.subject,
                    required_fields=node.required_fields,
                    parameters=node.parameters,
                    timeout_ms=min(node.timeout_ms, self._manifest.budget_ms),
                ),
            )
            for node in self._manifest.nodes
        )

    def _claim_specs(
        self,
        owner_id: str,
        execution,
    ) -> tuple[ResearchClaimSpec, ...]:
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
                claim_id=f"claim-stock-{item.metric}",
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
    def _derived_findings(
        owner_id: str,
        facts: tuple[Fact, ...],
        manifest: StockResearchManifest,
    ) -> tuple[Finding, ...]:
        by_metric = {fact.metric: fact for fact in facts}
        required = {
            "revenue_cny",
            "net_profit_cny",
            "operating_cash_flow_cny",
            "accounts_receivable_cny",
            "debt_ratio_pct",
        }
        if not required.issubset(by_metric):
            raise StockResearchError("stock deterministic risk inputs are incomplete")
        revenue = _decimal(by_metric["revenue_cny"].value)
        net_profit = _decimal(by_metric["net_profit_cny"].value)
        cashflow = _decimal(by_metric["operating_cash_flow_cny"].value)
        receivable = _decimal(by_metric["accounts_receivable_cny"].value)
        debt_ratio = _decimal(by_metric["debt_ratio_pct"].value)
        facts_for = lambda *metrics: tuple(
            sorted((by_metric[metric].fact_id for metric in metrics))
        )
        findings: list[Finding] = []

        cashflow_ratio = _pct(cashflow, net_profit)
        if cashflow_ratio < manifest.cashflow_quality_min_pct:
            kind = "STOCK_CASHFLOW_QUALITY_ANOMALY"
            methodology = "deterministic Decimal ratio: operating_cash_flow_cny / net_profit_cny × 100; stock-risk.v1"
            statement = (
                f"经营现金流/净利润为 {cashflow_ratio:.2f}%，低于 {manifest.cashflow_quality_min_pct:.2f}% 阈值。"
            )
            findings.append(
                Finding(
                    finding_id=_stable_id("finding", owner_id, kind, statement, methodology),
                    kind=kind,
                    severity=FindingSeverity.WARNING,
                    statement=statement,
                    fact_ids=facts_for("operating_cash_flow_cny", "net_profit_cny"),
                    confidence=1.0,
                    methodology=methodology,
                )
            )

        receivable_ratio = _pct(receivable, revenue)
        if receivable_ratio > manifest.receivable_ratio_max_pct:
            kind = "STOCK_RECEIVABLE_QUALITY_ANOMALY"
            methodology = "deterministic Decimal ratio: accounts_receivable_cny / revenue_cny × 100; stock-risk.v1"
            statement = (
                f"应收账款/营业收入为 {receivable_ratio:.2f}%，高于 {manifest.receivable_ratio_max_pct:.2f}% 阈值。"
            )
            findings.append(
                Finding(
                    finding_id=_stable_id("finding", owner_id, kind, statement, methodology),
                    kind=kind,
                    severity=FindingSeverity.WARNING,
                    statement=statement,
                    fact_ids=facts_for("accounts_receivable_cny", "revenue_cny"),
                    confidence=1.0,
                    methodology=methodology,
                )
            )

        if debt_ratio > manifest.debt_ratio_max_pct:
            kind = "STOCK_LEVERAGE_RISK"
            methodology = "deterministic Decimal threshold: debt_ratio_pct > stock-risk.v1 limit"
            statement = (
                f"资产负债率为 {debt_ratio:.2f}%，高于 {manifest.debt_ratio_max_pct:.2f}% 阈值，需人工复核。"
            )
            findings.append(
                Finding(
                    finding_id=_stable_id("finding", owner_id, kind, statement, methodology),
                    kind=kind,
                    severity=FindingSeverity.CRITICAL,
                    statement=statement,
                    fact_ids=facts_for("debt_ratio_pct"),
                    confidence=1.0,
                    methodology=methodology,
                )
            )
        return tuple(sorted(findings, key=lambda item: item.finding_id))

    @staticmethod
    def _risk(findings: tuple[Finding, ...]) -> StockRiskSummary:
        critical = tuple(sorted(item.finding_id for item in findings if item.severity == FindingSeverity.CRITICAL))
        warning = tuple(sorted(item.finding_id for item in findings if item.severity == FindingSeverity.WARNING))
        if critical:
            return StockRiskSummary(
                status=StockRiskStatus.HIGH_RISK,
                summary=f"检测到 {len(critical)} 项 CRITICAL 风险，需人工复核；这不是交易建议。",
                finding_ids=tuple(sorted(set(critical) | set(warning))),
            )
        if warning:
            return StockRiskSummary(
                status=StockRiskStatus.WATCH,
                summary=f"检测到 {len(warning)} 项 WARNING 异常，需人工复核；这不是交易建议。",
                finding_ids=warning,
            )
        return StockRiskSummary(
            status=StockRiskStatus.CLEAR,
            summary="固定风险规则未触发；这不是交易建议。",
            finding_ids=(),
        )

    async def run(self, request: StockResearchRequest) -> StockResearchResponse:
        try:
            request = StockResearchRequest.model_validate(
                request.model_dump(mode="python")
                if isinstance(request, StockResearchRequest)
                else request
            )
        except Exception as exc:
            raise StockResearchError("stock research request was refused") from exc
        if request.subject != self._manifest.subject or request.period != self._manifest.period:
            raise StockResearchError("requested stock research scope is unavailable")
        scenario = _SCENARIO_BY_ID.get(request.scenario_id)
        if scenario is None:
            raise StockResearchError("requested stock research scenario is unavailable")

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
                _StockScenarioFixtureProvider(
                    FixtureFinancialProvider(fixture_dir=self._provider_dir, clock=clock),
                    request.scenario_id,
                ),
                self._requests(request.owner_id),
                started_at=request.generated_at,
                clock=clock,
            )
            pipeline = build_research_evidence_pipeline(
                execution,
                self._claim_specs(request.owner_id, execution),
            )
            issues = tuple(
                StockResearchIssue(
                    code=issue.code.value,
                    safe_message=issue.safe_message,
                    claim_id=issue.claim_id,
                )
                for issue in pipeline.issues
            )
            if pipeline.status != ResearchPipelineStatus.READY:
                return StockResearchResponse(
                    manifest_id=self._manifest.manifest_id,
                    request_id=request.request_id,
                    owner_id=request.owner_id,
                    subject=self._manifest.subject,
                    period=self._manifest.period,
                    scenario=StockResearchScenarioResponse(
                        schema_version="stock-research-scenario-response.v1",
                        scenario_id=scenario.scenario_id,
                        label=scenario.label,
                        description=scenario.description,
                    ),
                    run_id=execution.state.run_id,
                    run_status=execution.state.status,
                    pipeline_status=pipeline.status,
                    validations=pipeline.validations,
                    facts=(),
                    findings=(),
                    risk=StockRiskSummary(
                        status=StockRiskStatus.NOT_ASSESSED,
                        summary="证据链未闭合，风险未评估。",
                        finding_ids=(),
                    ),
                    issues=issues,
                    trace=pipeline.trace,
                )

            facts = tuple(sorted(pipeline.trace.facts, key=lambda item: item.fact_id))
            derived = self._derived_findings(request.owner_id, facts, self._manifest)
            findings = tuple(sorted((*pipeline.trace.findings, *derived), key=lambda item: item.finding_id))
            from app.contracts.evidence import DecisionTrace

            trace = DecisionTrace(
                evidence=execution.evidence,
                facts=facts,
                findings=findings,
                recommendations=(),
            )
            return StockResearchResponse(
                manifest_id=self._manifest.manifest_id,
                request_id=request.request_id,
                owner_id=request.owner_id,
                subject=self._manifest.subject,
                period=self._manifest.period,
                scenario=StockResearchScenarioResponse(
                    schema_version="stock-research-scenario-response.v1",
                    scenario_id=scenario.scenario_id,
                    label=scenario.label,
                    description=scenario.description,
                ),
                run_id=execution.state.run_id,
                run_status=execution.state.status,
                pipeline_status=pipeline.status,
                validations=pipeline.validations,
                facts=facts,
                findings=findings,
                risk=self._risk(derived),
                issues=issues,
                trace=trace,
            )
        except StockResearchError:
            raise
        except Exception as exc:
            raise StockResearchError("stock research execution was refused") from exc


__all__ = ["FixtureStockResearchService", "StockResearchError"]
