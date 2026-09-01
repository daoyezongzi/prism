from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.contracts.evidence import EvidenceQualityStatus
from app.orchestration import (
    ResearchNodeRunStatus,
    ResearchNodeSpec,
    ResearchNodeStatus,
    ResearchRunIssueCode,
    ResearchRunStatus,
    build_research_plan,
    cancel_research_run,
    create_research_run,
    finish_research_run,
    record_node_result,
    start_research_run,
)
from app.orchestration.contracts import ResearchPlan, ResearchRunState
from app.research import (
    ResearchNodeIssue,
    ResearchNodeIssueCode,
    ResearchNodeKind,
    ResearchNodeResult,
    ResearchObservation,
)


T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OWNER = "orchestration-owner-001"


def specs() -> tuple[ResearchNodeSpec, ...]:
    return (
        ResearchNodeSpec(
            node_id="macro",
            owner_id=OWNER,
            node_kind=ResearchNodeKind.MACRO,
            required=True,
            timeout_ms=100,
        ),
        ResearchNodeSpec(
            node_id="industry",
            owner_id=OWNER,
            node_kind=ResearchNodeKind.INDUSTRY,
            required=True,
            dependencies=("macro",),
            timeout_ms=100,
        ),
        ResearchNodeSpec(
            node_id="stock",
            owner_id=OWNER,
            node_kind=ResearchNodeKind.STOCK,
            required=True,
            dependencies=("industry",),
            timeout_ms=100,
        ),
        ResearchNodeSpec(
            node_id="fund",
            owner_id=OWNER,
            node_kind=ResearchNodeKind.FUND,
            required=False,
            timeout_ms=100,
        ),
    )


def plan():
    return build_research_plan(OWNER, "synthetic flagship research", reversed(specs()))


def observation(evidence_id: str, value: str = "10") -> ResearchObservation:
    return ResearchObservation(
        observation_id=f"observation-{evidence_id}",
        owner_id=OWNER,
        evidence_id=evidence_id,
        subject="STOCK_ORCHESTRATION_001",
        metric="revenue",
        value=Decimal(value),
        unit="CNY",
        period="2026-Q2",
        provider="synthetic-provider",
        source="synthetic-source",
        lineage_id=f"lineage-{evidence_id}",
        quality_status=EvidenceQualityStatus.VERIFIED,
        retrieved_at=T0,
    )


def result(
    state,
    node_id: str,
    status: ResearchNodeStatus = ResearchNodeStatus.COMPLETE,
    *,
    completed_at: datetime | None = None,
) -> ResearchNodeResult:
    spec = next(node for node in state.plan.nodes if node.node_id == node_id)
    observations = (observation(f"evidence-{node_id}"),) if status in {
        ResearchNodeStatus.COMPLETE,
        ResearchNodeStatus.PARTIAL,
    } else ()
    missing = ("eps",) if status == ResearchNodeStatus.PARTIAL else ()
    issues = (
        ResearchNodeIssue(
            code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
            safe_message="synthetic source unavailable",
        ),
    ) if status == ResearchNodeStatus.FAILED else ()
    return ResearchNodeResult(
        request_id=state.request_id,
        node_id=node_id,
        owner_id=OWNER,
        node_kind=spec.node_kind,
        subject="STOCK_ORCHESTRATION_001",
        completed_at=completed_at or T0 + timedelta(milliseconds=2),
        status=status,
        observations=observations,
        missing_fields=missing,
        issues=issues,
        scope_description="synthetic node scope" if status == ResearchNodeStatus.EMPTY else None,
    )


def running_state(*, budget_ms: int = 1000):
    return start_research_run(
        create_research_run(plan(), "orchestration-request-001", budget_ms, T0),
        T0 + timedelta(milliseconds=1),
    )


def test_plan_is_canonical_and_topologically_closed() -> None:
    first = plan()
    second = build_research_plan(OWNER, "synthetic flagship research", specs())
    assert first.plan_id == second.plan_id
    assert first.topological_order == ("fund", "macro", "industry", "stock")
    assert tuple(node.node_id for node in first.nodes) == (
        "fund",
        "industry",
        "macro",
        "stock",
    )


def test_invalid_dag_shapes_are_rejected() -> None:
    with pytest.raises(ValueError, match="unknown"):
        build_research_plan(
            OWNER,
            "scope",
            (
                ResearchNodeSpec(
                    node_id="a",
                    owner_id=OWNER,
                    node_kind=ResearchNodeKind.STOCK,
                    timeout_ms=1,
                    dependencies=("missing",),
                ),
            ),
        )
    with pytest.raises(ValueError, match="cycle"):
        build_research_plan(
            OWNER,
            "scope",
            (
                ResearchNodeSpec(
                    node_id="a",
                    owner_id=OWNER,
                    node_kind=ResearchNodeKind.STOCK,
                    timeout_ms=1,
                    dependencies=("b",),
                ),
                ResearchNodeSpec(
                    node_id="b",
                    owner_id=OWNER,
                    node_kind=ResearchNodeKind.STOCK,
                    timeout_ms=1,
                    dependencies=("a",),
                ),
            ),
        )
    with pytest.raises(ValidationError, match="self"):
        ResearchNodeSpec(
            node_id="self",
            owner_id=OWNER,
            node_kind=ResearchNodeKind.STOCK,
            timeout_ms=1,
            dependencies=("self",),
        )
    with pytest.raises(ValidationError, match="duplicates"):
        ResearchNodeSpec(
            node_id="duplicate-dep",
            owner_id=OWNER,
            node_kind=ResearchNodeKind.STOCK,
            timeout_ms=1,
            dependencies=("a", "a"),
        )


