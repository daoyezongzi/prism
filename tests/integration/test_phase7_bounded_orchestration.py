import json
from datetime import UTC, datetime
from pathlib import Path

from app.orchestration import (
    ResearchNodeSpec,
    ResearchRunStatus,
    build_research_plan,
    create_research_run,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "orchestration"
    / "bounded_research_plan.json"
)


def test_synthetic_plan_fixture_creates_closed_pending_run() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    owner_id = payload["owner_id"]
    nodes = tuple(
        ResearchNodeSpec.model_validate(item) for item in payload["nodes"]
    )
    plan = build_research_plan(owner_id, payload["scope_description"], nodes)
    state = create_research_run(
        plan,
        "fixture-orchestration-request-001",
        500,
        datetime(2026, 9, 1, 12, 0, tzinfo=UTC),
    )
    assert plan.topological_order == ("fund", "macro", "industry", "stock")
    assert state.status == ResearchRunStatus.PENDING
    serialized = json.dumps(state.model_dump(mode="json"), ensure_ascii=False).lower()
    for field in (
        "recommendation",
        "trade_order",
        "target_price",
        "expected_return",
        "api_key",
        "authorization",
        "secret",
    ):
        assert field not in serialized
