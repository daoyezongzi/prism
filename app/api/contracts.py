"""Public API response contracts with no raw exception payloads."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from app.contracts.evidence import (
    ContractModel,
    DecisionTrace,
    NonEmptyStr,
)
from app.gates import GateStatus
from app.orchestration import ResearchNodeRunStatus, ResearchRunStatus
from app.research import (
    ResearchNodeKind,
    CrossValidationResult,
    ResearchPipelineIssue,
    ResearchPipelineStatus,
    ResearchSpecialistMatrixRequest,
    ResearchSpecialistRole,
)
from app.store import DecisionEvent, DecisionEventSummary
from app.portfolio import PortfolioImportBundle
from app.profile import RiskQuestionnaire
from app.service import (
    AdvisorQueryRequest,
)
from pydantic import Field
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


class ResearchMatrixTemplateResponse(ContractModel):
    schema_version: Literal["research-matrix-template.v1"] = (
        "research-matrix-template.v1"
    )
    matrix_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    scope_description: NonEmptyStr
    roles: tuple[ResearchSpecialistRole, ...] = Field(min_length=4)
    node_count: int = Field(ge=4)

    @model_validator(mode="after")
    def validate_template_response(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("research template generated_at must be timezone-aware")
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("research template roles must not contain duplicates")
        if set(self.roles) != set(ResearchSpecialistRole):
            raise ValueError("research template must cover all specialist roles")
        if self.node_count < len(self.roles):
            raise ValueError("research template node_count is too small")
        return self


class ResearchMatrixIssueResponse(ContractModel):
    code: NonEmptyStr
    safe_message: NonEmptyStr


class ResearchMatrixNodeResponse(ContractModel):
    node_id: NonEmptyStr
    role: ResearchSpecialistRole
    node_kind: ResearchNodeKind
    subject: NonEmptyStr
    required: bool
    status: ResearchNodeRunStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    issues: tuple[ResearchMatrixIssueResponse, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_timestamps(self) -> Self:
        for name, value in (
            ("started_at", self.started_at),
            ("finished_at", self.finished_at),
        ):
            if value is not None and (value.tzinfo is None or value.utcoffset() is None):
                raise ValueError(f"research node {name} must be timezone-aware")
        if self.started_at is None and self.finished_at is not None:
            raise ValueError("research node finished_at requires started_at")
        if self.started_at is not None and self.finished_at is not None:
            if self.finished_at < self.started_at:
                raise ValueError("research node finished_at must not precede started_at")
        return self


class ResearchMatrixResponse(ContractModel):
    schema_version: Literal["research-matrix-response.v1"] = (
        "research-matrix-response.v1"
    )
    matrix_id: NonEmptyStr
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    run_id: NonEmptyStr
    run_status: ResearchRunStatus
    pipeline_status: ResearchPipelineStatus
    nodes: tuple[ResearchMatrixNodeResponse, ...] = Field(min_length=4)
    validations: tuple[CrossValidationResult, ...] = Field(default_factory=tuple)
    issues: tuple[ResearchPipelineIssue, ...] = Field(default_factory=tuple)
    trace: DecisionTrace

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        node_ids = [node.node_id for node in self.nodes]
        if node_ids != sorted(node_ids) or len(node_ids) != len(set(node_ids)):
            raise ValueError("research response nodes must be unique and sorted")
        if {node.role for node in self.nodes} != set(ResearchSpecialistRole):
            raise ValueError("research response must cover all specialist roles")
        claim_ids = [item.claim_id for item in self.validations]
        if len(claim_ids) != len(set(claim_ids)):
            raise ValueError("research response validations must be unique")
        if any(item.owner_id != self.owner_id for item in self.validations):
            raise ValueError("research response validation owner does not match")
        if self.trace.recommendations:
            raise ValueError("research response must not contain recommendations")
        if self.pipeline_status.value == "READY":
            if self.run_status != ResearchRunStatus.COMPLETED:
                raise ValueError("READY research response requires completed run")
            if not self.validations or not self.trace.facts or not self.trace.findings:
                raise ValueError("READY research response requires validation trace")
        elif self.trace.facts or self.trace.findings:
            raise ValueError("non-ready research response must not expose facts/findings")
        serialized = self.model_dump_json().casefold()
        for forbidden in (
            "api_key",
            "authorization",
            "password",
            "private_key",
            "secret",
            "token",
            "credential",
            "cookie",
        ):
            if forbidden in serialized:
                raise ValueError("research response must not contain sensitive fields")
        return self


__all__ = [
    "DecisionEventListResponse",
    "DecisionEventWriteResponse",
    "AdvisorQueryResponse",
    "AdvisorQueryTemplateResponse",
    "ResearchMatrixTemplateResponse",
    "ResearchMatrixIssueResponse",
    "ResearchMatrixNodeResponse",
    "ResearchMatrixResponse",
    "ErrorResponse",
    "AdvisorQueryRequest",
    "ResearchSpecialistMatrixRequest",
]
