from datetime import UTC, datetime
from decimal import Decimal

from app.explainability.contracts import (
    AdvancedExplainabilityRequest,
    AdvancedExplainabilityResponse,
    CausalNodeType,
)
from app.recommendation.contracts import ActionType
from app.service import AdvancedExplainabilityService


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def test_advanced_explainability_service():
    service = AdvancedExplainabilityService()

    req = AdvancedExplainabilityRequest(
        request_id="exp-req-001",
        owner_id="exp-owner-001",
        generated_at=NOW,
        risk_score=Decimal("30.00"),
        risk_level="CONSERVATIVE",
        action_type=ActionType.REDUCE,
        asset="ASSET-TECH-ETF-001",
        tech_exposure_pct=Decimal("45.00"),
        tech_cap_pct=Decimal("30.00"),
        top_asset_weight_pct=Decimal("40.00"),
        finding_count=6,
    )

    res = service.explain_decision(req)
    assert isinstance(res, AdvancedExplainabilityResponse)
    assert len(res.causal_nodes) >= 5
    assert len(res.causal_edges) >= 4
    assert len(res.key_drivers) >= 3
    assert len(res.counterfactuals) >= 2
    assert len(res.invalidation_triggers) >= 3

    node_types = {n.node_type for n in res.causal_nodes}
    assert CausalNodeType.PROFILE_CONSTRAINT in node_types
    assert CausalNodeType.MARKET_FACT in node_types
    assert CausalNodeType.RECOMMENDATION in node_types
