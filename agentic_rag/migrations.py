"""Einzige Schema-Wahrheit und versionierte Migration (Spezifikation §4).

## Warum diese Datei die Wahrheit ist

Vor dieser Aenderung gab es zwei DDL-Quellen ohne Versionsbegriff:
`audit_db.connect()` fuehrte `schema.sql` nur bei frischer Datei aus,
`store.connect()` fuehrte `schema_provenance.sql` bei JEDEM Verbindungsaufbau
aus. Beides funktionierte ausschliesslich, weil alle Statements
`IF NOT EXISTS` tragen — eine Schemaaenderung waere stillschweigend nicht
angekommen.

Ab jetzt gilt:

* `migrations.py` besitzt Reihenfolge, Version und Deltas.
* `schema.sql` und `schema_provenance.sql` bleiben die DDL ihrer
  jeweiligen BASELINE-Version (Audit v1.0, Provenance v1.1) und werden von
  der Registry geladen. Sie sind nicht mehr der aktuelle Stand; der
  aktuelle Stand ist `audit_ctl.py dump-schema`.
* Jede Datenbank fuehrt `schema_migrations`.

## Zwei Datenbanken, eine Wahrheit

`audit_trail.db` (Audit, append-only, EIN Schreiber) und `provenance.db`
(Dokument- und Chunkregister, vom Ingestionsprozess geschrieben) bleiben
physisch getrennt. Grund: §2 verlangt, dass NUR der Audit Writer eine
schreibende Verbindung zu `audit_trail.db` besitzt. Wuerde das
Provenienzregister in dieselbe Datei wandern, muesste entweder die
Ingestion durch den Audit Writer laufen — dann liefen Dateiparsings in
einer offenen SQLite-Transaktion, was §2 ausdruecklich verbietet — oder
`audit_trail.db` bekaeme einen zweiten Schreiber. Beide Varianten sind
Spezifikationsverstoesse. Die Migrationsregistry deckt daher beide
Datenbanken ab; die Schema-Wahrheit ist eine, die Dateien sind zwei.
"""

import os
import re
import sqlite3
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIT_BASELINE_SQL = os.path.join(HERE, "schema.sql")
PROVENANCE_BASELINE_SQL = os.path.join(HERE, "schema_provenance.sql")

AUDIT_SCHEMA_VERSION = 3
PROVENANCE_SCHEMA_VERSION = 2


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# Audit-Schema v2.0 — laufzentriert
# ---------------------------------------------------------------------------

