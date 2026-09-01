import json
from datetime import datetime
from pathlib import Path

from app.research import (
    ResearchNodeKind,
    ResearchNodeResult,
    ResearchNodeStatus,
    ResearchObservation,
    ValidationClaim,
    ValidationStatus,
    validate_node_claim,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "research" / "research_validation_case.json"


def test_synthetic_research_fixture_produces_lineage_aware_result() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    claim = ValidationClaim.model_validate(payload["claim"])
    observations = tuple(
        ResearchObservation.model_validate(item) for item in payload["observations"]
    )
    node = ResearchNodeResult(
        request_id="fixture-research-request-001",
        node_id="fixture-research-node-001",
        owner_id=claim.owner_id,
        node_kind=ResearchNodeKind.STOCK,
        subject=claim.subject,
        completed_at=datetime.fromisoformat("2026-09-01T12:00:00+00:00"),
        status=ResearchNodeStatus.COMPLETE,
        observations=observations,
    )
    result = validate_node_claim(claim, node)
    assert result.status == ValidationStatus.SUPPORTED
    assert result.independent_lineage_count == 2
    assert result.duplicate_lineage_evidence_ids == (
        "fixture-evidence-a",
        "fixture-evidence-a-copy",
    )
    serialized = json.dumps(result.model_dump(mode="json"), ensure_ascii=False).lower()
    for field in payload["forbidden_fields"]:
        assert field not in serialized
    assert "api_key" not in serialized
