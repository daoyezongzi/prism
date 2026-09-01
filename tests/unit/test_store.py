from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile

import pytest

from app.gates import GateStatus
from app.recommendation import RecommendationCompositionResult, RecommendationIssue, RecommendationIssueCode, compose_recommendations
from app.store import (
    SQLiteDecisionEventStore,
    StoreConflictError,
    StoreCorruptError,
    StoreOwnerError,
)
from app.store.contracts import build_decision_event
from tests.recommendation_scenario import build_recommendation_case


FIXED_RECORDED_AT = datetime(2026, 9, 2, 2, 0, tzinfo=UTC)


def _pass_event(recorded_at: datetime = FIXED_RECORDED_AT):
    case = build_recommendation_case()
    result = compose_recommendations(
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
    return build_decision_event(result, recorded_at=recorded_at)


def _blocked_event(message: str):
    result = RecommendationCompositionResult(
        composition_id="same-composition-for-conflict",
        owner_id="receipt-owner-001",
        status=GateStatus.BLOCKED,
        issues=(
            RecommendationIssue(
                code=RecommendationIssueCode.INVALID_INPUT,
                safe_message=message,
            ),
        ),
    )
    return build_decision_event(result, recorded_at=FIXED_RECORDED_AT)


def test_sqlite_store_migrates_round_trips_and_is_idempotent() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    database = Path(temp_dir.name) / "decisions.sqlite3"
    store = SQLiteDecisionEventStore(database)
    event = _pass_event()

    saved, created = store.save(event)
    assert created is True
    assert saved == event
    repeated, created = store.save(
        _pass_event(FIXED_RECORDED_AT + timedelta(seconds=30))
    )
    assert created is False
    assert repeated == event
    assert store.get(event.owner_id, event.event_id) == event
    assert store.list(event.owner_id)[0].event_id == event.event_id
    store.close()

    reopened = SQLiteDecisionEventStore(database)
    assert reopened.get(event.owner_id, event.event_id) == event
    assert len(reopened.list(event.owner_id)) == 1
    reopened.close()
    temp_dir.cleanup()


def test_store_rejects_same_identity_with_different_content() -> None:
    store = SQLiteDecisionEventStore(":memory:")
    first = _blocked_event("first refusal")
    second = _blocked_event("second refusal")
    assert first.event_id == second.event_id
    assert first.content_hash != second.content_hash
    store.save(first)
    with pytest.raises(StoreConflictError):
        store.save(second)
    store.close()


def test_store_is_owner_scoped_and_detects_corrupt_rows() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    store = SQLiteDecisionEventStore(Path(temp_dir.name) / "decisions.sqlite3")
    event = _pass_event()
    store.save(event)
    assert store.get("another-owner", event.event_id) is None
    assert store.list("another-owner") == ()
    with pytest.raises(StoreOwnerError):
        store.list("api_key-owner")

    store._connection.execute(
        "UPDATE decision_events SET content_hash = ? WHERE event_id = ?",
        ("f" * 64, event.event_id),
    )
    with pytest.raises(StoreCorruptError):
        store.get(event.owner_id, event.event_id)
    store.close()


def test_store_detects_payload_json_tampering() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    store = SQLiteDecisionEventStore(Path(temp_dir.name) / "decisions.sqlite3")
    event = _pass_event()
    store.save(event)
    store._connection.execute(
        "UPDATE decision_events SET payload_json = ? WHERE event_id = ?",
        ("{}", event.event_id),
    )
    with pytest.raises(StoreCorruptError):
        store.get(event.owner_id, event.event_id)
    store.close()
    temp_dir.cleanup()


def test_store_rejects_sensitive_owner_identity_before_persistence() -> None:
    store = SQLiteDecisionEventStore(":memory:")
    event = _pass_event()
    unsafe_result = event.result.model_copy(update={"owner_id": "api_key-owner"})
    with pytest.raises(StoreCorruptError):
        store.save(
            event.model_copy(
                update={"owner_id": "api_key-owner", "result": unsafe_result}
            )
        )
    assert store.list(event.owner_id) == ()
    store.close()


def test_concurrent_idempotent_writes_create_one_row() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    store = SQLiteDecisionEventStore(Path(temp_dir.name) / "decisions.sqlite3")
    event = _pass_event()
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(lambda _: store.save(event), range(20)))
    assert sum(created for _, created in results) == 1
    assert len(store.list(event.owner_id)) == 1
    store.close()
    temp_dir.cleanup()
