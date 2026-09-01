from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.contracts.evidence import EvidenceQualityStatus
from app.research import (
    CrossValidationResult,
    ResearchNodeIssue,
    ResearchNodeIssueCode,
    ResearchNodeKind,
    ResearchNodeResult,
    ResearchNodeStatus,
    ResearchObservation,
    ValidationClaim,
    ValidationIssueCode,
    ValidationStatus,
    validate_claim,
    validate_node_claim,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OWNER = "research-owner-001"


def claim(
    *,
    expected: str = "10.00",
    owner_id: str = OWNER,
    unit: str = "CNY",
    period: str = "2026-Q2",
) -> ValidationClaim:
    return ValidationClaim(
        claim_id="claim-revenue-001",
        owner_id=owner_id,
        subject="STOCK_RESEARCH_001",
        metric="revenue",
        unit=unit,
        period=period,
        expected_value=Decimal(expected),
    )


def observation(
    evidence_id: str,
    value: str,
    lineage_id: str | None,
    *,
    quality: EvidenceQualityStatus = EvidenceQualityStatus.VERIFIED,
    owner_id: str = OWNER,
    subject: str = "STOCK_RESEARCH_001",
    metric: str = "revenue",
    unit: str = "CNY",
    period: str = "2026-Q2",
) -> ResearchObservation:
    return ResearchObservation(
        observation_id=f"observation-{evidence_id}",
        owner_id=owner_id,
        evidence_id=evidence_id,
        subject=subject,
        metric=metric,
        value=Decimal(value),
        unit=unit,
        period=period,
        provider="synthetic-provider",
        source=f"synthetic-source-{evidence_id}",
        lineage_id=lineage_id,
        quality_status=quality,
        observed_at=NOW,
        retrieved_at=NOW,
    )


def node(
    status: ResearchNodeStatus,
    observations: tuple[ResearchObservation, ...] = (),
    *,
    missing_fields: tuple[str, ...] = (),
    issues: tuple[ResearchNodeIssue, ...] = (),
    scope_description: str | None = None,
) -> ResearchNodeResult:
    return ResearchNodeResult(
        request_id="research-request-001",
        node_id="research-node-001",
        owner_id=OWNER,
        node_kind=ResearchNodeKind.STOCK,
        subject="STOCK_RESEARCH_001",
        completed_at=NOW,
        status=status,
        observations=observations,
        missing_fields=missing_fields,
        issues=issues,
        scope_description=scope_description,
    )


def test_research_node_four_states_have_explicit_invariants() -> None:
    verified = observation("e-complete", "10", "lineage-complete")
    assert node(ResearchNodeStatus.COMPLETE, (verified,)).status == ResearchNodeStatus.COMPLETE
    assert node(
        ResearchNodeStatus.PARTIAL,
        (verified,),
        missing_fields=("gross_margin",),
    ).status == ResearchNodeStatus.PARTIAL
    assert node(
        ResearchNodeStatus.EMPTY,
        scope_description="no listed stock matched the requested scope",
    ).status == ResearchNodeStatus.EMPTY
    assert node(
        ResearchNodeStatus.FAILED,
        issues=(
            ResearchNodeIssue(
                code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                safe_message="synthetic source unavailable",
            ),
        ),
    ).status == ResearchNodeStatus.FAILED


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": ResearchNodeStatus.COMPLETE},
        {
            "status": ResearchNodeStatus.EMPTY,
            "observations": (observation("e-empty-invalid", "1", "l"),),
            "scope_description": "invalid",
        },
        {
            "status": ResearchNodeStatus.FAILED,
            "observations": (observation("e-failed-invalid", "1", "l"),),
            "issues": (
                ResearchNodeIssue(
                    code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                    safe_message="source failed",
                ),
            ),
        },
    ],
)
def test_research_node_invalid_state_combinations_are_rejected(kwargs) -> None:
    with pytest.raises(ValidationError):
        node(**kwargs)


def test_duplicate_observation_or_evidence_ids_are_rejected() -> None:
    first = observation("e-duplicate", "10", "lineage-a")
    with pytest.raises(ValidationError, match="duplicate observation_id"):
        node(ResearchNodeStatus.COMPLETE, (first, first.model_copy(update={"evidence_id": "e-other"})))
    with pytest.raises(ValidationError, match="duplicate evidence_id"):
        node(ResearchNodeStatus.COMPLETE, (first, first.model_copy(update={"observation_id": "observation-other"})))


def test_two_distinct_lineages_support_a_claim() -> None:
    result = validate_claim(
        claim(),
        (
            observation("e-b", "10", "lineage-b"),
            observation("e-a", "10", "lineage-a"),
        ),
    )
    assert result.status == ValidationStatus.SUPPORTED
    assert result.independent_lineage_count == 2
    assert result.confidence == Decimal("1.00")
    assert result.supporting_evidence_ids == ("e-a", "e-b")


def test_same_lineage_duplicate_does_not_count_as_independent_support() -> None:
    result = validate_claim(
        claim(),
        (
            observation("e-copy-2", "10", "lineage-copy"),
            observation("e-copy-1", "10", "lineage-copy"),
        ),
    )
    assert result.status == ValidationStatus.INSUFFICIENT
    assert result.independent_lineage_count == 1
    assert result.duplicate_lineage_evidence_ids == ("e-copy-1", "e-copy-2")
    assert ValidationIssueCode.DUPLICATE_LINEAGE in {
        issue.code for issue in result.issues
    }


def test_two_distinct_lineages_contradict_a_claim() -> None:
    result = validate_claim(
        claim(),
        (
            observation("e-low-a", "9", "lineage-a"),
            observation("e-low-b", "8", "lineage-b"),
        ),
    )
    assert result.status == ValidationStatus.CONTRADICTED
    assert result.contradicting_evidence_ids == ("e-low-a", "e-low-b")
    assert result.confidence == Decimal("0.00")