AUDIT_V2_SQL = """
-- ===========================================================================
-- Audit-Schema v2.0
--
-- Aenderung gegenueber v1.0: `run_id` ist die primaere Evaluierungseinheit.
-- `agent_id` war in v1.0 Primaerschluessel von `runs` und damit implizit
-- die Auswertungseinheit — mit der Folge, dass ein Run mit zwei Subagenten
-- nicht darstellbar war und Kontrollvariablen keinen Ort hatten.
--
-- Die drei v1.0-Tabellen `runs`, `assertions`, `actions` werden neu
-- aufgebaut (12-Schritt-Verfahren), weil ihre Fremdschluessel auf
-- `runs(agent_id)` zeigen. Ein reines ALTER TABLE ... ADD COLUMN wuerde
-- `PRAGMA foreign_key_check` mit 'foreign key mismatch' scheitern lassen,
-- sobald `agent_id` nicht mehr Schluesselkandidat ist.
-- ===========================================================================

-- --- Laeufe ----------------------------------------------------------------
CREATE TABLE runs_v2 (
    run_id              TEXT PRIMARY KEY,
    -- Kontrollvariablen als eigene, indizierte Spalten (§4). Ein JSON-Feld
    -- allein genuegt nicht; die Auswertung filtert auf diese Spalten.
    experiment_id       TEXT,
    workflow_condition  TEXT CHECK (workflow_condition IS NULL
                                    OR workflow_condition IN ('A','B','C')),
    domain              TEXT CHECK (domain IS NULL
                                    OR domain IN ('physics','biology','chemistry')),
    provider            TEXT,
    model_version       TEXT,
    output_enforcement  TEXT CHECK (output_enforcement IS NULL
                                    OR output_enforcement IN ('native','prompt')),
    schema_version      TEXT,
    -- Experimentelle Kontrollvariablen. Eigene Spalten, nicht nur JSON:
    -- die Auswertung filtert und gruppiert darauf (§4).
    task_id             TEXT,
    replicate           INTEGER CHECK (replicate IS NULL OR replicate >= 1),
    -- NULL heisst 'kein Seed gesetzt'. Kein Default 0 — das waere eine
    -- erfundene Reproduzierbarkeit.
    seed                INTEGER,
    batch_id            TEXT,
    -- Vollstaendiger RunContext als kanonisches JSON plus Hash. Der Hash
    -- ist die Sperre gegen Kontextmutation (§9.4).
    context_json        TEXT,
    context_sha256      TEXT,
    -- 'complete' | 'context_incomplete' — fehlende historische
    -- Kontrollvariablen werden NICHT erfunden (§4).
    context_state       TEXT NOT NULL DEFAULT 'complete'
                        CHECK (context_state IN ('complete','context_incomplete')),
    is_legacy           INTEGER NOT NULL DEFAULT 0 CHECK (is_legacy IN (0,1)),
    -- Originalstatus aus Schema v1.0, unveraendert aufbewahrt.
    legacy_status_v1    TEXT,
    primary_agent_id    TEXT,
    -- v1.0 hiess diese Spalte `session_id`; §3 benennt sie eindeutig als
    -- uebergeordnete Claude-Code-Sitzung. Werte werden 1:1 uebernommen.
    parent_session_id   TEXT,
    agent_type          TEXT,
    cwd                 TEXT,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    attempts            INTEGER NOT NULL DEFAULT 0,
    status              TEXT NOT NULL DEFAULT 'open'
);

-- Altdatenuebernahme. Kontrollvariablen bleiben NULL — sie sind in v1.0
-- nie erhoben worden und werden nicht erfunden (§4). Der Status wird
-- unveraendert uebernommen, mit einer Ausnahme: ein v1.0-'verified'
-- beruhte auf einer Pruefung ohne RunContext, ohne kollisionsfreie
-- Quellenidentitaet und ohne Claim-Status. Er wird deshalb auf
-- 'legacy_unverified' abgebildet. Der Originalwert bleibt in
-- `legacy_status_v1` erhalten — nichts wird geloescht, nur nichts
-- faelschlich als verifiziert gefuehrt.
INSERT INTO runs_v2 (
    run_id, experiment_id, workflow_condition, domain, provider,
    model_version, output_enforcement, schema_version, task_id, replicate,
    seed, batch_id, context_json, context_sha256, context_state, is_legacy,
    legacy_status_v1, primary_agent_id, parent_session_id, agent_type, cwd,
    started_at, finished_at, attempts, status)
SELECT
    'legacy:' || agent_id,
    NULL, NULL, NULL, NULL, NULL, NULL, '1.0', NULL, NULL,
    NULL, NULL, NULL, NULL, 'context_incomplete', 1,
    status, agent_id, session_id, agent_type, cwd,
    started_at, finished_at, attempts,
    CASE status WHEN 'verified' THEN 'legacy_unverified' ELSE status END
FROM runs;

-- --- Agentenzuordnung -----------------------------------------------------
CREATE TABLE run_agents (
    run_id          TEXT NOT NULL REFERENCES runs_v2(run_id),
    agent_id        TEXT NOT NULL,
    agent_type      TEXT,
    registered_at   TEXT NOT NULL,
    PRIMARY KEY (run_id, agent_id)
);

-- `agent_id` ist genau einem Run zugeordnet. Das ist der 'vorgesehene
-- Geltungsbereich' aus §3 und gleichzeitig die Sperre gegen
-- runfremde Evidenz (§7): ein Agent kann keine zwei Evidenzraeume haben.
CREATE UNIQUE INDEX idx_run_agents_agent ON run_agents(agent_id);

INSERT INTO run_agents (run_id, agent_id, agent_type, registered_at)
SELECT 'legacy:' || agent_id, agent_id, agent_type, started_at FROM runs;

-- --- KANAL A --------------------------------------------------------------
CREATE TABLE assertions_v2 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT UNIQUE,
    run_id          TEXT NOT NULL REFERENCES runs_v2(run_id),
    agent_id        TEXT,
    claim_id        TEXT,
    claim           TEXT NOT NULL,
    evidence_id     TEXT,
    -- v1.0-Spalte: normalisierter Bezeichner. Bleibt fuer Altdaten erhalten.
    source_id       TEXT NOT NULL,
    -- v2.0: kollisionsfreier Vergleichsschluessel, siehe audit_db.source_key
    source_key      TEXT,
    raw_source_ref  TEXT,
    locator         TEXT,
    quote           TEXT,
    stance          TEXT NOT NULL,
    required        INTEGER NOT NULL DEFAULT 1,
    reconciled      INTEGER NOT NULL DEFAULT 0,
    recorded_at     TEXT NOT NULL,
    prev_hash       TEXT,
    row_hash        TEXT NOT NULL
);

INSERT INTO assertions_v2 (
    id, event_id, run_id, agent_id, claim_id, claim, evidence_id, source_id,
    source_key, raw_source_ref, locator, quote, stance, required,
    reconciled, recorded_at, prev_hash, row_hash)
SELECT
    id, NULL, 'legacy:' || agent_id, agent_id, NULL, claim, NULL, source_id,
    NULL, NULL, locator, quote, stance, 1,
    reconciled, recorded_at, prev_hash, row_hash
FROM assertions;

-- --- KANAL B --------------------------------------------------------------
CREATE TABLE actions_v2 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT UNIQUE,
    run_id          TEXT NOT NULL REFERENCES runs_v2(run_id),
    agent_id        TEXT,
    tool_name       TEXT,
    source_id       TEXT NOT NULL,
    source_key      TEXT,
    raw_ref         TEXT,
    evidence_key    TEXT,
    phase           TEXT NOT NULL DEFAULT 'tool_use',
    recorded_at     TEXT NOT NULL,
    prev_hash       TEXT,
    row_hash        TEXT
);

INSERT INTO actions_v2 (
    id, event_id, run_id, agent_id, tool_name, source_id, source_key,
    raw_ref, evidence_key, phase, recorded_at, prev_hash, row_hash)
SELECT
    id, NULL, 'legacy:' || agent_id, agent_id, tool_name, source_id, NULL,
    raw_ref, NULL, 'transcript_scan', recorded_at, NULL, NULL
FROM actions;

DROP TABLE assertions;
DROP TABLE actions;
DROP TABLE runs;
ALTER TABLE runs_v2 RENAME TO runs;
ALTER TABLE assertions_v2 RENAME TO assertions;
ALTER TABLE actions_v2 RENAME TO actions;

-- --- Unveraenderliches Ereignisprotokoll ----------------------------------
-- Kein Fremdschluessel auf runs: Ein hard_fail zu einer unbekannten oder
-- fremden run_id MUSS protokollierbar bleiben, sonst waere genau der
-- Auditbefund nicht speicherbar, um den es geht.
CREATE TABLE audit_events (
    seq                 INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            TEXT NOT NULL UNIQUE,
    event_type          TEXT NOT NULL,
    schema_version      TEXT NOT NULL,
    run_id              TEXT,
    agent_id            TEXT,
    occurred_at         TEXT NOT NULL,
    received_at         TEXT NOT NULL,
    payload_json        TEXT NOT NULL,
    payload_sha256      TEXT NOT NULL,
    prev_hash           TEXT NOT NULL,
    row_hash            TEXT NOT NULL,
    writer_session_id   TEXT NOT NULL
);

-- --- Claims (Projektion des Ereignisprotokolls) ---------------------------
CREATE TABLE claims (
    run_id                  TEXT NOT NULL REFERENCES runs(run_id),
    claim_id                TEXT NOT NULL,
    agent_id                TEXT,
    claim_text              TEXT NOT NULL,
    status                  TEXT NOT NULL
                            CHECK (status IN ('VERIFIED','PARTIALLY_VERIFIED',
                                              'UNVERIFIED','BLOCKED')),
    status_reason           TEXT,
    error_class             TEXT,
    evidence_free           INTEGER NOT NULL DEFAULT 0,
    repair_count            INTEGER NOT NULL DEFAULT 0,
    confirmed_evidence_json TEXT NOT NULL DEFAULT '[]',
    missing_evidence_json   TEXT NOT NULL DEFAULT '[]',
    first_seen_at           TEXT NOT NULL,
    updated_at              TEXT NOT NULL,
    PRIMARY KEY (run_id, claim_id)
);

-- --- Reparaturen ----------------------------------------------------------
CREATE TABLE repairs (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            TEXT NOT NULL UNIQUE,
    run_id              TEXT NOT NULL,
    agent_id            TEXT,
    target_id           TEXT NOT NULL,
    attempt             INTEGER NOT NULL,
    -- Format- und Evidenzreparatur sind getrennte Zustaende (§8).
    kind                TEXT NOT NULL CHECK (kind IN ('format','evidence')),
    error_class         TEXT NOT NULL,
    input_sha256        TEXT NOT NULL,
    output_sha256       TEXT NOT NULL,
    validated           INTEGER NOT NULL,
    validation_detail   TEXT,
    occurred_at         TEXT NOT NULL,
    UNIQUE (run_id, target_id, kind, attempt)
);

-- --- Hard Fails -----------------------------------------------------------
CREATE TABLE hard_fails (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            TEXT NOT NULL UNIQUE,
    run_id              TEXT,
    agent_id            TEXT,
    claim_id            TEXT,
    error_class         TEXT NOT NULL,
    scope               TEXT NOT NULL,
    cause               TEXT NOT NULL,
    raw_payload_sha256  TEXT,
    raw_payload_excerpt TEXT,
    recorded_at         TEXT NOT NULL
);

-- --- Metriken je Phase ----------------------------------------------------
-- Verbindliche Phasentrennung: initial_generation | format_repair |
-- evidence_retrieval | total. Append-only wie jede Messung.
CREATE TABLE phase_metrics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            TEXT NOT NULL UNIQUE,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    agent_id            TEXT,
    phase               TEXT NOT NULL CHECK (phase IN (
                            'initial_generation','format_repair',
                            'evidence_retrieval','total')),
    attempt             INTEGER NOT NULL DEFAULT 1,
    duration_ms         INTEGER,
    input_tokens        INTEGER,
    output_tokens       INTEGER,
    cached_input_tokens INTEGER,
    cost_usd            REAL,
    model_version       TEXT,
    detail              TEXT,
    recorded_at         TEXT NOT NULL,
    UNIQUE (run_id, phase, attempt, agent_id)
);

-- --- Writer-Sitzungen -----------------------------------------------------
-- Ohne diese Tabelle waere §9.14 nicht pruefbar: Ein Run, dessen Writer
-- abgebrochen ist, saehe von aussen wie ein vollstaendiger Run aus.
CREATE TABLE writer_sessions (
    writer_session_id   TEXT PRIMARY KEY,
    pid                 INTEGER NOT NULL,
    db_path             TEXT NOT NULL,
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    status              TEXT NOT NULL
                        CHECK (status IN ('running','closed','failed')),
    shutdown_reason     TEXT,
    events_received     INTEGER NOT NULL DEFAULT 0,
    events_persisted    INTEGER NOT NULL DEFAULT 0,
    events_duplicate    INTEGER NOT NULL DEFAULT 0,
    events_rejected     INTEGER NOT NULL DEFAULT 0
);

-- --- Indizes --------------------------------------------------------------
CREATE INDEX idx_runs_experiment   ON runs(experiment_id);
CREATE INDEX idx_runs_condition    ON runs(workflow_condition);
CREATE INDEX idx_runs_domain       ON runs(domain);
CREATE INDEX idx_runs_provider     ON runs(provider);
CREATE INDEX idx_runs_model        ON runs(model_version);
CREATE INDEX idx_runs_enforcement  ON runs(output_enforcement);
CREATE INDEX idx_runs_schema       ON runs(schema_version);
CREATE INDEX idx_runs_session      ON runs(parent_session_id);
CREATE INDEX idx_runs_status       ON runs(status);
CREATE INDEX idx_runs_task         ON runs(task_id);
CREATE INDEX idx_runs_replicate    ON runs(replicate);
CREATE INDEX idx_runs_seed         ON runs(seed);
CREATE INDEX idx_runs_batch        ON runs(batch_id);
CREATE INDEX idx_runs_legacy       ON runs(is_legacy);
-- Die haeufigste Auswertungsachse: Aufgabe x Bedingung x Wiederholung.
CREATE INDEX idx_runs_cell         ON runs(experiment_id, task_id,
                                           workflow_condition, replicate);

CREATE INDEX idx_metrics_run       ON phase_metrics(run_id);
CREATE INDEX idx_metrics_phase     ON phase_metrics(run_id, phase);

CREATE INDEX idx_assert_run    ON assertions(run_id);
CREATE INDEX idx_assert_agent  ON assertions(agent_id);
CREATE INDEX idx_assert_claim  ON assertions(run_id, claim_id);
CREATE INDEX idx_assert_key    ON assertions(run_id, source_key);

CREATE INDEX idx_action_run    ON actions(run_id);
CREATE INDEX idx_action_agent  ON actions(agent_id);
CREATE INDEX idx_action_src    ON actions(run_id, source_id);
CREATE INDEX idx_action_key    ON actions(run_id, source_key);
CREATE INDEX idx_action_evkey  ON actions(run_id, evidence_key);

CREATE INDEX idx_events_run    ON audit_events(run_id);
CREATE INDEX idx_events_type   ON audit_events(event_type);
CREATE INDEX idx_events_seq    ON audit_events(run_id, seq);

CREATE INDEX idx_claims_status ON claims(status);
CREATE INDEX idx_claims_run    ON claims(run_id);
CREATE INDEX idx_repairs_run   ON repairs(run_id, target_id);
CREATE INDEX idx_hf_run        ON hard_fails(run_id);
CREATE INDEX idx_hf_class      ON hard_fails(error_class);

-- --- Append-only-Durchsetzung in der Datenbank (§10) ----------------------
-- Anwendungscode allein genuegt nicht: Der Schutz muss auch gegen den
-- Writer selbst wirken, denn der Writer ist der einzige Prozess mit
-- Schreibverbindung. Erlaubt ist ihm ausschliesslich INSERT.
CREATE TRIGGER trg_actions_no_update BEFORE UPDATE ON actions
BEGIN
    SELECT RAISE(ABORT, 'CHANNEL_B_MUTATION: actions ist append-only');
END;
CREATE TRIGGER trg_actions_no_delete BEFORE DELETE ON actions
BEGIN
    SELECT RAISE(ABORT, 'CHANNEL_B_MUTATION: actions ist append-only');
END;
CREATE TRIGGER trg_assertions_no_update BEFORE UPDATE ON assertions
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: assertions ist append-only');
END;
CREATE TRIGGER trg_assertions_no_delete BEFORE DELETE ON assertions
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: assertions ist append-only');
END;
CREATE TRIGGER trg_events_no_update BEFORE UPDATE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: audit_events ist append-only');
END;
CREATE TRIGGER trg_events_no_delete BEFORE DELETE ON audit_events
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: audit_events ist append-only');
END;
CREATE TRIGGER trg_hf_no_update BEFORE UPDATE ON hard_fails
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: hard_fails ist append-only');
END;
CREATE TRIGGER trg_hf_no_delete BEFORE DELETE ON hard_fails
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: hard_fails ist append-only');
END;
CREATE TRIGGER trg_repairs_no_update BEFORE UPDATE ON repairs
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: repairs ist append-only');
END;
CREATE TRIGGER trg_repairs_no_delete BEFORE DELETE ON repairs
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: repairs ist append-only');
END;
CREATE TRIGGER trg_metrics_no_update BEFORE UPDATE ON phase_metrics
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: phase_metrics ist append-only');
END;
CREATE TRIGGER trg_metrics_no_delete BEFORE DELETE ON phase_metrics
BEGIN
    SELECT RAISE(ABORT, 'APPEND_ONLY: phase_metrics ist append-only');
END;

-- Kontrollvariablen sind unveraenderlich (§3). Der Writer aktualisiert an
-- `runs` ausschliesslich Status, Zeitpunkt und Versuchszaehler; jede
-- Aenderung an einer Kontrollvariablen oder am Kontexthash wird hier
-- abgebrochen — auch dann, wenn der Anwendungscode einen Fehler haette.
CREATE TRIGGER trg_runs_context_immutable BEFORE UPDATE ON runs
WHEN OLD.context_sha256 IS NOT NULL AND (
       NEW.context_sha256     IS NOT OLD.context_sha256
    OR NEW.context_json       IS NOT OLD.context_json
    OR NEW.experiment_id      IS NOT OLD.experiment_id
    OR NEW.workflow_condition IS NOT OLD.workflow_condition
    OR NEW.domain             IS NOT OLD.domain
    OR NEW.provider           IS NOT OLD.provider
    OR NEW.model_version      IS NOT OLD.model_version
    OR NEW.output_enforcement IS NOT OLD.output_enforcement
    OR NEW.task_id            IS NOT OLD.task_id
    OR NEW.replicate          IS NOT OLD.replicate
    OR NEW.seed               IS NOT OLD.seed
    OR NEW.batch_id           IS NOT OLD.batch_id)
BEGIN
    SELECT RAISE(ABORT, 'CONTEXT_MUTATION: RunContext ist unveraenderlich');
END;

-- Legacy-Laeufe koennen nachtraeglich nicht verifiziert werden (§4).
CREATE TRIGGER trg_runs_legacy_never_verified BEFORE UPDATE ON runs
WHEN NEW.is_legacy = 1 AND NEW.status = 'verified'
BEGIN
    SELECT RAISE(ABORT, 'LEGACY_NOT_VERIFIABLE: Legacy-Lauf ohne RunContext darf nicht als verifiziert gelten');
END;

-- --- Auswertungssichten ---------------------------------------------------
-- Reconciliation auf Datenbankebene: nach aussen LEFT JOIN, damit die
-- Abwesenheit eines Kanal-B-Zugriffs eine Zeile mit NULL ergibt und nicht
-- gar keine Zeile. Dieselbe Begruendung wie bei `hit_resolution`.
CREATE VIEW channel_reconciliation AS
SELECT a.run_id, a.agent_id, a.claim_id, a.id AS assertion_id,
       a.claim, a.evidence_id, a.source_key, a.source_id, a.required,
       b.id AS action_id, b.phase AS action_phase,
       CASE WHEN b.id IS NULL THEN 'unconfirmed' ELSE 'confirmed' END
       AS evidence_state
FROM assertions a
LEFT JOIN actions b
       ON b.run_id = a.run_id
      AND b.source_key IS NOT NULL
      AND b.source_key = a.source_key;

CREATE VIEW run_overview AS
SELECT r.run_id, r.experiment_id, r.task_id, r.replicate, r.seed,
       r.batch_id, r.workflow_condition, r.domain,
       r.provider, r.model_version, r.output_enforcement, r.status,
       r.context_state, r.is_legacy, r.legacy_status_v1,
       r.started_at, r.finished_at,
       (SELECT COUNT(*) FROM claims c WHERE c.run_id = r.run_id) AS claim_count,
       (SELECT COUNT(*) FROM claims c WHERE c.run_id = r.run_id
         AND c.status = 'VERIFIED') AS verified_count,
       (SELECT COUNT(*) FROM claims c WHERE c.run_id = r.run_id
         AND c.status = 'BLOCKED') AS blocked_count,
       (SELECT COUNT(*) FROM actions a WHERE a.run_id = r.run_id) AS action_count,
       (SELECT COUNT(*) FROM hard_fails h WHERE h.run_id = r.run_id) AS hard_fail_count
FROM runs r;

-- Metriken je Lauf und Phase, aufbereitet fuer die Auswertung. Die Summe
-- der Phasen wird bewusst NICHT als 'total' ausgegeben: 'total' ist eine
-- eigene Messung, und die Differenz zur Phasensumme ist selbst ein Befund.
CREATE VIEW run_phase_metrics AS
SELECT r.run_id, r.experiment_id, r.task_id, r.workflow_condition,
       r.replicate, r.batch_id, m.phase,
       COUNT(*)                AS measurements,
       SUM(m.duration_ms)      AS duration_ms,
       SUM(m.input_tokens)     AS input_tokens,
       SUM(m.output_tokens)    AS output_tokens,
       SUM(m.cached_input_tokens) AS cached_input_tokens,
       SUM(m.cost_usd)         AS cost_usd
FROM runs r JOIN phase_metrics m ON m.run_id = r.run_id
GROUP BY r.run_id, m.phase;
"""


