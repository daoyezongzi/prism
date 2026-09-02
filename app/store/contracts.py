"""Immutable contracts for persisted decision events."""

from __future__ import annotations

from datetime import datetime
from hashlib import sha256
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from app.gates import GateStatus, scan_compliance_texts
from app.gates.contracts import ComplianceGateIssueCode
from app.gates.fingerprint import canonical_payload_signature
from app.contracts.evidence import ContractModel, NonEmptyStr
from app.recommendation.contracts import RecommendationCompositionResult


Digest = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    ),
]


class StoreIssueCode(StrEnum):
    """Static issue labels exposed by the HTTP boundary."""

    INVALID_INPUT = "INVALID_INPUT"
    OWNER_MISMATCH = "OWNER_MISMATCH"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    CORRUPT_RECORD = "CORRUPT_RECORD"


def decision_event_id(
    *, owner_id: str, composition_id: str, status: GateStatus, receipt_id: str | None
) -> str:
    payload = "\x1f".join(
        (owner_id, composition_id, status.value, receipt_id or "NO_RECEIPT")
    ).encode("utf-8")
    return "decision-event:" + sha256(payload).hexdigest()[:32]


def event_content_payload(event: "DecisionEvent") -> dict[str, object]:
    """Return the content-addressed fields, excluding storage metadata/hash."""

    return event.model_dump(
        mode="json",
        exclude={"content_hash", "recorded_at"},
    )


def _validate_result_text(result: RecommendationCompositionResult) -> None:
    if result.status != GateStatus.PASS:
        return
    texts: list[str] = []
    if result.summary is not None:
        texts.append(result.summary)
    for recommendation in result.trace.recommendations:
        texts.extend(
            (
                recommendation.rationale,
                *recommendation.invalidation_conditions,
            )
        )
    codes = scan_compliance_texts(texts=tuple(texts))
    if codes:
        raise ValueError(
            "result contains text rejected by compliance policy: "
            + ",".join(code.value for code in codes)
        )


class DecisionEvent(ContractModel):
    """One owner-bound decision response stored for replay and audit."""

    schema_version: Literal["decision-event.v1"] = "decision-event.v1"
    event_id: NonEmptyStr
    owner_id: NonEmptyStr
    composition_id: NonEmptyStr
    status: GateStatus
    receipt_id: NonEmptyStr | None = None
    result: RecommendationCompositionResult
    recorded_at: datetime
    content_hash: Digest

    @model_validator(mode="after")
    def validate_event(self) -> Self:
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.owner_id != self.result.owner_id:
            raise ValueError("event owner does not match result owner")
        _validate_result_text(self.result)
        if self.composition_id != self.result.composition_id:
            raise ValueError("event composition does not match result")
        if self.status != self.result.status:
            raise ValueError("event status does not match result")
        expected_receipt_id = (
            self.result.receipt.receipt_id
            if self.result.receipt is not None
            else None
        )
        if self.receipt_id != expected_receipt_id:
            raise ValueError("event receipt does not match result")
        if self.status == GateStatus.PASS and self.receipt_id is None:
            raise ValueError("PASS event requires a receipt")
        if self.status != GateStatus.PASS and self.receipt_id is not None:
            raise ValueError("non-PASS event must not carry a receipt")
        if self.event_id != decision_event_id(
            owner_id=self.owner_id,
            composition_id=self.composition_id,
            status=self.status,
            receipt_id=self.receipt_id,
        ):
            raise ValueError("event_id does not match decision identity")
        expected_hash = canonical_payload_signature(event_content_payload(self))
        if self.content_hash != expected_hash:
            raise ValueError("content_hash does not match event content")
        return self


class DecisionEventSummary(ContractModel):
    """List projection that omits the potentially larger trace payload."""

    schema_version: Literal["decision-event-summary.v1"] = (
        "decision-event-summary.v1"
    )
    event_id: NonEmptyStr
    owner_id: NonEmptyStr
    composition_id: NonEmptyStr
    status: GateStatus
    receipt_id: NonEmptyStr | None = None
    recorded_at: datetime
    content_hash: Digest

    @model_validator(mode="after")
    def validate_summary(self) -> Self:
        if self.recorded_at.tzinfo is None or self.recorded_at.utcoffset() is None:
            raise ValueError("recorded_at must be timezone-aware")
        if self.event_id != decision_event_id(
            owner_id=self.owner_id,
            composition_id=self.composition_id,
            status=self.status,
            receipt_id=self.receipt_id,
        ):
            raise ValueError("summary event_id does not match decision identity")
        return self


def build_decision_event(
    result: RecommendationCompositionResult,
    *,
    recorded_at: datetime,
) -> DecisionEvent:
    """Revalidate a composition and derive its stable event identity/hash."""

    normalized = RecommendationCompositionResult.model_validate(
        result.model_dump(mode="python")
    )
    _validate_result_text(normalized)
    receipt_id = normalized.receipt.receipt_id if normalized.receipt else None
    event_id = decision_event_id(
        owner_id=normalized.owner_id,
        composition_id=normalized.composition_id,
        status=normalized.status,
        receipt_id=receipt_id,
    )
    unsigned = DecisionEvent.model_construct(
        event_id=event_id,
        owner_id=normalized.owner_id,
        composition_id=normalized.composition_id,
        status=normalized.status,
        receipt_id=receipt_id,
        result=normalized,
        recorded_at=recorded_at,
        content_hash="0" * 64,
    )
    content_hash = canonical_payload_signature(event_content_payload(unsigned))
    return DecisionEvent(
        event_id=event_id,
        owner_id=normalized.owner_id,
        composition_id=normalized.composition_id,
        status=normalized.status,
        receipt_id=receipt_id,
        result=normalized,
        recorded_at=recorded_at,
        content_hash=content_hash,
    )


__all__ = [
    "ContextMemoryListResponse",
    "ContextMemoryRecord",
    "ContextMemoryReferences",
    "ContextMemorySource",
    "ContextMemoryWriteRequest",
    "ContextMemoryWriteResponse",
    "DecisionEvent",
    "DecisionEventSummary",
    "Digest",
    "StoreIssueCode",
    "build_decision_event",
    "decision_event_id",
    "event_content_payload",
]


def __getattr__(name: str) -> object:
    """Lazily expose context contracts without introducing an import cycle."""

    if name in {
        "ContextMemoryListResponse",
        "ContextMemoryRecord",
        "ContextMemoryReferences",
        "ContextMemorySource",
        "ContextMemoryWriteRequest",
        "ContextMemoryWriteResponse",
    }:
        from app.store import context as context_module

        return getattr(context_module, name)
    raise AttributeError(name)
