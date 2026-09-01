import asyncio
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api import create_app
from app.optimization import (
    OptimizationDimension,
    OptimizationDisposition,
    OptimizationScenarioId,
    OptimizationStatus,
    PortfolioOptimizationRequest,
    PortfolioOptimizationResponse,
    PortfolioOptimizationTemplateResponse,
)
from app.profile import (
    ExperienceLevel,
    InvestmentHorizon,
    LiquidityNeed,
    ReturnExpectation,
)
from app.service import FixturePortfolioOptimizationService, PortfolioOptimizationError
from app.store import SQLiteDecisionEventStore


NOW = datetime(2026, 9, 2, 2, tzinfo=UTC)


def _client(*, optimization_service: object | None = None):
    store = SQLiteDecisionEventStore(":memory:")
    client = TestClient(
        create_app(
            store,
            clock=lambda: NOW,
            portfolio_optimization_service=optimization_service,
        )
    )
    return client, store


def _template(owner: str = "phase28-owner"):
    service = FixturePortfolioOptimizationService()
    return service, service.template(owner)


def _request(
    template: PortfolioOptimizationTemplateResponse,
    *,
    owner: str = "phase28-owner",
    request_id: str = "phase28-optimization-001",
    scenario: OptimizationScenarioId = OptimizationScenarioId.BASELINE_READY,
    profile: str = "balanced",
) -> PortfolioOptimizationRequest:
    if profile == "conservative":
        questionnaire = template.questionnaire.model_copy(
            update={
                "loss_tolerance_score": 1,
                "investment_horizon": InvestmentHorizon.SHORT,
                "liquidity_need": LiquidityNeed.HIGH,
                "experience_level": ExperienceLevel.NOVICE,
                "return_expectation": ReturnExpectation.LOW,
            }
        )
    elif profile == "growth":
        questionnaire = template.questionnaire.model_copy(
            update={
                "loss_tolerance_score": 5,
                "investment_horizon": InvestmentHorizon.LONG,
                "liquidity_need": LiquidityNeed.LOW,
                "experience_level": ExperienceLevel.EXPERIENCED,
                "return_expectation": ReturnExpectation.HIGH,
            }
        )
    else:
        questionnaire = template.questionnaire
    questionnaire = questionnaire.model_copy(update={"owner_id": owner})
    portfolio = template.portfolio
    if portfolio.owner_id != owner:
        portfolio = FixturePortfolioOptimizationService._rebind_portfolio(portfolio, owner)
    return PortfolioOptimizationRequest(
        request_id=request_id,
        owner_id=owner,
        generated_at=template.generated_at,
        questionnaire=questionnaire,
        portfolio=portfolio,
        scenario_id=scenario,
    )


