"""Run-aware cross-validation and Evidence/Finding consumption.

The pipeline is the first consumer of the Phase 9 execution result.  It does
not call a provider and does not compose a recommendation: it only validates
declared claims against the normalized observations and delegates Fact/Finding
creation to the Phase 8 bridge.
"""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256
from typing import TYPE_CHECKING, Literal, Self

from pydantic import Field, model_validator

from app.contracts.evidence import (
    ContractModel,
    DecisionTrace,
    FindingSeverity,
    NonEmptyStr,
)
from app.research.contracts import (
    CrossValidationResult,
    ValidationIssue,
    ValidationIssueCode,
    ValidationStatus,
    ValidationClaim,
)
from app.research.cross_validation import validate_claim
from app.research.evidence_bridge import (
    EvidenceBridgeStatus,
    EvidenceFindingBridgeResult,
    bridge_cross_validation,
)

if TYPE_CHECKING:
    from app.orchestration.executor import ResearchRunExecutionResult


class ResearchPipelineStatus(StrEnum):
    """Overall downstream usability of one executed research run."""

    READY = "READY"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    BLOCKED = "BLOCKED"


class ResearchPipelineIssueCode(StrEnum):
    """Safe pipeline-level issue categories."""

    EMPTY_CLAIMS = "EMPTY_CLAIMS"
    DUPLICATE_CLAIM = "DUPLICATE_CLAIM"
    CLAIM_OWNER_MISMATCH = "CLAIM_OWNER_MISMATCH"
    CLAIM_INVALID = "CLAIM_INVALID"
    RUN_DEGRADED = "RUN_DEGRADED"
    CLAIM_REVIEW_REQUIRED = "CLAIM_REVIEW_REQUIRED"
    CLAIM_BLOCKED = "CLAIM_BLOCKED"


_SENSITIVE_SUBSTRINGS = (
    "api_key",
    "apikey",
    "authorization",
    "password",
    "private_key",
    "secret",
    "token",
    "credential",
    "cookie",
)


def _contains_sensitive(value: str) -> bool:
    normalized = value.casefold().replace("-", "_")
    return any(item in normalized for item in _SENSITIVE_SUBSTRINGS)


def _stable_id(prefix: str, *parts: str) -> str:
    payload = "\x1f".join(parts).encode("utf-8")
    return f"{prefix}:" + sha256(payload).hexdigest()[:32]


class ResearchClaimSpec(ContractModel):
    """A claim plus explicit metadata required to build a Finding."""

    schema_version: Literal["research-claim-spec.v1"] = "research-claim-spec.v1"
    claim: ValidationClaim
    finding_kind: NonEmptyStr
    finding_severity: FindingSeverity
    statement: NonEmptyStr
    observation_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_safe_text(self) -> Self:
        values = (
            self.claim.owner_id,
            self.claim.claim_id,
            self.claim.subject,
            self.claim.metric,
            self.claim.unit,
            self.claim.period,
            self.finding_kind,
            self.statement,
        )
        if any(_contains_sensitive(value) for value in values):
            raise ValueError("research claim metadata must not contain sensitive fields")
        if len(set(self.observation_ids)) != len(self.observation_ids):
            raise ValueError("claim observation_ids must not contain duplicates")
        if self.observation_ids != tuple(sorted(self.observation_ids)):
            raise ValueError("claim observation_ids must be in deterministic order")
        if any(_contains_sensitive(value) for value in self.observation_ids):
            raise ValueError("claim observation IDs must not contain sensitive fields")
        return self


class ResearchPipelineIssue(ContractModel):
    """Safe issue without raw provider or validation payloads."""

    code: ResearchPipelineIssueCode
    safe_message: NonEmptyStr
    claim_id: NonEmptyStr | None = None

    @model_validator(mode="after")
    def validate_safe_fields(self) -> Self:
        if _contains_sensitive(self.safe_message):
            raise ValueError("safe_message must not contain sensitive fields")
        if self.claim_id is not None and _contains_sensitive(self.claim_id):
            raise ValueError("claim_id must not contain sensitive fields")
        return self


