"""Structured, fixture-friendly recipes for the four research specialist tracks."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.contracts.evidence import ContractModel, FindingSeverity, NonEmptyStr
from app.providers import FrozenDict, ProviderOperation
from app.research.contracts import ResearchNodeKind


ResearchIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=160,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/%\-]*$",
    ),
]


class ResearchSpecialistRole(StrEnum):
    """Product-facing names for the four bounded research tracks."""

    MACRO = "MACRO"
    INDUSTRY = "INDUSTRY"
    STOCK = "STOCK"
    ETF_FUND = "ETF_FUND"


_ROLE_TO_NODE_KIND: dict[ResearchSpecialistRole, ResearchNodeKind] = {
    ResearchSpecialistRole.MACRO: ResearchNodeKind.MACRO,
    ResearchSpecialistRole.INDUSTRY: ResearchNodeKind.INDUSTRY,
    ResearchSpecialistRole.STOCK: ResearchNodeKind.STOCK,
    ResearchSpecialistRole.ETF_FUND: ResearchNodeKind.FUND,
}

_ALLOWED_OPERATIONS: dict[ResearchNodeKind, frozenset[ProviderOperation]] = {
    ResearchNodeKind.MACRO: frozenset({ProviderOperation.MACRO_DATA}),
    ResearchNodeKind.INDUSTRY: frozenset({ProviderOperation.INDUSTRY_DATA}),
    ResearchNodeKind.STOCK: frozenset(
        {ProviderOperation.COMPANY_DATA, ProviderOperation.MARKET_DATA}
    ),
    ResearchNodeKind.FUND: frozenset({ProviderOperation.FUND_DATA}),
}


def allowed_operations_for_node(
    node_kind: ResearchNodeKind,
) -> frozenset[ProviderOperation]:
    """Return the single source of truth for node-kind/provider compatibility."""

    try:
        return _ALLOWED_OPERATIONS[node_kind]
    except KeyError as exc:  # pragma: no cover - StrEnum validation normally prevents this
        raise ValueError(f"unsupported research node kind: {node_kind!r}") from exc


_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "secret",
    "token",
    "credential",
    "cookie",
)


def _contains_sensitive(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return any(item in normalized for item in _SENSITIVE_SUBSTRINGS)


def _finite(value: Decimal, field_name: str) -> None:
    if not value.is_finite():
        raise ValueError(f"{field_name} must be finite")


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


class ResearchSpecialistNode(ContractModel):
    """One provider-backed source node belonging to a specialist track.

    Two nodes may share ``claim_id`` while carrying different source/lineage
    identities.  The executor still treats each node as one bounded request;
    the matrix service aggregates their observations for Cross Validation.
    """

    schema_version: Literal["research-specialist-node.v1"] = (
        "research-specialist-node.v1"
    )
    node_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    role: ResearchSpecialistRole
    node_kind: ResearchNodeKind
    operation: ProviderOperation
    request_id: ResearchIdentifier
    subject: ResearchIdentifier
    required_fields: tuple[NonEmptyStr, ...] = Field(min_length=1)
    parameters: FrozenDict = Field(default_factory=FrozenDict)
    required: bool = True
    dependencies: tuple[ResearchIdentifier, ...] = Field(default_factory=tuple)
    timeout_ms: int = Field(gt=0)
    claim_id: ResearchIdentifier
    metric: NonEmptyStr
    unit: NonEmptyStr
    period: NonEmptyStr
    expected_value: Decimal
    finding_kind: NonEmptyStr
    finding_severity: FindingSeverity
    finding_statement: NonEmptyStr
    source: ResearchIdentifier
    record_id: ResearchIdentifier
    lineage_id: ResearchIdentifier

    @model_validator(mode="after")
    def validate_node(self) -> Self:
        _finite(self.expected_value, "expected_value")
        if self.node_kind != _ROLE_TO_NODE_KIND[self.role]:
            raise ValueError("role does not match node_kind")
        if self.operation not in allowed_operations_for_node(self.node_kind):
            raise ValueError("operation does not match node_kind")
        if self.metric not in self.required_fields:
            raise ValueError("claim metric must be one of required_fields")
        if len(set(self.required_fields)) != len(self.required_fields):
            raise ValueError("required_fields must not contain duplicates")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("dependencies must not contain duplicates")
        if self.dependencies != tuple(sorted(self.dependencies)):
            raise ValueError("dependencies must be in deterministic order")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("specialist node must not contain sensitive metadata")
        return self


class ResearchSpecialistMatrix(ContractModel):
    """Owner-closed recipes for a complete four-track research run."""

    schema_version: Literal["research-specialist-matrix.v1"] = (
        "research-specialist-matrix.v1"
    )
    matrix_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    generated_at: datetime
    budget_ms: int = Field(gt=0)
    scope_description: NonEmptyStr
    nodes: tuple[ResearchSpecialistNode, ...] = Field(min_length=4)

    @model_validator(mode="after")
    def validate_matrix(self) -> Self:
        _aware(self.generated_at, "generated_at")
        if tuple(node.node_id for node in self.nodes) != tuple(
            sorted(node.node_id for node in self.nodes)
        ):
            raise ValueError("specialist nodes must be in deterministic node_id order")
        node_ids = [node.node_id for node in self.nodes]
        if len(node_ids) != len(set(node_ids)):
            raise ValueError("specialist node IDs must be unique")
        request_ids = [node.request_id for node in self.nodes]
        if len(request_ids) != len(set(request_ids)):
            raise ValueError("specialist request IDs must be unique")
        source_ids = [node.source for node in self.nodes]
        if len(source_ids) != len(set(source_ids)):
            raise ValueError("specialist source IDs must be unique")
        record_ids = [node.record_id for node in self.nodes]
        if len(record_ids) != len(set(record_ids)):
            raise ValueError("specialist record IDs must be unique")
        lineage_ids = [node.lineage_id for node in self.nodes]
        if len(lineage_ids) != len(set(lineage_ids)):
            raise ValueError("specialist lineage IDs must be unique")
        if any(node.owner_id != self.owner_id for node in self.nodes):
            raise ValueError("specialist node owner does not match matrix owner")
        if any(node.timeout_ms > self.budget_ms for node in self.nodes):
            raise ValueError("specialist node timeout must not exceed matrix budget")

        known_ids = set(node_ids)
        if any(
            dependency not in known_ids
            for node in self.nodes
            for dependency in node.dependencies
        ):
            raise ValueError("specialist node dependency references an unknown node")
        if any(
            dependency == node.node_id
            for node in self.nodes
            for dependency in node.dependencies
        ):
            raise ValueError("specialist node must not depend on itself")
        indegree = {node_id: 0 for node_id in node_ids}
        children: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for node in self.nodes:
            for dependency in node.dependencies:
                indegree[node.node_id] += 1
                children[dependency].append(node.node_id)
        ready = sorted(node_id for node_id, degree in indegree.items() if degree == 0)
        visited = 0
        while ready:
            current = ready.pop(0)
            visited += 1
            for child in sorted(children[current]):
                indegree[child] -= 1
                if indegree[child] == 0:
                    ready.append(child)
            ready.sort()
        if visited != len(node_ids):
            raise ValueError("specialist node dependencies contain a cycle")

        required_kinds = {
            ResearchNodeKind.MACRO,
            ResearchNodeKind.INDUSTRY,
            ResearchNodeKind.STOCK,
            ResearchNodeKind.FUND,
        }
        present_kinds = {node.node_kind for node in self.nodes}
        if not required_kinds.issubset(present_kinds):
            missing = ", ".join(sorted(kind.value for kind in required_kinds - present_kinds))
            raise ValueError("specialist matrix is missing node kind(s): " + missing)

        by_claim: dict[str, list[ResearchSpecialistNode]] = {}
        for node in self.nodes:
            by_claim.setdefault(node.claim_id, []).append(node)
        for claim_id, claim_nodes in by_claim.items():
            if len(claim_nodes) < 2:
                raise ValueError(f"claim {claim_id!r} requires two source nodes")
            if len({node.lineage_id for node in claim_nodes}) < 2:
                raise ValueError(f"claim {claim_id!r} requires independent lineages")
            first = claim_nodes[0]
            for node in claim_nodes[1:]:
                if any(
                    getattr(node, field) != getattr(first, field)
                    for field in (
                        "role",
                        "node_kind",
                        "subject",
                        "metric",
                        "unit",
                        "period",
                        "expected_value",
                        "finding_kind",
                        "finding_severity",
                        "finding_statement",
                    )
                ):
                    raise ValueError(f"claim {claim_id!r} has inconsistent source metadata")

        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("specialist matrix must not contain sensitive metadata")
        return self

    def claims(self) -> tuple[ResearchSpecialistNode, ...]:
        """Return one deterministic representative node per claim."""

        representatives: dict[str, ResearchSpecialistNode] = {}
        for node in self.nodes:
            representatives.setdefault(node.claim_id, node)
        return tuple(representatives[key] for key in sorted(representatives))


class ResearchSpecialistMatrixRequest(ContractModel):
    """Replay-safe owner/request envelope for running one matrix."""

    schema_version: Literal["research-specialist-matrix-request.v1"] = (
        "research-specialist-matrix-request.v1"
    )
    matrix_id: ResearchIdentifier
    request_id: ResearchIdentifier
    owner_id: ResearchIdentifier
    generated_at: datetime

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        _aware(self.generated_at, "generated_at")
        serialized = self.model_dump_json().casefold()
        if any(token in serialized for token in _SENSITIVE_SUBSTRINGS):
            raise ValueError("specialist matrix request must not contain sensitive metadata")
        return self


__all__ = [
    "ResearchIdentifier",
    "ResearchSpecialistMatrix",
    "ResearchSpecialistMatrixRequest",
    "ResearchSpecialistNode",
    "ResearchSpecialistRole",
    "allowed_operations_for_node",
]
