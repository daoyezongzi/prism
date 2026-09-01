import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.contracts import (
    ActionType,
    AllocationRange,
    ComplianceStatus,
    EvidenceQualityStatus,
    FindingSeverity,
    Recommendation,
)
from app.orchestration import (
    ResearchClaimSpec,
    ResearchNodeSpec,
    ResearchPipelineIssueCode,
    ResearchPipelineStatus,
    ResearchRunStatus,
    ResearchRunExecutionResult,
    build_research_evidence_pipeline,
    build_research_plan,
    create_research_run,
    execute_research_run,
)
from app.providers import (
    ProviderOperation,
    ProviderRecord,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    compute_request_fingerprint,
)
from app.research import (
    EvidenceBridgeStatus,
    ResearchNodeKind,
    ValidationStatus,
)


NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
OWNER = "pipeline-owner-001"


class MultiSourceProvider:
    @property
    def name(self) -> str:
        return "pipeline-synthetic-provider"

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        fingerprint = compute_request_fingerprint(request)
        if request.subject == "EMPTY":
            return ProviderResult(
                request_id=request.request_id,
                request_fingerprint=fingerprint,
                provider=self.name,
                status=ProviderStatus.EMPTY,
                retrieved_at=NOW,
                scope_description="synthetic empty scope",
            )
        value = "9.00" if request.subject == "CONTRADICT" else "10.00"
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=fingerprint,
            provider=self.name,
            status=ProviderStatus.SUCCESS,
            retrieved_at=NOW,
            records=(
                ProviderRecord(
                    source=f"source-{request.request_id}",
                    record_id=f"record-{request.request_id}",
                    fields={"revenue": value},
                    units={"revenue": "CNY"},
                    period="2026-Q2",
                    observed_at=NOW,
                    lineage_id=f"lineage-{request.request_id}",
                ),
            ),
        )


def _execution(
    subjects: tuple[str, ...],
    *,
    required: tuple[bool, ...] | None = None,
) -> ResearchRunExecutionResult:
    required = required or tuple(True for _ in subjects)
    kinds = (ResearchNodeKind.MACRO, ResearchNodeKind.INDUSTRY, ResearchNodeKind.FUND)
    nodes = tuple(
        ResearchNodeSpec(
            node_id=f"node-{index}",
            owner_id=OWNER,
            node_kind=kinds[index % len(kinds)],
            required=required[index],
            timeout_ms=1000,
        )
        for index in range(len(subjects))
    )
    plan = build_research_plan(OWNER, "pipeline synthetic run", nodes)
    state = create_research_run(plan, "pipeline-run-001", 2000, NOW)
    requests = {
        f"node-{index}": ProviderRequest(
            request_id=f"provider-request-{index}",
            operation=(
                ProviderOperation.MACRO_DATA
                if kinds[index % len(kinds)] == ResearchNodeKind.MACRO
                else ProviderOperation.INDUSTRY_DATA
                if kinds[index % len(kinds)] == ResearchNodeKind.INDUSTRY
                else ProviderOperation.FUND_DATA
            ),
            subject=subject,
            required_fields=("revenue",),
            parameters={"period": "2026-Q2"},
            timeout_ms=1000,
        )
        for index, subject in enumerate(subjects)
    }
    return asyncio.run(
        execute_research_run(
            state,
            MultiSourceProvider(),
            requests,
            started_at=NOW,
            clock=lambda: NOW,
        )
    )


def _claim(
    *,
    claim_id: str = "claim-revenue",
    owner_id: str = OWNER,
    expected: str = "10.00",
    subject: str = "STOCK",
) -> ResearchClaimSpec:
    from app.research import ValidationClaim

    return ResearchClaimSpec(
        claim=ValidationClaim(
            claim_id=claim_id,
            owner_id=owner_id,
            subject=subject,
            metric="revenue",
            unit="CNY",
            period="2026-Q2",
            expected_value=Decimal(expected),
        ),
        finding_kind="REVENUE_STABLE",
        finding_severity=FindingSeverity.INFO,
        statement="独立来源对该报告期的收入数值一致。",
    )


def test_completed_run_with_two_lineages_becomes_ready_closed_trace() -> None:
    execution = _execution(("STOCK", "STOCK"))
    result = build_research_evidence_pipeline(execution, (_claim(),))

    assert execution.state.status == ResearchRunStatus.COMPLETED
    assert result.status == ResearchPipelineStatus.READY
    assert result.validations[0].status == ValidationStatus.SUPPORTED
    assert result.bridges[0].status == EvidenceBridgeStatus.READY
    assert result.trace.facts and result.trace.findings
    assert result.trace.recommendations == ()
    assert result.trace.findings[0].fact_ids == (result.trace.facts[0].fact_id,)