def test_create_fixes_budget_deadline_and_rejects_long_node() -> None:
    state = create_research_run(plan(), "request-budget", 250, T0)
    assert state.status == ResearchRunStatus.PENDING
    assert state.deadline_at == T0 + timedelta(milliseconds=250)
    assert all(node.status == ResearchNodeRunStatus.PENDING for node in state.nodes)
    with pytest.raises(ValueError, match="must not exceed"):
        create_research_run(plan(), "request-too-small", 50, T0)


def test_start_only_activates_root_nodes_and_keeps_original_immutable() -> None:
    pending = create_research_run(plan(), "request-start", 1000, T0)
    running = start_research_run(pending, T0 + timedelta(milliseconds=1))
    assert pending.status == ResearchRunStatus.PENDING
    assert running.status == ResearchRunStatus.RUNNING
    running_ids = {
        node.node_id for node in running.nodes if node.status == ResearchNodeRunStatus.RUNNING
    }
    assert running_ids == {"fund", "macro"}
    assert all(
        node.status == ResearchNodeRunStatus.PENDING
        for node in running.nodes
        if node.node_id in {"industry", "stock"}
    )


def test_success_and_optional_partial_close_to_partial_run() -> None:
    state = running_state()
    state = record_node_result(state, "macro", result(state, "macro"), T0 + timedelta(milliseconds=3))
    assert next(node for node in state.nodes if node.node_id == "industry").status == ResearchNodeRunStatus.RUNNING
    state = record_node_result(
        state,
        "fund",
        result(state, "fund", ResearchNodeStatus.PARTIAL),
        T0 + timedelta(milliseconds=4),
    )
    state = record_node_result(
        state,
        "industry",
        result(state, "industry", completed_at=T0 + timedelta(milliseconds=5)),
        T0 + timedelta(milliseconds=5),
    )
    state = record_node_result(
        state,
        "stock",
        result(state, "stock", completed_at=T0 + timedelta(milliseconds=6)),
        T0 + timedelta(milliseconds=6),
    )
    assert state.status == ResearchRunStatus.PARTIAL
    assert any(issue.code == ResearchRunIssueCode.OPTIONAL_NODE_INCOMPLETE for issue in state.issues)
    assert all(
        node.status not in {ResearchNodeRunStatus.PENDING, ResearchNodeRunStatus.RUNNING}
        for node in state.nodes
    )


@pytest.mark.parametrize("incomplete_status", [ResearchNodeStatus.PARTIAL, ResearchNodeStatus.EMPTY, ResearchNodeStatus.FAILED])
def test_required_incomplete_node_fails_run(incomplete_status: ResearchNodeStatus) -> None:
    state = running_state()
    failed = record_node_result(
        state,
        "macro",
        result(state, "macro", incomplete_status),
        T0 + timedelta(milliseconds=3),
    )
    assert failed.status == ResearchRunStatus.FAILED
    assert any(issue.code == ResearchRunIssueCode.REQUIRED_NODE_INCOMPLETE for issue in failed.issues)
    assert all(
        node.status
        not in {ResearchNodeRunStatus.PENDING, ResearchNodeRunStatus.RUNNING}
        for node in failed.nodes
    )
    assert failed is not state


def test_dependencies_duplicate_submission_and_owner_kind_request_are_rejected() -> None:
    state = running_state()
    with pytest.raises(ValueError, match="dependencies"):
        record_node_result(state, "industry", result(state, "industry"), T0 + timedelta(milliseconds=2))
    state = record_node_result(state, "macro", result(state, "macro"), T0 + timedelta(milliseconds=3))
    with pytest.raises(ValueError, match="once"):
        record_node_result(state, "macro", result(state, "macro"), T0 + timedelta(milliseconds=4))
    industry = result(state, "industry")
    with pytest.raises(ValueError, match="request_id"):
        record_node_result(
            state,
            "industry",
            industry.model_copy(update={"request_id": "other-request"}),
            T0 + timedelta(milliseconds=4),
        )
    with pytest.raises(ValueError, match="node_kind"):
        record_node_result(
            state,
            "industry",
            industry.model_copy(update={"node_kind": ResearchNodeKind.MACRO}),
            T0 + timedelta(milliseconds=4),
        )


