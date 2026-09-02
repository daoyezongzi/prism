"""Contracts for advanced decision explainability and causal attribution."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, model_validator

from app.contracts import ActionType, AllocationRange
from app.contracts.evidence import ContractModel, NonEmptyStr
from app.gates import GateStatus


class CausalNodeType(StrEnum):
    PROFILE_CONSTRAINT = "PROFILE_CONSTRAINT"
    MARKET_FACT = "MARKET_FACT"
    RESEARCH_FINDING = "RESEARCH_FINDING"
    RISK_ASSESSMENT = "RISK_ASSESSMENT"
    COMPLIANCE_RULE = "COMPLIANCE_RULE"
    RECOMMENDATION = "RECOMMENDATION"


class CausalNode(ContractModel):
    """A node in the decision causal DAG."""

    node_id: NonEmptyStr
    node_type: CausalNodeType
    label: NonEmptyStr
    value_summary: NonEmptyStr
    status: GateStatus
    influence_weight_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))


class CausalEdge(ContractModel):
    """Directed connection in the causal graph."""

    from_node_id: NonEmptyStr
    to_node_id: NonEmptyStr
    relationship: NonEmptyStr


class KeyDecisionDriver(ContractModel):
    """Ranked primary driver influencing the final decision."""

    driver_name: NonEmptyStr
    category: NonEmptyStr
    contribution_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    evidence_reference: NonEmptyStr
    explanation: NonEmptyStr


class CounterfactualCondition(ContractModel):
    """What-If condition under which the recommendation would change."""

    scenario_name: NonEmptyStr
    condition_change: NonEmptyStr
    expected_action_change: NonEmptyStr
    rationale: NonEmptyStr


class InvalidationTrigger(ContractModel):
    """Explicit condition that invalidates the recommendation."""

    trigger_id: NonEmptyStr
    trigger_type: NonEmptyStr
    description: NonEmptyStr
    threshold_or_event: NonEmptyStr


class AdvancedExplainabilityRequest(ContractModel):
    """Request to generate full causal explainability report."""

    schema_version: Literal["advanced-explainability-request.v1"] = "advanced-explainability-request.v1"
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    risk_score: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    risk_level: NonEmptyStr
    action_type: ActionType
    asset: NonEmptyStr
    tech_exposure_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    tech_cap_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    top_asset_weight_pct: Decimal = Field(ge=Decimal("0"), le=Decimal("100"))
    finding_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_request(self) -> Self:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return self


class AdvancedExplainabilityResponse(ContractModel):
    """Comprehensive causal attribution and counterfactual response."""

    schema_version: Literal["advanced-explainability-response.v1"] = "advanced-explainability-response.v1"
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    generated_at: datetime
    decision_summary: NonEmptyStr
    causal_nodes: tuple[CausalNode, ...]
    causal_edges: tuple[CausalEdge, ...]
    key_drivers: tuple[KeyDecisionDriver, ...]
    counterfactuals: tuple[CounterfactualCondition, ...]
    invalidation_triggers: tuple[InvalidationTrigger, ...]
