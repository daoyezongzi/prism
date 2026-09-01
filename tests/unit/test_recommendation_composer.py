from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.allocation import AllocationBandDimension, build_allocation_envelope
from app.contracts import (
    ActionType,
    ComplianceStatus,
    DecisionTrace,
    EvidenceQualityStatus,
)
from app.gates import GateStatus, evaluate_decision_gates
from app.gates.fingerprint import canonical_payload_signature
from app.portfolio import (
    AssetType,
    FundHoldingSnapshot,
    LookThroughHolding,
    Position,
    PositionSnapshot,
    PortfolioImportBundle,
    calculate_exposure,
)
from app.profile import RiskLevel
from app.recommendation import (
    DecisionReceipt,
    RecommendationCompositionResult,
    RecommendationIssueCode,
    compose_recommendations,
)
from app.risk import assess_risk_budget, calculate_concentration
from tests.recommendation_scenario import build_recommendation_case


def _compose(case):
    return compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=case.pipeline,
        candidate=case.candidate,
        decision_gate=case.decision_gate,
        generated_at=case.generated_at,
    )


def test_balanced_case_composes_asset_holds_and_closed_receipt() -> None:
    case = build_recommendation_case()
    result = _compose(case)

    assert result.status == GateStatus.PASS
    assert result.summary == case.candidate.statement
    assert result.decision_gate == case.decision_gate
    assert result.receipt is not None
    assert result.receipt.model_versions == ()
    assert len(result.trace.recommendations) == 4
    assert all(
        recommendation.action_type == ActionType.HOLD
        for recommendation in result.trace.recommendations
    )
    assert all(
        recommendation.compliance_status == ComplianceStatus.PASSED
        for recommendation in result.trace.recommendations
    )
    for recommendation, binding in zip(
        result.trace.recommendations,
        result.receipt.recommendation_bindings,
    ):
        assert binding.breach_ids == ()
        assert recommendation.asset_id == binding.target_id
        assert recommendation.allocation_range.minimum_pct == binding.current_weight_pct
        assert recommendation.allocation_range.maximum_pct == binding.current_weight_pct
        assert recommendation.rationale == case.candidate.rationale
        assert set(recommendation.finding_ids) == set(case.candidate.finding_ids)


def test_conservative_case_composes_only_breach_bound_reductions() -> None:
    case = build_recommendation_case(RiskLevel.CONSERVATIVE)
    result = _compose(case)

    assert case.decision_gate.risk_gate.remediation_required is True
    assert result.status == GateStatus.PASS
    assert result.receipt is not None
    assert len(result.trace.recommendations) == 4
    assert all(
        recommendation.action_type == ActionType.REDUCE
        for recommendation in result.trace.recommendations
    )
    bound_breaches = {
        breach_id
        for binding in result.receipt.recommendation_bindings
        for breach_id in binding.breach_ids
    }
    assert bound_breaches == set(
        case.decision_gate.risk_gate.remediation_breach_ids
    )
    for recommendation, binding in zip(
        result.trace.recommendations,
        result.receipt.recommendation_bindings,
    ):
        assert binding.breach_ids
        assert binding.current_weight_pct == Decimal("25.00")
        assert binding.allowed_max_weight_pct == Decimal("20")
        assert recommendation.allocation_range.minimum_pct == Decimal("0")
        assert recommendation.allocation_range.maximum_pct == Decimal("20")


