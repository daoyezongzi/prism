"""Structured research node contracts and lineage-aware cross-validation."""

from app.research.contracts import (
    CrossValidationResult,
    ResearchNodeIssue,
    ResearchNodeIssueCode,
    ResearchNodeKind,
    ResearchNodeResult,
    ResearchNodeStatus,
    ResearchObservation,
    ValidationClaim,
    ValidationIssue,
    ValidationIssueCode,
    ValidationStatus,
)
from app.research.cross_validation import validate_claim, validate_node_claim

__all__ = [
    "CrossValidationResult",
    "ResearchNodeIssue",
    "ResearchNodeIssueCode",
    "ResearchNodeKind",
    "ResearchNodeResult",
    "ResearchNodeStatus",
    "ResearchObservation",
    "ValidationClaim",
    "ValidationIssue",
    "ValidationIssueCode",
    "ValidationStatus",
    "validate_claim",
    "validate_node_claim",
]
