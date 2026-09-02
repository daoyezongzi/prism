"""Immutable, owner-scoped structured context-memory contracts.

Context memory deliberately stores only validated domain objects.  It is an
append-only replay anchor for a confirmed questionnaire/profile and portfolio,
not a transcript, prompt cache, or general-purpose JSON document.
"""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.gates.fingerprint import canonical_payload_signature
from app.convertible_bond import ConvertibleBondResearchScenarioId
from app.fund import FundResearchScenarioId
from app.optimization import OptimizationScenarioId
from app.portfolio import PortfolioImportBundle
from app.profile import RiskProfile, RiskQuestionnaire
from app.research import ResearchScenarioId
from app.service.intent_planning import AdvisorIntentRequest, AdvisorPlanResponse
from app.stock import StockResearchScenarioId


Digest = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    ),
]

ReferenceId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    ),
]

MemoryId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=47,
        max_length=47,
        pattern=r"^context-memory:[0-9a-f]{32}$",
    ),
]


_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "privatekey",
    "secret",
    "token",
    "credential",
    "cookie",
)


class ContextMemorySource(StrEnum):
    """How a record entered the local memory ledger."""

    EXPLICIT_SAVE = "EXPLICIT_SAVE"


class ContextMemoryReferences(ContractModel):
    """Stable IDs of optional derived work; no derived payload is copied."""

    research_matrix_id: ReferenceId | None = None
    research_run_id: ReferenceId | None = None
    research_scenario_id: ResearchScenarioId | None = None
    stock_research_run_id: ReferenceId | None = None
    stock_research_scenario_id: StockResearchScenarioId | None = None
    fund_research_run_id: ReferenceId | None = None
    fund_research_scenario_id: FundResearchScenarioId | None = None
    convertible_bond_research_run_id: ReferenceId | None = None
    convertible_bond_research_scenario_id: ConvertibleBondResearchScenarioId | None = None
    optimization_request_id: ReferenceId | None = None
    optimization_scenario_id: OptimizationScenarioId | None = None

    @model_validator(mode="after")
    def validate_references(self) -> Self:
        pair_rules = (
            (self.research_run_id, self.research_matrix_id, "research_run_id"),
            (self.research_scenario_id, self.research_run_id, "research_scenario_id"),
            (
                self.stock_research_scenario_id,
                self.stock_research_run_id,
                "stock_research_scenario_id",
            ),
            (
                self.fund_research_scenario_id,
                self.fund_research_run_id,
                "fund_research_scenario_id",
            ),
            (
                self.convertible_bond_research_scenario_id,
                self.convertible_bond_research_run_id,
                "convertible_bond_research_scenario_id",
            ),
            (
                self.optimization_scenario_id,
                self.optimization_request_id,
                "optimization_scenario_id",
            ),
        )
        for child, parent, child_name in pair_rules:
            if child is not None and parent is None:
                raise ValueError(f"{child_name} requires its parent reference")
        if any(
            item in self.model_dump_json().casefold().replace("-", "_")
            for item in _SENSITIVE_SUBSTRINGS
        ):
            raise ValueError("context references must not contain sensitive fields")
        return self


class _ContextMemoryPayload(ContractModel):
    """Shared validated payload for write requests and stored records."""

    owner_id: NonEmptyStr
    questionnaire: RiskQuestionnaire
    profile: RiskProfile
    portfolio: PortfolioImportBundle
    intent: AdvisorIntentRequest | None = None
    plan: AdvisorPlanResponse | None = None
    references: ContextMemoryReferences = Field(default_factory=ContextMemoryReferences)

    @model_validator(mode="after")
    def validate_payload(self) -> Self:
        if self.questionnaire.owner_id != self.owner_id:
            raise ValueError("questionnaire owner_id does not match context owner_id")
        if self.profile.owner_id != self.owner_id:
            raise ValueError("profile owner_id does not match context owner_id")
        if self.portfolio.owner_id != self.owner_id:
            raise ValueError("portfolio owner_id does not match context owner_id")
        if self.profile.questionnaire_id != self.questionnaire.questionnaire_id:
            raise ValueError("profile questionnaire_id does not match questionnaire")
        if self.profile.created_at != self.questionnaire.answered_at:
            raise ValueError("profile created_at does not match questionnaire answered_at")

        if self.intent is not None:
            if self.intent.owner_id != self.owner_id:
                raise ValueError("intent owner_id does not match context owner_id")
            if self.intent.questionnaire_id != self.questionnaire.questionnaire_id:
                raise ValueError("intent questionnaire_id does not match questionnaire")
            if self.intent.portfolio_bundle_id != self.portfolio.bundle_id:
                raise ValueError("intent portfolio_bundle_id does not match portfolio")
            if (
                self.intent.position_snapshot_id
                != self.portfolio.position_snapshot.snapshot_id
            ):
                raise ValueError("intent position_snapshot_id does not match portfolio")

        if self.plan is not None:
            if self.intent is None:
                raise ValueError("plan requires its intent")
            if self.plan.owner_id != self.owner_id:
                raise ValueError("plan owner_id does not match context owner_id")
            if self.plan.intent_id != self.intent.intent_id:
                raise ValueError("plan intent_id does not match intent")
            if self.plan.intent_type != self.intent.intent_type:
                raise ValueError("plan intent_type does not match intent")
            if self.plan.questionnaire_id != self.questionnaire.questionnaire_id:
                raise ValueError("plan questionnaire_id does not match questionnaire")
            if self.plan.portfolio_bundle_id != self.portfolio.bundle_id:
                raise ValueError("plan portfolio_bundle_id does not match portfolio")
            if (
                self.plan.position_snapshot_id
                != self.portfolio.position_snapshot.snapshot_id
            ):
                raise ValueError("plan position_snapshot_id does not match portfolio")
            if self.plan.generated_at != self.intent.generated_at:
                raise ValueError("plan generated_at does not match intent generated_at")

        serialized = self.model_dump_json().casefold().replace("-", "_")
        if any(item in serialized for item in _SENSITIVE_SUBSTRINGS):
            raise ValueError("context memory must not contain sensitive fields")
        return self


