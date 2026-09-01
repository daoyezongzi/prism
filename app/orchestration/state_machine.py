"""Pure bounded research-run state transitions.

This module deliberately does not schedule work.  An eventual async executor
can call these functions around provider tasks while retaining the same
deterministic state and failure semantics.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from hashlib import sha256
from typing import Iterable

from app.orchestration.contracts import (
    ResearchNodeRun,
    ResearchNodeRunIssue,
    ResearchNodeRunIssueCode,
    ResearchNodeRunStatus,
    ResearchNodeSpec,
    ResearchPlan,
    ResearchRunIssue,
    ResearchRunIssueCode,
    ResearchRunState,
    ResearchRunStatus,
)
from app.research import ResearchNodeResult, ResearchNodeStatus


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "research-run:" + sha256(payload).hexdigest()[:32]


def _require_aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _canonical_nodes(nodes: Iterable[ResearchNodeSpec]) -> tuple[ResearchNodeSpec, ...]:
    canonical = []
    for node in nodes:
        canonical.append(
            node.model_copy(update={"dependencies": tuple(sorted(node.dependencies))})
        )
    return tuple(sorted(canonical, key=lambda node: node.node_id))


def _topological_order(nodes: tuple[ResearchNodeSpec, ...]) -> tuple[str, ...]:
    by_id = {node.node_id: node for node in nodes}
    if not by_id:
        raise ValueError("research plan requires at least one node")
    if len(by_id) != len(nodes):
        raise ValueError("nodes must not contain duplicate node_id")
    unknown = sorted(
        {
            dependency
            for node in nodes
            for dependency in node.dependencies
            if dependency not in by_id
        }
    )
    if unknown:
        raise ValueError("node dependencies reference unknown node IDs: " + ", ".join(unknown))
    indegree = {node_id: len(node.dependencies) for node_id, node in by_id.items()}
    children: dict[str, list[str]] = {node_id: [] for node_id in by_id}
    for node in nodes:
        for dependency in node.dependencies:
            children[dependency].append(node.node_id)
    ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for child in sorted(children[current]):
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
        ready.sort()
    if len(order) != len(nodes):
        raise ValueError("research plan dependencies contain a cycle")
    return tuple(order)


def build_research_plan(
    owner_id: str,
    scope_description: str,
    nodes: Iterable[ResearchNodeSpec],
) -> ResearchPlan:
    """Canonicalize node order and build a stable DAG plan."""
    owner_id = owner_id.strip()
    scope_description = scope_description.strip()
    canonical_nodes = _canonical_nodes(nodes)
    if not owner_id or not scope_description:
        raise ValueError("owner_id and scope_description must not be empty")
    if any(node.owner_id != owner_id for node in canonical_nodes):
        raise ValueError("node owner_id does not match plan owner_id")
    order = _topological_order(canonical_nodes)
    signature = [owner_id.strip(), scope_description.strip()]
    for node in canonical_nodes:
        signature.extend(
            (
                node.node_id,
                node.node_kind.value,
                "required" if node.required else "optional",
                str(node.timeout_ms),
                ",".join(node.dependencies),
            )
        )
    return ResearchPlan(
        plan_id=_stable_id("plan", *signature),
        owner_id=owner_id,
        scope_description=scope_description,
        nodes=canonical_nodes,
        topological_order=order,
    )


def _replace_state(state: ResearchRunState, **updates: object) -> ResearchRunState:
    payload = state.model_dump(mode="python")
    payload.update(updates)
    return ResearchRunState.model_validate(payload)


def _replace_node(node: ResearchNodeRun, **updates: object) -> ResearchNodeRun:
    payload = node.model_dump(mode="python")
    payload.update(updates)
    return ResearchNodeRun.model_validate(payload)


def _ensure_live(state: ResearchRunState) -> None:
    if state.status not in {ResearchRunStatus.PENDING, ResearchRunStatus.RUNNING}:
        raise ValueError(f"research run is already terminal: {state.status.value}")


def _ready_node_ids(nodes: tuple[ResearchNodeRun, ...]) -> set[str]:
    by_id = {node.node_id: node for node in nodes}
    ready = set()
    for node in nodes:
        if node.status != ResearchNodeRunStatus.PENDING:
            continue
        if all(by_id[dependency].status == ResearchNodeRunStatus.COMPLETE for dependency in node.dependencies):
            ready.add(node.node_id)
    return ready


def _activate_ready_nodes(
    nodes: tuple[ResearchNodeRun, ...],
    now: datetime,
) -> tuple[ResearchNodeRun, ...]:
    ready = _ready_node_ids(nodes)
    activated = []
    for node in nodes:
        if node.node_id in ready:
            activated.append(
                _replace_node(
                    node,
                    status=ResearchNodeRunStatus.RUNNING,
                    attempt=node.attempt + 1,
                    started_at=now,
                )
            )
        else:
            activated.append(node)
    return tuple(activated)


def _cancel_blocked_nodes(
    nodes: tuple[ResearchNodeRun, ...],
    now: datetime,
) -> tuple[ResearchNodeRun, ...]:
    """Close pending descendants whose dependency ended non-successfully."""
    current = list(nodes)
    while True:
        by_id = {node.node_id: node for node in current}
        blocked = [
            node
            for node in current
            if node.status == ResearchNodeRunStatus.PENDING
            and any(
                by_id[dependency].status
                in {
                    ResearchNodeRunStatus.PARTIAL,
                    ResearchNodeRunStatus.EMPTY,
                    ResearchNodeRunStatus.FAILED,
                    ResearchNodeRunStatus.CANCELLED,
                }
                for dependency in node.dependencies
            )
        ]
        if not blocked:
            return tuple(current)
        blocked_ids = {node.node_id for node in blocked}
        current = [
            _replace_node(
                node,
                status=ResearchNodeRunStatus.CANCELLED,
                finished_at=now,
                issues=(
                    ResearchNodeRunIssue(
                        code=ResearchNodeRunIssueCode.CANCELLED,
                        safe_message="node was not started because a dependency did not complete",
                    ),
                ),
            )
            if node.node_id in blocked_ids
            else node
            for node in current
        ]


def _safe_cancel_reason(reason: str) -> str:
    normalized = " ".join(reason.split())
    if not normalized:
        raise ValueError("cancellation reason must not be empty")
    forbidden = (
        "api_key",
        "authorization",
        "password",
        "private_key",
        "secret",
        "token",
    )
    if any(item in normalized.casefold() for item in forbidden):
        raise ValueError("cancellation reason must not contain sensitive fields")
    return normalized[:160]


def _finalize_terminal_nodes(
    state: ResearchRunState,
    nodes: tuple[ResearchNodeRun, ...],
    now: datetime,
) -> ResearchRunState:
    """Close a state whose node set is already terminal."""
    required_incomplete = [
        node.node_id
        for node in nodes
        if node.required and node.status != ResearchNodeRunStatus.COMPLETE
    ]
    if required_incomplete:
        return _replace_state(
            state,
            nodes=nodes,
            updated_at=now,
            status=ResearchRunStatus.FAILED,
            issues=(
                ResearchRunIssue(
                    code=ResearchRunIssueCode.REQUIRED_NODE_INCOMPLETE,
                    safe_message="one or more required research nodes are incomplete",
                    node_id=required_incomplete[0],
                ),
            ),
        )
    optional_incomplete = [
        node.node_id
        for node in nodes
        if not node.required and node.status != ResearchNodeRunStatus.COMPLETE
    ]
    if optional_incomplete:
        return _replace_state(
            state,
            nodes=nodes,
            updated_at=now,
            status=ResearchRunStatus.PARTIAL,
            issues=(
                ResearchRunIssue(
                    code=ResearchRunIssueCode.OPTIONAL_NODE_INCOMPLETE,
                    safe_message="optional research nodes were incomplete; run is partial",
                ),
            ),
        )
    return _replace_state(
        state,
        nodes=nodes,
        updated_at=now,
        status=ResearchRunStatus.COMPLETED,
    )


def _deadline_failure(state: ResearchRunState, now: datetime) -> ResearchRunState:
    nodes = []
    for node in state.nodes:
        if node.status in {
            ResearchNodeRunStatus.PENDING,
            ResearchNodeRunStatus.RUNNING,
        }:
            nodes.append(
                _replace_node(
                    node,
                    status=ResearchNodeRunStatus.FAILED,
                    finished_at=now,
                    issues=(
                        ResearchNodeRunIssue(
                            code=ResearchNodeRunIssueCode.DEADLINE_EXCEEDED,
                            safe_message="research run deadline exceeded before node completion",
                        ),
                    ),
                )
            )
        else:
            nodes.append(node)
    return _replace_state(
        state,
        nodes=tuple(nodes),
        updated_at=now,
        status=ResearchRunStatus.FAILED,
        issues=(
            ResearchRunIssue(
                code=ResearchRunIssueCode.DEADLINE_EXCEEDED,
                safe_message="research run deadline exceeded; incomplete nodes were failed safely",
            ),
        ),
    )


def _cancel_active_nodes(
    nodes: tuple[ResearchNodeRun, ...],
    now: datetime,
    message: str,
) -> tuple[ResearchNodeRun, ...]:
    closed = []
    for node in nodes:
        if node.status in {
            ResearchNodeRunStatus.PENDING,
            ResearchNodeRunStatus.RUNNING,
        }:
            closed.append(
                _replace_node(
                    node,
                    status=ResearchNodeRunStatus.CANCELLED,
                    finished_at=now,
                    issues=(
                        ResearchNodeRunIssue(
                            code=ResearchNodeRunIssueCode.CANCELLED,
                            safe_message=message,
                        ),
                    ),
                )
            )
        else:
            closed.append(node)
    return tuple(closed)


def create_research_run(
    plan: ResearchPlan,
    request_id: str,
    budget_ms: int,
    created_at: datetime,
) -> ResearchRunState:
    """Create a pending run and fix its deadline before any execution starts."""
    _require_aware(created_at, "created_at")
    if budget_ms <= 0:
        raise ValueError("budget_ms must be positive")
    if any(node.timeout_ms > budget_ms for node in plan.nodes):
        raise ValueError("node timeout_ms must not exceed run budget_ms")
    node_by_id = {node.node_id: node for node in plan.nodes}
    node_runs = tuple(
        ResearchNodeRun(
            node_id=node_id,
            owner_id=plan.owner_id,
            node_kind=node_by_id[node_id].node_kind,
            required=node_by_id[node_id].required,
            dependencies=node_by_id[node_id].dependencies,
            timeout_ms=node_by_id[node_id].timeout_ms,
            status=ResearchNodeRunStatus.PENDING,
            attempt=0,
        )
        for node_id in plan.topological_order
    )
    request_id = request_id.strip()
    if not request_id:
        raise ValueError("request_id must not be empty")
    return ResearchRunState(
        run_id=_stable_id("run", plan.plan_id, request_id, created_at.isoformat(), str(budget_ms)),
        request_id=request_id,
        owner_id=plan.owner_id,
        plan=plan,
        budget_ms=budget_ms,
        created_at=created_at,
        deadline_at=created_at + timedelta(milliseconds=budget_ms),
        updated_at=created_at,
        status=ResearchRunStatus.PENDING,
        nodes=node_runs,
    )


def start_research_run(state: ResearchRunState, now: datetime) -> ResearchRunState:
    """Start all currently eligible root nodes in deterministic plan order."""
    _require_aware(now, "now")
    if state.status != ResearchRunStatus.PENDING:
        raise ValueError("only a PENDING research run can start")
    if now >= state.deadline_at:
        return _deadline_failure(state, now)
    nodes = _activate_ready_nodes(state.nodes, now)
    if not any(node.status == ResearchNodeRunStatus.RUNNING for node in nodes):
        raise ValueError("research plan has no runnable root node")
    return _replace_state(state, nodes=nodes, updated_at=now, status=ResearchRunStatus.RUNNING)


def record_node_result(
    state: ResearchRunState,
    node_id: str,
    result: ResearchNodeResult,
    now: datetime,
) -> ResearchRunState:
    """Record one completed node result and activate newly unblocked children."""
    _require_aware(now, "now")
    if state.status != ResearchRunStatus.RUNNING:
        raise ValueError("only a RUNNING research run can accept node results")
    by_id = {node.node_id: node for node in state.nodes}
    node = by_id.get(node_id)
    if node is None:
        raise ValueError("node_id is not part of the research plan")
    if node.status == ResearchNodeRunStatus.PENDING and any(
        by_id[dependency].status != ResearchNodeRunStatus.COMPLETE
        for dependency in node.dependencies
    ):
        raise ValueError("node dependencies are not complete")
    if node.status != ResearchNodeRunStatus.RUNNING:
        raise ValueError("node result can only be recorded once for a RUNNING node")
    if result.request_id != state.request_id:
        raise ValueError("result request_id does not match research run")
    if result.node_id != node.node_id:
        raise ValueError("result node_id does not match requested node")
    if result.owner_id != state.owner_id or result.owner_id != node.owner_id:
        raise ValueError("result owner_id does not match research run")
    if result.node_kind != node.node_kind:
        raise ValueError("result node_kind does not match node run")
    if now >= state.deadline_at:
        return _deadline_failure(state, now)
    if result.completed_at > now:
        raise ValueError("result completed_at must not be in the future")
    if node.started_at is not None and result.completed_at < node.started_at:
        raise ValueError("result completed_at must not precede node start")
    if any(
        by_id[dependency].status != ResearchNodeRunStatus.COMPLETE
        for dependency in node.dependencies
    ):
        raise ValueError("node dependencies are not complete")

    result_status = {
        ResearchNodeStatus.COMPLETE: ResearchNodeRunStatus.COMPLETE,
        ResearchNodeStatus.PARTIAL: ResearchNodeRunStatus.PARTIAL,
        ResearchNodeStatus.EMPTY: ResearchNodeRunStatus.EMPTY,
        ResearchNodeStatus.FAILED: ResearchNodeRunStatus.FAILED,
    }[result.status]
    updated_node = _replace_node(
        node,
        status=result_status,
        finished_at=now,
        result=result,
        issues=(),
    )
    updated_nodes = tuple(
        updated_node if item.node_id == node.node_id else item for item in state.nodes
    )
    if result_status != ResearchNodeRunStatus.COMPLETE and node.required:
        closed_nodes = _cancel_active_nodes(
            updated_nodes,
            now,
            "research run stopped after a required node was incomplete",
        )
        return _replace_state(
            state,
            nodes=closed_nodes,
            updated_at=now,
            status=ResearchRunStatus.FAILED,
            issues=(
                ResearchRunIssue(
                    code=ResearchRunIssueCode.REQUIRED_NODE_INCOMPLETE,
                    safe_message="required research node did not complete; run was failed safely",
                    node_id=node.node_id,
                ),
            ),
        )
    unblocked = _cancel_blocked_nodes(updated_nodes, now)
    activated = _activate_ready_nodes(unblocked, now)
    if all(
        item.status
        not in {ResearchNodeRunStatus.PENDING, ResearchNodeRunStatus.RUNNING}
        for item in activated
    ):
        return _finalize_terminal_nodes(state, activated, now)
    return _replace_state(state, nodes=activated, updated_at=now)


def finish_research_run(state: ResearchRunState, now: datetime) -> ResearchRunState:
    """Close a run only after every node is terminal and required nodes pass."""
    _require_aware(now, "now")
    if state.status != ResearchRunStatus.RUNNING:
        raise ValueError("only a RUNNING research run can finish")
    active = {
        ResearchNodeRunStatus.PENDING,
        ResearchNodeRunStatus.RUNNING,
    }
    if now >= state.deadline_at and any(node.status in active for node in state.nodes):
        return _deadline_failure(state, now)
    if any(node.status in active for node in state.nodes):
        closed = _cancel_blocked_nodes(state.nodes, now)
        if any(node.status in active for node in closed):
            raise ValueError("research run still has active pending or running nodes")
        return _finalize_terminal_nodes(state, closed, now)
    return _finalize_terminal_nodes(state, state.nodes, now)


def cancel_research_run(
    state: ResearchRunState,
    now: datetime,
    reason: str,
) -> ResearchRunState:
    """Cancel a non-terminal run without retaining an exception or payload."""
    _require_aware(now, "now")
    _ensure_live(state)
    reason = _safe_cancel_reason(reason)
    if now >= state.deadline_at:
        return _deadline_failure(state, now)
    nodes = []
    for node in state.nodes:
        if node.status in {
            ResearchNodeRunStatus.PENDING,
            ResearchNodeRunStatus.RUNNING,
        }:
            nodes.append(
                _replace_node(
                    node,
                    status=ResearchNodeRunStatus.CANCELLED,
                    finished_at=now,
                    issues=(
                        ResearchNodeRunIssue(
                            code=ResearchNodeRunIssueCode.CANCELLED,
                            safe_message=reason,
                        ),
                    ),
                )
            )
        else:
            nodes.append(node)
    return _replace_state(
        state,
        nodes=tuple(nodes),
        updated_at=now,
        status=ResearchRunStatus.CANCELLED,
        issues=(
            ResearchRunIssue(
                code=ResearchRunIssueCode.CANCELLED,
                safe_message=reason,
            ),
        ),
    )
