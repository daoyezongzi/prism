CREATE TABLE IF NOT EXISTS context_memory (
    memory_id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('EXPLICIT_SAVE')),
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    saved_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_context_memory_owner_saved
    ON context_memory (owner_id, saved_at DESC, memory_id DESC);
