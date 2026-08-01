"""Versionierte Kanonisierung.

Ihr Einwand ist zwingend: Ohne Version kann eine spätere Änderung der
Normalisierungsregel denselben Feldnamen bei anderer Semantik erzeugen.
Zwei kanonische Hashes wären dann unvergleichbar, ohne dass es auffällt.

Deshalb wird die Regel selbst zum versionierten Objekt, und die Version
wandert mit in `document_versions`.

PRÄZISIERUNG zu Ihrer Relation:

    gleicher byte_sha256  ⇒  gleicher canonical_sha256

gilt nur bei FESTER canonicalizer_version. Über Versionsgrenzen hinweg
bricht die Implikation — was genau der Grund für die Versionierung ist.
Ein Vergleich kanonischer Hashes ist daher nur innerhalb einer Version
zulässig; das gehört in jede Auswertung als Filterbedingung.
"""

import re

from identity import canonical_json, sha256_text

# ---------------------------------------------------------------------------
# ipynb-scientific-content
# ---------------------------------------------------------------------------

IPYNB_SPEC = {
    "canonicalizer_name": "ipynb-scientific-content",
    "canonicalizer_version": "1.0.0",
    "included": ["cell_type", "source", "normalized_outputs"],
    "excluded": [
        "execution_count", "cell_metadata", "notebook_metadata",
        "output_metadata", "output_transient", "ansi_escapes",
    ],
    # Bewusst NICHT normalisiert — mit Begründung, damit die Lücke
    # dokumentiert und nicht bloss vergessen ist:
    "known_unnormalized": [
        "html_dom_ids",       # zufällige IDs in text/html-Outputs
        "widget_state",       # Jupyter-Widget-Referenzen
        "image_bytes",        # siehe unten
    ],
}

ANSI = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

# Entscheidung zu image_bytes: Bilddaten bleiben IM kanonischen Hash.
# Begründung: Ein anderer Plot ist eine andere Messung. Würde man Bilder
# ausschliessen, gälte eine Zelle, deren Datenreihe sich geändert hat,
# deren Textoutput aber gleich blieb, als inhaltlich unverändert — genau
# der Fehler, den wir in v1 beim Output gerade behoben haben.
# PREIS: Ein reines Neuausführen ohne Datenänderung kann durch
# Rendering-Unterschiede (Matplotlib-/Fontversion) eine neue kanonische
# Fassung erzeugen. Das ist Rauschen, aber Rauschen in die sichere
# Richtung — es meldet zu viel, nicht zu wenig.
INCLUDE_IMAGE_BYTES = True


def _strip_ansi(value):
    if isinstance(value, str):
        return ANSI.sub("", value)
    if isinstance(value, list):
        return [_strip_ansi(v) for v in value]
    return value


def normalize_output(output: dict) -> dict:
    """Volatile Bestandteile eines Notebook-Outputs entfernen."""
    otype = output.get("output_type")
    out = {"output_type": otype}

    if otype == "stream":
        out["name"] = output.get("name")
        out["text"] = _strip_ansi(output.get("text"))

    elif otype in ("execute_result", "display_data"):
        data = {}
        for mime, payload in (output.get("data") or {}).items():
            if mime.startswith("image/") and not INCLUDE_IMAGE_BYTES:
                continue
            data[mime] = _strip_ansi(payload)
        out["data"] = data
        # metadata und transient bleiben aussen vor

    elif otype == "error":
        out["ename"] = output.get("ename")
        out["evalue"] = output.get("evalue")
        out["traceback"] = _strip_ansi(output.get("traceback"))

    return out


def canonicalize_notebook(nb: dict) -> tuple:
    """Gibt (canonical_text, spec) zurück."""
    cells = []
    for cell in nb.get("cells", []):
        source = cell.get("source")
        cells.append({
            "cell_type": cell.get("cell_type"),
            "source": "".join(source) if isinstance(source, list) else source,
            "normalized_outputs": [
                normalize_output(o) for o in cell.get("outputs", [])
            ],
        })
    return canonical_json({"spec": IPYNB_SPEC, "cells": cells}), IPYNB_SPEC


# ---------------------------------------------------------------------------
# pptx-extracted-content
# ---------------------------------------------------------------------------

PPTX_SPEC = {
    "canonicalizer_name": "pptx-extracted-content",
    "canonicalizer_version": "1.0.0",
    "included": ["reading_order_text", "omml_latex", "notes"],
    "excluded": ["shape_ids", "theme", "revision_metadata", "timestamps"],
    "known_unnormalized": ["image_bytes", "embedded_fonts"],
}


def canonicalize_units(unit_texts: list, spec: dict) -> tuple:
    return canonical_json({"spec": spec, "units": unit_texts}), spec


def canonical_hash(canonical_text: str) -> str:
    return sha256_text(canonical_text)
