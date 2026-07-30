-- provenance.db — Schema v1.1  ***BASELINE, NICHT DER AKTUELLE STAND***
--
-- DDL der Migrationsversion 1, geladen ausschliesslich von
-- `migrations.py`. `store.connect()` fuehrte diese Datei frueher bei JEDEM
-- Verbindungsaufbau aus; das war ein implizites Upgrade ohne Version und
-- ohne Wirkung (alles IF NOT EXISTS). Jetzt migriert `store.connect()`
-- ueber die Registry. Aktueller Stand: Provenance v2 (Laufzuordnung).
--
--   source → document_version → ingestion_unit → chunk
--
-- Getrennte Laufbegriffe: agent_runs (audit_trail.db), ingestion_runs,
-- retrieval_runs — keine mehrdeutige `run_id`.

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sources (
    source_id           TEXT PRIMARY KEY,   -- local: | zotero: | doi: | url:
    source_type         TEXT NOT NULL,
    canonical_path      TEXT,
    external_id         TEXT,
    created_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS document_versions (
    document_version_id TEXT PRIMARY KEY,   -- dv:<byte_sha256>
    source_id           TEXT NOT NULL REFERENCES sources(source_id),
    byte_sha256         TEXT NOT NULL,
    byte_size           INTEGER NOT NULL,
    modified_at         TEXT,
    ingested_at         TEXT NOT NULL,
    media_type          TEXT,
    parser_name         TEXT NOT NULL,
    parser_version      TEXT NOT NULL,
    -- Kanonische Inhaltsidentität. Die Implikation
    --   gleicher byte_sha256 ⇒ gleicher canonical_sha256
    -- gilt NUR bei fester canonicalizer_version. Jeder Vergleich
    -- kanonischer Hashes muss daher auf die Version filtern.
    canonical_sha256        TEXT,
    canonicalizer_name      TEXT,
    canonicalizer_version   TEXT,
    canonicalizer_spec_json TEXT,
    UNIQUE(source_id, byte_sha256)
);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    ingestion_run_id    TEXT PRIMARY KEY,
    document_version_id TEXT NOT NULL
                        REFERENCES document_versions(document_version_id),
    started_at          TEXT NOT NULL,
    finished_at         TEXT,
    status              TEXT NOT NULL,      -- ok | degraded | failed
    parser_name         TEXT NOT NULL,
    parser_version      TEXT NOT NULL,
    config_json         TEXT NOT NULL,
    config_hash         TEXT NOT NULL,
    unit_count          INTEGER,
    warning_count       INTEGER,
    error_message       TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_units (
    unit_id             TEXT PRIMARY KEY,
    ingestion_run_id    TEXT NOT NULL
                        REFERENCES ingestion_runs(ingestion_run_id),
    document_version_id TEXT NOT NULL
                        REFERENCES document_versions(document_version_id),
    structure_anchor    TEXT NOT NULL,
    -- fassungsfreie Evidenzidentitaet, siehe identity.make_evidence_key
    evidence_key        TEXT NOT NULL,
    anchor_is_fallback  INTEGER NOT NULL DEFAULT 0,
    label               TEXT NOT NULL,      -- nur Darstellung
    kind                TEXT NOT NULL,
    content_sha256      TEXT NOT NULL,
    -- Offset-Basis für Chunks. Enthält KEINE Locator-Syntax.
    content_text        TEXT NOT NULL,
    -- Serialisierung mit Locator-Header. Nie Offset-Basis, nie Embedding-Input.
    rendered_text       TEXT NOT NULL,
    locator_json        TEXT NOT NULL,
    warnings_json       TEXT NOT NULL,
    UNIQUE(document_version_id, structure_anchor)
);

-- ---------------------------------------------------------------------------
-- Chunk als CONTAINER von Segmenten. Die Provenienzeinheit ist das Segment.
-- Ein Chunk hat bewusst KEINE unit_id: Die Beziehung ist n:m und wird
-- ausschliesslich über chunk_segments geführt.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id             TEXT PRIMARY KEY,
    ordinal              INTEGER NOT NULL,
    text_sha256          TEXT NOT NULL,
    text                 TEXT NOT NULL,     -- exakt der Embedding-Text
    chunker_name         TEXT NOT NULL,
    chunker_version      TEXT NOT NULL,
    chunker_config_json  TEXT NOT NULL,
    chunker_config_hash  TEXT NOT NULL,
    unit_count           INTEGER NOT NULL,
    is_composite         INTEGER NOT NULL CHECK (is_composite IN (0, 1)),
    -- 1, wenn ein Segment nur einen Teilbereich seiner Einheit abdeckt
    -- (Intra-Unit-Split). is_composite allein kann diesen Fall nicht
    -- von 'ganze Einheit' unterscheiden.
    is_partial           INTEGER NOT NULL DEFAULT 0 CHECK (is_partial IN (0, 1))
);

