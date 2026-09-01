import json
from decimal import Decimal
from pathlib import Path

from app.portfolio import (
    ExposureIssueCode,
    ExposureStatus,
    PortfolioImportBundle,
    calculate_exposure,
)


FIXTURE = (
    Path(__file__).parents[1]
    / "fixtures"
    / "portfolio"
    / "portfolio_exposure_bundle.json"
)


def test_synthetic_exposure_fixture_is_offline_partial_and_closed() -> None:
    bundle = PortfolioImportBundle.model_validate(json.loads(FIXTURE.read_text()))
    first = calculate_exposure(bundle)
    second = calculate_exposure(bundle)
    assert first.status == ExposureStatus.PARTIAL
    assert first.report is not None
    assert first.report.total_market_value == Decimal("17000")
    assert first.report.unclassified_market_value == Decimal("7425.00")
    assert first.report.technology_market_value == Decimal("3550.00")
    assert {issue.code for issue in first.issues} == {
        ExposureIssueCode.INCOMPLETE_LOOK_THROUGH,
        ExposureIssueCode.MISSING_LOOK_THROUGH,
        ExposureIssueCode.NON_BASE_CURRENCY,
    }
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
    assert sum(
        contribution.market_value for contribution in first.report.contributions
    ) == first.report.total_market_value
