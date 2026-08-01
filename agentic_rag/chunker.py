"""Schritt 5 — deterministischer Chunker über Ingestion-Einheiten.

Tragende Modellentscheidung: Ingestion-Einheiten bleiben atomare
Evidenzobjekte; Retrieval-Chunks sind deterministische Kompositionen
daraus. Die Provenienzeinheit ist das SEGMENT, nicht der Chunk.

Keine LLM-Entscheidung, keine Heuristik mit Zufallsanteil. Gleiche
Einheiten und gleiche Konfiguration ergeben denselben Chunk-Satz.

ZWEI PUNKTE, die Ihre Spezifikation offenlässt und die hier entschieden
werden mussten:

1. TOKENZÄHLUNG. `min_tokens`/`max_tokens` steuern die Fusion und gehen
   damit in die Chunk-Identität ein. Ein echter Tokenizer wäre ein
   verdeckter Provenienz-Eingang: Ein Upgrade von tiktoken änderte die
   Chunkzusammensetzung, ohne dass sich Konfiguration oder Inhalt ändern.
   Deshalb ein deterministischer, versionierter Schätzer, der in der
   Konfiguration steht (`token_estimator`). Wer später einen echten
   Tokenizer einsetzt, MUSS dessen Name und Version dort eintragen.

2. ÜBERSCHRIFTENGRENZE. Ihre Regel 'keine Überschreitung von
   Abschnittsgrenzen' kollidiert mit Ihrer eigenen `paired`-Strategie
   ('Überschrift + unmittelbar folgender Absatz'). Präzisiert: Eine
   Überschrift darf ERSTES Segment eines Fensters sein, aber ein Fenster
   darf keine Überschrift an späterer Position enthalten. Damit bleibt
   die Paarung möglich, ohne dass ein Fenster über einen Abschnitt
   hinweggreift.
"""

import re

from identity import canonical_json, config_hash, make_chunk_id, sha256_text

CHUNKER_NAME = "unit-window"
CHUNKER_VERSION = "1.1.0"

DEFAULT_CONFIG = {
    "strategy": "unit_window",
    "min_tokens": 80,
    "target_tokens": 220,
    # Umbenannt: die Grenze wirkt auf den fertigen Chunk INKLUSIVE
    # Separatoren, nicht nur auf die Summe der Einheiten.
    "max_chunk_tokens": 320,
    "max_units": 4,
    # "keep"  = Variante A: übergrosse Einheit bleibt ungeteilt atomar
    # "split" = Variante B: deterministischer Intra-Unit-Split
    "oversize_unit_strategy": "split",
    "respect_heading_boundaries": True,
    "separator": "\n\n<UNIT_BOUNDARY>\n\n",
    # Versionierter Schätzer statt echtem Tokenizer — siehe Modulkopf.
    "token_estimator": "whitespace-x1.3/1.0.0",
}

HEADING = re.compile(r"^\s{0,3}#{1,6}\s", re.MULTILINE)


def _whitespace_x13_v1(text: str) -> int:
    """whitespace-x1.3/1.0.0 — deterministisch, dokumentiert, versioniert.

    Kein Anspruch auf Übereinstimmung mit einem BPE-Tokenizer. Der Zweck
    ist Reproduzierbarkeit der Fusionsentscheidung, nicht Genauigkeit
    gegenüber einem Modell-Vokabular.
    """
    return int(len(text.split()) * 1.3) + 1


# Ihr Einwand war berechtigt: Die Konfiguration dokumentierte den Schätzer,
# steuerte ihn aber nicht. Ein geänderter Name hätte den config_hash
# verändert, ohne das Verhalten zu ändern — eine Chunk-Identität, die eine
# Rechenvorschrift behauptet, die gar nicht ausgeführt wurde.
TOKEN_ESTIMATORS = {
    "whitespace-x1.3/1.0.0": _whitespace_x13_v1,
}


def get_estimator(name: str):
    try:
        return TOKEN_ESTIMATORS[name]
    except KeyError:
        raise ValueError(
            f"Unbekannter token_estimator: {name!r}. Registriert: "
            f"{sorted(TOKEN_ESTIMATORS)}. Ein nur deklarierter Schätzer "
            f"wäre eine unbelegte Identitätsaussage."
        ) from None