class ResearchEvidencePipelineResult(ContractModel):
    """Closed result of validation and Fact/Finding registration for a run."""

    schema_version: Literal["research-evidence-pipeline.v1"] = (
        "research-evidence-pipeline.v1"
    )
    run_id: NonEmptyStr
    request_id: NonEmptyStr
    owner_id: NonEmptyStr
    status: ResearchPipelineStatus
    validations: tuple[CrossValidationResult, ...] = Field(default_factory=tuple)
    bridges: tuple[EvidenceFindingBridgeResult, ...] = Field(default_factory=tuple)
    trace: DecisionTrace
    issues: tuple[ResearchPipelineIssue, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_pipeline(self) -> Self:
        serialized = self.model_dump_json().casefold()
        if any(item in serialized for item in _SENSITIVE_SUBSTRINGS):
            raise ValueError("pipeline result must not contain sensitive fields")

        validation_ids = [item.validation_id for item in self.validations]
        if len(validation_ids) != len(set(validation_ids)):
            raise ValueError("pipeline validations must not contain duplicate IDs")
        bridge_ids = [item.validation_id for item in self.bridges]
        if len(bridge_ids) != len(set(bridge_ids)):
            raise ValueError("pipeline bridges must not contain duplicate IDs")
        if set(bridge_ids) != set(validation_ids):
            raise ValueError("pipeline bridges must match validation results exactly")
        if bridge_ids != validation_ids:
            raise ValueError("pipeline bridges must follow validation order")
        if any(item.owner_id != self.owner_id for item in self.validations):
            raise ValueError("pipeline validation owner does not match pipeline owner")
        issue_codes = [issue.code for issue in self.issues]
        if len(issue_codes) != len(set(issue_codes)):
            raise ValueError("pipeline issues must not contain duplicate codes")
        if self.trace.recommendations:
            raise ValueError("research evidence pipeline must not contain recommendations")

        ready_bridges = [
            bridge
            for bridge in self.bridges
            if bridge.status == EvidenceBridgeStatus.READY
        ]
        if self.status == ResearchPipelineStatus.READY:
            if self.issues:
                raise ValueError("READY pipeline must not carry issues")
            if not self.validations or len(ready_bridges) != len(self.bridges):
                raise ValueError("READY pipeline requires every claim to be ready")
            if len(self.trace.facts) != len(ready_bridges):
                raise ValueError("READY trace must contain every ready Fact")
            trace_fact_ids = {fact.fact_id for fact in self.trace.facts}
            trace_finding_ids = {finding.finding_id for finding in self.trace.findings}
            for bridge in ready_bridges:
                if bridge.fact is None or bridge.finding is None:
                    raise ValueError("READY bridge must expose Fact and Finding")
                if bridge.fact.fact_id not in trace_fact_ids:
                    raise ValueError("READY trace is missing a bridge Fact")
                if bridge.finding.finding_id not in trace_finding_ids:
                    raise ValueError("READY trace is missing a bridge Finding")
        else:
            if self.trace.facts or self.trace.findings:
                raise ValueError("non-ready pipeline must not expose Facts or Findings")
            if not self.issues:
                raise ValueError("non-ready pipeline requires an explicit issue")
        return self


def _degrade_supported_validation(
    validation: CrossValidationResult,
    run_status: object,
) -> CrossValidationResult:
    if validation.status != ValidationStatus.SUPPORTED:
        return validation
    if getattr(run_status, "value", run_status) == "PARTIAL":
        issue_code = ValidationIssueCode.NODE_PARTIAL
        message = "research run was partial; supported claim requires human review"
    else:
        issue_code = ValidationIssueCode.NODE_UNAVAILABLE
        message = "research run was not completed; supported claim requires human review"
    issue = ValidationIssue(
        code=issue_code,
        safe_message=message,
        evidence_ids=validation.supporting_evidence_ids,
    )
    return CrossValidationResult(
        validation_id=_stable_id(
            "validation",
            validation.validation_id,
            run_status.value,
        ),
        owner_id=validation.owner_id,
        claim_id=validation.claim_id,
        subject=validation.subject,
        metric=validation.metric,
        unit=validation.unit,
        period=validation.period,
        expected_value=validation.expected_value,
        status=ValidationStatus.UNRESOLVED,
        supporting_evidence_ids=validation.supporting_evidence_ids,
        contradicting_evidence_ids=(),
        duplicate_lineage_evidence_ids=validation.duplicate_lineage_evidence_ids,
        unlinked_evidence_ids=validation.unlinked_evidence_ids,
        unresolved_evidence_ids=tuple(
            sorted(
                set(validation.unresolved_evidence_ids)
                | set(validation.supporting_evidence_ids)
            )
        ),
        independent_lineage_count=validation.independent_lineage_count,
        confidence=Decimal("0.50"),
        methodology=validation.methodology,
        issues=tuple((*validation.issues, issue)),
    )


def _pipeline_issue(
    code: ResearchPipelineIssueCode,
    message: str,
    claim_id: str | None = None,
) -> ResearchPipelineIssue:
    return ResearchPipelineIssue(code=code, safe_message=message, claim_id=claim_id)


def _result(
    execution: ResearchRunExecutionResult,
    *,
    status: ResearchPipelineStatus,
    validations: tuple[CrossValidationResult, ...] = (),
    bridges: tuple[EvidenceFindingBridgeResult, ...] = (),
    issues: tuple[ResearchPipelineIssue, ...] = (),
) -> ResearchEvidencePipelineResult:
    if status == ResearchPipelineStatus.READY:
        facts = tuple(
            bridge.fact
            for bridge in bridges
            if bridge.status == EvidenceBridgeStatus.READY and bridge.fact is not None
        )
        findings = tuple(
            bridge.finding
            for bridge in bridges
            if bridge.status == EvidenceBridgeStatus.READY
            and bridge.finding is not None
        )
    else:
        facts = ()
        findings = ()
    trace = DecisionTrace(
        evidence=execution.evidence,
        facts=facts,
        findings=findings,
        recommendations=(),
    )
    return ResearchEvidencePipelineResult(
        run_id=execution.state.run_id,
        request_id=execution.state.request_id,
        owner_id=execution.state.owner_id,
        status=status,
        validations=validations,
        bridges=bridges,
        trace=trace,
        issues=issues,
    )


def build_research_evidence_pipeline(
    execution: "ResearchRunExecutionResult",
    claim_specs: Iterable[ResearchClaimSpec],
) -> ResearchEvidencePipelineResult:
    """Validate claims from one execution and register only closed findings."""

    from app.orchestration.executor import ResearchRunExecutionResult

    if not isinstance(execution, ResearchRunExecutionResult):
        raise TypeError("execution must be a ResearchRunExecutionResult")
    specs = tuple(claim_specs)
    if not specs:
        return _result(
            execution,
            status=ResearchPipelineStatus.BLOCKED,
            issues=(
                _pipeline_issue(
                    ResearchPipelineIssueCode.EMPTY_CLAIMS,
                    "at least one research claim is required",
                ),
            ),
        )
    if not all(isinstance(spec, ResearchClaimSpec) for spec in specs):
        return _result(
            execution,
            status=ResearchPipelineStatus.BLOCKED,
            issues=(
                _pipeline_issue(
                    ResearchPipelineIssueCode.CLAIM_INVALID,
                    "claim specification is invalid",
                ),
            ),
        )

    ordered_specs = tuple(sorted(specs, key=lambda item: item.claim.claim_id))
    claim_ids = [spec.claim.claim_id for spec in ordered_specs]
    if len(claim_ids) != len(set(claim_ids)):
        return _result(
            execution,
            status=ResearchPipelineStatus.BLOCKED,
            issues=(
                _pipeline_issue(
                    ResearchPipelineIssueCode.DUPLICATE_CLAIM,
                    "claim specifications must have unique claim IDs",
                ),
            ),
        )
    foreign = [
        spec.claim.claim_id
        for spec in ordered_specs
        if spec.claim.owner_id != execution.state.owner_id
    ]
    if foreign:
        return _result(
            execution,
            status=ResearchPipelineStatus.BLOCKED,
            issues=(
                _pipeline_issue(
                    ResearchPipelineIssueCode.CLAIM_OWNER_MISMATCH,
                    "claim owner does not match the executed research owner",
                    foreign[0],
                ),
            ),
        )

    run_status = execution.state.status
    validations: list[CrossValidationResult] = []
    bridges: list[EvidenceFindingBridgeResult] = []
    issues: list[ResearchPipelineIssue] = []
    if getattr(run_status, "value", run_status) != "COMPLETED":
        issues.append(
            _pipeline_issue(
                ResearchPipelineIssueCode.RUN_DEGRADED,
                "research run was not fully completed; findings require human review",
            )
        )

    known_observation_ids = {item.observation_id for item in execution.observations}

    def append_claim_issue(
        code: ResearchPipelineIssueCode,
        message: str,
        claim_id: str,
    ) -> None:
        # Pipeline-level issue codes are intentionally unique.  Multiple claims
        # can have the same review/blocked outcome; their individual bridge and
        # validation objects retain the claim-specific detail.
        if any(issue.code == code for issue in issues):
            return
        issues.append(_pipeline_issue(code, message, claim_id))

    for spec in ordered_specs:
        selected_observations = execution.observations
        if spec.observation_ids:
            unknown_observations = set(spec.observation_ids) - known_observation_ids
            if unknown_observations:
                append_claim_issue(
                    ResearchPipelineIssueCode.CLAIM_INVALID,
                    "claim references an observation outside the executed research result",
                    spec.claim.claim_id,
                )
                continue
            scoped_observations = tuple(
                item
                for item in execution.observations
                if (
                    item.subject == spec.claim.subject
                    and item.metric == spec.claim.metric
                    and item.unit == spec.claim.unit
                    and item.period == spec.claim.period
                )
            )
            scoped_ids = {item.observation_id for item in scoped_observations}
            if set(spec.observation_ids) != scoped_ids:
                append_claim_issue(
                    ResearchPipelineIssueCode.CLAIM_INVALID,
                    "claim observation scope must include every matching executed observation",
                    spec.claim.claim_id,
                )
                continue
            selected_observations = scoped_observations
        try:
            validation = validate_claim(spec.claim, selected_observations)
        except ValueError:
            append_claim_issue(
                ResearchPipelineIssueCode.CLAIM_INVALID,
                "claim could not be validated against the execution observations",
                spec.claim.claim_id,
            )
            continue
        if getattr(run_status, "value", run_status) != "COMPLETED":
            validation = _degrade_supported_validation(validation, run_status)
        validations.append(validation)
        bridge = bridge_cross_validation(
            validation,
            execution.evidence,
            selected_observations,
            finding_kind=spec.finding_kind,
            finding_severity=spec.finding_severity,
            statement=spec.statement,
        )
        bridges.append(bridge)
        if bridge.status == EvidenceBridgeStatus.BLOCKED:
            append_claim_issue(
                ResearchPipelineIssueCode.CLAIM_BLOCKED,
                "claim could not close to registered Evidence and requires correction",
                spec.claim.claim_id,
            )
        elif bridge.status == EvidenceBridgeStatus.REVIEW_REQUIRED:
            append_claim_issue(
                ResearchPipelineIssueCode.CLAIM_REVIEW_REQUIRED,
                "claim requires review before it can be consumed downstream",
                spec.claim.claim_id,
            )

    if issues and any(
        issue.code
        in {
            ResearchPipelineIssueCode.CLAIM_BLOCKED,
            ResearchPipelineIssueCode.CLAIM_OWNER_MISMATCH,
            ResearchPipelineIssueCode.CLAIM_INVALID,
            ResearchPipelineIssueCode.DUPLICATE_CLAIM,
            ResearchPipelineIssueCode.EMPTY_CLAIMS,
        }
        for issue in issues
    ):
        status = ResearchPipelineStatus.BLOCKED
    elif getattr(run_status, "value", run_status) != "COMPLETED" or any(
        bridge.status == EvidenceBridgeStatus.REVIEW_REQUIRED for bridge in bridges
    ):
        status = ResearchPipelineStatus.REVIEW_REQUIRED
    elif all(bridge.status == EvidenceBridgeStatus.READY for bridge in bridges):
        status = ResearchPipelineStatus.READY
    else:
        status = ResearchPipelineStatus.BLOCKED

    return _result(
        execution,
        status=status,
        validations=tuple(validations),
        bridges=tuple(bridges),
        issues=tuple(issues),
    )


def evaluate_research_run(
    execution: "ResearchRunExecutionResult",
    claim_specs: Iterable[ResearchClaimSpec],
) -> ResearchEvidencePipelineResult:
    """Semantic alias for callers that treat the pipeline as an evaluation step."""

    return build_research_evidence_pipeline(execution, claim_specs)


__all__ = [
    "ResearchClaimSpec",
    "ResearchEvidencePipelineResult",
    "ResearchPipelineIssue",
    "ResearchPipelineIssueCode",
    "ResearchPipelineStatus",
    "build_research_evidence_pipeline",
    "evaluate_research_run",
]