# ---------------------------------------------------------------------------
# Provenance-Schema v2 — Laufzuordnung
# ---------------------------------------------------------------------------

PROVENANCE_V2_SQL = """
-- ===========================================================================
-- Provenance v2: Rueckfuehrbarkeit auf run_id (§4).
--
-- Bewusst additiv und NULL-zulassend: Bestehende Retrieval- und
-- Evidenzdatensaetze haben keine run_id, und eine erfundene Zuordnung
-- waere schlimmer als eine fehlende (§4).
-- ===========================================================================
ALTER TABLE retrieval_runs   ADD COLUMN run_id TEXT;
ALTER TABLE assertion_evidence ADD COLUMN run_id TEXT;
CREATE INDEX IF NOT EXISTS idx_rr_run ON retrieval_runs(run_id);
CREATE INDEX IF NOT EXISTS idx_ae_run ON assertion_evidence(run_id);
"""


AUDIT_V3_SQL = """
-- ===========================================================================
-- Audit-Schema v3 — Evidenzregistry (§7)
--
-- Bis v2 gab es keinen Ort, an dem ein AUSGELIEFERTER Beleg protokolliert
-- wurde. `actions` haelt fest, dass eine Quelle beruehrt wurde; welcher
-- Textausschnitt welcher Dokumentfassung dem Agenten tatsaechlich vorlag,
-- stand nirgends. Der Locator-Header zeigt dem Agenten aber einen
-- `evidence_key` — zitierte er ihn, war er per Definition unbekannt, weil
-- die Registry leer war. Ein korrekt belegtes Zitat wurde damit BLOCKED.
--
-- `evidence_registry` schliesst diese Luecke. Sie ist Kanal B: append-only,
-- Teil der Hash-Kette, und der einzige Weg, wie ein `ev:`-Schluessel
-- gueltig werden kann.
-- ===========================================================================

CREATE TABLE evidence_registry (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id            TEXT NOT NULL UNIQUE,
    run_id              TEXT NOT NULL REFERENCES runs(run_id),
    agent_id            TEXT,
    -- fassungsfreie Evidenzidentitaet (identity.make_evidence_key)
    evidence_key        TEXT NOT NULL,
    -- Vergleichsschluessel fuer den Kanal-A-Abgleich (audit_db.source_key)
    source_key          TEXT NOT NULL,
    -- Dokumentidentitaet
    source_id           TEXT NOT NULL,
    document_version_id TEXT NOT NULL,
    unit_id             TEXT NOT NULL,
    chunk_id            TEXT,
    -- Fundstelle
    structure_anchor    TEXT NOT NULL,
    label               TEXT,
    locator_json        TEXT,
    anchor_is_fallback  INTEGER NOT NULL DEFAULT 0,
    -- Inhaltsidentitaet: content_sha256 ist die Einheit, chunk_text_sha256
    -- der tatsaechlich ausgelieferte Text. Derselbe evidence_key mit
    -- abweichendem chunk_text_sha256 ist eine Kollision (Hard Fail).
    content_sha256      TEXT NOT NULL,
    chunk_text_sha256   TEXT NOT NULL,
    -- Herkunft der Auslieferung
    retrieval_run_id    TEXT,
    parser_name         TEXT,
    parser_version      TEXT,
    chunker_name        TEXT,
    chunker_version     TEXT,
    retrieved_at        TEXT NOT NULL,
    recorded_at         TEXT NOT NULL,
    prev_hash           TEXT,
    row_hash            TEXT,
    -- Traegt die zusammengesetzte Fremdschluesselbeziehung aus `actions`.
    UNIQUE (run_id, evidence_key)
);

CREATE INDEX idx_evreg_run    ON evidence_registry(run_id);
CREATE INDEX idx_evreg_key    ON evidence_registry(evidence_key);
CREATE INDEX idx_evreg_srckey ON evidence_registry(run_id, source_key);
CREATE INDEX idx_evreg_unit   ON evidence_registry(unit_id);
CREATE INDEX idx_evreg_chunk  ON evidence_registry(chunk_id);

CREATE TRIGGER trg_evreg_no_update BEFORE UPDATE ON evidence_registry
BEGIN
    SELECT RAISE(ABORT, 'CHANNEL_B_MUTATION: evidence_registry ist append-only');
END;
CREATE TRIGGER trg_evreg_no_delete BEFORE DELETE ON evidence_registry
BEGIN
    SELECT RAISE(ABORT, 'CHANNEL_B_MUTATION: evidence_registry ist append-only');
END;

-- --- `actions` neu aufbauen -----------------------------------------------
-- Zweck: die zusammengesetzte Fremdschluesselbeziehung
--   (run_id, evidence_key) -> evidence_registry(run_id, evidence_key)
-- Ein Kanal-B-Zugriff darf sich nur auf einen Beleg berufen, der im selben
-- Lauf registriert ist. Bestandszeilen tragen evidence_key IS NULL und
-- bleiben gueltig (NULL erfuellt jede Fremdschluesselbedingung).
-- Der Neuaufbau ist noetig, weil SQLite keinen nachtraeglichen
-- Fremdschluessel per ALTER TABLE kennt.
-- Beide Sichten muessen vor dem Neuaufbau weichen: SQLite prueft
-- abhaengige Sichten beim DROP TABLE und bricht sonst ab.
-- `channel_reconciliation` wird unveraendert wiederhergestellt,
-- `run_overview` um `evidence_count` erweitert.
DROP VIEW channel_reconciliation;
DROP VIEW run_overview;

CREATE TABLE actions_v3 (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id        TEXT UNIQUE,
    run_id          TEXT NOT NULL REFERENCES runs(run_id),
    agent_id        TEXT,
    tool_name       TEXT,
    source_id       TEXT NOT NULL,
    source_key      TEXT,
    raw_ref         TEXT,
    evidence_key    TEXT,
    phase           TEXT NOT NULL DEFAULT 'tool_use',
    recorded_at     TEXT NOT NULL,
    prev_hash       TEXT,
    row_hash        TEXT,
    FOREIGN KEY (run_id, evidence_key)
        REFERENCES evidence_registry(run_id, evidence_key)
);

INSERT INTO actions_v3 (id, event_id, run_id, agent_id, tool_name, source_id,
                        source_key, raw_ref, evidence_key, phase, recorded_at,
                        prev_hash, row_hash)
SELECT id, event_id, run_id, agent_id, tool_name, source_id, source_key,
       raw_ref, evidence_key, phase, recorded_at, prev_hash, row_hash
FROM actions;

DROP TRIGGER trg_actions_no_update;
DROP TRIGGER trg_actions_no_delete;
DROP TABLE actions;
ALTER TABLE actions_v3 RENAME TO actions;

CREATE INDEX idx_action_run    ON actions(run_id);
CREATE INDEX idx_action_agent  ON actions(agent_id);
CREATE INDEX idx_action_src    ON actions(run_id, source_id);
CREATE INDEX idx_action_key    ON actions(run_id, source_key);
CREATE INDEX idx_action_evkey  ON actions(run_id, evidence_key);

CREATE TRIGGER trg_actions_no_update BEFORE UPDATE ON actions
BEGIN
    SELECT RAISE(ABORT, 'CHANNEL_B_MUTATION: actions ist append-only');
END;
CREATE TRIGGER trg_actions_no_delete BEFORE DELETE ON actions
BEGIN
    SELECT RAISE(ABORT, 'CHANNEL_B_MUTATION: actions ist append-only');
END;

CREATE VIEW channel_reconciliation AS
SELECT a.run_id, a.agent_id, a.claim_id, a.id AS assertion_id,
       a.claim, a.evidence_id, a.source_key, a.source_id, a.required,
       b.id AS action_id, b.phase AS action_phase,
       CASE WHEN b.id IS NULL THEN 'unconfirmed' ELSE 'confirmed' END
       AS evidence_state
FROM assertions a
LEFT JOIN actions b
       ON b.run_id = a.run_id
      AND b.source_key IS NOT NULL
      AND b.source_key = a.source_key;

-- --- Reparaturbaseline ----------------------------------------------------
-- Haelt fest, was in der verworfenen Ausgabe nachweislich stand. Ohne
-- diese Spalte kann der Hook-Reparaturpfad die Verbote aus §8 nicht
-- pruefen: Er sieht nur die neue Ausgabe, nicht die alte.
ALTER TABLE repairs ADD COLUMN baseline_json TEXT;

-- --- Sichten neu ----------------------------------------------------------
CREATE VIEW run_overview AS
SELECT r.run_id, r.experiment_id, r.task_id, r.replicate, r.seed,
       r.batch_id, r.workflow_condition, r.domain,
       r.provider, r.model_version, r.output_enforcement, r.status,
       r.context_state, r.is_legacy, r.legacy_status_v1,
       r.started_at, r.finished_at,
       (SELECT COUNT(*) FROM claims c WHERE c.run_id = r.run_id) AS claim_count,
       (SELECT COUNT(*) FROM claims c WHERE c.run_id = r.run_id
         AND c.status = 'VERIFIED') AS verified_count,
       (SELECT COUNT(*) FROM claims c WHERE c.run_id = r.run_id
         AND c.status = 'BLOCKED') AS blocked_count,
       (SELECT COUNT(*) FROM actions a WHERE a.run_id = r.run_id) AS action_count,
       (SELECT COUNT(*) FROM evidence_registry e WHERE e.run_id = r.run_id)
         AS evidence_count,
       (SELECT COUNT(*) FROM hard_fails h WHERE h.run_id = r.run_id) AS hard_fail_count
FROM runs r;

-- Registry und zugehoeriger Zugriff in einer Zeile. Basis fuer die
-- Auswertung 'welcher Beleg lag vor und wurde er zitiert?'.
CREATE VIEW registered_evidence AS
SELECT e.run_id, e.agent_id, e.evidence_key, e.source_key, e.source_id,
       e.document_version_id, e.unit_id, e.chunk_id, e.structure_anchor,
       e.label, e.anchor_is_fallback, e.content_sha256, e.chunk_text_sha256,
       e.retrieval_run_id, e.retrieved_at,
       a.id AS action_id, a.phase AS action_phase,
       (SELECT COUNT(*) FROM assertions s
         WHERE s.run_id = e.run_id AND s.evidence_id = e.evidence_key)
        AS cited_count
FROM evidence_registry e
LEFT JOIN actions a
       ON a.run_id = e.run_id AND a.evidence_key = e.evidence_key;
"""


