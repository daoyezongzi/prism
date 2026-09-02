from datetime import UTC, datetime
from decimal import Decimal

from app.evaluation.contracts import (
    EvaluationDashboardRequest,
    EvaluationDashboardResponse,
)
from app.service import EvaluationDashboardService


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def test_evaluation_dashboard_service_run_all_cases():
    service = EvaluationDashboardService()

    req = EvaluationDashboardRequest(
        request_id="eval-dash-001",
        operator_id="operator-001",
        generated_at=NOW,
        repeat_count=1,
    )

    res = service.run_dashboard(req)
    assert isinstance(res, EvaluationDashboardResponse)
    assert res.total_cases > 0
    assert res.passed_cases == res.total_cases
    assert res.summary.case_pass_rate_pct == Decimal("100.00")
    assert res.summary.hallucination_rate_pct == Decimal("0.00")
    assert res.latency.p50_ms >= Decimal("0.00")
    assert len(res.cases) == res.total_cases


def test_evaluation_dashboard_subset_cases():
    service = EvaluationDashboardService()

    req = EvaluationDashboardRequest(
        request_id="eval-dash-002",
        operator_id="operator-002",
        generated_at=NOW,
        selected_cases=("balanced-hold", "conservative-reduce"),
        repeat_count=1,
    )

    res = service.run_dashboard(req)
    assert isinstance(res, EvaluationDashboardResponse)
    assert res.total_cases == 2
    assert res.passed_cases == 2
    assert res.summary.case_pass_rate_pct == Decimal("100.00")
