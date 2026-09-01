"""Immutable contracts for a bounded, replayable research run."""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.research import ResearchNodeKind, ResearchNodeResult, ResearchNodeStatus


class ResearchRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResearchNodeRunStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ResearchRunIssueCode(StrEnum):
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    REQUIRED_NODE_INCOMPLETE = "REQUIRED_NODE_INCOMPLETE"
    OPTIONAL_NODE_INCOMPLETE = "OPTIONAL_NODE_INCOMPLETE"
    CANCELLED = "CANCELLED"


class ResearchNodeRunIssueCode(StrEnum):
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"
    CANCELLED = "CANCELLED"


class ResearchNodeSpec(ContractModel):
    """Static node metadata used to validate a research DAG."""

    schema_version: Literal["research-node-spec.v1"] = "research-node-spec.v1"
    node_id: NonEmptyStr
    owner_id: NonEmptyStr
    node_kind: ResearchNodeKind
    required: bool = True
    dependencies: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    timeout_ms: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_spec(self) -> Self:
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must not contain duplicates")
        if self.dependencies != tuple(sorted(self.dependencies)):
            raise ValueError("dependencies must be in deterministic order")
        if self.node_id in self.dependencies:
            raise ValueError("a node must not depend on itself")
        return self


def _topological_order(nodes: tuple[ResearchNodeSpec, ...]) -> tuple[str, ...]:
    by_id = {node.node_id: node for node in nodes}
    if len(by_id) != len(nodes):
        raise ValueError("nodes must not contain duplicate node_id")
    if any(node.owner_id != nodes[0].owner_id for node in nodes):
        raise ValueError("node owner_id values must match the plan owner")
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

    indegree = {node_id: len(by_id[node_id].dependencies) for node_id in by_id}
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


