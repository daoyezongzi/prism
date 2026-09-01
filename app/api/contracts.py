"""Public API response contracts with no raw exception payloads."""

from __future__ import annotations

from typing import Literal

from app.contracts.evidence import ContractModel
from app.store import DecisionEvent, DecisionEventSummary


class DecisionEventWriteResponse(ContractModel):
    schema_version: Literal["decision-event-write.v1"] = "decision-event-write.v1"
    event: DecisionEvent
    created: bool


class DecisionEventListResponse(ContractModel):
    schema_version: Literal["decision-event-list.v1"] = "decision-event-list.v1"
    items: tuple[DecisionEventSummary, ...]


class ErrorResponse(ContractModel):
    schema_version: Literal["api-error.v1"] = "api-error.v1"
    error_code: str
    message: str


__all__ = [
    "DecisionEventListResponse",
    "DecisionEventWriteResponse",
    "ErrorResponse",
]