CREATE TABLE IF NOT EXISTS chunk_segments (
    chunk_id             TEXT NOT NULL REFERENCES chunks(chunk_id),
    segment_ordinal      INTEGER NOT NULL,
    unit_id              TEXT NOT NULL REFERENCES ingestion_units(unit_id),
    -- Offsets in ingestion_units.content_text
    unit_char_start      INTEGER NOT NULL,
    unit_char_end        INTEGER NOT NULL,
    -- Offsets in chunks.text
    chunk_char_start     INTEGER NOT NULL,
    chunk_char_end       INTEGER NOT NULL,
    PRIMARY KEY (chunk_id, segment_ordinal)
);

-- ---------------------------------------------------------------------------
-- Evidenzadresse einer Assertion. Bewusst auf SEGMENT-Ebene: Ein Treffer
-- auf einen zusammengesetzten Chunk stützt in der Regel nur einen Teil
-- davon. evidence_char_* beziehen sich auf content_text der Einheit, nicht
-- auf den Chunk — sonst würde die Evidenzadresse bei einer späteren
-- anderen Chunkzusammensetzung ungültig.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS assertion_evidence (
    assertion_id         TEXT NOT NULL,
    retrieval_run_id     TEXT,
    chunk_id             TEXT NOT NULL,
    segment_ordinal      INTEGER NOT NULL,
    unit_id              TEXT NOT NULL,
    evidence_char_start  INTEGER,
    evidence_char_end    INTEGER,
    PRIMARY KEY (assertion_id, chunk_id, segment_ordinal)
);

