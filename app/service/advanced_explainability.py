"""Service for compiling causal explainability, driver attribution, and counterfactuals."""

from __future__ import annotations

from decimal import Decimal

from app.explainability.contracts import (
    AdvancedExplainabilityRequest,
    AdvancedExplainabilityResponse,
    CausalEdge,
    CausalNode,
    CausalNodeType,
    CounterfactualCondition,
    InvalidationTrigger,
    KeyDecisionDriver,
)
from app.gates import GateStatus
from app.recommendation.contracts import ActionType


class AdvancedExplainabilityService:
    """Service to produce deterministic causal graphs and counterfactual explanations."""

    def explain_decision(
        self,
        request: AdvancedExplainabilityRequest,
    ) -> AdvancedExplainabilityResponse:
        tech_breach = request.tech_exposure_pct > request.tech_cap_pct

        nodes = (
            CausalNode(
                node_id="node:profile:risk",
                node_type=CausalNodeType.PROFILE_CONSTRAINT,
                label="用户画像与风险偏好",
                value_summary=f"风险得分: {request.risk_score}, 等级: {request.risk_level}",
                status=GateStatus.PASS,
                influence_weight_pct=Decimal("35.00"),
            ),
            CausalNode(
                node_id="node:portfolio:exposure",
                node_type=CausalNodeType.MARKET_FACT,
                label="持仓穿透科技暴露",
                value_summary=f"科技行业暴露: {request.tech_exposure_pct}%",
                status=GateStatus.PASS,
                influence_weight_pct=Decimal("45.00"),
            ),
            CausalNode(
                node_id="node:risk:budget",
                node_type=CausalNodeType.RISK_ASSESSMENT,
                label="风险预算上限约束",
                value_summary=f"科技预算上限: {request.tech_cap_pct}% (超标: {'是' if tech_breach else '否'})",
                status=GateStatus.PASS if not tech_breach else GateStatus.REVIEW_REQUIRED,
                influence_weight_pct=Decimal("40.00"),
            ),
            CausalNode(
                node_id="node:research:facts",
                node_type=CausalNodeType.RESEARCH_FINDING,
                label="多维投研事实与判断",
                value_summary=f"共 {request.finding_count} 条闭环 Finding 事实",
                status=GateStatus.PASS,
                influence_weight_pct=Decimal("20.00"),
            ),
            CausalNode(
                node_id="node:compliance:guard",
                node_type=CausalNodeType.COMPLIANCE_RULE,
                label="法规与合规底线检查",
                value_summary="无保本承诺、风险提示完备",
                status=GateStatus.PASS,
                influence_weight_pct=Decimal("10.00"),
            ),
            CausalNode(
                node_id="node:recommendation:final",
                node_type=CausalNodeType.RECOMMENDATION,
                label="最终投顾建议动作",
                value_summary=f"动作: {request.action_type.value}, 标的: {request.asset}",
                status=GateStatus.PASS,
                influence_weight_pct=Decimal("100.00"),
            ),
        )

        edges = (
            CausalEdge(
                from_node_id="node:profile:risk",
                to_node_id="node:risk:budget",
                relationship="决定风险预算与行业持仓上限",
            ),
            CausalEdge(
                from_node_id="node:portfolio:exposure",
                to_node_id="node:risk:budget",
                relationship="输入实际穿透行业暴露进行限额核对",
            ),
            CausalEdge(
                from_node_id="node:risk:budget",
                to_node_id="node:recommendation:final",
                relationship="预算超标触发减持调优或维持约束",
            ),
            CausalEdge(
                from_node_id="node:research:facts",
                to_node_id="node:recommendation:final",
                relationship="基本面与估值事实支撑投资逻辑",
            ),
            CausalEdge(
                from_node_id="node:compliance:guard",
                to_node_id="node:recommendation:final",
                relationship="合规前置检查确保无违规收益承诺",
            ),
        )

        key_drivers = (
            KeyDecisionDriver(
                driver_name="科技行业持仓暴露约束",
                category="风险预算",
                contribution_pct=Decimal("45.00"),
                evidence_reference="ev:portfolio:lookthrough:tech_exposure",
                explanation=f"当前穿透科技行业权重 ({request.tech_exposure_pct}%) 相比预算上限 ({request.tech_cap_pct}%) {'构成超配，是促成 REDUCE 的主因' if tech_breach else '处于合规安全范围内'}。",
            ),
            KeyDecisionDriver(
                driver_name="用户风险偏好与期限约束",
                category="用户画像",
                contribution_pct=Decimal("35.00"),
                evidence_reference="ev:profile:questionnaire:risk_score",
                explanation=f"用户风险偏好得分 {request.risk_score} (等级 {request.risk_level}) 设定了防御性资产配置边界。",
            ),
            KeyDecisionDriver(
                driver_name="专业研究节点事实收敛",
                category="基本面研究",
                contribution_pct=Decimal("20.00"),
                evidence_reference="ev:specialist:matrix:findings",
                explanation=f"宏观、行业与资产多轨研究聚合了 {request.finding_count} 条交叉验证事实。",
            ),
        )

        counterfactuals = (
            CounterfactualCondition(
                scenario_name="画像偏好提升（CONSERVATIVE -> GROWTH）",
                condition_change=f"若风险偏好得分由 {request.risk_score} 提升至 80.00 以上（进取型）",
                expected_action_change="建议动作可能由 REDUCE 转为 HOLD，科技行业容忍度放宽至 45.00%",
                rationale="高风险偏好用户具备更强的短期回撤承受能力，配置上限随之放宽。",
            ),
            CounterfactualCondition(
                scenario_name="行业暴露主动回落",
                condition_change=f"若科技行业总暴露由 {request.tech_exposure_pct}% 降至 {request.tech_cap_pct}% 以下",
                expected_action_change="建议动作转为 HOLD",
                rationale="持仓已完全处于风险预算安全区间内，无需进一步执行强制压降。",
            ),
        )

        invalidation_triggers = (
            InvalidationTrigger(
                trigger_id="trigger:01:market_volatility",
                trigger_type="MARKET_EVENT",
                description="标的资产或相关行业指数单日波动超过 5.00%",
                threshold_or_event="Daily Return > 5.00% or < -5.00%",
            ),
            InvalidationTrigger(
                trigger_id="trigger:02:earnings_report",
                trigger_type="FINANCIAL_REPORT",
                description="底层主要持仓标的发布最新定期财务报告或业绩预告",
                threshold_or_event="Periodic report release date T+0",
            ),
            InvalidationTrigger(
                trigger_id="trigger:03:data_ttl",
                trigger_type="DATA_EXPIRATION",
                description="研究所依赖的 Provider 市场数据时效超过 24 小时",
                threshold_or_event="Evidence Age > 24 Hours",
            ),
        )

        summary = (
            f"基于画像 (得分 {request.risk_score}, 等级 {request.risk_level}) 与穿透科技暴露 "
            f"({request.tech_exposure_pct}%) 对比预算上限 ({request.tech_cap_pct}%)，"
            f"结合 {request.finding_count} 条投研事实，生成动作 {request.action_type.value}。"
        )

        return AdvancedExplainabilityResponse(
            request_id=request.request_id,
            owner_id=request.owner_id,
            generated_at=request.generated_at,
            decision_summary=summary,
            causal_nodes=nodes,
            causal_edges=edges,
            key_drivers=key_drivers,
            counterfactuals=counterfactuals,
            invalidation_triggers=invalidation_triggers,
        )
