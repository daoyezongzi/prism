from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
import tempfile

import pytest
from pydantic import ValidationError

from app.service import (
    AdvisorIntentRequest,
    FixtureAdvisorQueryService,
    FixtureResearchSpecialistMatrixService,
    build_intent_plan,
    confirm_questionnaire,
)
from app.store import (
    ContextMemoryReferences,
    ContextMemoryWriteRequest,
    SQLiteDecisionEventStore,
    StoreCorruptError,
    StoreError,
    StoreOwnerError,
    build_context_memory_record,
    context_memory_content_hash,
    context_memory_id,
)


NOW = datetime(2026, 9, 2, 3, 0, tzinfo=UTC)


def _request(owner: str = "memory-owner", *, with_derived: bool = False):
    advisor = FixtureAdvisorQueryService()
    template = advisor.query_template(owner)
    profile = confirm_questionnaire(template.questionnaire)
    intent = None
    plan = None
    refs = ContextMemoryReferences()
    if with_derived:
        specialist = FixtureResearchSpecialistMatrixService()
        intent = AdvisorIntentRequest(
            intent_id="memory-intent-001",
            owner_id=owner,
            intent_type="PORTFOLIO_RISK_REVIEW",
            generated_at=template.generated_at,
            portfolio_bundle_id=template.portfolio.bundle_id,
            position_snapshot_id=template.portfolio.position_snapshot.snapshot_id,
            questionnaire_id=template.questionnaire.questionnaire_id,
        )
        plan = build_intent_plan(intent, specialist.matrix_template(owner))
        refs = ContextMemoryReferences(
            research_matrix_id="matrix-memory-001",
            research_run_id="run-memory-001",
            research_scenario_id="BASELINE_READY",
            stock_research_run_id="stock-memory-001",
            stock_research_scenario_id="BASELINE_READY",
            fund_research_run_id="fund-memory-001",
            fund_research_scenario_id="BASELINE_READY",
            convertible_bond_research_run_id="cb-memory-001",
            convertible_bond_research_scenario_id="BASELINE_READY",
            optimization_request_id="optimization-memory-001",
            optimization_scenario_id="BASELINE_READY",
        )
    return ContextMemoryWriteRequest(
        owner_id=owner,
        questionnaire=template.questionnaire,
        profile=profile,
        portfolio=template.portfolio,
        intent=intent,
        plan=plan,
        references=refs,
    )


def test_context_memory_identity_is_deterministic_and_server_timestamp_is_metadata() -> None:
    request = _request()
    first = build_context_memory_record(request, saved_at=NOW)
    second = build_context_memory_record(request, saved_at=NOW + timedelta(minutes=1))
    assert first.memory_id == second.memory_id
    assert first.content_hash == second.content_hash
    assert first.saved_at != second.saved_at
    assert context_memory_content_hash(request) == first.content_hash
    assert context_memory_id(owner_id=request.owner_id, content_hash=first.content_hash) == first.memory_id


def test_context_memory_accepts_closed_optional_intent_plan_and_references() -> None:
    record = build_context_memory_record(_request(with_derived=True), saved_at=NOW)
    assert record.intent is not None
    assert record.plan is not None
    assert record.references.optimization_scenario_id == "BASELINE_READY"


@pytest.mark.parametrize(
    "update",
    [
        {"owner_id": "other-owner"},
        {"questionnaire": _request().questionnaire.model_copy(update={"owner_id": "other-owner"})},
        {"profile": _request().profile.model_copy(update={"owner_id": "other-owner"})},
        {"portfolio": _request().portfolio.model_copy(update={"owner_id": "other-owner"})},
        {"profile": _request().profile.model_copy(update={"questionnaire_id": "drifted"})},
    ],
)
def test_context_memory_rejects_owner_and_identity_drift(update: dict[str, object]) -> None:
    request = _request()
    payload = request.model_dump(mode="python")
    payload.update(update)
    with pytest.raises(ValidationError):
        ContextMemoryWriteRequest.model_validate(payload)


def test_context_memory_rejects_plan_without_matching_intent() -> None:
    request = _request(with_derived=True)
    with pytest.raises(ValidationError):
        ContextMemoryWriteRequest(
            owner_id=request.owner_id,
            questionnaire=request.questionnaire,
            profile=request.profile,
            portfolio=request.portfolio,
            plan=request.plan,
        )
    with pytest.raises(ValidationError):
        ContextMemoryWriteRequest(
            owner_id=request.owner_id,
            questionnaire=request.questionnaire,
            profile=request.profile,
            portfolio=request.portfolio,
            intent=request.intent.model_copy(update={"owner_id": "other-owner"}),
        )


