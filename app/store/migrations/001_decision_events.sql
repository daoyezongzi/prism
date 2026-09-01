CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_events (
    event_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    composition_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('PASS', 'REVIEW_REQUIRED', 'BLOCKED')),
    receipt_id TEXT,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decision_events_owner_recorded
    ON decision_events (owner_id, recorded_at DESC, event_id DESC);
