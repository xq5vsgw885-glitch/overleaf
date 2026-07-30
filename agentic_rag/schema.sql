-- audit_trail.db — Schema v1.0  ***BASELINE, NICHT DER AKTUELLE STAND***
--
-- Diese Datei ist die DDL der Migrationsversion 1 und wird ausschliesslich
-- von `migrations.py` geladen. Sie darf NICHT mehr direkt ausgefuehrt
-- werden — weder beim Verbindungsaufbau noch von Hand:
--
--   * Der aktuelle Stand ist Audit-Schema v2.0 (laufzentriert, append-only,
--     Kontrollvariablen, Writer-Sitzungen). Wer diese Datei auf eine
--     bestehende Datenbank anwendet, erzeugt keinen Fehler und keine
--     Wirkung — alle Statements sind IF NOT EXISTS. Genau diese stille
--     Wirkungslosigkeit war der Defekt des alten Verfahrens.
--   * Migration und Versionsstempel: `python3 audit_ctl.py init`
--   * Aktuellen Stand ansehen:      `python3 audit_ctl.py dump-schema`
--
-- Zwei-Kanal-Protokollierung für den RAG-Subagenten.
--
-- Kanal A (assertions): Was der Subagent BEHAUPTET  — semantisch, fehlbar.
-- Kanal B (actions):    Was der Subagent GETAN hat  — aus dem Transkript, nicht fabrizierbar.
-- Die Differenz beider Kanäle ist das eigentliche Prüfsignal.
--
-- Schreibrechte: ausschliesslich die Hook-Prozesse. Der Agent selbst hat
-- KEINEN Schreibzugriff (siehe hooks/protect_audit_db.py).

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- Lauf-Metadaten. Ein Datensatz pro gespawntem Subagenten.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS runs (
    agent_id        TEXT PRIMARY KEY,   -- Korrelationsschlüssel, von Claude Code vergeben
    session_id      TEXT NOT NULL,      -- Parent-Session
    agent_type      TEXT NOT NULL,
    cwd             TEXT,
    started_at      TEXT NOT NULL,      -- ISO 8601, UTC
    finished_at     TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,  -- Anzahl SubagentStop-Blocks
    status          TEXT NOT NULL DEFAULT 'open' -- open | verified | degraded | abandoned
);

-- ---------------------------------------------------------------------------
-- KANAL A — Behauptungen des Subagenten (Claim <-> Quelle).
-- Wird vom SubagentStop-Hook aus last_assistant_message geschrieben,
-- NICHT vom Modell selbst.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assertions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES runs(agent_id),
    claim           TEXT NOT NULL,      -- die gestützte Aussage
    source_id       TEXT NOT NULL,      -- Dateiname, DOI, Zotero-Key, Chunk-ID
    locator         TEXT,               -- Seite, Abschnitt, Chunk-Offset
    quote           TEXT,               -- wörtliches Belegzitat
    stance          TEXT NOT NULL,      -- supports | contradicts | unclear
    reconciled      INTEGER NOT NULL DEFAULT 0,  -- 1 = source_id in Kanal B belegt
    recorded_at     TEXT NOT NULL,
    prev_hash       TEXT,
    row_hash        TEXT NOT NULL
);

-- ---------------------------------------------------------------------------
-- KANAL B — tatsächlich ausgeführte Retrieval-Aktionen, aus dem
-- Subagenten-Transkript extrahiert.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id        TEXT NOT NULL REFERENCES runs(agent_id),
    tool_name       TEXT,
    source_id       TEXT NOT NULL,      -- berührte Quelle (normalisiert)
    raw_ref         TEXT,               -- unnormalisierte Fundstelle
    recorded_at     TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_assert_agent ON assertions(agent_id);
CREATE INDEX IF NOT EXISTS idx_action_agent ON actions(agent_id);
CREATE INDEX IF NOT EXISTS idx_action_src   ON actions(agent_id, source_id);

-- ---------------------------------------------------------------------------
-- Integritätsanker der Hash-Kette (letzter Zustand).
-- Erlaubt Manipulations-DETEKTION, nicht Manipulations-VERHINDERUNG.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chain_head (
    id              INTEGER PRIMARY KEY CHECK (id = 1),
    last_hash       TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