def test_context_memory_rejects_sensitive_extra_forged_hash_and_naive_time() -> None:
    request = _request()
    payload = request.model_dump(mode="json")
    payload["unexpected"] = True
    with pytest.raises(ValidationError):
        ContextMemoryWriteRequest.model_validate(payload)
    payload = request.model_dump(mode="json")
    payload["owner_id"] = "api_key-owner"
    with pytest.raises(ValidationError):
        ContextMemoryWriteRequest.model_validate(payload)
    record = build_context_memory_record(request, saved_at=NOW)
    payload = record.model_dump(mode="json")
    payload["content_hash"] = "0" * 64
    with pytest.raises(ValidationError):
        type(record).model_validate(payload)
    payload = record.model_dump(mode="json")
    payload["saved_at"] = "2026-09-02T03:00:00"
    with pytest.raises(ValidationError):
        type(record).model_validate(payload)


def test_context_memory_references_require_parent_and_reject_secrets() -> None:
    with pytest.raises(ValidationError):
        ContextMemoryReferences(research_scenario_id="scenario-only")
    with pytest.raises(ValidationError):
        ContextMemoryReferences(optimization_request_id="api-key-request")


def test_sqlite_context_memory_migrates_restarts_and_is_append_only_idempotent() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    database = Path(temp_dir.name) / "context.sqlite3"
    request = _request()
    record = build_context_memory_record(request, saved_at=NOW)
    store = SQLiteDecisionEventStore(database)
    saved, created = store.save_context_memory(record)
    assert created is True
    assert saved == record
    repeated, created = store.save_context_memory(
        build_context_memory_record(request, saved_at=NOW + timedelta(hours=1))
    )
    assert created is False
    assert repeated == record
    assert store.get_context_memory(request.owner_id, record.memory_id) == record
    assert len(store.list_context_memory(request.owner_id)) == 1
    store.close()

    reopened = SQLiteDecisionEventStore(database)
    assert reopened.get_context_memory(request.owner_id, record.memory_id) == record
    assert reopened.list_context_memory(request.owner_id)[0] == record
    assert reopened.list(request.owner_id) == ()
    reopened.close()
    temp_dir.cleanup()


def test_sqlite_context_memory_is_owner_scoped_limited_and_rejects_bad_limits() -> None:
    store = SQLiteDecisionEventStore(":memory:")
    request = _request()
    record = build_context_memory_record(request, saved_at=NOW)
    store.save_context_memory(record)
    assert store.get_context_memory("another-owner", record.memory_id) is None
    assert store.list_context_memory("another-owner") == ()
    with pytest.raises(StoreOwnerError):
        store.list_context_memory("api_key-owner")
    for bad in (0, -1, 101, True, "2"):
        with pytest.raises(StoreError):
            store.list_context_memory(request.owner_id, bad)  # type: ignore[arg-type]
    store.close()


def test_sqlite_context_memory_detects_payload_hash_timestamp_and_owner_tampering() -> None:
    temp_dir = tempfile.TemporaryDirectory()
    store = SQLiteDecisionEventStore(Path(temp_dir.name) / "context.sqlite3")
    record = build_context_memory_record(_request(), saved_at=NOW)
    store.save_context_memory(record)
    for column, value in (
        ("content_hash", "f" * 64),
        ("saved_at", "2026-09-02T03:01:00+00:00"),
        ("owner_id", "tampered-owner"),
        ("payload_json", "{}"),
    ):
        original = store._connection.execute(
            f"SELECT {column} FROM context_memory WHERE memory_id = ?",
            (record.memory_id,),
        ).fetchone()[0]
        store._connection.execute(
            f"UPDATE context_memory SET {column} = ? WHERE memory_id = ?",
            (value, record.memory_id),
        )
        with pytest.raises(StoreCorruptError):
            store.get_context_memory(
                value if column == "owner_id" else record.owner_id,
                record.memory_id,
            )
        store._connection.execute(
            f"UPDATE context_memory SET {column} = ? WHERE memory_id = ?",
            (original, record.memory_id),
        )
    store.close()
    temp_dir.cleanup()


def test_concurrent_context_memory_writes_are_idempotent() -> None:
    store = SQLiteDecisionEventStore(":memory:")
    record = build_context_memory_record(_request(), saved_at=NOW)
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = tuple(executor.map(lambda _: store.save_context_memory(record), range(100)))
    assert sum(created for _, created in results) == 1
    assert len(store.list_context_memory(record.owner_id)) == 1
    store.close()