def test_aggregate_breach_is_not_pseudomapped_to_a_security() -> None:
    case = build_recommendation_case(RiskLevel.CONSERVATIVE)
    as_of = datetime(2026, 8, 31, 16, 0, tzinfo=UTC)
    position = Position(
        position_id="aggregate-position-etf",
        owner_id=case.profile.owner_id,
        asset_id="aggregate-etf",
        asset_type=AssetType.ETF,
        asset_name="Synthetic aggregate ETF",
        quantity=Decimal("1"),
        market_value=Decimal("1000"),
        currency="CNY",
        as_of=as_of,
        source="synthetic-aggregate",
    )
    holdings = tuple(
        LookThroughHolding(
            holding_id=f"aggregate-holding-{index}",
            parent_asset_id=position.asset_id,
            underlying_asset_id=f"aggregate-stock-{index}",
            underlying_name=f"Synthetic aggregate stock {index}",
            asset_type=AssetType.STOCK,
            weight_pct=Decimal("10"),
            sector="Technology" if index < 4 else "Healthcare",
            as_of=as_of,
            source="synthetic-aggregate",
        )
        for index in range(10)
    )
    portfolio = PortfolioImportBundle(
        bundle_id="aggregate-bundle",
        owner_id=case.profile.owner_id,
        created_at=case.profile.created_at,
        position_snapshot=PositionSnapshot(
            snapshot_id="aggregate-position-snapshot",
            owner_id=case.profile.owner_id,
            as_of=as_of,
            base_currency="CNY",
            source="synthetic-aggregate",
            positions=(position,),
        ),
        fund_holdings=(
            FundHoldingSnapshot(
                snapshot_id="aggregate-fund-snapshot",
                owner_id=case.profile.owner_id,
                parent_asset_id=position.asset_id,
                parent_asset_type=AssetType.ETF,
                as_of=as_of,
                source="synthetic-aggregate",
                coverage_pct=Decimal("100"),
                holdings=holdings,
            ),
        ),
    )
    exposure = calculate_exposure(portfolio)
    concentration = calculate_concentration(exposure)
    assessment = assess_risk_budget(case.profile, concentration)
    allocation = build_allocation_envelope(
        case.profile, exposure, concentration, assessment
    )
    gate = evaluate_decision_gates(
        case.profile, case.pipeline, assessment, allocation, case.candidate
    )
    assert gate.status == GateStatus.PASS
    assert gate.risk_gate.remediation_required is True
    result = compose_recommendations(
        profile=case.profile,
        portfolio=portfolio,
        exposure=exposure,
        concentration=concentration,
        assessment=assessment,
        allocation=allocation,
        pipeline=case.pipeline,
        candidate=case.candidate,
        decision_gate=gate,
        generated_at=case.generated_at,
    )
    assert result.status == GateStatus.BLOCKED
    assert result.issues[0].code == RecommendationIssueCode.AGGREGATE_BREACH_UNMAPPED
    assert result.trace == DecisionTrace() and result.receipt is None


def test_same_portfolio_and_evidence_change_materially_with_profile() -> None:
    balanced = _compose(build_recommendation_case(RiskLevel.BALANCED))
    conservative = _compose(build_recommendation_case(RiskLevel.CONSERVATIVE))

    assert {item.action_type for item in balanced.trace.recommendations} == {
        ActionType.HOLD
    }
    assert {item.action_type for item in conservative.trace.recommendations} == {
        ActionType.REDUCE
    }
    assert balanced.receipt is not None and conservative.receipt is not None
    assert balanced.receipt.profile_id != conservative.receipt.profile_id
    assert balanced.receipt.content_hash != conservative.receipt.content_hash


def test_partial_risk_gate_preserves_review_without_candidate_prose() -> None:
    case = build_recommendation_case()
    fund_snapshot = case.portfolio.fund_holdings[0].model_copy(
        update={"coverage_pct": Decimal("80")}
    )
    portfolio = case.portfolio.model_copy(
        update={"fund_holdings": (fund_snapshot,)}
    )
    exposure = calculate_exposure(portfolio)
    concentration = calculate_concentration(exposure)
    assessment = assess_risk_budget(case.profile, concentration)
    allocation = build_allocation_envelope(
        case.profile, exposure, concentration, assessment
    )
    gate = evaluate_decision_gates(
        case.profile, case.pipeline, assessment, allocation, case.candidate
    )
    result = compose_recommendations(
        profile=case.profile,
        portfolio=portfolio,
        exposure=exposure,
        concentration=concentration,
        assessment=assessment,
        allocation=allocation,
        pipeline=case.pipeline,
        candidate=case.candidate,
        decision_gate=gate,
        generated_at=case.generated_at,
    )

    assert gate.status == GateStatus.REVIEW_REQUIRED
    assert result.status == GateStatus.REVIEW_REQUIRED
    assert result.trace == DecisionTrace()
    assert result.receipt is None and result.summary is None
    serialized = result.model_dump_json()
    assert case.candidate.statement not in serialized
    assert case.candidate.rationale not in serialized


def test_blocked_compliance_gate_never_echoes_or_composes_promise() -> None:
    case = build_recommendation_case()
    promise = "保证收益率达到20%"
    candidate = case.candidate.model_copy(update={"statement": promise})
    gate = evaluate_decision_gates(
        case.profile,
        case.pipeline,
        case.assessment,
        case.allocation,
        candidate,
    )
    result = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=case.pipeline,
        candidate=candidate,
        decision_gate=gate,
        generated_at=case.generated_at,
    )

    assert gate.status == GateStatus.BLOCKED
    assert result.status == GateStatus.BLOCKED
    assert result.trace == DecisionTrace() and result.receipt is None
    assert promise not in result.model_dump_json()