def test_deadline_fails_active_nodes_without_raw_exception() -> None:
    state = running_state(budget_ms=100)
    expired = record_node_result(
        state,
        "macro",
        result(state, "macro", completed_at=T0 + timedelta(milliseconds=2)),
        T0 + timedelta(milliseconds=100),
    )
    assert expired.status == ResearchRunStatus.FAILED
    assert expired.issues[0].code == ResearchRunIssueCode.DEADLINE_EXCEEDED
    assert all(
        node.status in {ResearchNodeRunStatus.COMPLETE, ResearchNodeRunStatus.FAILED}
        for node in expired.nodes
    )
    assert all("exception" not in issue.safe_message.lower() for issue in expired.issues)


def test_finish_requires_terminal_nodes_and_completes_all_required() -> None:
    state = running_state()
    with pytest.raises(ValueError, match="active"):
        finish_research_run(state, T0 + timedelta(milliseconds=3))
    state = record_node_result(state, "macro", result(state, "macro"), T0 + timedelta(milliseconds=3))
    with pytest.raises(ValueError, match="active"):
        finish_research_run(state, T0 + timedelta(milliseconds=4))

    # Complete the two required descendants and optional root.
    state = record_node_result(state, "fund", result(state, "fund"), T0 + timedelta(milliseconds=4))
    state = record_node_result(
        state,
        "industry",
        result(state, "industry", completed_at=T0 + timedelta(milliseconds=5)),
        T0 + timedelta(milliseconds=5),
    )
    state = record_node_result(
        state,
        "stock",
        result(state, "stock", completed_at=T0 + timedelta(milliseconds=6)),
        T0 + timedelta(milliseconds=6),
    )
    assert state.status == ResearchRunStatus.COMPLETED
    with pytest.raises(ValueError, match="terminal"):
        cancel_research_run(state, T0 + timedelta(milliseconds=7), "too late")


def test_cancel_pending_or_running_is_terminal_and_reason_is_safe() -> None:
    pending = create_research_run(plan(), "request-cancel-pending", 1000, T0)
    cancelled_pending = cancel_research_run(pending, T0 + timedelta(milliseconds=1), "user stopped")
    assert cancelled_pending.status == ResearchRunStatus.CANCELLED
    assert all(node.status == ResearchNodeRunStatus.CANCELLED for node in cancelled_pending.nodes)
    running = running_state()
    cancelled_running = cancel_research_run(running, T0 + timedelta(milliseconds=3), "user stopped")
    assert cancelled_running.status == ResearchRunStatus.CANCELLED
    assert all(
        node.status not in {ResearchNodeRunStatus.PENDING, ResearchNodeRunStatus.RUNNING}
        for node in cancelled_running.nodes
    )
    with pytest.raises(ValueError, match="empty"):
        cancel_research_run(running, T0 + timedelta(milliseconds=3), "   ")
    with pytest.raises(ValueError, match="sensitive"):
        cancel_research_run(running, T0 + timedelta(milliseconds=3), "api_key=leak")


def test_optional_dependency_is_cancelled_when_its_parent_is_incomplete() -> None:
    optional_child = ResearchNodeSpec(
        node_id="fund-child",
        owner_id=OWNER,
        node_kind=ResearchNodeKind.FUND,
        required=False,
        dependencies=("fund",),
        timeout_ms=100,
    )
    custom_plan = build_research_plan(OWNER, "optional dependency", (*specs(), optional_child))
    state = start_research_run(
        create_research_run(custom_plan, "optional-dependency-request", 1000, T0),
        T0 + timedelta(milliseconds=1),
    )
    state = record_node_result(
        state,
        "fund",
        result(state, "fund", ResearchNodeStatus.PARTIAL),
        T0 + timedelta(milliseconds=3),
    )
    child = next(node for node in state.nodes if node.node_id == "fund-child")
    assert child.status == ResearchNodeRunStatus.CANCELLED
    assert child.issues


def test_result_request_identity_is_closed_in_serialized_run_state() -> None:
    state = running_state()
    state = record_node_result(state, "macro", result(state, "macro"), T0 + timedelta(milliseconds=3))
    payload = state.model_dump(mode="python")
    for item in payload["nodes"]:
        if item["result"] is not None:
            item["result"]["request_id"] = "other-request"
            break
    with pytest.raises(ValidationError, match="request_id"):
        ResearchRunState.model_validate(payload)


def test_tampered_plan_or_run_state_is_rejected_and_serialization_has_no_secrets() -> None:
    state = create_research_run(plan(), "request-tamper", 1000, T0)
    payload = state.plan.model_dump(mode="python")
    payload["topological_order"] = tuple(reversed(payload["topological_order"]))
    with pytest.raises(ValidationError, match="topological"):
        ResearchPlan.model_validate(payload)
    run_payload = state.model_dump(mode="python")
    run_payload["status"] = ResearchRunStatus.COMPLETED
    with pytest.raises(ValidationError, match="COMPLETED"):
        ResearchRunState.model_validate(run_payload)
    serialized = str(state.model_dump(mode="json")).lower()
    for forbidden in ("recommendation", "trade_order", "target_price", "return promise", "api_key", "authorization", "secret"):
        assert forbidden not in serialized