def test_claim_order_and_observation_order_are_deterministic() -> None:
    execution = _execution(("STOCK", "STOCK"))
    first = build_research_evidence_pipeline(
        execution,
        (_claim(claim_id="claim-b"), _claim(claim_id="claim-a")),
    )
    second = build_research_evidence_pipeline(
        execution,
        (_claim(claim_id="claim-a"), _claim(claim_id="claim-b")),
    )

    assert [item.claim_id for item in first.validations] == ["claim-a", "claim-b"]
    assert [item.claim_id for item in second.validations] == ["claim-a", "claim-b"]
    assert [item.validation_id for item in first.validations] == [
        item.validation_id for item in second.validations
    ]


def test_partial_run_degrades_supported_claim_to_review_without_fact() -> None:
    execution = _execution(("STOCK", "STOCK", "EMPTY"), required=(True, True, False))
    result = build_research_evidence_pipeline(execution, (_claim(),))

    assert execution.state.status == ResearchRunStatus.PARTIAL
    assert result.status == ResearchPipelineStatus.REVIEW_REQUIRED
    assert result.validations[0].status == ValidationStatus.UNRESOLVED
    assert result.bridges[0].status == EvidenceBridgeStatus.REVIEW_REQUIRED
    assert result.trace.facts == () and result.trace.findings == ()
    assert any(issue.code == ResearchPipelineIssueCode.RUN_DEGRADED for issue in result.issues)


def test_single_lineage_and_contradiction_require_review() -> None:
    single = build_research_evidence_pipeline(_execution(("STOCK",)), (_claim(),))
    assert single.status == ResearchPipelineStatus.REVIEW_REQUIRED
    assert single.validations[0].status == ValidationStatus.INSUFFICIENT
    assert single.trace.facts == ()

    contradiction = build_research_evidence_pipeline(
        _execution(("CONTRADICT", "CONTRADICT")),
        (_claim(expected="10.00", subject="CONTRADICT"),),
    )
    assert contradiction.status == ResearchPipelineStatus.REVIEW_REQUIRED
    assert contradiction.validations[0].status == ValidationStatus.CONTRADICTED
    assert contradiction.bridges[0].status == EvidenceBridgeStatus.REVIEW_REQUIRED


def test_owner_duplicate_and_empty_claim_errors_block_pipeline() -> None:
    execution = _execution(("STOCK", "STOCK"))
    foreign = build_research_evidence_pipeline(
        execution,
        (_claim(owner_id="foreign-owner"),),
    )
    assert foreign.status == ResearchPipelineStatus.BLOCKED
    assert foreign.issues[0].code == ResearchPipelineIssueCode.CLAIM_OWNER_MISMATCH
    assert foreign.trace.facts == ()

    duplicate = build_research_evidence_pipeline(execution, (_claim(), _claim()))
    assert duplicate.status == ResearchPipelineStatus.BLOCKED
    assert duplicate.issues[0].code == ResearchPipelineIssueCode.DUPLICATE_CLAIM

    empty = build_research_evidence_pipeline(execution, ())
    assert empty.status == ResearchPipelineStatus.BLOCKED
    assert empty.issues[0].code == ResearchPipelineIssueCode.EMPTY_CLAIMS


def test_sensitive_claim_text_is_blocked_without_raw_output() -> None:
    execution = _execution(("STOCK", "STOCK"))
    unsafe = _claim().model_copy(update={"statement": "api_key=do-not-emit"})
    result = build_research_evidence_pipeline(execution, (unsafe,))

    assert result.status == ResearchPipelineStatus.BLOCKED
    assert result.trace.facts == () and result.trace.findings == ()
    serialized = result.model_dump_json().lower()
    assert "api_key" not in serialized
    assert "do-not-emit" not in serialized


def test_pipeline_result_contract_rejects_recommendation() -> None:
    execution = _execution(("STOCK", "STOCK"))
    result = build_research_evidence_pipeline(execution, (_claim(),))
    assert result.trace.findings
    recommendation = Recommendation(
        recommendation_id="rec-not-allowed",
        action_type=ActionType.REVIEW,
        asset_id="STOCK",
        allocation_range=AllocationRange(minimum_pct=Decimal("0"), maximum_pct=Decimal("1")),
        rationale="review only",
        finding_ids=(result.trace.findings[0].finding_id,),
        compliance_status=ComplianceStatus.BLOCKED,
        invalidation_conditions=("new evidence",),
    )
    payload = result.model_dump(mode="python")
    payload["trace"] = result.trace.model_copy(
        update={"recommendations": (recommendation,)}
    )
    with pytest.raises(ValueError, match="recommendation"):
        from app.research.pipeline import ResearchEvidencePipelineResult

        ResearchEvidencePipelineResult.model_validate(payload)

    # The original execution result remains immutable after evaluation.
    before = execution.model_dump(mode="json")
    build_research_evidence_pipeline(execution, (_claim(),))
    assert execution.model_dump(mode="json") == before
