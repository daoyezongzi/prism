from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.contracts import (
    DecisionTrace,
    Evidence,
    EvidenceQualityStatus,
    FindingSeverity,
)
from app.research import (
    EvidenceBridgeIssueCode,
    EvidenceBridgeStatus,
    EvidenceFindingBridgeResult,
    ResearchObservation,
    ValidationClaim,
    ValidationIssue,
    ValidationIssueCode,
    ValidationStatus,
    bridge_cross_validation,
    validate_claim,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OWNER = "bridge-owner-001"
SUBJECT = "BRIDGE_STOCK_001"


def _claim(*, expected: str = "10.00", owner_id: str = OWNER) -> ValidationClaim:
    return ValidationClaim(
        claim_id="bridge-claim-revenue-001",
        owner_id=owner_id,
        subject=SUBJECT,
        metric="revenue",
        unit="CNY",
        period="2026-Q2",
        expected_value=Decimal(expected),
    )


def _observation(
    evidence_id: str,
    value: str = "10.00",
    lineage_id: str | None = "lineage-a",
    *,
    owner_id: str = OWNER,
    subject: str = SUBJECT,
    metric: str = "revenue",
    unit: str = "CNY",
    period: str = "2026-Q2",
    quality: EvidenceQualityStatus = EvidenceQualityStatus.VERIFIED,
    provider: str | None = None,
    source: str | None = None,
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
        provider=provider or f"provider-{evidence_id}",
        source=source or f"source-{evidence_id}",
        lineage_id=lineage_id,
        quality_status=quality,
        observed_at=NOW,
        retrieved_at=NOW,
    )


def _evidence(
    observation: ResearchObservation,
    *,
    value: object = "10.00",
    field: str = "revenue",
    unit: str | None = "CNY",
    period: str | None = "2026-Q2",
    quality: EvidenceQualityStatus = EvidenceQualityStatus.VERIFIED,
    quality_note: str | None = None,
    lineage_id: str | None = None,
) -> Evidence:
    if quality != EvidenceQualityStatus.VERIFIED and quality_note is None:
        quality_note = "synthetic evidence requires review"
    return Evidence(
        evidence_id=observation.evidence_id,
        provider=observation.provider,
        source=observation.source,
        field=field,
        value=value,
        unit=unit,
        period=period,
        observed_at=observation.observed_at,
        retrieved_at=observation.retrieved_at,
        quality_status=quality,
        quality_note=quality_note,
        lineage_id=observation.lineage_id if lineage_id is None else lineage_id,
    )


def _valid_bundle():
    observations = (
        _observation("evidence-a", lineage_id="lineage-a"),
        _observation("evidence-b", lineage_id="lineage-b"),
    )
    evidence = tuple(_evidence(item) for item in observations)
    validation = validate_claim(_claim(), observations)
    return validation, evidence, observations


def _bridge(validation, evidence, observations, **overrides):
    values = {
        "finding_kind": "REVENUE_STABLE",
        "finding_severity": FindingSeverity.INFO,
        "statement": "两条独立来源对该报告期的收入数值一致。",
    }
    values.update(overrides)
    return bridge_cross_validation(validation, evidence, observations, **values)


def test_supported_claim_builds_stable_closed_fact_and_finding() -> None:
    validation, evidence, observations = _valid_bundle()
    first = _bridge(validation, evidence, observations)
    second = _bridge(validation, tuple(reversed(evidence)), tuple(reversed(observations)))

    assert first.status == EvidenceBridgeStatus.READY
    assert first.fact is not None
    assert first.fact.status.value == "VERIFIED"
    assert first.finding is not None
    assert first.finding.fact_ids == (first.fact.fact_id,)
    assert first.supporting_evidence_ids == ("evidence-a", "evidence-b")
    assert first.model_dump(mode="json") == second.model_dump(mode="json")

    trace = DecisionTrace(
        evidence=evidence,
        facts=(first.fact,),
        findings=(first.finding,),
    )
    assert trace.findings[0].fact_ids == (first.fact.fact_id,)


@pytest.mark.parametrize(
    ("values", "expected_status", "expected_issue"),
    [
        (("9.00", "9.00"), EvidenceBridgeStatus.REVIEW_REQUIRED, EvidenceBridgeIssueCode.VALIDATION_CONTRADICTED),
        (("10.00", "11.00"), EvidenceBridgeStatus.REVIEW_REQUIRED, EvidenceBridgeIssueCode.VALIDATION_UNRESOLVED),
        (("10.00",), EvidenceBridgeStatus.REVIEW_REQUIRED, EvidenceBridgeIssueCode.INSUFFICIENT_SOURCES),
    ],
)
def test_non_supported_validation_never_emits_fact(
    values: tuple[str, ...],
    expected_status: EvidenceBridgeStatus,
    expected_issue: EvidenceBridgeIssueCode,
) -> None:
    observations = tuple(
        _observation(
            f"evidence-{index}",
            value=value,
            lineage_id=f"lineage-{index}",
        )
        for index, value in enumerate(values)
    )
    validation = validate_claim(_claim(), observations)

    result = _bridge(validation, (), ())

    assert result.status == expected_status
    assert result.fact is None and result.finding is None
    assert result.issues[0].code == expected_issue


def test_missing_registered_evidence_is_blocked_with_safe_identifier() -> None:
    validation, evidence, observations = _valid_bundle()
    result = _bridge(validation, (evidence[0],), observations)

    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.UNKNOWN_EVIDENCE
    assert result.issues[0].evidence_ids == ("evidence-b",)
    assert "api_key" not in result.model_dump_json().lower()


def test_missing_observation_blocks_owner_lineage_closure() -> None:
    validation, evidence, observations = _valid_bundle()
    result = _bridge(validation, evidence, (observations[0],))

    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.MISSING_OBSERVATION


def test_stale_registered_evidence_cannot_support_a_verified_fact() -> None:
    validation, evidence, observations = _valid_bundle()
    stale = _evidence(
        observations[0],
        quality=EvidenceQualityStatus.STALE,
        quality_note="synthetic row is outside the freshness window",
    )
    result = _bridge(validation, (stale, evidence[1]), observations)

    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.NON_VERIFIED_EVIDENCE
    assert result.fact is None


@pytest.mark.parametrize(
    ("field", "unit", "period", "expected_issue"),
    [
        ("gross_profit", "CNY", "2026-Q2", EvidenceBridgeIssueCode.SCOPE_MISMATCH),
        ("revenue", "USD", "2026-Q2", EvidenceBridgeIssueCode.UNIT_MISMATCH),
        ("revenue", "CNY", "2026-Q1", EvidenceBridgeIssueCode.PERIOD_MISMATCH),
    ],
)
def test_evidence_scope_mismatch_is_blocked(
    field: str,
    unit: str,
    period: str,
    expected_issue: EvidenceBridgeIssueCode,
) -> None:
    validation, evidence, observations = _valid_bundle()
    changed = _evidence(evidence_observation := observations[0], field=field, unit=unit, period=period)
    result = _bridge(validation, (changed, evidence[1]), observations)

    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == expected_issue
    assert result.issues[0].evidence_ids == (evidence_observation.evidence_id,)


def test_value_and_provenance_mismatches_are_blocked() -> None:
    validation, evidence, observations = _valid_bundle()
    changed = _evidence(observations[0], value="10.01")
    result = _bridge(validation, (changed, evidence[1]), observations)
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.VALUE_MISMATCH

    changed_lineage = _evidence(observations[0], lineage_id="different-lineage")
    result = _bridge(validation, (changed_lineage, evidence[1]), observations)
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.PROVENANCE_MISMATCH

    changed_timestamp = _evidence(observations[0]).model_copy(
        update={"retrieved_at": datetime(2026, 9, 2, 12, 0, tzinfo=UTC)}
    )
    result = _bridge(validation, (changed_timestamp, evidence[1]), observations)
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.PROVENANCE_MISMATCH


def test_owner_mismatch_and_duplicate_registries_are_blocked() -> None:
    validation, evidence, observations = _valid_bundle()
    foreign = observations[0].model_copy(update={"owner_id": "other-owner"})
    result = _bridge(validation, evidence, (foreign, observations[1]))
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.OWNER_MISMATCH

    result = _bridge(validation, (evidence[0], evidence[0], evidence[1]), observations)
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.DUPLICATE_EVIDENCE

    result = _bridge(validation, evidence, (observations[0], observations[0], observations[1]))
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.DUPLICATE_OBSERVATION


def test_forged_supported_metadata_and_duplicate_lineage_do_not_pass() -> None:
    validation, evidence, observations = _valid_bundle()
    forged = validation.model_copy(
        update={
            "issues": (
                ValidationIssue(
                    code=ValidationIssueCode.SCOPE_MISMATCH,
                    safe_message="synthetic tampered metadata",
                ),
            )
        }
    )
    result = _bridge(forged, evidence, observations)
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.VALIDATION_ISSUES

    duplicate_observation = _observation("evidence-copy", lineage_id="lineage-a")
    duplicate_validation = validate_claim(
        _claim(),
        (observations[0], duplicate_observation, observations[1]),
    )
    duplicate_evidence = evidence + (_evidence(duplicate_observation),)
    result = _bridge(duplicate_validation, duplicate_evidence, observations + (duplicate_observation,))
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.VALIDATION_ISSUES


def test_sensitive_statement_is_rejected_without_serializing_raw_text() -> None:
    validation, evidence, observations = _valid_bundle()
    result = _bridge(validation, evidence, observations, statement="api_key=do-not-emit")

    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.SENSITIVE_INPUT
    serialized = result.model_dump_json().lower()
    assert "api_key" not in serialized
    assert "do-not-emit" not in serialized


def test_bridge_does_not_expose_recommendation_or_mutate_inputs() -> None:
    validation, evidence, observations = _valid_bundle()
    before_validation = validation.model_dump(mode="json")
    before_evidence = tuple(item.model_dump(mode="json") for item in evidence)
    result = _bridge(validation, evidence, observations)

    serialized = result.model_dump_json().lower()
    assert "recommendation" not in serialized
    assert "trade_order" not in serialized
    assert "target_price" not in serialized
    assert validation.model_dump(mode="json") == before_validation
    assert tuple(item.model_dump(mode="json") for item in evidence) == before_evidence


def test_bridge_contract_rejects_fact_without_evidence_and_invalid_severity() -> None:
    with pytest.raises(ValidationError):
        # The result contract itself must retain the existing Evidence closure rule.
        EvidenceFindingBridgeResult(
            validation_id="validation:test",
            status=EvidenceBridgeStatus.READY,
            fact=None,
            finding=None,
        )

    with pytest.raises(ValidationError, match="sensitive"):
        EvidenceFindingBridgeResult(
            validation_id="api_key=leak",
            status=EvidenceBridgeStatus.REVIEW_REQUIRED,
            issues=(),
        )

    validation, evidence, observations = _valid_bundle()
    result = _bridge(validation, evidence, observations, finding_severity="INFO")
    assert result.status == EvidenceBridgeStatus.BLOCKED
    assert result.issues[0].code == EvidenceBridgeIssueCode.INVALID_INPUT


def test_fixture_json_is_valid_and_contains_no_credentials() -> None:
    path = Path(__file__).parents[1] / "fixtures" / "research" / "evidence_finding_bridge_case.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(payload, ensure_ascii=False).lower()
    assert payload["schema_version"] == "evidence-finding-bridge-fixture.v1"
    assert "api_key" not in serialized
    assert "password" not in serialized
