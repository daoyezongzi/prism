import asyncio
from datetime import datetime
import json
from pathlib import Path

from app.orchestration import (
    ResearchNodeSpec,
    ResearchRunStatus,
    build_research_plan,
    create_research_run,
    execute_research_run,
)
from app.providers import FixtureFinancialProvider, ProviderRequest
from app.research import ResearchNodeKind, ResearchNodeStatus


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "orchestration"
    / "fixture_research_run_case.json"
)


def test_fixture_provider_runs_parallel_nodes_into_a_replayable_partial_state() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    created_at = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
    nodes = tuple(ResearchNodeSpec(**item) for item in payload["nodes"])
    plan = build_research_plan(
        payload["owner_id"],
        payload["scope_description"],
        nodes,
    )
    state = create_research_run(
        plan,
        payload["request_id"],
        payload["budget_ms"],
        created_at,
    )
    requests = {
        item["node_id"]: ProviderRequest(**item["request"])
        for item in payload["requests"]
    }

    result = asyncio.run(
        execute_research_run(
            state,
            FixtureFinancialProvider(),
            requests,
            started_at=created_at,
            clock=lambda: created_at,
        )
    )

    assert result.state.status == ResearchRunStatus.PARTIAL
    by_id = {node.node_id: node for node in result.state.nodes}
    assert by_id["fund_success"].status.value == "COMPLETE"
    assert by_id["fund_empty"].status.value == "EMPTY"
    assert by_id["fund_success"].result is not None
    assert by_id["fund_success"].result.status == ResearchNodeStatus.COMPLETE
    assert by_id["fund_empty"].result is not None
    assert by_id["fund_empty"].result.status == ResearchNodeStatus.EMPTY
    assert len(result.evidence) == 3
    assert len(result.observations) == 2
    assert {item.metric for item in result.observations} == {
        "technology_weight_pct",
        "top10_concentration_pct",
    }
    serialized = result.model_dump_json().lower()
    for forbidden in (
        "recommendation",
        "trade_order",
        "target_price",
        "api_key",
        "password",
        "secret",
    ):
        assert forbidden not in serialized


def test_fixture_partial_required_node_fails_without_zero_fallback() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    created_at = datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00"))
    partial_node = {
        "node_id": "fund_partial",
        "owner_id": payload["owner_id"],
        "node_kind": "FUND",
        "required": True,
        "dependencies": [],
        "timeout_ms": 1000,
    }
    plan = build_research_plan(
        payload["owner_id"],
        payload["scope_description"],
        (ResearchNodeSpec(**partial_node),),
    )
    state = create_research_run(
        plan,
        payload["request_id"],
        payload["budget_ms"],
        created_at,
    )
    partial_request = next(
        item["request"]
        for item in payload["requests"]
        if item["node_id"] == "fund_success"
    )
    partial_request = dict(partial_request)
    partial_request["subject"] = "FUND_FIXTURE_001_PARTIAL"
    partial_request["request_id"] = "fixture-node-request-partial"
    requests = {"fund_partial": ProviderRequest(**partial_request)}

    result = asyncio.run(
        execute_research_run(
            state,
            FixtureFinancialProvider(),
            requests,
            started_at=created_at,
            clock=lambda: created_at,
        )
    )

    assert result.state.status == ResearchRunStatus.FAILED
    assert result.state.nodes[0].result is not None
    assert result.state.nodes[0].result.status == ResearchNodeStatus.PARTIAL
    assert len(result.observations) == 1
    assert all(item.value != 0 for item in result.observations)
