import json
from decimal import Decimal
from pathlib import Path

from app.contracts import DecisionTrace, Evidence, FindingSeverity
from app.research import (
    EvidenceBridgeStatus,
    ResearchObservation,
    ValidationClaim,
    bridge_cross_validation,
    validate_claim,
)


FIXTURE = Path(__file__).parents[1] / "fixtures" / "research" / "evidence_finding_bridge_case.json"


def test_fixture_research_claim_closes_into_evidence_fact_finding_trace() -> None:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    claim = ValidationClaim(**payload["claim"])
    observations = tuple(
        ResearchObservation(**item) for item in payload["observations"]
    )
    evidence = tuple(Evidence(**item) for item in payload["evidence"])
    validation = validate_claim(claim, observations)

    result = bridge_cross_validation(
        validation,
        evidence,
        observations,
        finding_kind=payload["finding"]["kind"],
        finding_severity=FindingSeverity(payload["finding"]["severity"]),
        statement=payload["finding"]["statement"],
    )

    assert result.status == EvidenceBridgeStatus.READY
    assert result.fact is not None
    assert result.finding is not None
    assert result.fact.value == "10.00"
    assert result.fact.value != Decimal("0")
    trace = DecisionTrace(
        evidence=evidence,
        facts=(result.fact,),
        findings=(result.finding,),
    )
    assert trace.findings[0].fact_ids == (result.fact.fact_id,)
    serialized = result.model_dump_json().lower()
    for forbidden in ("recommendation", "trade_order", "target_price", "expected_return", "api_key", "password"):
        assert forbidden not in serialized
