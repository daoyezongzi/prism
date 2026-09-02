from datetime import UTC, datetime
from decimal import Decimal
import pytest

from app.gates import GateStatus
from app.rebalancing.contracts import (
    PortfolioRebalancingRequest,
    PortfolioRebalancingResponse,
    RebalancingActionType,
)
from app.service import (
    FixtureAdvisorQueryService,
    PortfolioRebalancingService,
)


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def test_rebalancing_plan_deterministic():
    advisor = FixtureAdvisorQueryService()
    template = advisor.query_template("reb-owner-001")
    bundle = template.portfolio

    service = PortfolioRebalancingService()

    # Target weights summing to 100.00%
    target_weights = {
        "ASSET-TECH-ETF-001": Decimal("30.00"),
        "ASSET-CSI300-001": Decimal("40.00"),
        "ASSET-DIVIDEND-001": Decimal("30.00"),
    }

    req = PortfolioRebalancingRequest(
        request_id="reb-req-001",
        owner_id="reb-owner-001",
        generated_at=NOW,
        bundle=bundle,
        target_weights=target_weights,
        deadband_pct=Decimal("0.50"),
        max_turnover_pct=Decimal("100.00"),
    )

    res = service.plan_rebalancing(req)
    assert isinstance(res, PortfolioRebalancingResponse)
    assert res.status == GateStatus.PASS
    assert len(res.actions) > 0
    assert len(res.execution_steps) > 0
    assert res.metrics.total_portfolio_value_cny > Decimal("0")
    assert res.metrics.turnover_cap_breached is False

    # Check that sell steps come before buy steps
    priorities = [step.liquidity_priority for step in res.execution_steps]
    assert priorities == sorted(priorities)


def test_rebalancing_deadband_suppresses_small_churn():
    advisor = FixtureAdvisorQueryService()
    template = advisor.query_template("reb-owner-002")
    bundle = template.portfolio
    service = PortfolioRebalancingService()

    # Get current weights by asking with current breakdown
    positions = bundle.position_snapshot.positions
    total_val = sum(p.market_value for p in positions)
    current_w = {p.asset_id: (p.market_value / total_val * 100).quantize(Decimal("0.01")) for p in positions}

    # Adjust sum to exactly 100
    first_key = list(current_w.keys())[0]
    diff = Decimal("100.00") - sum(current_w.values())
    current_w[first_key] += diff

    req = PortfolioRebalancingRequest(
        request_id="reb-req-002",
        owner_id="reb-owner-002",
        generated_at=NOW,
        bundle=bundle,
        target_weights=current_w,
        deadband_pct=Decimal("1.00"),
    )
    res = service.plan_rebalancing(req)
    assert all(a.action_type == RebalancingActionType.HOLD for a in res.actions)
    assert res.metrics.total_turnover_pct == Decimal("0.00")


def test_rebalancing_invalid_sum_fails_validation():
    advisor = FixtureAdvisorQueryService()
    template = advisor.query_template("reb-owner-003")
    bundle = template.portfolio

    with pytest.raises(ValueError, match="target_weights must sum to 100.00%"):
        PortfolioRebalancingRequest(
            request_id="reb-req-003",
            owner_id="reb-owner-003",
            generated_at=NOW,
            bundle=bundle,
            target_weights={"ASSET-1": Decimal("80.00")},  # sums to 80%, not 100%
        )
