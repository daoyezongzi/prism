"""Lineage-aware deterministic cross-validation for scalar observations."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from decimal import Decimal, ROUND_HALF_UP
from hashlib import sha256

from app.research.contracts import (
    CrossValidationResult,
    ResearchNodeResult,
    ResearchNodeStatus,
    ResearchObservation,
    ValidationClaim,
    ValidationIssue,
    ValidationIssueCode,
    ValidationStatus,
)


def _stable_id(*parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return "validation:" + sha256(payload).hexdigest()[:32]


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def _confidence(status: ValidationStatus, support_count: int, independent_count: int) -> Decimal:
    if status == ValidationStatus.SUPPORTED:
        return Decimal("1.00")
    if status == ValidationStatus.CONTRADICTED:
        return Decimal("0.00")
    if status == ValidationStatus.UNRESOLVED and independent_count:
        return (Decimal(support_count) / Decimal(independent_count)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    return Decimal("0.00")


def _issue(
    code: ValidationIssueCode,
    message: str,
    evidence_ids: Iterable[str] = (),
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        safe_message=message,
        evidence_ids=_ordered_unique(evidence_ids),
    )


def _build_result(
    claim: ValidationClaim,
    observations: tuple[ResearchObservation, ...],
    *,
    node_issue: tuple[ValidationIssueCode, str] | None = None,
    node_observation_ids: Iterable[str] = (),
) -> CrossValidationResult:
    mismatched: list[str] = []
    non_verified: list[str] = []
    verified_matching: list[ResearchObservation] = []
    for observation in observations:
        if observation.owner_id != claim.owner_id:
            raise ValueError("observation owner_id does not match claim owner_id")
        if (
            observation.subject != claim.subject
            or observation.metric != claim.metric
            or observation.unit != claim.unit
            or observation.period != claim.period
        ):
            mismatched.append(observation.evidence_id)
            continue
        if observation.quality_status.value != "VERIFIED":
            non_verified.append(observation.evidence_id)
            continue
        verified_matching.append(observation)

    lineage_groups: dict[str, list[ResearchObservation]] = defaultdict(list)
    unlinked: list[ResearchObservation] = []
    for observation in verified_matching:
        if observation.lineage_id is None:
            unlinked.append(observation)
        else:
            lineage_groups[observation.lineage_id].append(observation)

    supporting: list[str] = []
    contradicting: list[str] = []
    unlinked_contradicting: list[str] = []
    duplicate_lineage: list[str] = []
    lineage_conflict: list[str] = []
    unresolved_evidence = list(mismatched) + list(non_verified)
    support_lineages = 0
    contradiction_lineages = 0
    for lineage_id in sorted(lineage_groups):
        group = sorted(lineage_groups[lineage_id], key=lambda item: item.evidence_id)
        evidence_ids = [item.evidence_id for item in group]
        values = {item.value for item in group}
        if len(group) > 1:
            duplicate_lineage.extend(evidence_ids)
        if len(values) > 1:
            lineage_conflict.extend(evidence_ids)
            unresolved_evidence.extend(evidence_ids)
            continue
        value = group[0].value
        if value == claim.expected_value:
            supporting.extend(evidence_ids)
            support_lineages += 1
        else:
            contradicting.extend(evidence_ids)
            contradiction_lineages += 1

    for observation in sorted(unlinked, key=lambda item: item.evidence_id):
        if observation.value == claim.expected_value:
            supporting.append(observation.evidence_id)
        else:
            contradicting.append(observation.evidence_id)
            unlinked_contradicting.append(observation.evidence_id)

    issues: list[ValidationIssue] = []
    if mismatched:
        issues.append(
            _issue(
                ValidationIssueCode.SCOPE_MISMATCH,
                "observation subject, metric, unit or period does not match the claim",
                mismatched,
            )
        )
    if non_verified:
        issues.append(
            _issue(
                ValidationIssueCode.NON_VERIFIED_EVIDENCE,
                "non-VERIFIED observations were excluded from support and contradiction",
                non_verified,
            )
        )
    if duplicate_lineage:
        issues.append(
            _issue(
                ValidationIssueCode.DUPLICATE_LINEAGE,
                "multiple observations share one lineage and count as one source",
                duplicate_lineage,
            )
        )
    if lineage_conflict:
        issues.append(
            _issue(
                ValidationIssueCode.LINEAGE_CONFLICT,
                "one lineage contains conflicting values",
                lineage_conflict,
            )
        )
    if unlinked:
        issues.append(
            _issue(
                ValidationIssueCode.INSUFFICIENT_INDEPENDENT_SOURCES,
                "observations without lineage cannot prove independent support",
                (item.evidence_id for item in unlinked),
            )
        )
    if node_issue is not None:
        issues.append(_issue(node_issue[0], node_issue[1], node_observation_ids))

    has_ambiguous_inputs = bool(
        mismatched
        or non_verified
        or lineage_conflict
        or unlinked_contradicting
        or (node_issue is not None and node_issue[0] == ValidationIssueCode.NODE_PARTIAL)
    )
    if support_lineages and contradiction_lineages:
        issues.append(
            _issue(
                ValidationIssueCode.CONFLICTING_VALUES,
                "independent sources support and contradict the same claim",
                tuple(supporting) + tuple(contradicting),
            )
        )
        has_ambiguous_inputs = True

    if support_lineages >= 2 and contradiction_lineages == 0 and not has_ambiguous_inputs:
        status = ValidationStatus.SUPPORTED
    elif contradiction_lineages >= 2 and support_lineages == 0 and not has_ambiguous_inputs:
        status = ValidationStatus.CONTRADICTED
    elif has_ambiguous_inputs or (support_lineages and contradiction_lineages):
        status = ValidationStatus.UNRESOLVED
    else:
        status = ValidationStatus.INSUFFICIENT

    if support_lineages < 2 and contradiction_lineages < 2:
        if not any(
            issue.code == ValidationIssueCode.INSUFFICIENT_INDEPENDENT_SOURCES
            for issue in issues
        ):
            issues.append(
                _issue(
                    ValidationIssueCode.INSUFFICIENT_INDEPENDENT_SOURCES,
                    "fewer than two independent lineage sources are available",
                )
            )
        if status not in {ValidationStatus.UNRESOLVED}:
            status = ValidationStatus.INSUFFICIENT

    issues.sort(key=lambda item: item.code.value)
    evidence_signature = []
    for observation in sorted(observations, key=lambda item: item.evidence_id):
        evidence_signature.append(
            "|".join(
                (
                    observation.evidence_id,
                    observation.lineage_id or "NO_LINEAGE",
                    str(observation.value),
                    observation.subject,
                    observation.metric,
                    observation.unit,
                    observation.period,
                    observation.quality_status.value,
                )
            )
        )
    validation_id = _stable_id(
        claim.claim_id,
        claim.owner_id,
        str(claim.expected_value),
        *evidence_signature,
    )
    return CrossValidationResult(
        validation_id=validation_id,
        owner_id=claim.owner_id,
        claim_id=claim.claim_id,
        subject=claim.subject,
        metric=claim.metric,
        unit=claim.unit,
        period=claim.period,
        expected_value=claim.expected_value,
        status=status,
        supporting_evidence_ids=_ordered_unique(supporting),
        contradicting_evidence_ids=_ordered_unique(contradicting),
        duplicate_lineage_evidence_ids=_ordered_unique(duplicate_lineage),
        unlinked_evidence_ids=_ordered_unique(item.evidence_id for item in unlinked),
        unresolved_evidence_ids=_ordered_unique(unresolved_evidence),
        independent_lineage_count=support_lineages + contradiction_lineages,
        confidence=_confidence(status, support_lineages, support_lineages + contradiction_lineages),
        methodology=(
            "lineage-keyed deterministic scalar equality; duplicate lineage records "
            "are not independent votes and no majority-vote inference is used"
        ),
        issues=tuple(issues),
    )


def validate_claim(
    claim: ValidationClaim,
    observations: Iterable[ResearchObservation],
) -> CrossValidationResult:
    """Validate one scalar claim against lineage-aware observations."""
    ordered = tuple(sorted(observations, key=lambda item: item.evidence_id))
    evidence_ids = [item.evidence_id for item in ordered]
    if len(set(evidence_ids)) != len(evidence_ids):
        raise ValueError("observations must not contain duplicate evidence_id")
    return _build_result(claim, ordered)


def validate_node_claim(
    claim: ValidationClaim,
    node_result: ResearchNodeResult,
) -> CrossValidationResult:
    """Validate a claim from a node while preserving the node's four-state status."""
    if claim.owner_id != node_result.owner_id:
        raise ValueError("claim owner_id does not match node owner_id")
    if node_result.status == ResearchNodeStatus.FAILED:
        return _build_result(
            claim,
            (),
            node_issue=(
                ValidationIssueCode.NODE_UNAVAILABLE,
                "research node failed; no observation can support the claim",
            ),
        )
    if node_result.status == ResearchNodeStatus.EMPTY:
        return _build_result(
            claim,
            (),
            node_issue=(
                ValidationIssueCode.NODE_UNAVAILABLE,
                "research node returned no observations for its declared scope",
            ),
        )
    if node_result.status == ResearchNodeStatus.PARTIAL:
        observation_ids = [item.evidence_id for item in node_result.observations]
        return _build_result(
            claim,
            tuple(sorted(node_result.observations, key=lambda item: item.evidence_id)),
            node_issue=(
                ValidationIssueCode.NODE_PARTIAL,
                "research node is partial; cross-validation requires human review",
            ),
            node_observation_ids=observation_ids,
        )
    return validate_claim(claim, node_result.observations)
