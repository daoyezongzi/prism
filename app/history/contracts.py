"""Contracts for recommendation history audit and comparison."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from app.contracts import ActionType, AllocationRange
from app.contracts.evidence import ContractModel, NonEmptyStr
from app.gates import GateStatus


Digest = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    ),
]


class RecommendationHistoryItem(ContractModel):
    """Summarized historical decision item for audit trail."""

    event_id: NonEmptyStr
    receipt_id: NonEmptyStr | None = None
    composition_id: NonEmptyStr
    status: GateStatus
    action_type: ActionType | None = None
    asset: str | None = None
    allocation_range: AllocationRange | None = None
    risk_score: Decimal | None = None
    profile_version: str | None = None
    recorded_at: datetime
    content_hash: Digest
    finding_count: int = 0
    invalidation_conditions: tuple[str, ...] = ()
    summary: str | None = None

    @model_validator(mode="after")
    def validate_item(self) -> Self:
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.finding_count < 0:
            raise ValueError("finding_count must be non-negative")
        return self


class RecommendationHistoryResponse(ContractModel):
    """Response containing owner-scoped recommendation history."""

    schema_version: Literal["recommendation-history-response.v1"] = "recommendation-history-response.v1"
    owner_id: NonEmptyStr
    total_count: int
    items: tuple[RecommendationHistoryItem, ...]

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if self.total_count < 0:
            raise ValueError("total_count must be non-negative")
        if len(self.items) != self.total_count:
            # When paginated, items count <= total_count
            if len(self.items) > self.total_count:
                raise ValueError("items count cannot exceed total_count")
        return self


class RecommendationComparisonRequest(ContractModel):
    """Request to compare two historical decision receipts for the same owner."""

    schema_version: Literal["recommendation-comparison-request.v1"] = "recommendation-comparison-request.v1"
    owner_id: NonEmptyStr
    receipt_a_id: NonEmptyStr
    receipt_b_id: NonEmptyStr


class RecommendationComparisonResponse(ContractModel):
    """Deterministic comparison between two historical decision receipts."""

    schema_version: Literal["recommendation-comparison-response.v1"] = "recommendation-comparison-response.v1"
    owner_id: NonEmptyStr
    receipt_a_id: NonEmptyStr
    receipt_b_id: NonEmptyStr
    event_a_id: NonEmptyStr
    event_b_id: NonEmptyStr
    action_a: ActionType | None = None
    action_b: ActionType | None = None
    action_changed: bool
    action_transition: str
    risk_score_a: Decimal | None = None
    risk_score_b: Decimal | None = None
    risk_score_delta: Decimal | None = None
    allocation_range_a: AllocationRange | None = None
    allocation_range_b: AllocationRange | None = None
    min_allocation_delta_pct: Decimal | None = None
    max_allocation_delta_pct: Decimal | None = None
    findings_count_a: int
    findings_count_b: int
    new_invalidation_conditions: tuple[str, ...] = ()
    removed_invalidation_conditions: tuple[str, ...] = ()
    summary: str
