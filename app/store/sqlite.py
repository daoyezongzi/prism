"""SQLite implementation of the owner-scoped decision-event store port."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Protocol

from app.store.contracts import (
    DecisionEvent,
    DecisionEventSummary,
    event_content_payload,
)


class StoreError(RuntimeError):
    """Base class for safe persistence failures."""


class StoreConflictError(StoreError):
    """A stable event identity already carries different content."""


class StoreOwnerError(StoreError):
    """The caller attempted a write outside the event owner scope."""


class StoreCorruptError(StoreError):
    """A stored row failed contract or content validation."""


class DecisionEventStore(Protocol):
    def save(self, event: DecisionEvent) -> tuple[DecisionEvent, bool]: ...

    def get(self, owner_id: str, event_id: str) -> DecisionEvent | None: ...

    def list(self, owner_id: str) -> tuple[DecisionEventSummary, ...]: ...

    def close(self) -> None: ...


_MIGRATION_DIR = Path(__file__).parent / "migrations"


def _canonical_event_json(event: DecisionEvent) -> str:
    return json.dumps(
        event.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _validate_owner(owner_id: str) -> str:
    if not isinstance(owner_id, str) or not owner_id.strip():
        raise StoreOwnerError("owner scope is required")
    normalized = owner_id.strip()
    lowered = normalized.casefold().replace("-", "_")
    if any(
        token in lowered
        for token in (
            "api_key",
            "apikey",
            "authorization",
            "password",
            "private_key",
            "secret",
            "token",
            "credential",
            "cookie",
        )
    ):
        raise StoreOwnerError("owner scope is not allowed")
    return normalized


class SQLiteDecisionEventStore:
    """Transactional local store; callers must inject the path explicitly."""

    def __init__(self, database: str | Path = ":memory:") -> None:
        if not isinstance(database, (str, Path)):
            raise TypeError("database must be a path or :memory:")
        self._database = str(database)
        if self._database != ":memory:":
            path = Path(self._database)
            if not path.parent.exists():
                raise FileNotFoundError("database parent directory does not exist")
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self._database,
            check_same_thread=False,
            isolation_level=None,
        )
        self._connection.row_factory = sqlite3.Row
        with self._lock:
            self._connection.execute("PRAGMA foreign_keys = ON")
            if self._database != ":memory:":
                self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA busy_timeout = 3000")
            self._run_migrations()

    def _run_migrations(self) -> None:
        self._connection.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        applied = {
            int(row["version"])
            for row in self._connection.execute(
                "SELECT version FROM schema_migrations"
            ).fetchall()
        }
        migration_files = sorted(_MIGRATION_DIR.glob("*.sql"))
        for migration_file in migration_files:
            version = int(migration_file.name.split("_", 1)[0])
            if version in applied:
                continue
            script = migration_file.read_text(encoding="utf-8")
            try:
                self._connection.executescript(script)
                self._connection.execute(
                    "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                    (version, datetime.now(UTC).isoformat()),
                )
            except Exception:
                raise

    @staticmethod
    def _parse_row(row: sqlite3.Row) -> DecisionEvent:
        try:
            payload = json.loads(row["payload_json"])
            event = DecisionEvent.model_validate(payload)
            if (
                event.event_id != row["event_id"]
                or event.owner_id != row["owner_id"]
                or event.composition_id != row["composition_id"]
                or event.status.value != row["status"]
                or event.receipt_id != row["receipt_id"]
            ):
                raise ValueError("row identity does not match payload")
            if event.content_hash != row["content_hash"]:
                raise ValueError("row hash does not match payload")
            if event.recorded_at.isoformat() != row["recorded_at"]:
                raise ValueError("row timestamp does not match payload")
            return event
        except Exception as exc:
            raise StoreCorruptError("stored decision event failed validation") from exc

    def save(self, event: DecisionEvent) -> tuple[DecisionEvent, bool]:
        try:
            normalized = DecisionEvent.model_validate(event.model_dump(mode="python"))
        except Exception as exc:
            raise StoreCorruptError("decision event failed contract validation") from exc
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                row = self._connection.execute(
                    "SELECT * FROM decision_events WHERE event_id = ?",
                    (normalized.event_id,),
                ).fetchone()
                if row is not None:
                    existing = self._parse_row(row)
                    if existing.owner_id != normalized.owner_id:
                        raise StoreConflictError("event identity belongs to another owner")
                    if existing.content_hash != normalized.content_hash:
                        raise StoreConflictError("event identity already has different content")
                    self._connection.execute("COMMIT")
                    return existing, False
                self._connection.execute(
                    """
                    INSERT INTO decision_events
                        (event_id, owner_id, composition_id, status, receipt_id,
                         content_hash, payload_json, recorded_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        normalized.event_id,
                        normalized.owner_id,
                        normalized.composition_id,
                        normalized.status.value,
                        normalized.receipt_id,
                        normalized.content_hash,
                        _canonical_event_json(normalized),
                        normalized.recorded_at.isoformat(),
                    ),
                )
                self._connection.execute("COMMIT")
                return normalized, True
            except Exception:
                self._connection.execute("ROLLBACK")
                raise

    def get(self, owner_id: str, event_id: str) -> DecisionEvent | None:
        owner_id = _validate_owner(owner_id)
        if not isinstance(event_id, str) or not event_id.strip():
            raise StoreError("event ID is required")
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM decision_events WHERE owner_id = ? AND event_id = ?",
                (owner_id, event_id.strip()),
            ).fetchone()
        return self._parse_row(row) if row is not None else None

    def list(self, owner_id: str) -> tuple[DecisionEventSummary, ...]:
        owner_id = _validate_owner(owner_id)
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM decision_events WHERE owner_id = ?",
                (owner_id,),
            ).fetchall()
        events = [self._parse_row(row) for row in rows]
        events.sort(
            key=lambda event: (event.recorded_at.astimezone(UTC), event.event_id),
            reverse=True,
        )
        summaries: list[DecisionEventSummary] = []
        for event in events:
            summaries.append(
                DecisionEventSummary(
                    event_id=event.event_id,
                    owner_id=event.owner_id,
                    composition_id=event.composition_id,
                    status=event.status,
                    receipt_id=event.receipt_id,
                    recorded_at=event.recorded_at,
                    content_hash=event.content_hash,
                )
            )
        return tuple(summaries)

    def close(self) -> None:
        with self._lock:
            self._connection.close()


__all__ = [
    "DecisionEventStore",
    "SQLiteDecisionEventStore",
    "StoreConflictError",
    "StoreCorruptError",
    "StoreError",
    "StoreOwnerError",
]
