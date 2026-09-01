import asyncio
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from app.gates import GateStatus
from app.service import AdvisorQueryError, AdvisorQueryRequest, FixtureAdvisorQueryService
from app.profile import RiskQuestionnaire
from tests.recommendation_scenario import build_recommendation_case


FIXTURE_ID = "advisor-research-two-lineage-001"
PROVIDER_FIXTURES = (
    Path(__file__).parents[2] / "app" / "fixtures" / "advisor" / "providers"
)


def _request(*, query_id: str = "unit-query-001", conservative: bool = False):
    case = build_recommendation_case()
    if conservative:
        values = {
            "loss_tolerance_score": 1,
            "investment_horizon": "SHORT",
            "liquidity_need": "HIGH",
            "experience_level": "NOVICE",
            "return_expectation": "LOW",
            "max_drawdown_tolerance_pct": "10",
        }
    else:
        values = {
            "loss_tolerance_score": 3,
            "investment_horizon": "MEDIUM",
            "liquidity_need": "MEDIUM",
            "experience_level": "INTERMEDIATE",
            "return_expectation": "MODERATE",
            "max_drawdown_tolerance_pct": "20",
        }
    questionnaire = RiskQuestionnaire(
        questionnaire_id=f"questionnaire-{query_id}",
        owner_id=case.profile.owner_id,
        answered_at="2026-09-02T01:00:00Z",
        **values,
    )
    return AdvisorQueryRequest(
        query_id=query_id,
        fixture_id=FIXTURE_ID,
        generated_at="2026-09-02T01:00:00Z",
        questionnaire=questionnaire,
        portfolio=case.portfolio,
    )


def test_fixture_query_closes_profile_portfolio_research_and_hold() -> None:
    output = asyncio.run(FixtureAdvisorQueryService().run(_request()))
    assert output.status == GateStatus.PASS
    assert output.result.receipt is not None
    assert len(output.result.trace.evidence) == 2
    assert len(output.result.trace.facts) == 1
    assert len(output.result.trace.findings) == 1
    assert {item.action_type.value for item in output.result.trace.recommendations} == {
        "HOLD"
    }


def test_fixture_query_profile_changes_action_to_breach_bound_reduce() -> None:
    output = asyncio.run(
        FixtureAdvisorQueryService().run(
            _request(query_id="unit-conservative-001", conservative=True)
        )
    )
    assert output.status == GateStatus.PASS
    assert output.result.receipt is not None
    assert {item.action_type.value for item in output.result.trace.recommendations} == {
        "REDUCE"
    }
    assert all(
        binding.breach_ids for binding in output.result.receipt.recommendation_bindings
    )


def test_fixture_query_replays_identically_for_fixed_input() -> None:
    request = _request(query_id="unit-replay-001")
    first = asyncio.run(FixtureAdvisorQueryService().run(request))
    second = asyncio.run(FixtureAdvisorQueryService().run(request))
    assert first == second
    assert first.result.composition_id == second.result.composition_id
    assert first.result.receipt is not None and second.result.receipt is not None
    assert first.result.receipt.content_hash == second.result.receipt.content_hash


def test_fixture_query_unknown_fixture_is_refused_without_details() -> None:
    request = _request().model_copy(update={"fixture_id": "unknown-fixture"})
    with pytest.raises(AdvisorQueryError, match="unavailable"):
        asyncio.run(FixtureAdvisorQueryService().run(request))


def test_fixture_query_revalidates_objects_that_bypass_pydantic_updates() -> None:
    request = _request().model_copy(update={"query_id": "api_key-leak"})
    with pytest.raises(AdvisorQueryError, match="refused"):
        asyncio.run(FixtureAdvisorQueryService().run(request))


def test_fixture_query_degraded_provider_remains_review() -> None:
    repo_root = Path(__file__).parents[2]
    with TemporaryDirectory(prefix=".phase14-provider-", dir=repo_root) as raw_dir:
        provider_dir = Path(raw_dir)
        for source in PROVIDER_FIXTURES.glob("*.json"):
            shutil.copy2(source, provider_dir / source.name)
        degraded_path = provider_dir / "advisor_company_data_b.json"
        payload = json.loads(degraded_path.read_text(encoding="utf-8"))
        payload["result"]["status"] = "PARTIAL"
        payload["result"]["records"][0]["fields"] = {"other_metric": "1.00"}
        payload["result"]["records"][0]["units"] = {"other_metric": "CNY"}
        payload["result"]["missing_fields"] = ["revenue"]
        payload["result"]["issues"] = [
            {
                "code": "INVALID_RESPONSE",
                "stage": "parse",
                "safe_message": "fixture omitted the required revenue field",
                "retriable": False,
                "diagnostics": {"missing_field": "revenue"},
            }
        ]
        degraded_path.write_text(json.dumps(payload), encoding="utf-8")
        service = FixtureAdvisorQueryService(provider_dir=provider_dir)
        output = asyncio.run(service.run(_request(query_id="unit-review-001")))
        assert output.status == GateStatus.REVIEW_REQUIRED
        assert output.result.receipt is None
        assert output.result.trace.evidence == ()
        assert output.result.trace.facts == ()
        assert output.result.trace.findings == ()
        assert output.result.trace.recommendations == ()


def test_fixture_query_refuses_completed_evidence_that_drifts_from_manifest() -> None:
    repo_root = Path(__file__).parents[2]
    with TemporaryDirectory(prefix=".phase14-provider-", dir=repo_root) as raw_dir:
        provider_dir = Path(raw_dir)
        for source in PROVIDER_FIXTURES.glob("*.json"):
            shutil.copy2(source, provider_dir / source.name)
        drifted_path = provider_dir / "advisor_company_data_a.json"
        payload = json.loads(drifted_path.read_text(encoding="utf-8"))
        payload["result"]["records"][0]["fields"]["revenue"] = "11.00"
        drifted_path.write_text(json.dumps(payload), encoding="utf-8")
        service = FixtureAdvisorQueryService(provider_dir=provider_dir)
        with pytest.raises(AdvisorQueryError, match="integrity"):
            asyncio.run(service.run(_request(query_id="unit-integrity-drift-001")))


def test_query_template_rebinds_every_nested_owner() -> None:
    template = FixtureAdvisorQueryService().query_template("ui-owner-001")
    assert template.fixture_id == FIXTURE_ID
    assert template.questionnaire.owner_id == "ui-owner-001"
    assert template.portfolio.owner_id == "ui-owner-001"
    assert template.portfolio.position_snapshot.owner_id == "ui-owner-001"
    assert all(
        position.owner_id == "ui-owner-001"
        for position in template.portfolio.position_snapshot.positions
    )
    assert all(snapshot.owner_id == "ui-owner-001" for snapshot in template.portfolio.fund_holdings)


def test_query_template_rejects_sensitive_owner() -> None:
    with pytest.raises(AdvisorQueryError, match="refused"):
        FixtureAdvisorQueryService().query_template("api_key-owner")
