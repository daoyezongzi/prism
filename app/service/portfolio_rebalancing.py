"""Service for computing deterministic portfolio rebalancing plans."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from app.gates import GateStatus
from app.portfolio.contracts import AssetType, PositionImportStatus
from app.rebalancing.contracts import (
    PortfolioRebalancingRequest,
    PortfolioRebalancingResponse,
    RebalancingAction,
    RebalancingActionType,
    RebalancingMetrics,
    RebalancingStep,
)


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


class PortfolioRebalancingService:
    """Deterministic rebalancing planner."""

    def plan_rebalancing(
        self,
        request: PortfolioRebalancingRequest,
    ) -> PortfolioRebalancingResponse:
        positions = request.bundle.position_snapshot.positions
        total_val = sum((pos.market_value for pos in positions), start=Decimal("0"))

        if total_val <= Decimal("0"):
            raise ValueError("Portfolio total market value must be positive")

        actions: list[RebalancingAction] = []
        pos_by_asset = {pos.asset_id: pos for pos in positions}

        # Process existing positions
        for pos in positions:
            curr_weight = _q2((pos.market_value / total_val) * Decimal("100"))
            target_weight = _q2(request.target_weights.get(pos.asset_id, Decimal("0.00")))
            delta_weight = _q2(target_weight - curr_weight)
            target_val = _q2(total_val * target_weight / Decimal("100"))
            cash_delta = _q2(target_val - pos.market_value)

            if abs(delta_weight) <= request.deadband_pct:
                action_type = RebalancingActionType.HOLD
                rationale = f"权重偏差 {delta_weight}% 在死区阈值 (±{request.deadband_pct}%) 内，维持现状以降低交易摩擦"
            elif delta_weight > Decimal("0"):
                action_type = RebalancingActionType.BUY
                rationale = f"当前权重 {curr_weight}% 低于目标 {target_weight}%，建议加仓补足"
            elif target_weight == Decimal("0"):
                action_type = RebalancingActionType.SELL
                rationale = "目标权重为 0.00%，建议全部清仓移出"
            else:
                action_type = RebalancingActionType.REDUCE
                rationale = f"当前权重 {curr_weight}% 高于目标 {target_weight}%，建议减仓调优"

            actions.append(
                RebalancingAction(
                    asset_id=pos.asset_id,
                    asset_name=pos.asset_name,
                    asset_type=pos.asset_type,
                    current_weight_pct=curr_weight,
                    target_weight_pct=target_weight,
                    delta_weight_pct=delta_weight,
                    current_value_cny=pos.market_value,
                    target_value_cny=target_val,
                    cash_delta_cny=cash_delta,
                    action_type=action_type,
                    rationale=rationale,
                )
            )

        # Process new target assets not in current portfolio
        for asset_id, target_w in request.target_weights.items():
            if asset_id not in pos_by_asset and target_w > Decimal("0"):
                tw = _q2(target_w)
                tv = _q2(total_val * tw / Decimal("100"))
                actions.append(
                    RebalancingAction(
                        asset_id=asset_id,
                        asset_name=f"新增资产({asset_id})",
                        asset_type=AssetType.ETF,
                        current_weight_pct=Decimal("0.00"),
                        target_weight_pct=tw,
                        delta_weight_pct=tw,
                        current_value_cny=Decimal("0.00"),
                        target_value_cny=tv,
                        cash_delta_cny=tv,
                        action_type=RebalancingActionType.BUY,
                        rationale=f"新建目标仓位 {tw}%",
                    )
                )

        # Calculate metrics
        total_buy = sum((abs(a.cash_delta_cny) for a in actions if a.action_type == RebalancingActionType.BUY), start=Decimal("0"))
        total_sell = sum((abs(a.cash_delta_cny) for a in actions if a.action_type in (RebalancingActionType.SELL, RebalancingActionType.REDUCE)), start=Decimal("0"))
        turnover_pct = _q2(sum((abs(a.delta_weight_pct) for a in actions), start=Decimal("0")) / Decimal("2"))
        net_cash = _q2(total_sell - total_buy)
        turnover_breached = turnover_pct > request.max_turnover_pct

        metrics = RebalancingMetrics(
            total_portfolio_value_cny=_q2(total_val),
            total_turnover_pct=turnover_pct,
            total_buy_cny=_q2(total_buy),
            total_sell_cny=_q2(total_sell),
            net_cash_flow_cny=net_cash,
            turnover_cap_breached=turnover_breached,
        )

        # Build execution steps: Sell/Reduce first, then Buy
        sells = [a for a in actions if a.action_type in (RebalancingActionType.SELL, RebalancingActionType.REDUCE)]
        buys = [a for a in actions if a.action_type == RebalancingActionType.BUY]
        sells.sort(key=lambda x: abs(x.cash_delta_cny), reverse=True)
        buys.sort(key=lambda x: abs(x.cash_delta_cny), reverse=True)

        steps: list[RebalancingStep] = []
        step_idx = 1
        for s in sells:
            steps.append(
                RebalancingStep(
                    step_number=step_idx,
                    action_type=s.action_type,
                    asset_id=s.asset_id,
                    asset_name=s.asset_name,
                    amount_cny=abs(s.cash_delta_cny),
                    liquidity_priority=1,
                    description=f"优先卖出/减持 {s.asset_name} 释放现金 {abs(s.cash_delta_cny)} CNY",
                )
            )
            step_idx += 1

        for b in buys:
            steps.append(
                RebalancingStep(
                    step_number=step_idx,
                    action_type=b.action_type,
                    asset_id=b.asset_id,
                    asset_name=b.asset_name,
                    amount_cny=abs(b.cash_delta_cny),
                    liquidity_priority=2,
                    description=f"使用释放流动性买入/增持 {b.asset_name} 金额 {abs(b.cash_delta_cny)} CNY",
                )
            )
            step_idx += 1

        issues: list[str] = []
        status = GateStatus.PASS

        if turnover_breached:
            status = GateStatus.REVIEW_REQUIRED
            issues.append(f"总换手率 {turnover_pct}% 超出设定上限 {request.max_turnover_pct}%")

        invalidation_conditions = (
            "组合内任意资产价格变动超过 5.00%",
            "宏观或行业风险预算上限调整",
            "用户风险画像发生变更",
        )

        return PortfolioRebalancingResponse(
            request_id=request.request_id,
            owner_id=request.owner_id,
            status=status,
            metrics=metrics,
            actions=tuple(actions),
            execution_steps=tuple(steps),
            issues=tuple(issues),
            invalidation_conditions=invalidation_conditions,
        )
