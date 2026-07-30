"""Schritt 4 — Manifestpersistierung.

Zwei Eigenschaften, die nicht verhandelbar sind:

ATOMAR      Ein Manifest wird vollständig oder gar nicht geschrieben.
            Eine halb persistierte Dokumentversion — Einheiten ohne Lauf,
            Lauf ohne Einheiten — ist im Audit schlimmer als keine, weil
            sie wie ein vollständiger Befund aussieht.

IDEMPOTENT  Dieselbe Datei zweimal eingelesen erzeugt keine zweite
            Dokumentversion und keine doppelten Einheiten. `unit_id` ist
            aus (dv, anchor, content) abgeleitet und damit stabil; ein
            erneuter Lauf wird als weiterer `ingestion_run` protokolliert,
            aber die Einheiten werden nicht dupliziert.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

import migrations

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                      "schema_provenance.sql")


def _default_db() -> str:
    return os.environ.get("PROVENANCE_DB_PATH", "./.audit/provenance.db")


#: Beibehalten fuer Aufrufer, die die Konstante importieren. Neuer Code
#: verwendet `_default_db()`, damit die Umgebung nach dem Import noch wirkt.
DEFAULT_DB = _default_db()


def connect(db_path: str = None) -> sqlite3.Connection:
    """Verbindung zum Provenienzregister, Schema ueber die Migrationsregistry.

    AENDERUNG: Frueher wurde hier bei JEDEM Verbindungsaufbau
    `schema_provenance.sql` ausgefuehrt. Das war ein implizites Upgrade
    ohne Versionsbegriff — und weil jedes Statement `IF NOT EXISTS` traegt,
    eines, das bei einer echten Schemaaenderung stillschweigend nichts
    getan haette. Zustaendig ist jetzt ausschliesslich `migrations.py`.
    """
    db_path = db_path or _default_db()
    parent = os.path.dirname(os.path.abspath(db_path))
    os.makedirs(parent, exist_ok=True)
    con = sqlite3.connect(db_path, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    migrations.ensure_provenance(con)
    con.execute("PRAGMA foreign_keys = ON")
    return con


def _source_type(source_id: str) -> str:
    return source_id.split(":", 1)[0]


def persist_manifest(manifest: dict, con: sqlite3.Connection) -> dict:
    """Schreibt ein Manifest in einer einzigen Transaktion."""
    doc = manifest["document"]
    ing = manifest["ingestion"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    report = {"source_inserted": False, "version_inserted": False,
              "units_inserted": 0, "units_existing": 0,
              "ingestion_run_id": ing["ingestion_run_id"]}

    try:
        con.execute("BEGIN")

        cur = con.execute(
            "INSERT OR IGNORE INTO sources "
            "(source_id, source_type, canonical_path, created_at) "
            "VALUES (?,?,?,?)",
            (doc["source_id"], _source_type(doc["source_id"]),
             doc.get("canonical_path"), now))
        report["source_inserted"] = cur.rowcount > 0

        cur = con.execute(
            "INSERT OR IGNORE INTO document_versions "
            "(document_version_id, source_id, byte_sha256, byte_size, "
            " modified_at, ingested_at, media_type, parser_name, "
            " parser_version, canonical_sha256, canonicalizer_name, "
            " canonicalizer_version, canonicalizer_spec_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (doc["document_version_id"], doc["source_id"], doc["byte_sha256"],
             doc["byte_size"], doc.get("modified_at"), doc["ingested_at"],
             doc.get("media_type"), doc["parser_name"], doc["parser_version"],
             doc.get("canonical_sha256"), doc.get("canonicalizer_name"),
             doc.get("canonicalizer_version"),
             doc.get("canonicalizer_spec_json")))
        report["version_inserted"] = cur.rowcount > 0

        con.execute(
            "INSERT INTO ingestion_runs "
            "(ingestion_run_id, document_version_id, started_at, finished_at, "
            " status, parser_name, parser_version, config_json, config_hash, "
            " unit_count, warning_count) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (ing["ingestion_run_id"], ing["document_version_id"],
             ing["started_at"], ing["finished_at"], ing["status"],
             ing["parser_name"], ing["parser_version"],
             json.dumps(ing["config_json"], sort_keys=True, ensure_ascii=False),
             ing["config_hash"], ing["unit_count"], ing["warning_count"]))

        for unit in manifest["units"]:
            loc = unit["locator"]
            cur = con.execute(
                "INSERT OR IGNORE INTO ingestion_units "
                "(unit_id, ingestion_run_id, document_version_id, "
                " structure_anchor, evidence_key, anchor_is_fallback, label, kind, "
                " content_sha256, content_text, rendered_text, locator_json, "
                " warnings_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (loc["unit_id"], ing["ingestion_run_id"],
                 loc["document_version_id"], loc["structure_anchor"],
                 loc["evidence_key"],
                 int(loc.get("anchor_is_fallback", False)), loc["label"],
                 loc["kind"], loc["content_sha256"], unit["content_text"],
                 unit["rendered_text"],
                 json.dumps(loc, sort_keys=True, ensure_ascii=False),
                 json.dumps(loc["warnings"], ensure_ascii=False)))
            if cur.rowcount > 0:
                report["units_inserted"] += 1
            else:
                report["units_existing"] += 1

        con.commit()
    except Exception:
        con.rollback()
        raise

    return report


def persist_chunks(chunks: list, con: sqlite3.Connection) -> dict:
    """Chunks und ihre Segmente atomar schreiben.

    Ein Chunk ohne seine Segmente wäre ein Retrievalobjekt ohne
    Provenienz — genau der Zustand, den das Segmentmodell verhindern soll.
    Deshalb eine Transaktion über beide Tabellen.
    """
    report = {"chunks_inserted": 0, "chunks_existing": 0, "segments": 0}
    try:
        con.execute("BEGIN")
        for chunk in chunks:
            cur = con.execute(
                "INSERT OR IGNORE INTO chunks "
                "(chunk_id, ordinal, text_sha256, text, chunker_name, "
                " chunker_version, chunker_config_json, chunker_config_hash, "
                " unit_count, is_composite, is_partial) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (chunk["chunk_id"], chunk["ordinal"], chunk["text_sha256"],
                 chunk["text"], chunk["chunker_name"], chunk["chunker_version"],
                 chunk["chunker_config_json"], chunk["chunker_config_hash"],
                 chunk["unit_count"], chunk["is_composite"],
                 chunk.get("is_partial", 0)))
            if cur.rowcount == 0:
                report["chunks_existing"] += 1
                continue
            report["chunks_inserted"] += 1
            for seg in chunk["segments"]:
                con.execute(
                    "INSERT INTO chunk_segments "
                    "(chunk_id, segment_ordinal, unit_id, unit_char_start, "
                    " unit_char_end, chunk_char_start, chunk_char_end) "
                    "VALUES (?,?,?,?,?,?,?)",
                    (chunk["chunk_id"], seg["segment_ordinal"], seg["unit_id"],
                     seg["unit_char_start"], seg["unit_char_end"],
                     seg["chunk_char_start"], seg["chunk_char_end"]))
                report["segments"] += 1
        con.commit()
    except Exception:
        con.rollback()
        raise
    return report


def resolve_unit(con: sqlite3.Connection, document_version_id: str,
                 structure_anchor: str) -> dict:
    """Auflösung mit explizitem Status — niemals Fallback auf die aktuelle
    Fassung. Ein Beleg, dessen Dokumentversion fehlt, ist ein Auditbefund,
    keine Gelegenheit zur stillen Korrektur."""
    dv = con.execute(
        "SELECT 1 FROM document_versions WHERE document_version_id = ?",
        (document_version_id,)).fetchone()
    if dv is None:
        return {"resolution_status": "unresolvable",
                "reason": "document_version nicht vorhanden"}

    row = con.execute(
        "SELECT * FROM ingestion_units "
        "WHERE document_version_id = ? AND structure_anchor = ?",
        (document_version_id, structure_anchor)).fetchone()
    if row is None:
        return {"resolution_status": "unit_missing",
                "reason": "Anker in dieser Fassung nicht vorhanden"}

    return {"resolution_status": "resolved", "unit": dict(row)}