class ResearchPlan(ContractModel):
    """A closed DAG whose topology is independent of execution arrival order."""

    schema_version: Literal["research-plan.v1"] = "research-plan.v1"
    plan_id: NonEmptyStr
    owner_id: NonEmptyStr
    scope_description: NonEmptyStr
    nodes: tuple[ResearchNodeSpec, ...] = Field(min_length=1)
    topological_order: tuple[NonEmptyStr, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan(self) -> Self:
        node_ids = tuple(node.node_id for node in self.nodes)
        if node_ids != tuple(sorted(node_ids)):
            raise ValueError("nodes must be in deterministic node_id order")
        if any(node.owner_id != self.owner_id for node in self.nodes):
            raise ValueError("node owner_id does not match plan owner_id")
        expected = _topological_order(self.nodes)
        if self.topological_order != expected:
            raise ValueError("topological_order is not the deterministic DAG order")
        if set(self.topological_order) != set(node_ids):
            raise ValueError("topological_order must contain every node exactly once")
        return self


class ResearchNodeRunIssue(ContractModel):
    code: ResearchNodeRunIssueCode
    safe_message: NonEmptyStr

    @model_validator(mode="after")
    def validate_safe_message(self) -> Self:
        forbidden = (
            "api_key",
            "authorization",
            "password",
            "private_key",
            "secret",
            "token",
        )
        if any(item in self.safe_message.casefold() for item in forbidden):
            raise ValueError("node run safe_message must not contain sensitive fields")
        return self


class ResearchNodeRun(ContractModel):
    """Runtime status for one node; result payloads remain typed Phase 6 objects."""

    schema_version: Literal["research-node-run.v1"] = "research-node-run.v1"
    node_id: NonEmptyStr
    owner_id: NonEmptyStr
    node_kind: ResearchNodeKind
    required: bool
    dependencies: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    timeout_ms: int = Field(gt=0)
    status: ResearchNodeRunStatus = ResearchNodeRunStatus.PENDING
    attempt: int = Field(ge=0)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: ResearchNodeResult | None = None
    issues: tuple[ResearchNodeRunIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_node_run(self) -> Self:
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("node run dependencies must not contain duplicates")
        if self.dependencies != tuple(sorted(self.dependencies)):
            raise ValueError("node run dependencies must be in deterministic order")
        if self.started_at is not None and (
            self.started_at.tzinfo is None or self.started_at.utcoffset() is None
        ):
            raise ValueError("started_at must be timezone-aware")
        if self.finished_at is not None and (
            self.finished_at.tzinfo is None or self.finished_at.utcoffset() is None
        ):
            raise ValueError("finished_at must be timezone-aware")
        if (
            self.started_at is None
            and self.finished_at is not None
            and self.status
            not in {ResearchNodeRunStatus.CANCELLED, ResearchNodeRunStatus.FAILED}
        ):
            raise ValueError("finished_at requires started_at")
        if self.started_at is not None and self.finished_at is not None:
            if self.finished_at < self.started_at:
                raise ValueError("finished_at must not precede started_at")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("node run issues must not contain duplicate code")

        if self.status == ResearchNodeRunStatus.PENDING:
            if self.started_at is not None or self.finished_at is not None or self.result is not None or self.issues:
                raise ValueError("PENDING node must not carry runtime data")
        elif self.status == ResearchNodeRunStatus.RUNNING:
            if self.started_at is None or self.finished_at is not None or self.result is not None or self.issues:
                raise ValueError("RUNNING node requires only started_at")
        elif self.status in {
            ResearchNodeRunStatus.COMPLETE,
            ResearchNodeRunStatus.PARTIAL,
            ResearchNodeRunStatus.EMPTY,
        }:
            if self.started_at is None or self.finished_at is None or self.result is None:
                raise ValueError("completed node requires timestamps and result")
            expected_status = {
                ResearchNodeRunStatus.COMPLETE: ResearchNodeStatus.COMPLETE,
                ResearchNodeRunStatus.PARTIAL: ResearchNodeStatus.PARTIAL,
                ResearchNodeRunStatus.EMPTY: ResearchNodeStatus.EMPTY,
            }[self.status]
            if self.result.status != expected_status:
                raise ValueError("node run status does not match research result status")
            if self.result.node_id != self.node_id:
                raise ValueError("result node_id does not match node run")
            if self.result.owner_id != self.owner_id:
                raise ValueError("result owner_id does not match node run")
            if self.result.node_kind != self.node_kind:
                raise ValueError("result node_kind does not match node run")
            if self.issues:
                raise ValueError("usable node result must not carry runtime issues")
        elif self.status == ResearchNodeRunStatus.FAILED:
            if self.finished_at is None:
                raise ValueError("FAILED node requires finished_at")
            if self.result is not None and self.started_at is None:
                raise ValueError("FAILED node with result requires started_at")
            if self.result is not None and self.result.status != ResearchNodeStatus.FAILED:
                raise ValueError("FAILED node result must be a failed research result")
            if not self.issues and self.result is None:
                raise ValueError("FAILED node requires a result or issue")
        elif self.status == ResearchNodeRunStatus.CANCELLED:
            if self.finished_at is None or not self.issues:
                raise ValueError("CANCELLED node requires finished_at and issue")
            if self.result is not None:
                raise ValueError("CANCELLED node must not carry a result")
        return self


class ResearchRunIssue(ContractModel):
    code: ResearchRunIssueCode
    safe_message: NonEmptyStr
    node_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_safe_message(self) -> Self:
        forbidden = (
            "api_key",
            "authorization",
            "password",
            "private_key",
            "secret",
            "token",
        )
        if any(item in self.safe_message.casefold() for item in forbidden):
            raise ValueError("run safe_message must not contain sensitive fields")
        return self


class ResearchRunState(ContractModel):
    """Immutable run state that can be replayed without executing a provider."""

    schema_version: Literal["research-run-state.v1"] = "research-run-state.v1"
    run_id: NonEmptyStr
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    plan: ResearchPlan
    budget_ms: int = Field(gt=0)
    created_at: datetime
    deadline_at: datetime
    updated_at: datetime
    status: ResearchRunStatus
    nodes: tuple[ResearchNodeRun, ...] = Field(min_length=1)
    issues: tuple[ResearchRunIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_run(self) -> Self:
        for field_name in ("created_at", "deadline_at", "updated_at"):
            value = getattr(self, field_name)
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must be timezone-aware")
        expected_deadline = self.created_at + timedelta(milliseconds=self.budget_ms)
        if self.deadline_at != expected_deadline:
            raise ValueError("deadline_at must equal created_at plus budget_ms")
        if self.updated_at < self.created_at:
            raise ValueError("updated_at must not precede created_at")
        if self.plan.owner_id != self.owner_id:
            raise ValueError("plan owner_id does not match run owner_id")
        if any(node.timeout_ms > self.budget_ms for node in self.plan.nodes):
            raise ValueError("node timeout_ms must not exceed run budget_ms")
        expected_ids = self.plan.topological_order
        actual_ids = tuple(node.node_id for node in self.nodes)
        if actual_ids != expected_ids:
            raise ValueError("run nodes must follow plan topological_order")
        specs = {node.node_id: node for node in self.plan.nodes}
        if any(node.owner_id != self.owner_id for node in self.nodes):
            raise ValueError("node run owner_id does not match run owner_id")
        for node in self.nodes:
            spec = specs[node.node_id]
            if (
                node.node_kind != spec.node_kind
                or node.required != spec.required
                or node.dependencies != spec.dependencies
                or node.timeout_ms != spec.timeout_ms
            ):
                raise ValueError("node run metadata does not match plan spec")
            if node.result is not None and node.result.request_id != self.request_id:
                raise ValueError("node result request_id does not match run request_id")
        issue_codes = [issue.code for issue in self.issues]
        if len(set(issue_codes)) != len(issue_codes):
            raise ValueError("run issues must not contain duplicate code")
        known_node_ids = set(expected_ids)
        if any(
            issue.node_id is not None and issue.node_id not in known_node_ids
            for issue in self.issues
        ):
            raise ValueError("run issue node_id is not part of the plan")

        node_statuses = {node.status for node in self.nodes}
        if self.status == ResearchRunStatus.PENDING:
            if any(node.status != ResearchNodeRunStatus.PENDING for node in self.nodes) or self.issues:
                raise ValueError("PENDING run must have untouched pending nodes")
        elif self.status == ResearchRunStatus.RUNNING:
            if not any(
                node.status
                in {ResearchNodeRunStatus.PENDING, ResearchNodeRunStatus.RUNNING}
                for node in self.nodes
            ):
                raise ValueError("RUNNING run requires pending or running nodes")
        elif self.status == ResearchRunStatus.COMPLETED:
            if any(node.status != ResearchNodeRunStatus.COMPLETE for node in self.nodes) or self.issues:
                raise ValueError("COMPLETED run requires all nodes complete and no issues")
        elif self.status == ResearchRunStatus.PARTIAL:
            if any(
                node.status in {ResearchNodeRunStatus.PENDING, ResearchNodeRunStatus.RUNNING}
                for node in self.nodes
            ):
                raise ValueError("PARTIAL run must not have active nodes")
            if any(
                node.required and node.status != ResearchNodeRunStatus.COMPLETE
                for node in self.nodes
            ):
                raise ValueError("PARTIAL run must not have an incomplete required node")
            if all(node.status == ResearchNodeRunStatus.COMPLETE for node in self.nodes):
                raise ValueError("PARTIAL run requires at least one incomplete optional node")
            if not self.issues:
                raise ValueError("PARTIAL run requires an explicit issue")
        elif self.status == ResearchRunStatus.FAILED:
            if not self.issues:
                raise ValueError("FAILED run requires an explicit issue")
            if any(
                node.status
                in {ResearchNodeRunStatus.PENDING, ResearchNodeRunStatus.RUNNING}
                for node in self.nodes
            ):
                raise ValueError("FAILED run must close all active nodes")
            if all(node.status == ResearchNodeRunStatus.COMPLETE for node in self.nodes):
                raise ValueError("FAILED run must not contain an entirely completed plan")
        elif self.status == ResearchRunStatus.CANCELLED:
            if not self.issues:
                raise ValueError("CANCELLED run requires an explicit issue")
            if all(node.status == ResearchNodeRunStatus.COMPLETE for node in self.nodes):
                raise ValueError("a fully completed run must not be cancelled")
        return self