def test_candidate_change_makes_previously_passed_gate_stale() -> None:
    case = build_recommendation_case()
    changed = case.candidate.model_copy(
        update={"rationale": "同一候选 ID 下已经改变的理由。"}
    )
    result = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=case.pipeline,
        candidate=changed,
        decision_gate=case.decision_gate,
        generated_at=case.generated_at,
    )

    assert result.status == GateStatus.BLOCKED
    assert result.issues[0].code == RecommendationIssueCode.STALE_GATE
    assert result.receipt is None and result.summary is None
    assert changed.rationale not in result.model_dump_json()


def test_non_verified_trace_cannot_reuse_a_passed_gate() -> None:
    case = build_recommendation_case()
    stale_evidence = case.pipeline.trace.evidence[0].model_copy(
        update={
            "quality_status": EvidenceQualityStatus.STALE,
            "quality_note": "source freshness window expired",
        }
    )
    trace = case.pipeline.trace.model_copy(
        update={
            "evidence": (stale_evidence,) + case.pipeline.trace.evidence[1:]
        }
    )
    pipeline = case.pipeline.model_copy(update={"trace": trace})
    result = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=pipeline,
        candidate=case.candidate,
        decision_gate=case.decision_gate,
        generated_at=case.generated_at,
    )

    assert result.status == GateStatus.BLOCKED
    assert result.issues[0].code == RecommendationIssueCode.STALE_GATE
    assert result.trace == DecisionTrace() and result.receipt is None


def test_forged_extra_remediation_breach_cannot_reuse_a_passed_gate() -> None:
    case = build_recommendation_case(RiskLevel.CONSERVATIVE)
    forged_risk_gate = case.decision_gate.risk_gate.model_copy(
        update={"remediation_breach_ids": case.decision_gate.risk_gate.remediation_breach_ids + ("forged-breach",)}
    )
    forged_gate = case.decision_gate.model_copy(update={"risk_gate": forged_risk_gate})
    result = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=case.pipeline,
        candidate=case.candidate,
        decision_gate=forged_gate,
        generated_at=case.generated_at,
    )

    assert result.status == GateStatus.BLOCKED
    assert result.issues[0].code == RecommendationIssueCode.STALE_GATE
    assert result.trace == DecisionTrace() and result.receipt is None


def test_owner_and_portfolio_identity_tampering_are_blocked() -> None:
    case = build_recommendation_case()
    foreign_candidate = case.candidate.model_copy(update={"owner_id": "foreign-owner"})
    owner_result = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=case.pipeline,
        candidate=foreign_candidate,
        decision_gate=case.decision_gate,
        generated_at=case.generated_at,
    )
    assert owner_result.status == GateStatus.BLOCKED
    assert owner_result.issues[0].code == RecommendationIssueCode.OWNER_MISMATCH

    assert case.exposure.report is not None
    report = case.exposure.report.model_copy(update={"bundle_id": "foreign-bundle"})
    exposure = case.exposure.model_copy(
        update={"bundle_id": "foreign-bundle", "report": report}
    )
    portfolio_result = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=case.pipeline,
        candidate=case.candidate,
        decision_gate=case.decision_gate,
        generated_at=case.generated_at,
    )
    assert portfolio_result.status == GateStatus.BLOCKED
    assert (
        portfolio_result.issues[0].code
        == RecommendationIssueCode.PORTFOLIO_MISMATCH
    )


def test_receipt_hash_rejects_material_tampering_but_ignores_id_order() -> None:
    result = _compose(build_recommendation_case())
    assert result.receipt is not None
    receipt = result.receipt

    payload = receipt.model_dump(mode="python")
    payload["generated_at"] = receipt.generated_at + timedelta(seconds=1)
    with pytest.raises(ValidationError, match="content_hash"):
        DecisionReceipt.model_validate(payload)

    payload = receipt.model_dump(mode="python")
    payload["content_hash"] = "0" * 64
    with pytest.raises(ValidationError, match="content_hash"):
        DecisionReceipt.model_validate(payload)

    reordered = receipt.model_dump(mode="python")
    reordered["evidence_ids"] = tuple(reversed(receipt.evidence_ids))
    rebuilt = DecisionReceipt.model_validate(reordered)
    assert rebuilt.content_hash == receipt.content_hash


