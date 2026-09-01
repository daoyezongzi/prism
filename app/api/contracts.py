"""Public API response contracts with no raw exception payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.gates import GateStatus
from app.store import DecisionEvent, DecisionEventSummary
from app.portfolio import PortfolioImportBundle
from app.profile import RiskQuestionnaire
from app.service import AdvisorQueryRequest
from pydantic import model_validator


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


class AdvisorQueryResponse(ContractModel):
    schema_version: Literal["advisor-query-response.v1"] = (
        "advisor-query-response.v1"
    )
    query_id: NonEmptyStr
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    research_run_id: NonEmptyStr
    status: GateStatus
    created: bool
    event: DecisionEvent

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if self.owner_id != self.event.owner_id:
            raise ValueError("advisor response owner does not match event")
        if self.status != self.event.status:
            raise ValueError("advisor response status does not match event")
        if self.event.result.decision_gate is not None and (
            self.profile_id != self.event.result.decision_gate.profile_id
        ):
            raise ValueError("advisor response profile does not match event")
        if self.event.result.receipt is not None and (
            self.profile_id != self.event.result.receipt.profile_id
            or self.research_run_id != self.event.result.receipt.research_run_id
        ):
            raise ValueError("advisor response receipt does not match event")
        return self


class AdvisorQueryTemplateResponse(ContractModel):
    schema_version: Literal["advisor-query-template.v1"] = (
        "advisor-query-template.v1"
    )
    fixture_id: NonEmptyStr
    generated_at: datetime
    questionnaire: RiskQuestionnaire
    portfolio: PortfolioImportBundle

    @model_validator(mode="after")
    def validate_template_response(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        if self.questionnaire.owner_id != self.portfolio.owner_id:
            raise ValueError("template response owners must match")
        return self


__all__ = [
    "DecisionEventListResponse",
    "DecisionEventWriteResponse",
    "AdvisorQueryResponse",
    "AdvisorQueryTemplateResponse",
    "ErrorResponse",
    "AdvisorQueryRequest",
]
