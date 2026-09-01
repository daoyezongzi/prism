from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.contracts.evidence import (
    ActionType,
    AllocationRange,
    ComplianceStatus,
    DecisionTrace,
    Evidence,
    EvidenceQualityStatus,
    Fact,
    FactStatus,
    Finding,
    FindingSeverity,
    Recommendation,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def verified_evidence(**overrides: object) -> Evidence:
    values: dict[str, object] = {
        "evidence_id": "ev:fund:technology_weight:2026-06-30",
        "provider": "fixture",
        "source": "fund-holdings",
        "field": "technology_weight_pct",
        "value": 63.5,
        "unit": "pct",
        "period": "2026-06-30",
        "retrieved_at": NOW,
        "quality_status": EvidenceQualityStatus.VERIFIED,
    }
    values.update(overrides)
    return Evidence.model_validate(values)


def verified_fact(**overrides: object) -> Fact:
    values: dict[str, object] = {
        "fact_id": "fact:portfolio:technology_weight:2026-06-30",
        "subject": "portfolio:user-1",
        "metric": "technology_weight_pct",
        "value": 63.5,
        "unit": "pct",
        "period": "2026-06-30",
        "status": FactStatus.VERIFIED,
        "evidence_ids": ("ev:fund:technology_weight:2026-06-30",),
    }
    values.update(overrides)
    return Fact.model_validate(values)


def concentration_finding(**overrides: object) -> Finding:
    values: dict[str, object] = {
        "finding_id": "finding:portfolio:technology_concentration",
        "kind": "CONCENTRATION_RISK",
        "severity": FindingSeverity.WARNING,
        "statement": "科技资产暴露高于当前画像的集中度上限。",
        "fact_ids": ("fact:portfolio:technology_weight:2026-06-30",),
        "confidence": 0.93,
        "methodology": "deterministic concentration rule v1",
    }
    values.update(overrides)
    return Finding.model_validate(values)


def reduce_recommendation(**overrides: object) -> Recommendation:
    values: dict[str, object] = {
        "recommendation_id": "rec:portfolio:reduce-technology",
        "action_type": ActionType.REDUCE,
        "asset_id": "portfolio:technology-exposure",
        "allocation_range": AllocationRange(
            minimum_pct=Decimal("35"),
            maximum_pct=Decimal("45"),
        ),
        "rationale": "将科技暴露降至当前画像允许的区间。",
        "finding_ids": ("finding:portfolio:technology_concentration",),
        "compliance_status": ComplianceStatus.PASSED,
        "invalidation_conditions": ("用户确认提高风险承受能力",),
    }
    values.update(overrides)
    return Recommendation.model_validate(values)


def test_accepts_a_closed_verified_decision_chain() -> None:
    trace = DecisionTrace(
        evidence=(verified_evidence(),),
        facts=(verified_fact(),),
        findings=(concentration_finding(),),
        recommendations=(reduce_recommendation(),),
    )

    assert trace.recommendations[0].compliance_status == ComplianceStatus.PASSED


def test_verified_fact_requires_registered_evidence() -> None:
    with pytest.raises(ValidationError, match="at least one evidence_id"):
        verified_fact(evidence_ids=())


def test_missing_fact_remains_missing_and_requires_a_reason() -> None:
    with pytest.raises(ValidationError, match="must not carry a value"):
        Fact(
            fact_id="fact:missing",
            subject="portfolio:user-1",
            metric="unknown_metric",
            value=0,
            status=FactStatus.UNAVAILABLE,
            reason="provider timeout",
        )

    missing = Fact(
        fact_id="fact:missing",
        subject="portfolio:user-1",
        metric="unknown_metric",
        status=FactStatus.UNAVAILABLE,
        reason="provider timeout",
    )
    assert missing.value is None


def test_rejects_dangling_references() -> None:
    with pytest.raises(ValidationError, match="unknown evidence"):
        DecisionTrace(
            facts=(verified_fact(),),
        )


def test_actionable_recommendation_cannot_depend_on_missing_fact() -> None:
    missing = Fact(
        fact_id="fact:portfolio:technology_weight:2026-06-30",
        subject="portfolio:user-1",
        metric="technology_weight_pct",
        status=FactStatus.UNAVAILABLE,
        reason="fund holdings unavailable",
    )

    with pytest.raises(ValidationError, match="non-VERIFIED facts"):
        DecisionTrace(
            facts=(missing,),
            findings=(concentration_finding(),),
            recommendations=(reduce_recommendation(),),
        )


def test_blocked_recommendation_can_explain_missing_evidence() -> None:
    missing = Fact(
        fact_id="fact:portfolio:technology_weight:2026-06-30",
        subject="portfolio:user-1",
        metric="technology_weight_pct",
        status=FactStatus.UNAVAILABLE,
        reason="fund holdings unavailable",
    )
    blocked = reduce_recommendation(
        action_type=ActionType.REVIEW,
        compliance_status=ComplianceStatus.BLOCKED,
        rationale="缺少基金持仓，不能计算可靠调整区间。",
        invalidation_conditions=("取得有效基金持仓快照",),
    )

    trace = DecisionTrace(
        facts=(missing,),
        findings=(concentration_finding(),),
        recommendations=(blocked,),
    )

    assert trace.recommendations[0].compliance_status == ComplianceStatus.BLOCKED


def test_passed_recommendation_rejects_stale_evidence() -> None:
    stale = verified_evidence(
        quality_status=EvidenceQualityStatus.STALE,
        quality_note="older than the configured fund-holdings freshness window",
    )

    with pytest.raises(ValidationError, match="non-VERIFIED evidence"):
        DecisionTrace(
            evidence=(stale,),
            facts=(verified_fact(),),
            findings=(concentration_finding(),),
            recommendations=(reduce_recommendation(),),
        )


def test_review_required_can_surface_stale_but_matching_evidence() -> None:
    stale = verified_evidence(
        quality_status=EvidenceQualityStatus.STALE,
        quality_note="older than the configured fund-holdings freshness window",
    )
    review = reduce_recommendation(
        compliance_status=ComplianceStatus.REVIEW_REQUIRED,
        invalidation_conditions=("取得更新的基金持仓快照",),
    )

    trace = DecisionTrace(
        evidence=(stale,),
        facts=(verified_fact(),),
        findings=(concentration_finding(),),
        recommendations=(review,),
    )

    assert trace.recommendations[0].compliance_status == ComplianceStatus.REVIEW_REQUIRED