def test_trace_or_binding_tampering_breaks_composition_validation() -> None:
    result = _compose(build_recommendation_case(RiskLevel.CONSERVATIVE))
    assert result.receipt is not None
    recommendation = result.trace.recommendations[0].model_copy(
        update={"rationale": "changed after receipt"}
    )
    trace = result.trace.model_copy(
        update={
            "recommendations": (recommendation,)
            + result.trace.recommendations[1:]
        }
    )
    payload = result.model_dump(mode="python")
    payload["trace"] = trace
    with pytest.raises(ValidationError, match="hash|recommendation_id"):
        RecommendationCompositionResult.model_validate(payload)

    binding = result.receipt.recommendation_bindings[0].model_copy(
        update={"target_max_weight_pct": Decimal("19")}
    )
    receipt = result.receipt.model_copy(
        update={
            "recommendation_bindings": (binding,)
            + result.receipt.recommendation_bindings[1:]
        }
    )
    payload = result.model_dump(mode="python")
    payload["receipt"] = receipt
    with pytest.raises(ValidationError):
        RecommendationCompositionResult.model_validate(payload)


def test_receipt_gate_identity_and_asset_dimension_are_closed() -> None:
    result = _compose(build_recommendation_case(RiskLevel.CONSERVATIVE))
    assert result.receipt is not None

    forged_binding = result.receipt.recommendation_bindings[0].model_copy(
        update={"dimension": AllocationBandDimension.SECTOR}
    )
    forged_receipt = result.receipt.model_copy(
        update={
            "recommendation_bindings": (
                forged_binding,
                *result.receipt.recommendation_bindings[1:],
            ),
            "candidate_id": "forged-candidate",
            "content_hash": "0" * 64,
        }
    )
    unsigned = forged_receipt.model_dump(mode="json", exclude={"content_hash"})
    forged_receipt = forged_receipt.model_copy(
        update={"content_hash": canonical_payload_signature(unsigned)}
    )
    forged_receipt = DecisionReceipt.model_validate(forged_receipt)

    with pytest.raises(ValidationError, match="candidate|ASSET"):
        RecommendationCompositionResult.model_validate(
            result.model_copy(update={"receipt": forged_receipt})
        )


def test_collection_reordering_does_not_change_composed_result() -> None:
    case = build_recommendation_case()
    first = _compose(case)
    assert case.allocation.envelope is not None

    trace = case.pipeline.trace.model_copy(
        update={"evidence": tuple(reversed(case.pipeline.trace.evidence))}
    )
    pipeline = case.pipeline.model_copy(update={"trace": trace})
    envelope = case.allocation.envelope.model_copy(
        update={
            "bands": tuple(reversed(case.allocation.envelope.bands)),
            "impacts": tuple(reversed(case.allocation.envelope.impacts)),
        }
    )
    allocation = case.allocation.model_copy(update={"envelope": envelope})
    gate = evaluate_decision_gates(
        case.profile, pipeline, case.assessment, allocation, case.candidate
    )
    second = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=allocation,
        pipeline=pipeline,
        candidate=case.candidate,
        decision_gate=gate,
        generated_at=case.generated_at,
    )

    assert second == first


def test_repeated_composition_is_deterministic_and_inputs_are_immutable() -> None:
    case = build_recommendation_case(RiskLevel.CONSERVATIVE)
    inputs = (
        case.profile,
        case.portfolio,
        case.exposure,
        case.concentration,
        case.assessment,
        case.allocation,
        case.pipeline,
        case.candidate,
        case.decision_gate,
    )
    before = tuple(item.model_dump_json() for item in inputs)
    results = tuple(_compose(case) for _ in range(100))
    assert all(result == results[0] for result in results)
    assert before == tuple(item.model_dump_json() for item in inputs)


def test_naive_generation_time_is_safely_blocked() -> None:
    case = build_recommendation_case()
    result = compose_recommendations(
        profile=case.profile,
        portfolio=case.portfolio,
        exposure=case.exposure,
        concentration=case.concentration,
        assessment=case.assessment,
        allocation=case.allocation,
        pipeline=case.pipeline,
        candidate=case.candidate,
        decision_gate=case.decision_gate,
        generated_at=case.generated_at.replace(tzinfo=None),
    )
    assert result.status == GateStatus.BLOCKED
    assert result.issues[0].code == RecommendationIssueCode.INVALID_INPUT
    assert result.receipt is None


def test_wrong_type_inputs_are_safely_blocked() -> None:
    result = compose_recommendations(
        profile=None,
        portfolio=None,
        exposure=None,
        concentration=None,
        assessment=None,
        allocation=None,
        pipeline=None,
        candidate=None,
        decision_gate=None,
        generated_at=None,
    )
    assert result.status == GateStatus.BLOCKED
    assert result.owner_id == "unknown-owner"
    assert result.issues[0].code == RecommendationIssueCode.INVALID_INPUT
