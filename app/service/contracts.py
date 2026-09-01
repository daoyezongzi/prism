"""Strict request and result contracts for the fixture Advisor query use case."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Self

from pydantic import StringConstraints, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr
from app.gates import GateStatus
from app.portfolio import PortfolioImportBundle
from app.profile import RiskQuestionnaire
from app.recommendation import RecommendationCompositionResult


QueryIdentifier = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9_.:/-]*$",
    ),
]


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


class AdvisorQueryRequest(ContractModel):
    """A structured, replayable request; no natural-language advice input."""

    schema_version: Literal["advisor-query.v1"] = "advisor-query.v1"
    query_id: QueryIdentifier
    fixture_id: QueryIdentifier
    generated_at: datetime
    questionnaire: RiskQuestionnaire
    portfolio: PortfolioImportBundle

    @model_validator(mode="after")
    def validate_query(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        if self.questionnaire.owner_id != self.portfolio.owner_id:
            raise ValueError("questionnaire and portfolio must share one owner")
        serialized = self.model_dump_json().casefold()
        if any(item in serialized for item in _SENSITIVE_SUBSTRINGS):
            raise ValueError("advisor query must not contain sensitive fields")
        return self


class AdvisorQueryOutput(ContractModel):
    """Safe service output bound to the submitted query and composed result."""

    schema_version: Literal["advisor-query-output.v1"] = "advisor-query-output.v1"
    query_id: QueryIdentifier
    owner_id: NonEmptyStr
    profile_id: NonEmptyStr
    research_run_id: NonEmptyStr
    status: GateStatus
    result: RecommendationCompositionResult

    @model_validator(mode="after")
    def validate_output(self) -> Self:
        if self.owner_id != self.result.owner_id:
            raise ValueError("query output owner does not match result")
        if self.status != self.result.status:
            raise ValueError("query output status does not match result")
        if self.result.decision_gate is not None:
            if self.result.decision_gate.profile_id != self.profile_id:
                raise ValueError("query gate profile does not match output profile")
            if self.result.decision_gate.owner_id != self.owner_id:
                raise ValueError("query gate owner does not match output owner")
            if self.result.decision_gate.research_run_id != self.research_run_id:
                raise ValueError("query gate run does not match output run")
        if self.result.receipt is not None:
            if self.result.receipt.profile_id != self.profile_id:
                raise ValueError("query receipt profile does not match output profile")
            if self.result.receipt.research_run_id != self.research_run_id:
                raise ValueError("query receipt run does not match output run")
        return self


__all__ = ["AdvisorQueryOutput", "AdvisorQueryRequest", "QueryIdentifier"]