def _audit_v1() -> str:
    return _read(AUDIT_BASELINE_SQL)


def _provenance_v1() -> str:
    return _read(PROVENANCE_BASELINE_SQL)


#: (version, description, sql_or_callable)
AUDIT_MIGRATIONS = [
    (1, "audit baseline v1.0 (runs/assertions/actions/chain_head)", _audit_v1),
    (2, "audit v2.0 run-centric, append-only, writer sessions", AUDIT_V2_SQL),
    (3, "audit v3 evidence registry, action FK, repair baseline", AUDIT_V3_SQL),
]

PROVENANCE_MIGRATIONS = [
    (1, "provenance baseline v1.1", _provenance_v1),
    (2, "provenance v2 run attribution", PROVENANCE_V2_SQL),
]


# ---------------------------------------------------------------------------
# Migrationsmaschine
# ---------------------------------------------------------------------------

class MigrationError(RuntimeError):
    pass


def _table_exists(con: sqlite3.Connection, name: str) -> bool:
    return con.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
    ).fetchone() is not None


def _ensure_registry(con: sqlite3.Connection) -> None:
    con.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " version INTEGER PRIMARY KEY,"
        " description TEXT NOT NULL,"
        " applied_at TEXT NOT NULL)"
    )


def current_version(con: sqlite3.Connection) -> int:
    if not _table_exists(con, "schema_migrations"):
        return 0
    row = con.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
    value = row[0] if not isinstance(row, sqlite3.Row) else row["v"]
    return int(value or 0)


