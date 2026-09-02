import asyncio
from datetime import UTC, datetime
from decimal import Decimal
import pytest

from app.history.contracts import (
    RecommendationComparisonRequest,
    RecommendationComparisonResponse,
    RecommendationHistoryResponse,
)
from app.service import (
    AdvisorQueryRequest,
    FixtureAdvisorQueryService,
    RecommendationHistoryService,
)
from app.store import SQLiteDecisionEventStore
from app.store.contracts import build_decision_event


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def test_recommendation_history_empty_store():
    store = SQLiteDecisionEventStore(":memory:")
    service = RecommendationHistoryService(store)
    res = service.get_history("test-owner")
    assert isinstance(res, RecommendationHistoryResponse)
    assert res.owner_id == "test-owner"
    assert res.total_count == 0
    assert len(res.items) == 0
    store.close()


def test_recommendation_history_query_and_compare():
    store = SQLiteDecisionEventStore(":memory:")
    advisor = FixtureAdvisorQueryService()
    history_svc = RecommendationHistoryService(store)

    owner = "hist-owner-001"
    template = advisor.query_template(owner)

    req1 = AdvisorQueryRequest(
        query_id="query-h-001",
        fixture_id="advisor-research-two-lineage-001",
        generated_at=NOW,
        questionnaire=template.questionnaire,
        portfolio=template.portfolio,
    )
    out1 = asyncio.run(advisor.run(req1))
    assert out1.result.receipt is not None
    ev1 = build_decision_event(out1.result, recorded_at=NOW)
    store.save(ev1)

    hist = history_svc.get_history(owner)
    assert hist.total_count == 1
    assert hist.items[0].receipt_id == out1.result.receipt.receipt_id
    assert hist.items[0].action_type is not None

    # Run a second query with different questionnaire (conservative)
    q2 = template.questionnaire.model_copy(update={"loss_tolerance_score": 1})
    req2 = AdvisorQueryRequest(
        query_id="query-h-002",
        fixture_id="advisor-research-two-lineage-001",
        generated_at=NOW,
        questionnaire=q2,
        portfolio=template.portfolio,
    )
    out2 = asyncio.run(advisor.run(req2))
    assert out2.result.receipt is not None
    ev2 = build_decision_event(out2.result, recorded_at=NOW)
    store.save(ev2)

    hist2 = history_svc.get_history(owner)
    assert hist2.total_count == 2

    # Compare receipt 1 and receipt 2
    comp_req = RecommendationComparisonRequest(
        owner_id=owner,
        receipt_a_id=out1.result.receipt.receipt_id,
        receipt_b_id=out2.result.receipt.receipt_id,
    )
    comp_res = history_svc.compare_receipts(comp_req)
    assert isinstance(comp_res, RecommendationComparisonResponse)
    assert comp_res.receipt_a_id == out1.result.receipt.receipt_id
    assert comp_res.receipt_b_id == out2.result.receipt.receipt_id
    assert comp_res.summary is not None
    assert comp_res.action_transition is not None

    store.close()


def test_recommendation_history_cross_owner_isolation():
    store = SQLiteDecisionEventStore(":memory:")
    advisor = FixtureAdvisorQueryService()
    history_svc = RecommendationHistoryService(store)

    owner1 = "owner-1"
    owner2 = "owner-2"

    t1 = advisor.query_template(owner1)
    req1 = AdvisorQueryRequest(
        query_id="q-iso-1",
        fixture_id="advisor-research-two-lineage-001",
        generated_at=NOW,
        questionnaire=t1.questionnaire,
        portfolio=t1.portfolio,
    )
    out1 = asyncio.run(advisor.run(req1))
    store.save(build_decision_event(out1.result, recorded_at=NOW))

    t2 = advisor.query_template(owner2)
    req2 = AdvisorQueryRequest(
        query_id="q-iso-2",
        fixture_id="advisor-research-two-lineage-001",
        generated_at=NOW,
        questionnaire=t2.questionnaire,
        portfolio=t2.portfolio,
    )
    out2 = asyncio.run(advisor.run(req2))
    store.save(build_decision_event(out2.result, recorded_at=NOW))

    # Owner 1 cannot see Owner 2 history
    h1 = history_svc.get_history(owner1)
    assert all(item.receipt_id != out2.result.receipt.receipt_id for item in h1.items)

    # Cross owner comparison must fail
    with pytest.raises(KeyError):
        history_svc.compare_receipts(
            RecommendationComparisonRequest(
                owner_id=owner1,
                receipt_a_id=out1.result.receipt.receipt_id,
                receipt_b_id=out2.result.receipt.receipt_id,
            )
        )

    store.close()