class ContextMemoryWriteRequest(_ContextMemoryPayload):
    """Client input; storage identity and timestamp are server-derived."""

    schema_version: Literal["context-memory-write-request.v1"] = (
        "context-memory-write-request.v1"
    )


class ContextMemoryRecord(_ContextMemoryPayload):
    """Immutable append-only memory record returned by the local store."""

    schema_version: Literal["context-memory-record.v1"] = "context-memory-record.v1"
    memory_id: MemoryId
    source: ContextMemorySource = ContextMemorySource.EXPLICIT_SAVE
    saved_at: datetime
    content_hash: Digest

    @model_validator(mode="after")
    def validate_record(self) -> Self:
        if self.saved_at.tzinfo is None or self.saved_at.utcoffset() is None:
            raise ValueError("saved_at must be timezone-aware")
        expected_hash = context_memory_content_hash(self)
        if self.content_hash != expected_hash:
            raise ValueError("content_hash does not match context memory content")
        expected_id = context_memory_id(owner_id=self.owner_id, content_hash=expected_hash)
        if self.memory_id != expected_id:
            raise ValueError("memory_id does not match context memory identity")
        return self


class ContextMemoryWriteResponse(ContractModel):
    schema_version: Literal["context-memory-write-response.v1"] = (
        "context-memory-write-response.v1"
    )
    record: ContextMemoryRecord
    created: bool


class ContextMemoryListResponse(ContractModel):
    schema_version: Literal["context-memory-list-response.v1"] = (
        "context-memory-list-response.v1"
    )
    owner_id: NonEmptyStr
    records: tuple[ContextMemoryRecord, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_list(self) -> Self:
        if any(record.owner_id != self.owner_id for record in self.records):
            raise ValueError("context memory record owner does not match list owner")
        keys = [(record.saved_at, record.memory_id) for record in self.records]
        if keys != sorted(keys, reverse=True):
            raise ValueError("context memory records must be sorted newest first")
        if len({record.memory_id for record in self.records}) != len(self.records):
            raise ValueError("context memory records must not contain duplicate IDs")
        return self


def context_memory_content_payload(value: _ContextMemoryPayload) -> dict[str, object]:
    """Return content-addressed fields, excluding server metadata and identity."""

    return value.model_dump(
        mode="json",
        exclude={"schema_version", "memory_id", "source", "saved_at", "content_hash"},
    )


def context_memory_content_hash(value: _ContextMemoryPayload) -> str:
    return canonical_payload_signature(context_memory_content_payload(value))


def context_memory_id(*, owner_id: str, content_hash: str) -> str:
    payload = f"{owner_id}\x1f{content_hash}".encode("utf-8")
    return "context-memory:" + sha256(payload).hexdigest()[:32]


def build_context_memory_record(
    request: ContextMemoryWriteRequest,
    *,
    saved_at: datetime,
) -> ContextMemoryRecord:
    """Revalidate client content and derive immutable server identity."""

    normalized = ContextMemoryWriteRequest.model_validate(
        request.model_dump(mode="python")
    )
    if saved_at.tzinfo is None or saved_at.utcoffset() is None:
        raise ValueError("saved_at must be timezone-aware")
    content_hash = context_memory_content_hash(normalized)
    return ContextMemoryRecord(
        owner_id=normalized.owner_id,
        questionnaire=normalized.questionnaire,
        profile=normalized.profile,
        portfolio=normalized.portfolio,
        intent=normalized.intent,
        plan=normalized.plan,
        references=normalized.references,
        memory_id=context_memory_id(
            owner_id=normalized.owner_id,
            content_hash=content_hash,
        ),
        source=ContextMemorySource.EXPLICIT_SAVE,
        saved_at=saved_at,
        content_hash=content_hash,
    )


__all__ = [
    "ContextMemoryListResponse",
    "ContextMemoryRecord",
    "ContextMemoryReferences",
    "ContextMemorySource",
    "ContextMemoryWriteRequest",
    "ContextMemoryWriteResponse",
    "build_context_memory_record",
    "context_memory_content_hash",
    "context_memory_content_payload",
    "context_memory_id",
]
