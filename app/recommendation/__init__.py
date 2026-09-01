"""Deterministic Recommendation composition and Decision Receipts."""

from app.recommendation.composer import (
    compose_recommendation_receipt,
    compose_recommendations,
)
from app.recommendation.contracts import (
    REQUIRED_RULE_VERSIONS,
    DecisionReceipt,
    GenerationMode,
    RecommendationBinding,
    RecommendationCompositionResult,
    RecommendationIssue,
    RecommendationIssueCode,
    RuleVersion,
    recommendation_content_id,
)
from app.recommendation.receipt import build_decision_receipt

__all__ = [
    "REQUIRED_RULE_VERSIONS",
    "DecisionReceipt",
    "GenerationMode",
    "RecommendationBinding",
    "RecommendationCompositionResult",
    "RecommendationIssue",
    "RecommendationIssueCode",
    "RuleVersion",
    "build_decision_receipt",
    "compose_recommendation_receipt",
    "compose_recommendations",
    "recommendation_content_id",
]