def _stamp_legacy(con: sqlite3.Connection, marker_table: str,
                  description: str) -> bool:
    """Vorhandene Datenbank ohne Registry als Version 1 kennzeichnen.

    Ohne diesen Schritt wuerde die Baseline-DDL erneut ausgefuehrt (harmlos,
    weil IF NOT EXISTS) und danach Migration 2 auf einer Datenbank laufen,
    deren Ausgangszustand unbekannt ist. Das ist genau die stille
    Umdeutung, die §4 verbietet.
    """
    if current_version(con) == 0 and _table_exists(con, marker_table):
        _ensure_registry(con)
        con.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, description, applied_at)"
            " VALUES (1, ?, ?)", (description + " [gestempelt, bestehende DB]", _now()))
        con.commit()
        return True
    return False


def backup_database(db_path: str, tag: str) -> str:
    """Ueberpruefbare Sicherung vor der Migration (§4).

    Nutzt die SQLite-Backup-API statt eines Dateikopiervorgangs: Ein
    `cp` waehrend eines offenen WAL-Zustands kann eine Sicherung erzeugen,
    die nur zusammen mit dem -wal gueltig ist. Die Sicherung wird
    anschliessend geoeffnet und mit `integrity_check` geprueft.
    """
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    target = f"{db_path}.backup-{tag}-{stamp}"
    src = sqlite3.connect(db_path)
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
        finally:
            dst.close()
    finally:
        src.close()

    check = sqlite3.connect(target)
    try:
        result = check.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise MigrationError(
                f"Sicherung {target} ist nicht integer: {result}")
    finally:
        check.close()
    return target


