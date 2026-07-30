"""Schritt 1 — reine Identitätsfunktionen.

Bewusst ohne Datenbank, ohne ChromaDB, ohne Dateisystem-Nebenwirkungen
ausser dem Lesen. Jede Funktion ist eine Abbildung von Eingabe auf
Bezeichner und damit isoliert testbar. Das ist die Voraussetzung dafür,
die Abnahmekriterien 1–7 ohne laufende Infrastruktur zu prüfen.
"""

import hashlib
import json
import os

CHUNK = 1 << 20


# ---------------------------------------------------------------------------
# Hashes
# ---------------------------------------------------------------------------

def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canonical_json(data) -> str:
    """Kanonische Serialisierung: sortierte Schlüssel, feste Separatoren,
    kein ASCII-Escaping. Zwei semantisch gleiche Konfigurationen ergeben
    denselben String und damit denselben Hash."""
    return json.dumps(data, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def config_hash(data) -> str:
    return sha256_text(canonical_json(data))


# ---------------------------------------------------------------------------
# Bezeichner
# ---------------------------------------------------------------------------

def make_document_version_id(byte_sha256: str) -> str:
    return f"dv:{byte_sha256}"


def make_unit_id(document_version_id: str, structure_anchor: str,
                 content_sha256: str) -> str:
    return "u:" + sha256_text(
        f"{document_version_id}|{structure_anchor}|{content_sha256}")


def make_evidence_key(source_id: str, structure_anchor: str,
                      content_sha256: str) -> str:
    """VERSIONSÜBERGREIFENDE Evidenzidentität.

    `unit_id` enthält die document_version_id und ist damit an eine
    Dateifassung gebunden. Das ist für ein Audit richtig — ein Beleg gilt
    immer relativ zu einer Fassung — hat aber eine Konsequenz, die
    ausgesprochen werden muss: Jede Byteänderung, auch reines Umsortieren,
    erzeugt neue unit_ids und damit neue chunk_ids.

    Für die Frage 'ist das dieselbe Evidenz wie vorher?' braucht es daher
    einen zweiten, versionsfreien Schlüssel. Genau das ist evidence_key.

    Arbeitsteilung:
        unit_id       Diese Stelle in DIESER Dateifassung.
        evidence_key  Dieser Inhalt an dieser Strukturstelle, fassungsfrei.
    """
    return "ev:" + sha256_text(
        f"{source_id}|{structure_anchor}|{content_sha256}")


def make_chunk_id(segments: list, text_sha256: str,
                  chunker_config_hash: str) -> str:
    """Identität eines — ggf. zusammengesetzten — Chunks.

    Der Chunk ist identisch, wenn dieselben Einheiten in denselben
    Ausschnitten und derselben Reihenfolge denselben Text ergeben, bei
    derselben Chunker-Konfiguration.

    ENTSCHEIDUNG zur Konfiguration: Es geht der Hash der VOLLSTÄNDIGEN
    Konfiguration ein, nicht nur der im Einzelfall wirksamen Parameter.
    'Relevante Konfiguration' liesse sich nur pro Dokument bestimmen —
    `respect_heading_boundaries` wirkt in einem Notebook ohne Überschriften
    nicht, in einem anderen schon. Ein von der Eingabe abhängiger
    Identitätsbegriff wäre nicht mehr lokal prüfbar. Der Preis ist
    Überempfindlichkeit: Ein Parameterwechsel ohne Wirkung erzeugt neue
    Chunk-IDs. Das meldet zu viel, nicht zu wenig.
    """
    payload = {
        "segments": [
            {
                "unit_id": s["unit_id"],
                "unit_char_start": s["unit_char_start"],
                "unit_char_end": s["unit_char_end"],
                "segment_ordinal": s["segment_ordinal"],
            }
            for s in segments
        ],
        "text_sha256": text_sha256,
        "chunker_config_hash": chunker_config_hash,
    }
    return "chk:" + sha256_text(canonical_json(payload))


def make_source_id(scheme: str, ident: str) -> str:
    """Logische Quellidentität, NICHT der momentane Inhalt.

    Ein blosser Dateiname ist projektübergreifend kollisionsanfällig —
    'analyse.ipynb' existiert in jedem zweiten Verzeichnis.
    """
    if scheme not in ("local", "zotero", "doi", "url"):
        raise ValueError(f"unbekanntes Quellschema: {scheme}")
    return f"{scheme}:{ident}"


# ---------------------------------------------------------------------------
# Dokumentversion
# ---------------------------------------------------------------------------

def describe_document_version(path: str, source_id: str, parser_name: str,
                              parser_version: str, media_type: str = None,
                              canonical_text: str = None) -> dict:
    """Vollständiger document_versions-Datensatz für eine Datei.

    canonical_text ist optional und ergänzt den Byte-Hash, er ersetzt ihn
    nicht. Grund: .ipynb-Dateien ändern ihre Bytes bei jedem Speichern
    (execution_count, Kernel-Metadaten), auch wenn inhaltlich nichts
    geschieht. Der Byte-Hash beantwortet 'exakt dieselbe Datei?', der
    kanonische Hash 'derselbe Inhalt?'. Beide Fragen sind legitim und
    verschieden.
    """
    byte_sha = sha256_file(path)
    stat = os.stat(path)
    from datetime import datetime, timezone
    return {
        "document_version_id": make_document_version_id(byte_sha),
        "source_id": source_id,
        "byte_sha256": byte_sha,
        "byte_size": stat.st_size,
        "modified_at": datetime.fromtimestamp(
            stat.st_mtime, timezone.utc).isoformat(timespec="seconds"),
        "ingested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "media_type": media_type,
        "parser_name": parser_name,
        "parser_version": parser_version,
        "canonical_sha256": sha256_text(canonical_text) if canonical_text else None,
    }