CREATE TABLE IF NOT EXISTS retrieval_runs (
    retrieval_run_id        TEXT PRIMARY KEY,
    agent_id                TEXT,
    query_text              TEXT NOT NULL,
    query_sha256            TEXT NOT NULL,
    index_id                TEXT NOT NULL,
    index_snapshot_sha256   TEXT NOT NULL,  -- Hash des Manifests, nicht der
                                            -- physischen ChromaDB-Dateien
    embedding_provider      TEXT NOT NULL,
    embedding_model         TEXT NOT NULL,
    embedding_model_version TEXT NOT NULL DEFAULT 'unknown',
    embedding_dimension     INTEGER,
    retrieval_method        TEXT NOT NULL,
    top_k                   INTEGER NOT NULL,
    filters_json            TEXT NOT NULL,
    parameters_json         TEXT NOT NULL,
    started_at              TEXT NOT NULL,
    finished_at             TEXT,
    status                  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS retrieval_hits (
    retrieval_run_id    TEXT NOT NULL
                        REFERENCES retrieval_runs(retrieval_run_id),
    rank                INTEGER NOT NULL,
    chunk_id            TEXT NOT NULL,
    score               REAL,
    distance            REAL,
    rerank_score        REAL,
    PRIMARY KEY (retrieval_run_id, rank)
);

CREATE INDEX IF NOT EXISTS idx_dv_source   ON document_versions(source_id);
CREATE INDEX IF NOT EXISTS idx_dv_canon    ON document_versions(canonical_sha256, canonicalizer_version);
CREATE INDEX IF NOT EXISTS idx_unit_dv     ON ingestion_units(document_version_id);
CREATE INDEX IF NOT EXISTS idx_unit_anchor ON ingestion_units(structure_anchor);
CREATE INDEX IF NOT EXISTS idx_unit_evkey ON ingestion_units(evidence_key);
CREATE INDEX IF NOT EXISTS idx_seg_unit   ON chunk_segments(unit_id);
CREATE INDEX IF NOT EXISTS idx_seg_chunk  ON chunk_segments(chunk_id);
CREATE INDEX IF NOT EXISTS idx_ae_unit    ON assertion_evidence(unit_id);
CREATE INDEX IF NOT EXISTS idx_hits_chunk  ON retrieval_hits(chunk_id);

-- ---------------------------------------------------------------------------
-- KORREKTUR zu Ihrem CASE-Vorschlag.
--
-- Ihre Formulierung setzte INNER JOINs voraus. Damit kann der Zweig
-- 'unresolvable' nie feuern: Bei gebrochener Kette liefert der Join gar
-- keine Zeile, statt einer Zeile mit NULL. Für ein Audit ist die stumme
-- Abwesenheit schlechter als NULL — sie sieht aus wie 'nichts zu melden'.
--
-- Die Auflösung muss deshalb von der REFERENZIERENDEN Seite ausgehen und
-- nach aussen LEFT JOINen. Basis ist hier retrieval_hits, weil dort die
-- Chunk-Referenzen liegen, die später in Assertions münden. Die FK auf
-- chunks ist absichtlich nicht deklariert — ein Treffer auf einen
-- inzwischen entfernten Chunk MUSS speicherbar bleiben, sonst wäre der
-- Auditbefund nicht protokollierbar.
-- ---------------------------------------------------------------------------
CREATE VIEW IF NOT EXISTS hit_resolution AS
SELECT
    h.retrieval_run_id, h.rank, h.chunk_id,
    seg.segment_ordinal, seg.unit_id,
    u.structure_anchor, u.label, u.anchor_is_fallback,
    dv.document_version_id, dv.byte_sha256,
    s.source_id, s.canonical_path,
    CASE
        WHEN c.chunk_id  IS NULL THEN 'chunk_missing'
        WHEN seg.unit_id IS NULL THEN 'segment_missing'
        WHEN u.unit_id   IS NULL THEN 'unit_missing'
        WHEN dv.document_version_id IS NULL THEN 'unresolvable'
        WHEN s.source_id IS NULL THEN 'source_missing'
        ELSE 'resolved'
    END AS resolution_status
FROM retrieval_hits h
LEFT JOIN chunks            c   ON c.chunk_id  = h.chunk_id
LEFT JOIN chunk_segments    seg ON seg.chunk_id = h.chunk_id
LEFT JOIN ingestion_units   u   ON u.unit_id   = seg.unit_id
LEFT JOIN document_versions dv  ON dv.document_version_id = u.document_version_id
LEFT JOIN sources           s   ON s.source_id = dv.source_id;

-- Dokumentseitige Kette auf Segmentebene.
CREATE VIEW IF NOT EXISTS provenance_chain AS
SELECT c.chunk_id, c.is_composite, seg.segment_ordinal,
       seg.unit_char_start, seg.unit_char_end,
       seg.chunk_char_start, seg.chunk_char_end,
       u.unit_id, u.structure_anchor, u.label, u.anchor_is_fallback,
       u.content_sha256, dv.document_version_id, dv.byte_sha256,
       dv.canonical_sha256, dv.canonicalizer_version,
       s.source_id, s.canonical_path
FROM chunks c
JOIN chunk_segments    seg ON seg.chunk_id = c.chunk_id
JOIN ingestion_units   u   ON u.unit_id = seg.unit_id
JOIN document_versions dv  ON dv.document_version_id = u.document_version_id
JOIN sources           s   ON s.source_id = dv.source_id;
