"""Deterministic structured investment-intent planning over the research matrix."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from hashlib import sha256
from typing import Literal, Self

from pydantic import model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.research import ResearchSpecialistMatrix, ResearchSpecialistRole
from app.service.contracts import QueryIdentifier


class InvestmentIntentType(StrEnum):
    """Supported explicit MVP questions; no natural-language inference."""

    TECHNOLOGY_EXPOSURE_REVIEW = "TECHNOLOGY_EXPOSURE_REVIEW"
    PORTFOLIO_RISK_REVIEW = "PORTFOLIO_RISK_REVIEW"


class AdvisorIntentRequest(ContractModel):
    """Owner-closed structured intent and context identity summary."""

    schema_version: Literal["advisor-intent-request.v1"] = "advisor-intent-request.v1"
    intent_id: QueryIdentifier
    owner_id: NonEmptyStr
    intent_type: InvestmentIntentType
    generated_at: datetime
    portfolio_bundle_id: NonEmptyStr
    position_snapshot_id: NonEmptyStr
    questionnaire_id: NonEmptyStr

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("intent generated_at must be timezone-aware")
        serialized = self.model_dump_json().casefold().replace("-", "_")
        for forbidden in (
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
        ):
            if forbidden in serialized:
                raise ValueError("intent request must not contain sensitive fields")
        return self


class AdvisorPlanResponse(ContractModel):
    """Read-only deterministic task plan; it contains no research result."""

    schema_version: Literal["advisor-plan-response.v1"] = "advisor-plan-response.v1"
    plan_id: NonEmptyStr
    intent_id: QueryIdentifier
    owner_id: NonEmptyStr
    intent_type: InvestmentIntentType
    portfolio_bundle_id: NonEmptyStr
    position_snapshot_id: NonEmptyStr
    questionnaire_id: NonEmptyStr
    generated_at: datetime
    scope_description: NonEmptyStr
    roles: tuple[ResearchSpecialistRole, ...]
    node_count: int

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("plan generated_at must be timezone-aware")
        if set(self.roles) != set(ResearchSpecialistRole):
            raise ValueError("plan must cover all specialist roles")
        if len(self.roles) != len(set(self.roles)):
            raise ValueError("plan roles must be unique")
        if self.node_count < len(self.roles):
            raise ValueError("plan node_count is too small")
        serialized = self.model_dump_json().casefold().replace("-", "_")
        for forbidden in (
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
        ):
            if forbidden in serialized:
                raise ValueError("plan response must not contain sensitive fields")
        return self


class IntentPlanningError(RuntimeError):
    """Safe refusal for an unavailable or invalid structured intent plan."""


_SCOPES = {
    InvestmentIntentType.TECHNOLOGY_EXPOSURE_REVIEW: (
        "Review technology exposure through Macro, Industry, Stock and ETF/Fund tracks."
    ),
    InvestmentIntentType.PORTFOLIO_RISK_REVIEW: (
        "Review portfolio risk constraints through Macro, Industry, Stock and ETF/Fund tracks."
    ),
}


def _stable_plan_id(request: AdvisorIntentRequest, matrix: ResearchSpecialistMatrix) -> str:
    payload = "\x1f".join(
        (
            request.owner_id,
            request.intent_id,
            request.intent_type.value,
            request.portfolio_bundle_id,
            request.position_snapshot_id,
            request.questionnaire_id,
            matrix.matrix_id,
        )
    ).encode("utf-8")
    return "advisor-plan:" + sha256(payload).hexdigest()[:32]


def build_intent_plan(
    request: AdvisorIntentRequest,
    matrix: ResearchSpecialistMatrix,
) -> AdvisorPlanResponse:
    """Map one explicit intent to the existing four-track matrix, without running it."""

    try:
        if matrix.owner_id != request.owner_id:
            raise ValueError("intent plan owner does not match matrix owner")
        roles = tuple(sorted(set(node.role for node in matrix.nodes), key=lambda role: role.value))
        return AdvisorPlanResponse(
            plan_id=_stable_plan_id(request, matrix),
            intent_id=request.intent_id,
            owner_id=request.owner_id,
            intent_type=request.intent_type,
            portfolio_bundle_id=request.portfolio_bundle_id,
            position_snapshot_id=request.position_snapshot_id,
            questionnaire_id=request.questionnaire_id,
            generated_at=request.generated_at,
            scope_description=_SCOPES[request.intent_type],
            roles=roles,
            node_count=len(matrix.nodes),
        )
    except IntentPlanningError:
        raise
    except Exception as exc:
        raise IntentPlanningError("advisor intent plan was refused") from exc


__all__ = [
    "AdvisorIntentRequest",
    "AdvisorPlanResponse",
    "IntentPlanningError",
    "InvestmentIntentType",
    "build_intent_plan",
]