def test_template_is_owner_closed_safe_and_sorted() -> None:
    client, store = _client()
    response = client.get(
        "/api/v1/advisor/portfolio-optimization-template",
        headers={"X-Owner-ID": "phase28-template-owner"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["manifest_id"] == "portfolio-optimization-demo-i-001"
    assert body["owner_id"] == "phase28-template-owner"
    assert len(body["portfolio"]["position_snapshot"]["positions"]) == 5
    assert [item["scenario_id"] for item in body["scenarios"]] == [
        item.value for item in sorted(OptimizationScenarioId, key=lambda item: item.value)
    ]
    assert [item["dimension"] for item in body["rules"]] == [
        "ASSET",
        "SECTOR",
        "TECHNOLOGY",
        "UNCLASSIFIED",
    ]
    assert "api_key" not in response.text.casefold()
    assert "optimization-position" in response.text
    store.close()


def test_baseline_is_deterministic_closed_and_no_store_side_effect() -> None:
    service, template = _template()
    request = _request(template)
    first = asyncio.run(service.run(request))
    second = asyncio.run(service.run(request))
    assert first == second
    assert first.status == OptimizationStatus.READY
    assert sum((item.target_weight_pct for item in first.targets), Decimal("0")) == Decimal("100.00")
    assert first.assessment_status == "REVIEW_REQUIRED"
    assert first.trace.methodology_version == "CAP_AND_REDISTRIBUTE_V1"
    assert first.trace.source_contribution_ids
    assert not hasattr(first, "recommendations")


@pytest.mark.parametrize(
    ("profile", "risk_level", "expected"),
    [
        ("conservative", "CONSERVATIVE", {"20.00"}),
        ("balanced", "BALANCED", {"15.00", "25.00", "35.00"}),
        ("growth", "GROWTH", {"5.00", "25.00", "45.00"}),
    ],
)
def test_profile_changes_target_structure(
    profile: str, risk_level: str, expected: set[str]
) -> None:
    service, template = _template()
    result = asyncio.run(service.run(_request(template, request_id=f"profile-{profile}", profile=profile)))
    assert result.status == OptimizationStatus.READY
    assert result.risk_level.value == risk_level
    values = {str(item.target_weight_pct) for item in result.targets}
    assert expected.issubset(values)
    if profile == "conservative":
        assert values == {"20.00"}
    if profile == "growth":
        assert next(item for item in result.targets if item.target_id == "OPT_TECH_ASSET").target_weight_pct == Decimal("45.00")


def test_ready_constraints_close_asset_sector_and_technology_caps() -> None:
    service, template = _template()
    result = asyncio.run(service.run(_request(template)))
    assert result.status == OptimizationStatus.READY
    by_dimension = {}
    for item in result.constraints:
        by_dimension.setdefault(item.dimension, []).append(item)
        assert item.delta_pct == item.target_weight_pct - item.current_weight_pct
        assert item.disposition in {
            OptimizationDisposition.WITHIN_LIMIT,
            OptimizationDisposition.REPAIRED,
        }
    assert len(by_dimension[OptimizationDimension.ASSET]) == 5
    tech = next(item for item in result.constraints if item.dimension == OptimizationDimension.TECHNOLOGY)
    assert tech.current_weight_pct == Decimal("45.00")
    assert tech.target_weight_pct == Decimal("35.00")
    assert tech.allowed_max_weight_pct == Decimal("40")


def test_multiple_technology_labels_still_respect_global_technology_cap() -> None:
    service, template = _template()
    funds = []
    for fund in template.portfolio.fund_holdings:
        if fund.parent_asset_id == "OPT_HEALTH_ASSET":
            holding = fund.holdings[0].model_copy(update={"sector": "Tech"})
            fund = fund.model_copy(update={"holdings": (holding,)})
        funds.append(fund)
    portfolio = template.portfolio.model_copy(update={"fund_holdings": tuple(funds)})
    request = _request(template, request_id="multi-tech")
    request = request.model_copy(update={"portfolio": portfolio})
    result = __import__("asyncio").run(service.run(request))
    assert result.status == OptimizationStatus.READY
    technology = next(
        item for item in result.constraints if item.dimension == OptimizationDimension.TECHNOLOGY
    )
    assert technology.target_weight_pct <= technology.allowed_max_weight_pct
    assert technology.target_weight_pct == Decimal("40.00")


@pytest.mark.parametrize(
    ("scenario", "status", "issue"),
    [
        (OptimizationScenarioId.SOURCE_PARTIAL, OptimizationStatus.REVIEW_REQUIRED, "INPUT_PARTIAL"),
        (OptimizationScenarioId.INFEASIBLE, OptimizationStatus.BLOCKED, "INFEASIBLE_CONSTRAINTS"),
    ],
)
def test_replay_scenarios_do_not_emit_partial_or_infeasible_targets(
    scenario: OptimizationScenarioId, status: OptimizationStatus, issue: str
) -> None:
    service, template = _template()
    result = asyncio.run(service.run(_request(template, request_id=f"scenario-{scenario.value}", scenario=scenario)))
    assert result.status == status
    assert result.targets == ()
    assert result.issues and result.issues[0].code.value == issue
    assert result.trace.source_contribution_ids or scenario == OptimizationScenarioId.INFEASIBLE


def test_api_baseline_partial_infeasible_and_owner_scope() -> None:
    client, store = _client()
    template = client.get(
        "/api/v1/advisor/portfolio-optimization-template",
        headers={"X-Owner-ID": "phase28-api-owner"},
    ).json()
    payload = {
        "schema_version": "portfolio-optimization-request.v1",
        "request_id": "phase28-api-run",
        "owner_id": "phase28-api-owner",
        "generated_at": template["generated_at"],
        "questionnaire": template["questionnaire"],
        "portfolio": template["portfolio"],
        "scenario_id": "BASELINE_READY",
    }
    ready = client.post(
        "/api/v1/advisor/portfolio-optimization-runs",
        headers={"X-Owner-ID": "phase28-api-owner"},
        json=payload,
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "READY"
    assert store.list("phase28-api-owner") == ()

    payload["scenario_id"] = "SOURCE_PARTIAL"
    partial = client.post(
        "/api/v1/advisor/portfolio-optimization-runs",
        headers={"X-Owner-ID": "phase28-api-owner"},
        json=payload,
    )
    assert partial.status_code == 200
    assert partial.json()["status"] == "REVIEW_REQUIRED"
    payload["scenario_id"] = "INFEASIBLE"
    blocked = client.post(
        "/api/v1/advisor/portfolio-optimization-runs",
        headers={"X-Owner-ID": "phase28-api-owner"},
        json=payload,
    )
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "BLOCKED"

    forbidden = client.post(
        "/api/v1/advisor/portfolio-optimization-runs",
        headers={"X-Owner-ID": "another-owner"},
        json=payload,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["error_code"] == "OWNER_SCOPE"
    store.close()


def test_request_rejects_owner_extra_sensitive_and_naive_timestamp() -> None:
    _, template = _template()
    base = _request(template).model_dump(mode="json")
    base["questionnaire"]["owner_id"] = "other-owner"
    with pytest.raises(ValidationError):
        PortfolioOptimizationRequest.model_validate(base)
    base = _request(template).model_dump(mode="json")
    base["unexpected"] = True
    with pytest.raises(ValidationError):
        PortfolioOptimizationRequest.model_validate(base)
    base = _request(template).model_dump(mode="json")
    base["request_id"] = "api_key-leak"
    with pytest.raises(ValidationError):
        PortfolioOptimizationRequest.model_validate(base)
    base = _request(template).model_dump(mode="json")
    base["generated_at"] = "2026-09-02T02:00:00"
    with pytest.raises(ValidationError):
        PortfolioOptimizationRequest.model_validate(base)


class _DriftedOptimizationService:
    def __init__(self) -> None:
        self._delegate = FixturePortfolioOptimizationService()

    def template(self, owner_id: str):
        return self._delegate.template(owner_id)

    async def run(self, request):
        output = await self._delegate.run(request)
        return output.model_copy(update={"request_id": "forged-request"})


def test_api_revalidates_injected_output_and_maps_safe_error() -> None:
    client, store = _client(optimization_service=_DriftedOptimizationService())
    template = client.get(
        "/api/v1/advisor/portfolio-optimization-template",
        headers={"X-Owner-ID": "phase28-injection-owner"},
    ).json()
    payload = {
        "schema_version": "portfolio-optimization-request.v1",
        "request_id": "phase28-injection-run",
        "owner_id": "phase28-injection-owner",
        "generated_at": template["generated_at"],
        "questionnaire": template["questionnaire"],
        "portfolio": template["portfolio"],
        "scenario_id": "BASELINE_READY",
    }
    response = client.post(
        "/api/v1/advisor/portfolio-optimization-runs",
        headers={"X-Owner-ID": "phase28-injection-owner"},
        json=payload,
    )
    assert response.status_code == 400
    assert response.json() == {
        "schema_version": "api-error.v1",
        "error_code": "PORTFOLIO_OPTIMIZATION_ERROR",
        "message": "portfolio optimization was refused",
    }
    store.close()


def test_response_rejects_forged_target_total_and_recommendation_like_fields() -> None:
    service, template = _template()
    result = asyncio.run(service.run(_request(template)))
    payload = result.model_dump(mode="python")
    payload["targets"] = tuple(
        item.model_copy(update={"target_weight_pct": item.target_weight_pct + Decimal("1")})
        for item in result.targets
    )
    with pytest.raises(ValidationError):
        PortfolioOptimizationResponse.model_validate(payload)
    payload = result.model_dump(mode="python")
    payload["recommendations"] = []
    with pytest.raises(ValidationError):
        PortfolioOptimizationResponse.model_validate(payload)


def test_service_rejects_missing_fixture() -> None:
    with pytest.raises(PortfolioOptimizationError):
        FixturePortfolioOptimizationService(template_path="missing-optimization-fixture.json")
