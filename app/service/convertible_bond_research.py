"""Fixture-first execution of the minimum convertible-bond Evidence Card."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from hashlib import sha256
from pathlib import Path

from app.contracts.evidence import (
    DecisionTrace,
    Evidence,
    EvidenceQualityStatus,
    Fact,
    FactStatus,
    Finding,
    FindingSeverity,
)
from app.convertible_bond.contracts import (
    CONVERTIBLE_BOND_METRIC_UNITS,
    ConvertibleBondMetricResponse,
    ConvertibleBondResearchIssue,
    ConvertibleBondResearchManifest,
    ConvertibleBondResearchNodeResponse,
    ConvertibleBondResearchRequest,
    ConvertibleBondResearchResponse,
    ConvertibleBondResearchScenarioDefinition,
    ConvertibleBondResearchScenarioId,
    ConvertibleBondResearchScenarioResponse,
    ConvertibleBondResearchTemplateResponse,
    ConvertibleBondRiskRuleResponse,
    ConvertibleBondRiskStatus,
    ConvertibleBondRiskSummary,
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
    ProviderStatus,
)
from app.research import (
    ResearchClaimSpec,
    ResearchNodeKind,
    ResearchPipelineStatus,
    ValidationClaim,
    build_research_evidence_pipeline,
)


_DEFAULT_MANIFEST = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "convertible_bond"
    / "convertible_bond_research_manifest.json"
)
_DEFAULT_PROVIDER_DIR = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "convertible_bond"
    / "providers"
)
_QUANTUM = Decimal("0.01")

_SCENARIOS: tuple[ConvertibleBondResearchScenarioDefinition, ...] = (
    ConvertibleBondResearchScenarioDefinition(
        scenario_id=ConvertibleBondResearchScenarioId.BASELINE_READY,
        label="基线：双源一致",
        description="两条独立合成来源在同一报告期一致，允许生成可追溯可转债事实与风险摘要。",
    ),
    ConvertibleBondResearchScenarioDefinition(
        scenario_id=ConvertibleBondResearchScenarioId.SOURCE_DISAGREEMENT,
        label="来源分歧：转股价冲突",
        description="来源 B 对转股价给出不同数值，冲突保持待复核，不升级为事实。",
    ),
    ConvertibleBondResearchScenarioDefinition(
        scenario_id=ConvertibleBondResearchScenarioId.SOURCE_PARTIAL,
        label="来源部分缺失",
        description="来源 B 缺少债底字段，保留可用证据但阻止完整资产结论。",
    ),
    ConvertibleBondResearchScenarioDefinition(
        scenario_id=ConvertibleBondResearchScenarioId.SOURCE_EMPTY,
        label="来源无结果",
        description="来源 B 在声明范围内没有记录，不能将无结果当作零值。",
    ),
    ConvertibleBondResearchScenarioDefinition(
        scenario_id=ConvertibleBondResearchScenarioId.SOURCE_FAILED,
        label="来源失败",
        description="来源 B 安全失败，失败状态不转换为 EMPTY 或可用事实。",
    ),
)
_SCENARIO_BY_ID = {item.scenario_id: item for item in _SCENARIOS}


class ConvertibleBondResearchError(RuntimeError):
    """Safe boundary for invalid or unavailable convertible-bond requests."""


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


def _decimal(value: object) -> Decimal:
    if isinstance(value, bool) or value is None or isinstance(value, (Mapping, list, tuple)):
        raise ValueError("convertible value is not a scalar")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("convertible value is not decimal") from exc
    if not parsed.is_finite():
        raise ValueError("convertible value must be finite")
    return parsed


def _money(value: Decimal) -> str:
    return str(value.quantize(_QUANTUM, rounding=ROUND_HALF_UP))


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


class _ConvertibleScenarioFixtureProvider:
    """Read-only deterministic overlay over the convertible-bond fixtures."""

    def __init__(self, base: FixtureFinancialProvider, scenario: ConvertibleBondResearchScenarioId):
        self._base = base
        self._scenario = scenario

    @property
    def name(self) -> str:
        return self._base.name

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        result = await self._base.execute(request)
        if request.parameters.get("source_slot") != "b":
            return result
        if self._scenario == ConvertibleBondResearchScenarioId.BASELINE_READY:
            return result
        if self._scenario == ConvertibleBondResearchScenarioId.SOURCE_DISAGREEMENT:
            if result.status != ProviderStatus.SUCCESS or not result.records:
                return result
            original = result.records[0]
            fields = dict(original.fields)
            fields["conversion_price"] = "11.00"
            record = ProviderRecord.model_validate(
                {**original.model_dump(mode="python"), "fields": fields}
            )
            return _result_with_record(result, record, status=ProviderStatus.SUCCESS)
        if self._scenario == ConvertibleBondResearchScenarioId.SOURCE_PARTIAL:
            if result.status != ProviderStatus.SUCCESS or not result.records:
                return result
            original = result.records[0]
            fields = {
                key: value for key, value in original.fields.items() if key != "bond_floor"
            }
            units = {key: value for key, value in original.units.items() if key in fields}
            record = ProviderRecord.model_validate(
                {**original.model_dump(mode="python"), "fields": fields, "units": units}
            )
            return _result_with_record(
                result,
                record,
                status=ProviderStatus.PARTIAL,
                missing_fields=("bond_floor",),
            )
        if self._scenario == ConvertibleBondResearchScenarioId.SOURCE_EMPTY:
            return ProviderResult.model_validate(
                {
                    **result.model_dump(mode="python"),
                    "status": ProviderStatus.EMPTY,
                    "records": (),
                    "missing_fields": (),
                    "issues": (),
                    "scope_description": "source B returned no convertible bond record for the requested period",
                }
            )
        if self._scenario == ConvertibleBondResearchScenarioId.SOURCE_FAILED:
            return ProviderResult.model_validate(
                {
                    **result.model_dump(mode="python"),
                    "status": ProviderStatus.FAILED,
                    "records": (),
                    "missing_fields": (),
                    "issues": (
                        {
                            "code": "TRANSPORT_ERROR",
                            "stage": "convertible-bond-source",
                            "safe_message": "source B was unavailable in this offline replay",
                            "retriable": False,
                            "diagnostics": {},
                        },
                    ),
                    "scope_description": None,
                }
            )
        raise ConvertibleBondResearchError("unsupported convertible-bond research scenario")


class FixtureConvertibleBondResearchService:
    """Run a fixed minimum convertible-bond card through Prism's research chain."""

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
            self._manifest = ConvertibleBondResearchManifest.model_validate(payload)
        except Exception as exc:
            raise ConvertibleBondResearchError(
                "convertible-bond research manifest could not be loaded"
            ) from exc
        if not self._provider_dir.exists() or not self._provider_dir.is_dir():
            raise ConvertibleBondResearchError(
                "convertible-bond research provider fixtures are unavailable"
            )

    @property
    def manifest_id(self) -> str:
        return self._manifest.manifest_id

    @property
    def scenarios(self) -> tuple[ConvertibleBondResearchScenarioDefinition, ...]:
        return tuple(sorted(_SCENARIOS, key=lambda item: item.scenario_id.value))

    def template(self, owner_id: str) -> ConvertibleBondResearchTemplateResponse:
        if not isinstance(owner_id, str) or not owner_id.strip():
            raise ConvertibleBondResearchError("convertible-bond research owner is required")
        if any(token in owner_id.casefold().replace("-", "_") for token in ("api_key", "token", "secret", "password")):
            raise ConvertibleBondResearchError("convertible-bond research owner is not allowed")
        metrics = tuple(
            ConvertibleBondMetricResponse(
                metric=item.metric,
                label=item.label,
                unit=item.unit,
                derived=item.derived,
                formula=item.formula,
            )
            for item in self._manifest.metrics
        )
        risk_rules = (
            ConvertibleBondRiskRuleResponse(
                rule_id="convertible-premium",
                label="转股溢价率超过阈值",
                operator="GT",
                threshold=self._manifest.conversion_premium_max_pct,
                unit="pct",
            ),
            ConvertibleBondRiskRuleResponse(
                rule_id="convertible-bond-floor",
                label="债底低于阈值",
                operator="LT",
                threshold=self._manifest.bond_floor_min,
                unit="CNY",
            ),
            ConvertibleBondRiskRuleResponse(
                rule_id="convertible-negative-yield",
                label="到期收益率低于阈值",
                operator="LT",
                threshold=self._manifest.negative_yield_min_pct,
                unit="pct",
            ),
            ConvertibleBondRiskRuleResponse(
                rule_id="convertible-credit-risk",
                label="信用评级序数达到风险阈值",
                operator="GTE",
                threshold=self._manifest.credit_rating_min_risk_rank,
                unit="rating_rank",
            ),
            ConvertibleBondRiskRuleResponse(
                rule_id="convertible-liquidity-risk",
                label="流动性等级序数达到风险阈值",
                operator="GTE",
                threshold=self._manifest.liquidity_min_risk_score,
                unit="score",
            ),
        )
        scenarios = tuple(
            ConvertibleBondResearchScenarioResponse(
                schema_version="convertible-bond-research-scenario-response.v1",
                scenario_id=item.scenario_id,
                label=item.label,
                description=item.description,
            )
            for item in self.scenarios
        )
        return ConvertibleBondResearchTemplateResponse(
            manifest_id=self._manifest.manifest_id,
            subject=self._manifest.subject,
            period=self._manifest.period,
            generated_at=self._manifest.generated_at,
            budget_ms=self._manifest.budget_ms,
            bond_par_value=self._manifest.bond_par_value,
            metrics=metrics,
            risk_rules=risk_rules,
            credit_rating_labels=self._manifest.credit_rating_labels,
            liquidity_labels=self._manifest.liquidity_labels,
            scenarios=scenarios,
        )

    def _plan(self, owner_id: str, scenario: ConvertibleBondResearchScenarioId):
        scope = f"{self._manifest.scope_description} · replay {scenario.value}"
        nodes = tuple(
            ResearchNodeSpec(
                node_id=node.node_id,
                owner_id=owner_id,
                node_kind=ResearchNodeKind.CONVERTIBLE_BOND,
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
                    operation=ProviderOperation.CONVERTIBLE_BOND_DATA,
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
            if item.derived:
                continue
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
                claim_id=f"claim-convertible-{item.metric}",
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
    def _node_responses(execution) -> tuple[ConvertibleBondResearchNodeResponse, ...]:
        responses: list[ConvertibleBondResearchNodeResponse] = []
        for node in sorted(execution.state.nodes, key=lambda item: item.node_id):
            issue_by_code: dict[str, ConvertibleBondResearchIssue] = {}
            for issue in node.issues:
                code = issue.code.value
                issue_by_code.setdefault(code, ConvertibleBondResearchIssue(code=code, safe_message=issue.safe_message))
            missing_fields: tuple[str, ...] = ()
            scope_description: str | None = None
            if node.result is not None:
                missing_fields = tuple(sorted(node.result.missing_fields))
                scope_description = node.result.scope_description
                for issue in node.result.issues:
                    code = issue.code.value
                    issue_by_code.setdefault(code, ConvertibleBondResearchIssue(code=code, safe_message=issue.safe_message))
            responses.append(
                ConvertibleBondResearchNodeResponse(
                    node_id=node.node_id,
                    required=node.required,
                    status=node.status,
                    started_at=node.started_at,
                    finished_at=node.finished_at,
                    missing_fields=missing_fields,
                    scope_description=scope_description,
                    issues=tuple(issue_by_code[key] for key in sorted(issue_by_code)),
                )
            )
        return tuple(responses)

    def _formula_fact(
        self,
        *,
        owner_id: str,
        metric: str,
        value: Decimal,
        formula: str,
        input_facts: tuple[Fact, ...],
        generated_at: datetime,
    ) -> tuple[Evidence, Fact, Finding]:
        formatted = _money(value)
        evidence_id = _stable_id(
            "evidence",
            owner_id,
            self._manifest.subject,
            self._manifest.period,
            metric,
            formatted,
            formula,
        )
        evidence = Evidence(
            evidence_id=evidence_id,
            provider="prism-deterministic",
            source="convertible-bond-formula-v1",
            field=metric,
            value=formatted,
            unit=CONVERTIBLE_BOND_METRIC_UNITS[metric],
            period=self._manifest.period,
            retrieved_at=generated_at,
            quality_status=EvidenceQualityStatus.VERIFIED,
            lineage_id=f"formula:{metric}",
        )
        fact_id = _stable_id(
            "fact",
            owner_id,
            self._manifest.subject,
            self._manifest.period,
            metric,
            formatted,
            evidence_id,
        )
        fact = Fact(
            fact_id=fact_id,
            subject=self._manifest.subject,
            metric=metric,
            value=formatted,
            unit=CONVERTIBLE_BOND_METRIC_UNITS[metric],
            period=self._manifest.period,
            status=FactStatus.VERIFIED,
            evidence_ids=(evidence_id,),
        )
        finding = Finding(
            finding_id=_stable_id("finding", fact_id, formula),
            kind=f"{metric.upper()}_FORMULA",
            severity=FindingSeverity.INFO,
            statement=f"{metric} 按固定 Decimal 公式计算：{formula}。",
            fact_ids=(fact_id,),
            confidence=1.0,
            methodology=f"deterministic Decimal convertible-bond-formula.v1; input_fact_ids={','.join(item.fact_id for item in input_facts)}",
        )
        return evidence, fact, finding

    def _derived_facts_and_findings(
        self,
        owner_id: str,
        facts: tuple[Fact, ...],
        generated_at: datetime,
    ) -> tuple[tuple[Evidence, ...], tuple[Fact, ...], tuple[Finding, ...]]:
        by_metric = {fact.metric: fact for fact in facts}
        required = {
            "underlying_stock_price",
            "conversion_price",
            "bond_price",
        }
        if not required.issubset(by_metric):
            raise ConvertibleBondResearchError("convertible deterministic inputs are incomplete")
        underlying = _decimal(by_metric["underlying_stock_price"].value)
        conversion_price = _decimal(by_metric["conversion_price"].value)
        bond_price = _decimal(by_metric["bond_price"].value)
        if underlying <= 0 or conversion_price <= 0 or bond_price <= 0:
            raise ConvertibleBondResearchError("convertible deterministic inputs must be positive")
        for metric, labels in (
            ("credit_rating_rank", self._manifest.credit_rating_labels),
            ("liquidity_score", self._manifest.liquidity_labels),
        ):
            level = _decimal(by_metric[metric].value)
            if level != level.to_integral_value() or str(int(level)) not in labels:
                raise ConvertibleBondResearchError(
                    f"convertible {metric} is outside the declared label set"
                )
        conversion_value = (underlying / conversion_price * self._manifest.bond_par_value).quantize(_QUANTUM, rounding=ROUND_HALF_UP)
        if conversion_value <= 0:
            raise ConvertibleBondResearchError("convertible conversion value must be positive")
        premium = ((bond_price / conversion_value - Decimal("1")) * Decimal("100")).quantize(
            _QUANTUM, rounding=ROUND_HALF_UP
        )
        evidence_items: list[Evidence] = []
        derived_facts: list[Fact] = []
        formula_findings: list[Finding] = []
        conversion_evidence, conversion_fact, conversion_finding = self._formula_fact(
            owner_id=owner_id,
            metric="conversion_value",
            value=conversion_value,
            formula="underlying_stock_price / conversion_price * bond_par_value",
            input_facts=(by_metric["underlying_stock_price"], by_metric["conversion_price"]),
            generated_at=generated_at,
        )
        evidence_items.append(conversion_evidence)
        derived_facts.append(conversion_fact)
        formula_findings.append(conversion_finding)
        for metric, value, formula, inputs in (
            (
                "conversion_premium_pct",
                premium,
                "(bond_price / conversion_value - 1) * 100",
                (by_metric["bond_price"], conversion_fact),
            ),
        ):
            evidence, fact, finding = self._formula_fact(
                owner_id=owner_id,
                metric=metric,
                value=value,
                formula=formula,
                input_facts=inputs,
                generated_at=generated_at,
            )
            evidence_items.append(evidence)
            derived_facts.append(fact)
            formula_findings.append(finding)
        return tuple(evidence_items), tuple(derived_facts), tuple(formula_findings)

    def _risk_findings(self, owner_id: str, facts: tuple[Fact, ...]) -> tuple[Finding, ...]:
        by_metric = {fact.metric: fact for fact in facts}
        values = {metric: _decimal(fact.value) for metric, fact in by_metric.items()}
        facts_for = lambda metric: (by_metric[metric].fact_id,)
        checks = (
            ("conversion_premium_pct", values["conversion_premium_pct"] > self._manifest.conversion_premium_max_pct, "CONVERTIBLE_PREMIUM_WARNING", FindingSeverity.WARNING, f"转股溢价率为 {values['conversion_premium_pct']:.2f}%，高于 {self._manifest.conversion_premium_max_pct:.2f}% 阈值。", "conversion premium threshold"),
            ("bond_floor", values["bond_floor"] < self._manifest.bond_floor_min, "CONVERTIBLE_BOND_FLOOR_WARNING", FindingSeverity.WARNING, f"债底为 {values['bond_floor']:.2f}，低于 {self._manifest.bond_floor_min:.2f} 阈值。", "bond floor threshold"),
            ("yield_to_maturity_pct", values["yield_to_maturity_pct"] < self._manifest.negative_yield_min_pct, "CONVERTIBLE_NEGATIVE_YIELD", FindingSeverity.WARNING, f"到期收益率为 {values['yield_to_maturity_pct']:.2f}%，低于 {self._manifest.negative_yield_min_pct:.2f}% 阈值。", "negative yield threshold"),
            ("credit_rating_rank", values["credit_rating_rank"] >= self._manifest.credit_rating_min_risk_rank, "CONVERTIBLE_CREDIT_RISK", FindingSeverity.CRITICAL, f"信用评级序数为 {values['credit_rating_rank']:.0f}，达到 {self._manifest.credit_rating_min_risk_rank:.0f} 风险阈值，需人工复核。", "credit rating rank threshold"),
            ("liquidity_score", values["liquidity_score"] >= self._manifest.liquidity_min_risk_score, "CONVERTIBLE_LIQUIDITY_RISK", FindingSeverity.WARNING, f"流动性等级序数为 {values['liquidity_score']:.0f}，达到 {self._manifest.liquidity_min_risk_score:.0f} 风险阈值。", "liquidity score threshold"),
        )
        findings: list[Finding] = []
        for metric, triggered, kind, severity, statement, method_label in checks:
            if not triggered:
                continue
            methodology = f"deterministic Decimal threshold: {metric} configured convertible-bond-risk.v1 limit ({method_label})"
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
    def _risk(findings: tuple[Finding, ...]) -> ConvertibleBondRiskSummary:
        critical = tuple(sorted(item.finding_id for item in findings if item.severity == FindingSeverity.CRITICAL))
        warning = tuple(sorted(item.finding_id for item in findings if item.severity == FindingSeverity.WARNING))
        if critical:
            return ConvertibleBondRiskSummary(
                status=ConvertibleBondRiskStatus.HIGH_RISK,
                summary=f"检测到 {len(critical)} 项 CRITICAL 可转债风险，需人工复核；这不是交易建议。",
                finding_ids=tuple(sorted(set(critical) | set(warning))),
            )
        if warning:
            return ConvertibleBondRiskSummary(
                status=ConvertibleBondRiskStatus.WATCH,
                summary=f"检测到 {len(warning)} 项 WARNING 可转债异常，需人工复核；这不是交易建议。",
                finding_ids=warning,
            )
        return ConvertibleBondRiskSummary(
            status=ConvertibleBondRiskStatus.CLEAR,
            summary="固定可转债风险规则未触发；这不是交易建议。",
            finding_ids=(),
        )

    async def run(self, request: ConvertibleBondResearchRequest) -> ConvertibleBondResearchResponse:
        try:
            request = ConvertibleBondResearchRequest.model_validate(
                request.model_dump(mode="python") if isinstance(request, ConvertibleBondResearchRequest) else request
            )
        except Exception as exc:
            raise ConvertibleBondResearchError("convertible-bond research request was refused") from exc
        if request.subject != self._manifest.subject or request.period != self._manifest.period:
            raise ConvertibleBondResearchError("requested convertible-bond research scope is unavailable")
        scenario = _SCENARIO_BY_ID.get(request.scenario_id)
        if scenario is None:
            raise ConvertibleBondResearchError("requested convertible-bond research scenario is unavailable")
        try:
            plan = self._plan(request.owner_id, request.scenario_id)
            state = create_research_run(plan, request.request_id, self._manifest.budget_ms, request.generated_at)
            clock = lambda: request.generated_at
            execution = await execute_research_run(
                state,
                _ConvertibleScenarioFixtureProvider(
                    FixtureFinancialProvider(fixture_dir=self._provider_dir, clock=clock),
                    request.scenario_id,
                ),
                self._requests(),
                started_at=request.generated_at,
                clock=clock,
            )
            pipeline = build_research_evidence_pipeline(execution, self._claim_specs(request.owner_id, execution))
            issues = tuple(
                ConvertibleBondResearchIssue(code=issue.code.value, safe_message=issue.safe_message, claim_id=issue.claim_id)
                for issue in pipeline.issues
            )
            response_scenario = ConvertibleBondResearchScenarioResponse(
                schema_version="convertible-bond-research-scenario-response.v1",
                scenario_id=scenario.scenario_id,
                label=scenario.label,
                description=scenario.description,
            )
            if pipeline.status != ResearchPipelineStatus.READY:
                return ConvertibleBondResearchResponse(
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
                    risk=ConvertibleBondRiskSummary(
                        status=ConvertibleBondRiskStatus.NOT_ASSESSED,
                        summary="证据链未闭合，可转债风险未评估。",
                        finding_ids=(),
                    ),
                    issues=issues,
                    trace=pipeline.trace,
                )
            raw_facts = tuple(sorted(pipeline.trace.facts, key=lambda item: item.fact_id))
            formula_evidence, derived_facts, formula_findings = self._derived_facts_and_findings(
                request.owner_id, raw_facts, request.generated_at
            )
            facts = tuple(sorted((*raw_facts, *derived_facts), key=lambda item: item.fact_id))
            findings = tuple(
                sorted(
                    (*pipeline.trace.findings, *formula_findings, *self._risk_findings(request.owner_id, facts)),
                    key=lambda item: item.finding_id,
                )
            )
            trace = DecisionTrace(
                evidence=tuple(sorted((*execution.evidence, *formula_evidence), key=lambda item: item.evidence_id)),
                facts=facts,
                findings=findings,
                recommendations=(),
            )
            return ConvertibleBondResearchResponse(
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
                risk=self._risk(self._risk_findings(request.owner_id, facts)),
                issues=issues,
                trace=trace,
            )
        except ConvertibleBondResearchError:
            raise
        except Exception as exc:
            raise ConvertibleBondResearchError("convertible-bond research execution was refused") from exc


__all__ = ["FixtureConvertibleBondResearchService", "ConvertibleBondResearchError"]