def test_independent_support_and_contradiction_are_unresolved() -> None:
    result = validate_claim(
        claim(),
        (
            observation("e-support", "10", "lineage-support"),
            observation("e-contradict", "11", "lineage-contradict"),
        ),
    )
    assert result.status == ValidationStatus.UNRESOLVED
    assert result.confidence == Decimal("0.50")
    assert ValidationIssueCode.CONFLICTING_VALUES in {
        issue.code for issue in result.issues
    }


def test_non_verified_observation_cannot_become_a_support_vote() -> None:
    result = validate_claim(
        claim(),
        (
            observation("e-verified-a", "10", "lineage-a"),
            observation("e-verified-b", "10", "lineage-b"),
            observation(
                "e-stale",
                "10",
                "lineage-stale",
                quality=EvidenceQualityStatus.STALE,
            ),
        ),
    )
    assert result.status == ValidationStatus.UNRESOLVED
    assert "e-stale" in result.unresolved_evidence_ids
    assert ValidationIssueCode.NON_VERIFIED_EVIDENCE in {
        issue.code for issue in result.issues
    }


def test_scope_mismatch_and_same_lineage_conflict_are_auditable() -> None:
    result = validate_claim(
        claim(),
        (
            observation("e-period", "10", "lineage-period", period="2026-Q1"),
            observation("e-lineage-1", "10", "lineage-conflict"),
            observation("e-lineage-2", "11", "lineage-conflict"),
        ),
    )
    assert result.status == ValidationStatus.UNRESOLVED
    codes = {issue.code for issue in result.issues}
    assert ValidationIssueCode.SCOPE_MISMATCH in codes
    assert ValidationIssueCode.LINEAGE_CONFLICT in codes
    assert "e-period" in result.unresolved_evidence_ids


def test_unlinked_sources_are_insufficient_even_when_values_match() -> None:
    result = validate_claim(
        claim(),
        (observation("e-unlinked-a", "10", None), observation("e-unlinked-b", "10", None)),
    )
    assert result.status == ValidationStatus.INSUFFICIENT
    assert result.independent_lineage_count == 0
    assert result.unlinked_evidence_ids == ("e-unlinked-a", "e-unlinked-b")


def test_unlinked_contradiction_prevents_false_supported_result() -> None:
    result = validate_claim(
        claim(),
        (
            observation("e-independent-a", "10", "lineage-a"),
            observation("e-independent-b", "10", "lineage-b"),
            observation("e-unlinked-conflict", "12", None),
        ),
    )
    assert result.status == ValidationStatus.UNRESOLVED
    assert "e-unlinked-conflict" in result.contradicting_evidence_ids


def test_node_rejects_observation_for_a_different_subject() -> None:
    with pytest.raises(ValidationError, match="subject"):
        node(
            ResearchNodeStatus.COMPLETE,
            (observation("e-other-subject", "10", "lineage-other", subject="OTHER"),),
        )


def test_single_source_is_insufficient_and_no_observation_is_not_zero() -> None:
    one = validate_claim(claim(), (observation("e-one", "10", "lineage-one"),))
    none = validate_claim(claim(), ())
    assert one.status == ValidationStatus.INSUFFICIENT
    assert none.status == ValidationStatus.INSUFFICIENT
    assert none.supporting_evidence_ids == ()
    assert none.contradicting_evidence_ids == ()
    assert none.confidence == Decimal("0.00")


def test_order_changes_do_not_change_result_identity_or_confidence() -> None:
    observations = (
        observation("e-order-c", "10", "lineage-c"),
        observation("e-order-a", "10", "lineage-a"),
        observation("e-order-b", "10", "lineage-b"),
    )
    first = validate_claim(claim(), observations)
    second = validate_claim(claim(), tuple(reversed(observations)))
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_node_status_and_owner_are_preserved_by_node_validation() -> None:
    c = claim()
    partial = validate_node_claim(
        c,
        node(
            ResearchNodeStatus.PARTIAL,
            (observation("e-node-a", "10", "lineage-a"), observation("e-node-b", "10", "lineage-b")),
            missing_fields=("eps",),
        ),
    )
    assert partial.status == ValidationStatus.UNRESOLVED
    assert ValidationIssueCode.NODE_PARTIAL in {issue.code for issue in partial.issues}
    failed = validate_node_claim(
        c,
        node(
            ResearchNodeStatus.FAILED,
            issues=(
                ResearchNodeIssue(
                    code=ResearchNodeIssueCode.SOURCE_UNAVAILABLE,
                    safe_message="source unavailable",
                ),
            ),
        ),
    )
    assert failed.status == ValidationStatus.INSUFFICIENT
    assert ValidationIssueCode.NODE_UNAVAILABLE in {issue.code for issue in failed.issues}
    with pytest.raises(ValueError, match="owner_id"):
        validate_node_claim(claim(owner_id="different-owner"), node(ResearchNodeStatus.COMPLETE, (observation("e-owner", "10", "lineage-owner"),)))


def test_observation_and_validation_models_are_immutable_and_finite() -> None:
    obs = observation("e-immutable", "10", "lineage-immutable")
    with pytest.raises((TypeError, ValidationError)):
        obs.value = Decimal("11")
    with pytest.raises(ValidationError, match="finite"):
        observation("e-nan", "NaN", "lineage-nan")
    result = validate_claim(claim(), (observation("e-finite-a", "10", "lineage-a"), observation("e-finite-b", "10", "lineage-b")))
    payload = result.model_dump(mode="python")
    payload["recommendation"] = "not allowed"
    with pytest.raises(ValidationError):
        CrossValidationResult.model_validate(payload)