def _row_counts(con: sqlite3.Connection) -> dict:
    tables = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'").fetchall()]
    return {t: con.execute(f"SELECT COUNT(*) FROM \"{t}\"").fetchone()[0]
            for t in tables}


def integrity_report(con: sqlite3.Connection) -> dict:
    """`PRAGMA foreign_key_check` und Integritaetscheck (§4)."""
    fk = [tuple(r) for r in con.execute("PRAGMA foreign_key_check").fetchall()]
    integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
    return {"foreign_key_violations": fk, "integrity_check": integrity,
            "ok": not fk and integrity == "ok"}


#: PRAGMA-Anweisungen aus Migrationsskripten entfernen.
#: `PRAGMA journal_mode` ist innerhalb einer Transaktion ein Fehler und
#: `PRAGMA foreign_keys` dort wirkungslos. Beide werden beim
#: Verbindungsaufbau gesetzt, nicht im Migrationsskript.
_PRAGMA_RE = re.compile(r"^[ \t]*PRAGMA[^;]*;[ \t]*$",
                        re.MULTILINE | re.IGNORECASE)


def _strip_pragmas(script: str) -> str:
    return _PRAGMA_RE.sub("", script)


def _sql_literal(text: str) -> str:
    return "'" + str(text).replace("'", "''") + "'"


