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
from app.research.evidence_bridge import (
    EvidenceBridgeIssue,
    EvidenceBridgeIssueCode,
    EvidenceBridgeStatus,
    EvidenceFindingBridgeResult,
    bridge_cross_validation,
    build_evidence_grounded_finding,
)

_PIPELINE_EXPORTS = {
    "ResearchClaimSpec",
    "ResearchEvidencePipelineResult",
    "ResearchPipelineIssue",
    "ResearchPipelineIssueCode",
    "ResearchPipelineStatus",
    "build_research_evidence_pipeline",
    "evaluate_research_run",
}


def __getattr__(name: str):
    """Lazily expose the orchestration-dependent pipeline without import cycles."""

    if name in _PIPELINE_EXPORTS:
        from app.research import pipeline

        return getattr(pipeline, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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
    "EvidenceBridgeIssue",
    "EvidenceBridgeIssueCode",
    "EvidenceBridgeStatus",
    "EvidenceFindingBridgeResult",
    "bridge_cross_validation",
    "build_evidence_grounded_finding",
    *sorted(_PIPELINE_EXPORTS),
]
