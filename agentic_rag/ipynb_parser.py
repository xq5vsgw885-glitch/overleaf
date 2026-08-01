"""Pairing-Parser für Jupyter Notebooks — Locator v2.1.

Neu: strikte Trennung von

    content_text   fachlicher Inhalt, Basis für Chunk-Offsets und Hash
    rendered_text  content_text mit vorangestelltem Locator-Header

Chunks werden ausschliesslich aus `content_text` gebildet. Enthielte die
Offset-Basis Locator-Kommentare, würden `char_start`/`char_end` auf
Syntax statt auf Inhalt zeigen und wären beim kleinsten Formatwechsel
ungültig.

ABWÄGUNG, die ich offenlegen möchte: Die Code-Fences ```python bleiben
Teil von `content_text`. Sie sind Darstellungssyntax, aber sie tragen bei
einer Code-Zelle Bedeutung — ohne sie wäre `print(x)` nicht mehr vom
Ergebnis `2.0` zu unterscheiden, sobald beides in einem flachen String
steht. Wer sie später entfernen will, muss stattdessen ein strukturiertes
Feld einführen; ein blosses Weglassen wäre Informationsverlust.
"""

import json

from canonicalize import canonical_hash, canonicalize_notebook
from identity import (canonical_json, describe_document_version,
                      make_source_id, sha256_text)
from locators import notebook_locator

PARSER_NAME = "ipynb-pairing"
PARSER_VERSION = "2.1"
TEXT_MIMES = ("text/plain", "text/latex", "text/markdown")


def _joined(value) -> str:
    return "".join(value) if isinstance(value, list) else (value or "")


def _render_outputs(outputs: list, warnings: list) -> str:
    blocks = []
    for out in outputs:
        otype = out.get("output_type")

        if otype == "stream":
            blocks.append(f"[{out.get('name', 'stdout')}]\n"
                          f"{_joined(out.get('text'))}")

        elif otype in ("execute_result", "display_data"):
            data = out.get("data", {})
            placed = False
            for mime in TEXT_MIMES:
                if mime in data:
                    blocks.append(f"[{mime}]\n{_joined(data[mime])}")
                    placed = True
                    break
            for mime in data:
                if mime.startswith("image/"):
                    payload = _joined(data[mime])
                    alt = _joined(data.get("text/plain", "")).strip()
                    blocks.append(
                        f"[ABBILDUNG {mime}, {len(payload)} B, "
                        f"sha={sha256_text(payload)[:12]}"
                        + (f", alt: {alt[:120]}" if alt else "") + "]")
                    warnings.append(
                        f"Grafik-Output ({mime}) nicht in Text überführbar — "
                        f"als Fundstelle indexiert, nicht als Inhalt")
                    placed = True
            if not placed:
                warnings.append(f"Output-MIME nicht abgedeckt: {list(data)}")

        elif otype == "error":
            blocks.append(f"[error: {out.get('ename')}]\n"
                          + "\n".join(out.get("traceback", [])))

    return "\n".join(blocks).rstrip()


def parse_notebook(path: str, source_id: str = None):
    """Gibt (document_version, units, config) zurück."""
    source_id = source_id or make_source_id("local", path)
    with open(path, "r", encoding="utf-8") as fh:
        nb = json.load(fh)

    major = nb.get("nbformat", 4)
    minor = nb.get("nbformat_minor", 0)
    has_ids = (major, minor) >= (4, 5)

    canonical_text, spec = canonicalize_notebook(nb)

    docver = describe_document_version(
        path, source_id, PARSER_NAME, PARSER_VERSION,
        media_type="application/x-ipynb+json")
    docver.update({
        "canonical_sha256": canonical_hash(canonical_text),
        "canonicalizer_name": spec["canonicalizer_name"],
        "canonicalizer_version": spec["canonicalizer_version"],
        "canonicalizer_spec_json": canonical_json(spec),
    })
    dv_id = docver["document_version_id"]

    units = []
    for idx, cell in enumerate(nb.get("cells", []), start=1):
        ctype = cell.get("cell_type", "raw")
        src = _joined(cell.get("source"))
        warnings: list = []

        if ctype == "code":
            rendered = _render_outputs(cell.get("outputs", []), warnings)
            paired = bool(rendered)
            content_text = f"```python\n{src.rstrip()}\n```"
            if rendered:
                content_text += f"\n\nOutput:\n```\n{rendered}\n```"
            else:
                warnings.append("Code-Zelle ohne Output — Methodik, keine Evidenz")
        else:
            if not src.strip():
                continue
            paired = False
            content_text = src.rstrip()

        loc = notebook_locator(
            source_id=source_id, document_version_id=dv_id, index=idx,
            cell_type=ctype, content_text=content_text,
            nb_cell_id=cell.get("id") if has_ids else None, paired=paired)
        loc.warnings = loc.warnings + warnings

        units.append({
            "locator": loc.to_dict(),
            "content_text": content_text,
            "rendered_text": f"{loc.header()}\n{content_text}",
            "cell_type": ctype,
            "paired": paired,
        })

    config = {"parser": PARSER_NAME, "parser_version": PARSER_VERSION,
              "pair_outputs": True, "image_ocr": False,
              "nbformat": f"{major}.{minor}"}
    return docver, units, config