def _apply(con: sqlite3.Connection, migrations, from_version: int) -> list:
    """Jede Migration laeuft als EINE Transaktion.

    `executescript` committet eine offene Transaktion implizit, bevor es
    startet — ein vorangestelltes `con.execute("BEGIN")` waere also
    wirkungslos und die Migration nicht atomar. Deshalb stehen BEGIN und
    COMMIT im Skript selbst, zusammen mit dem Registry-Eintrag.
    """
    applied = []
    for version, description, sql in migrations:
        if version <= from_version:
            continue
        body = _strip_pragmas(sql() if callable(sql) else sql)
        script = (
            "BEGIN;\n" + body + "\n"
            "INSERT INTO schema_migrations (version, description, applied_at) "
            f"VALUES ({int(version)}, {_sql_literal(description)}, "
            f"{_sql_literal(_now())});\n"
            "COMMIT;\n"
        )
        # Fremdschluessel waehrend des Tabellenneuaufbaus aus: Das
        # 12-Schritt-Verfahren von SQLite verlangt das ausdruecklich.
        con.execute("PRAGMA foreign_keys = OFF")
        try:
            con.executescript(script)
        except Exception:
            con.rollback()
            raise
        finally:
            con.execute("PRAGMA foreign_keys = ON")
        applied.append((version, description))
    return applied


