"""Contracts for portfolio rebalancing planning and execution steps."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.gates import GateStatus
from app.portfolio.contracts import AssetType, PortfolioImportBundle


class RebalancingActionType(StrEnum):
    """Action recommendation for an asset in rebalancing."""

    BUY = "BUY"
    SELL = "SELL"
    REDUCE = "REDUCE"
    HOLD = "HOLD"


class RebalancingAction(ContractModel):
    """Specific rebalancing action for a single portfolio asset."""

    asset_id: NonEmptyStr
    asset_name: NonEmptyStr
    asset_type: AssetType
    current_weight_pct: Decimal
    target_weight_pct: Decimal
    delta_weight_pct: Decimal
    current_value_cny: Decimal
    target_value_cny: Decimal
    cash_delta_cny: Decimal
    action_type: RebalancingActionType
    rationale: NonEmptyStr

    @model_validator(mode="after")
    def validate_action(self) -> Self:
        if self.current_weight_pct < Decimal("0"):
            raise ValueError("current_weight_pct cannot be negative")
        if self.target_weight_pct < Decimal("0"):
            raise ValueError("target_weight_pct cannot be negative")
        return self


class RebalancingStep(ContractModel):
    """Ordered step for executing rebalancing with liquidity awareness."""

    step_number: int = Field(ge=1)
    action_type: RebalancingActionType
    asset_id: NonEmptyStr
    asset_name: NonEmptyStr
    amount_cny: Decimal = Field(ge=Decimal("0"))
    liquidity_priority: int = Field(ge=1)
    description: NonEmptyStr


class RebalancingMetrics(ContractModel):
    """Summary metrics of the rebalancing plan."""

    total_portfolio_value_cny: Decimal
    total_turnover_pct: Decimal
    total_buy_cny: Decimal
    total_sell_cny: Decimal
    net_cash_flow_cny: Decimal
    turnover_cap_breached: bool = False


class PortfolioRebalancingRequest(ContractModel):
    """Request to generate an actionable rebalancing plan."""

    schema_version: Literal["portfolio-rebalancing-request.v1"] = "portfolio-rebalancing-request.v1"
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    bundle: PortfolioImportBundle
    target_weights: dict[str, Decimal]
    deadband_pct: Decimal = Decimal("0.50")
    max_turnover_pct: Decimal = Decimal("50.00")

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        if self.owner_id != self.bundle.position_snapshot.owner_id:
            raise ValueError("request owner_id does not match bundle owner_id")
        total_target = sum(self.target_weights.values())
        if abs(total_target - Decimal("100.00")) > Decimal("0.05"):
            raise ValueError(f"target_weights must sum to 100.00% (got {total_target}%)")
        return self


class PortfolioRebalancingResponse(ContractModel):
    """Deterministic rebalancing plan response."""

    schema_version: Literal["portfolio-rebalancing-response.v1"] = "portfolio-rebalancing-response.v1"
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    status: GateStatus
    metrics: RebalancingMetrics
    actions: tuple[RebalancingAction, ...]
    execution_steps: tuple[RebalancingStep, ...]
    issues: tuple[str, ...] = ()
    invalidation_conditions: tuple[str, ...] = ()
    disclaimer: str = "调仓方案仅供决策参考（ADVISORY_ONLY），不构成自动交易或委托指令。"
