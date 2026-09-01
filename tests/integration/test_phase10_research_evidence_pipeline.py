import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import json
from pathlib import Path

from app.contracts import FindingSeverity
from app.orchestration import (
    ResearchClaimSpec,
    ResearchNodeSpec,
    ResearchPipelineStatus,
    ResearchRunStatus,
    build_research_evidence_pipeline,
    build_research_plan,
    create_research_run,
    execute_research_run,
)
from app.providers import (
    ProviderRecord,
    ProviderRequest,
    ProviderResult,
    ProviderStatus,
    compute_request_fingerprint,
)
from app.research import ResearchNodeKind, ValidationClaim


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "research"
    / "pipeline_two_lineage_case.json"
)
NOW = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


class PipelineFixtureProvider:
    def __init__(self, source_by_request: dict[str, dict]) -> None:
        self.source_by_request = source_by_request

    @property
    def name(self) -> str:
        return "pipeline-fixture-provider"

    async def execute(self, request: ProviderRequest) -> ProviderResult:
        source = self.source_by_request[request.request_id]
        return ProviderResult(
            request_id=request.request_id,
            request_fingerprint=compute_request_fingerprint(request),
            provider=self.name,
            status=ProviderStatus.SUCCESS,
            retrieved_at=NOW,
            records=(
                ProviderRecord(
                    source=source["source"],
                    record_id=source["record_id"],
                    fields={"revenue": source["value"]},
                    units={"revenue": "CNY"},
                    period="2026-Q2",
                    observed_at=NOW,
                    lineage_id=source["lineage_id"],
                ),
            ),
        )


def test_fixture_two_lineage_run_closes_through_pipeline_and_trace() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    nodes = tuple(
        ResearchNodeSpec(
            node_id=item["node_id"],
            owner_id=payload["owner_id"],
            node_kind=ResearchNodeKind(item["node_kind"]),
            required=True,
            timeout_ms=1000,
        )
        for item in payload["sources"]
    )
    plan = build_research_plan(
        payload["owner_id"],
        payload["scope_description"],
        nodes,
    )
    state = create_research_run(
        plan,
        payload["request_id"],
        payload["budget_ms"],
        datetime.fromisoformat(payload["created_at"].replace("Z", "+00:00")),
    )
    requests = {
        item["node_id"]: ProviderRequest(
            request_id=item["request_id"],
            operation=item["operation"],
            subject=payload["claim"]["subject"],
            required_fields=("revenue",),
            parameters={"period": payload["claim"]["period"]},
            timeout_ms=1000,
        )
        for item in payload["sources"]
    }
    provider = PipelineFixtureProvider(
        {item["request_id"]: item for item in payload["sources"]}
    )
    execution = asyncio.run(
        execute_research_run(
            state,
            provider,
            requests,
            started_at=NOW,
            clock=lambda: NOW,
        )
    )
    claim = ValidationClaim(**payload["claim"])
    spec = ResearchClaimSpec(
        claim=claim,
        finding_kind=payload["finding"]["kind"],
        finding_severity=FindingSeverity(payload["finding"]["severity"]),
        statement=payload["finding"]["statement"],
    )

    pipeline = build_research_evidence_pipeline(execution, (spec,))

    assert execution.state.status == ResearchRunStatus.COMPLETED
    assert pipeline.status == ResearchPipelineStatus.READY
    assert pipeline.validations[0].independent_lineage_count == 2
    assert pipeline.trace.facts[0].value == "10.00"
    assert pipeline.trace.findings[0].fact_ids == (pipeline.trace.facts[0].fact_id,)
    assert len(pipeline.trace.evidence) == 2
    assert Decimal(pipeline.trace.facts[0].value) == Decimal("10.00")
