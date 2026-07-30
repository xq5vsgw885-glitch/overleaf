-- Migration 0001: initial normalized audit schema.
-- Applied in order by verification.db.repository.apply_migrations().
-- Column choices favor SQLite now, PostgreSQL-compatible types later
-- (TEXT for ids/enums, INTEGER for bools/timestamps-as-unix-epoch avoided
-- in favor of ISO8601 TEXT so both engines read it identically).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS claims (
    id                    TEXT PRIMARY KEY,
    document_id           TEXT NOT NULL,
    location              TEXT NOT NULL,
    text                  TEXT NOT NULL,
    claim_type            TEXT NOT NULL,
    search_query          TEXT NOT NULL,
    extraction_confidence REAL NOT NULL,
    context               TEXT NOT NULL DEFAULT '',
    cache_key             TEXT NOT NULL,
    created_at            TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_claims_cache_key ON claims (cache_key);
CREATE INDEX IF NOT EXISTS idx_claims_document_id ON claims (document_id);

CREATE TABLE IF NOT EXISTS sources (
    id           TEXT PRIMARY KEY,
    provider     TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    title        TEXT NOT NULL,
    authors_json TEXT NOT NULL DEFAULT '[]',
    year         INTEGER,
    doi          TEXT,
    url          TEXT,
    venue        TEXT,
    raw_snippet  TEXT NOT NULL DEFAULT '',
    locator      TEXT NOT NULL,
    created_at   TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sources_locator ON sources (locator);

CREATE TABLE IF NOT EXISTS verification_runs (
    id              TEXT PRIMARY KEY,
    claim_id        TEXT NOT NULL REFERENCES claims (id),
    status          TEXT NOT NULL,
    failure_reason  TEXT,
    iteration_count INTEGER NOT NULL DEFAULT 0,
    cache_hit       INTEGER NOT NULL DEFAULT 0,
    providers_used_json TEXT NOT NULL DEFAULT '[]',
    started_at      TEXT NOT NULL,
    completed_at    TEXT
);

CREATE INDEX IF NOT EXISTS idx_runs_claim_id ON verification_runs (claim_id);
CREATE INDEX IF NOT EXISTS idx_runs_status ON verification_runs (status);

CREATE TABLE IF NOT EXISTS run_sources (
    run_id    TEXT NOT NULL REFERENCES verification_runs (id),
    source_id TEXT NOT NULL REFERENCES sources (id),
    PRIMARY KEY (run_id, source_id)
);

CREATE TABLE IF NOT EXISTS search_attempts (
    id         TEXT PRIMARY KEY,
    run_id     TEXT NOT NULL REFERENCES verification_runs (id),
    provider   TEXT NOT NULL,
    query      TEXT NOT NULL,
    iteration  INTEGER NOT NULL,
    error      TEXT,
    queried_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_attempts_run_id ON search_attempts (run_id);

CREATE TABLE IF NOT EXISTS attempt_sources (
    attempt_id TEXT NOT NULL REFERENCES search_attempts (id),
    source_id  TEXT NOT NULL REFERENCES sources (id),
    PRIMARY KEY (attempt_id, source_id)
);

CREATE TABLE IF NOT EXISTS validations (
    id                    TEXT PRIMARY KEY,
    run_id                TEXT NOT NULL REFERENCES verification_runs (id),
    source_id             TEXT NOT NULL REFERENCES sources (id),
    is_allowed_source     INTEGER NOT NULL,
    supports_claim        INTEGER NOT NULL,
    validation_confidence REAL NOT NULL,
    reasoning             TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_validations_run_id ON validations (run_id);

CREATE TABLE IF NOT EXISTS risk_assessments (
    run_id          TEXT PRIMARY KEY REFERENCES verification_runs (id),
    risk_level      TEXT NOT NULL,
    reasons_json    TEXT NOT NULL DEFAULT '[]',
    requires_review INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS review_decisions (
    id          TEXT PRIMARY KEY,
    run_id      TEXT NOT NULL REFERENCES verification_runs (id),
    decision    TEXT NOT NULL,
    risk_level  TEXT NOT NULL,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    reviewer    TEXT,
    notes       TEXT NOT NULL DEFAULT '',
    decided_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_review_run_id ON review_decisions (run_id);