def estimate_tokens(text: str, config: dict = None) -> int:
    name = (config or DEFAULT_CONFIG)["token_estimator"]
    return get_estimator(name)(text)


def is_heading_unit(unit: dict) -> bool:
    return (unit["locator"]["kind"] == "cell"
            and unit.get("cell_type") == "markdown"
            and bool(HEADING.search(unit["content_text"])))


# ---------------------------------------------------------------------------
# Fusionsregel
# ---------------------------------------------------------------------------

def fusion_allowed(window: list, candidate: dict, config: dict) -> bool:
    """Prüft, ob `candidate` an das bestehende Fenster angehängt werden darf."""
    if not window:
        return True
    if len(window) >= config["max_units"]:
        return False

    first, last = window[0], window[-1]

    # gleiche Quelle und gleiche Dokumentversion (Invariante 7)
    if (candidate["locator"]["document_version_id"]
            != first["locator"]["document_version_id"]):
        return False
    if candidate["locator"]["source_id"] != first["locator"]["source_id"]:
        return False

    # keine Überschrift an späterer Position
    if config["respect_heading_boundaries"] and is_heading_unit(candidate):
        return False

    # kompatible Einheitstypen
    if candidate["locator"]["kind"] != first["locator"]["kind"]:
        return False

    # unterschiedliche Auflösungszustände nur explizit
    if (candidate["locator"].get("anchor_is_fallback")
            != last["locator"].get("anchor_is_fallback")):
        return False

    return True


# ---------------------------------------------------------------------------
# Chunkbildung
# ---------------------------------------------------------------------------

def _assemble(window: list, config: dict) -> dict:
    """Segmente, Text und Identität. window: Liste von (unit, start, end)."""
    sep = config["separator"]
    segments, parts, cursor = [], [], 0

    for ordinal, (unit, start, end) in enumerate(window):
        text = unit["content_text"][start:end]
        if ordinal > 0:
            cursor += len(sep)
        segments.append({
            "segment_ordinal": ordinal,
            "unit_id": unit["locator"]["unit_id"],
            "unit_char_start": start,
            "unit_char_end": end,
            "chunk_char_start": cursor,
            "chunk_char_end": cursor + len(text),
        })
        parts.append(text)
        cursor += len(text)

    chunk_text = sep.join(parts)
    text_sha = sha256_text(chunk_text)
    cfg_hash = config_hash(config)
    units = [w[0] for w in window]
    # Entailed durch Variante B: Bei Intra-Unit-Split hat ein Chunk genau
    # eine Einheit, deckt sie aber nur teilweise ab. `is_composite` allein
    # kann diesen Fall nicht mehr von 'ganze Einheit' unterscheiden.
    is_partial = any(
        not (s_["unit_char_start"] == 0
             and s_["unit_char_end"] == len(u["content_text"]))
        for s_, u in zip(segments, units))

    return {
        "chunk_id": make_chunk_id(segments, text_sha, cfg_hash),
        "text": chunk_text,
        "text_sha256": text_sha,
        "chunker_name": CHUNKER_NAME,
        "chunker_version": CHUNKER_VERSION,
        "chunker_config_json": canonical_json(config),
        "chunker_config_hash": cfg_hash,
        "unit_count": len(window),
        "is_composite": int(len(window) > 1),
        "is_partial": int(is_partial),
        "segments": segments,
        "_units": units,
    }