def _migrate(db_path: str, migrations, marker_table: str, tag: str,
             target_version: int) -> dict:
    parent = os.path.dirname(os.path.abspath(db_path))
    if parent:
        os.makedirs(parent, exist_ok=True)

    existed = os.path.exists(db_path) and os.path.getsize(db_path) > 0
    con = sqlite3.connect(db_path, timeout=30)
    con.row_factory = sqlite3.Row
    try:
        con.execute("PRAGMA journal_mode = WAL")
        _ensure_registry(con)
        stamped = _stamp_legacy(con, marker_table, migrations[0][1])
        version = current_version(con)

        pending = [m for m in migrations if m[0] > version]
        report = {"db_path": db_path, "version_before": version,
                  "legacy_stamped": stamped, "backup_path": None,
                  "applied": [], "counts_before": None, "counts_after": None}

        if not pending:
            report["version_after"] = version
            report["integrity"] = integrity_report(con)
            return report

        if existed:
            report["counts_before"] = _row_counts(con)
            # Sicherung vor der ersten Aenderung. WAL-Inhalt zuerst in die
            # Hauptdatei schreiben, damit die Sicherung vollstaendig ist.
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            report["backup_path"] = backup_database(db_path, tag)

        report["applied"] = _apply(con, migrations, version)
        report["version_after"] = current_version(con)
        report["counts_after"] = _row_counts(con)
        report["integrity"] = integrity_report(con)

        if report["version_after"] != target_version:
            raise MigrationError(
                f"Zielversion {target_version} nicht erreicht: "
                f"{report['version_after']}")
        if not report["integrity"]["ok"]:
            raise MigrationError(
                f"Integritaetspruefung nach Migration fehlgeschlagen: "
                f"{report['integrity']}")
        return report
    finally:
        con.close()


def migrate_audit(db_path: str) -> dict:
    return _migrate(db_path, AUDIT_MIGRATIONS, "runs", "audit",
                    AUDIT_SCHEMA_VERSION)


def migrate_provenance(db_path: str) -> dict:
    return _migrate(db_path, PROVENANCE_MIGRATIONS, "sources", "provenance",
                    PROVENANCE_SCHEMA_VERSION)


def connection_path(con: sqlite3.Connection) -> str:
    for _, name, path in con.execute("PRAGMA database_list").fetchall():
        if name == "main":
            return path or ""
    return ""                                                 # pragma: no cover


def ensure_provenance(con: sqlite3.Connection) -> int:
    """Provenance-Schema auf einer bereits offenen Verbindung sicherstellen.

    `store.connect()` haelt die Verbindung; ein zweiter Verbindungsaufbau
    zur Migration wuerde in WAL-Modus mit derselben Datei konkurrieren.

    Auch dieser Pfad sichert vor jeder tatsaechlichen Aenderung und prueft
    danach Fremdschluessel und Integritaet — eine Migration ohne Sicherung
    gibt es nicht, unabhaengig davon, wer sie ausloest.
    """
    _ensure_registry(con)
    _stamp_legacy(con, "sources", PROVENANCE_MIGRATIONS[0][1])
    version = current_version(con)
    pending = [m for m in PROVENANCE_MIGRATIONS if m[0] > version]
    if not pending:
        return version

    path = connection_path(con)
    if path and os.path.exists(path) and os.path.getsize(path) > 0 and version:
        con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        backup_database(path, "provenance")

    _apply(con, PROVENANCE_MIGRATIONS, version)
    report = integrity_report(con)
    if not report["ok"]:
        raise MigrationError(
            f"Integritaetspruefung nach Provenance-Migration fehlgeschlagen: "
            f"{report}")
    return current_version(con)


def live_schema(db_path: str) -> str:
    """Aktueller Stand — das ist die einzige verlaessliche Auskunft."""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "SELECT type, name, sql FROM sqlite_master "
            "WHERE sql IS NOT NULL ORDER BY "
            "CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 "
            "WHEN 'view' THEN 2 ELSE 3 END, name").fetchall()
        return "\n".join(f"-- {t}: {n}\n{s};" for t, n, s in rows)
    finally:
        con.close()
