import json

from app.contracts import ActionType, ComplianceStatus
from app.gates import GateStatus
from app.profile import RiskLevel
from app.recommendation import compose_recommendations
from tests.recommendation_scenario import (
    RECOMMENDATION_FIXTURE,
    build_recommendation_case,
)


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


def test_fixture_proves_profile_conditioned_hold_vs_reduce_receipts() -> None:
    fixture = json.loads(RECOMMENDATION_FIXTURE.read_text(encoding="utf-8"))
    balanced = _compose(build_recommendation_case(RiskLevel.BALANCED))
    conservative = _compose(build_recommendation_case(RiskLevel.CONSERVATIVE))

    for result in (balanced, conservative):
        assert result.status == GateStatus.PASS
        assert result.receipt is not None
        assert result.receipt.generation_mode.value == "DETERMINISTIC"
        assert result.receipt.model_versions == ()
        assert result.receipt.decision_trace_hash
        assert result.receipt.content_hash
        assert all(
            item.compliance_status == ComplianceStatus.PASSED
            for item in result.trace.recommendations
        )
        serialized = result.model_dump_json().casefold()
        for field in fixture["expected"]["forbidden_output_fields"]:
            assert f'"{field.casefold()}"' not in serialized

    expected_balanced = fixture["expected"]["balanced"]
    assert len(balanced.trace.recommendations) == expected_balanced["recommendation_count"]
    assert all(
        item.action_type.value == expected_balanced["action_type"]
        for item in balanced.trace.recommendations
    )
    assert balanced.decision_gate is not None
    assert (
        balanced.decision_gate.risk_gate.remediation_required
        is expected_balanced["remediation_required"]
    )

    expected_conservative = fixture["expected"]["conservative"]
    assert len(conservative.trace.recommendations) == expected_conservative[
        "recommendation_count"
    ]
    assert all(
        item.action_type.value == expected_conservative["action_type"]
        for item in conservative.trace.recommendations
    )
    assert conservative.decision_gate is not None
    assert (
        conservative.decision_gate.risk_gate.remediation_required
        is expected_conservative["remediation_required"]
    )
    assert all(
        str(item.allocation_range.maximum_pct)
        == expected_conservative["target_maximum_pct"]
        for item in conservative.trace.recommendations
    )

    assert {
        item.action_type for item in balanced.trace.recommendations
    } == {ActionType.HOLD}
    assert {
        item.action_type for item in conservative.trace.recommendations
    } == {ActionType.REDUCE}