def split_oversize(unit: dict, config: dict) -> list:
    """Deterministischer Intra-Unit-Split: Absatz → Satz → Zeichen.

    Erst hier tragen `unit_char_start`/`unit_char_end` echte Teilbereiche
    statt durchgehend 0:len(text). Das Zwei-Koordinaten-System war bislang
    gebaut und geprüft, aber nie belastet.

    GELTUNGSGRENZE: Der Split respektiert keine Code-Fences. Eine sehr
    lange Code-Zelle kann mitten in einem ```-Block getrennt werden; die
    Teilstücke sind dann kein gültiges Markdown mehr. Die Offsets und
    damit die Provenienz bleiben korrekt, die Darstellung nicht. Für
    fence-bewusstes Trennen braucht es einen Sprachparser — bewusst nicht
    Teil dieser deterministischen ersten Fassung.
    """
    text = unit["content_text"]
    est = get_estimator(config["token_estimator"])
    budget = config["max_chunk_tokens"]

    def cut(start: int, end: int) -> list:
        piece = text[start:end]
        if est(piece) <= budget or end - start <= 1:
            return [(start, end)]
        for pattern in ("\n\n", ". ", " "):
            middle = piece.rfind(pattern, 0, len(piece) // 2 + len(piece) // 4)
            if middle > 0:
                boundary = start + middle + len(pattern)
                return cut(start, boundary) + cut(boundary, end)
        middle = start + (end - start) // 2
        return cut(start, middle) + cut(middle, end)

    return cut(0, len(text))


def chunk_units(units: list, config: dict = None) -> list:
    """Deterministische Fensterbildung in Dokumentreihenfolge.

    1. Übergrosse Einheit ggf. intra-unit teilen (oversize_unit_strategy).
    2. Einheit allein verwenden, wenn sie gross genug ist.
    3. Sonst nachfolgende Einheiten ergänzen, bis target_tokens erreicht.
    4. max_chunk_tokens und max_units begrenzen das Fenster — Separatoren
       eingerechnet, denn sie sind Bestandteil des eingebetteten Textes.
    """
    config = {**DEFAULT_CONFIG, **(config or {})}
    est = get_estimator(config["token_estimator"])
    sep_tokens = est(config["separator"])

    chunks, index = [], 0
    while index < len(units):
        unit = units[index]
        tokens = est(unit["content_text"])
        index += 1

        # (1) Übergrosse Einheit
        if (tokens > config["max_chunk_tokens"]
                and config["oversize_unit_strategy"] == "split"):
            for start, end in split_oversize(unit, config):
                chunks.append(_assemble([(unit, start, end)], config))
            continue

        window = [(unit, 0, len(unit["content_text"]))]

        # (3) Fusion nur, wenn die erste Einheit zu klein ist
        if tokens < config["min_tokens"]:
            while index < len(units):
                candidate = units[index]
                if not fusion_allowed([w[0] for w in window], candidate, config):
                    break
                extra = sep_tokens + est(candidate["content_text"])
                if tokens + extra > config["max_chunk_tokens"]:
                    break
                window.append((candidate, 0, len(candidate["content_text"])))
                tokens += extra
                index += 1
                if tokens >= config["target_tokens"]:
                    break

        chunks.append(_assemble(window, config))

    for ordinal, chunk in enumerate(chunks):
        chunk["ordinal"] = ordinal
    return chunks


# ---------------------------------------------------------------------------
# Serialisierung für Agent und Audit
# ---------------------------------------------------------------------------

def chunk_locator_header(chunk: dict) -> str:
    """Vollständiger Segment-Locator. Gehört NICHT in den Embedding-Text."""
    units = {u["locator"]["unit_id"]: u["locator"] for u in chunk["_units"]}
    lines = [
        "<!-- CHUNK_LOCATOR",
        f"chunk_id={chunk['chunk_id']}",
        f"document_version_id="
        f"{chunk['_units'][0]['locator']['document_version_id']}",
        f"segment_count={len(chunk['segments'])}",
    ]
    for seg in chunk["segments"]:
        loc = units[seg["unit_id"]]
        lines += [
            f"segment[{seg['segment_ordinal']}]:",
            f"  unit_id={seg['unit_id']}",
            f"  anchor={loc['structure_anchor']}",
            f"  label={loc['label']}",
            f"  unit_range={seg['unit_char_start']}:{seg['unit_char_end']}",
            f"  chunk_range={seg['chunk_char_start']}:{seg['chunk_char_end']}",
        ]
        if loc.get("anchor_is_fallback"):
            lines.append("  anchor_stability=fallback")
    lines.append("END_CHUNK_LOCATOR -->")
    return "\n".join(lines)


def serialize_for_agent(chunk: dict) -> str:
    return f"{chunk_locator_header(chunk)}\n{chunk['text']}"


def embedding_text(chunk: dict) -> str:
    """Der an das Embedding-Modell übergebene Text. Ohne Locator-Syntax."""
    return chunk["text"]
