"""Contracts for evaluation dashboard aggregation and reporting."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import ContractModel, NonEmptyStr


class EvaluationDashboardSummary(ContractModel):
    """Aggregated evaluation score summary percentages."""

    case_pass_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    profile_alignment_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    evidence_coverage_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    hallucination_rate_pct: Decimal = Field(default=Decimal("0.00"), ge=Decimal("0"), le=Decimal("100"))
    risk_detection_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    compliance_pass_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    semantic_consistency_rate_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))


class EvaluationDashboardLatency(ContractModel):
    """Latency distribution measurements."""

    p50_ms: Decimal = Field(ge=Decimal("0"))
    p95_ms: Decimal = Field(ge=Decimal("0"))


class EvaluationDashboardCaseItem(ContractModel):
    """Per-case evaluation execution status."""

    case_id: NonEmptyStr
    title: NonEmptyStr
    expected_status: NonEmptyStr
    actual_status: NonEmptyStr
    passed: bool
    latency_ms: Decimal = Field(ge=Decimal("0"))
    error_code: str | None = None


class EvaluationDashboardRequest(ContractModel):
    """Request to execute evaluation suite and compile dashboard."""

    schema_version: Literal["evaluation-dashboard-request.v1"] = "evaluation-dashboard-request.v1"
    request_id: NonEmptyStr
    operator_id: NonEmptyStr
    generated_at: datetime
    selected_cases: tuple[str, ...] = ()
    repeat_count: int = Field(default=1, ge=1, le=10)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return self


class EvaluationDashboardResponse(ContractModel):
    """Consolidated evaluation dashboard response."""

    schema_version: Literal["evaluation-dashboard-response.v1"] = "evaluation-dashboard-response.v1"
    request_id: NonEmptyStr
    operator_id: NonEmptyStr
    generated_at: datetime
    total_cases: int = Field(ge=0)
    passed_cases: int = Field(ge=0)
    summary: EvaluationDashboardSummary
    latency: EvaluationDashboardLatency
    cases: tuple[EvaluationDashboardCaseItem, ...]

    @model_validator(mode="after")
    def validate_response(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        if self.passed_cases > self.total_cases:
            raise ValueError("passed_cases cannot exceed total_cases")
        return self
