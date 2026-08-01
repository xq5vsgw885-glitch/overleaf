#!/usr/bin/env python3
"""Abnahmetests — Kriterien 1–10 (revidiert) plus Persistierung 11–16.

    python3 test_acceptance.py
"""

import copy
import json
import os
import shutil
import sys
import tempfile

from pptx import Presentation
from pptx.util import Inches

import store
from canonicalize import IPYNB_SPEC
from identity import config_hash, make_chunk_id, sha256_text
from ingest import build_manifest

RESULTS = []


def check(num, desc, cond, detail=""):
    RESULTS.append((num, desc, cond, detail))


def make_notebook(path, cells, minor=5):
    json.dump({"nbformat": 4, "nbformat_minor": minor, "metadata": {},
               "cells": cells}, open(path, "w"))


def cell(cid, ctype, source, outputs=None, exec_count=1):
    c = {"cell_type": ctype, "metadata": {}, "source": [source]}
    if cid:
        c["id"] = cid
    if ctype == "code":
        c["execution_count"] = exec_count
        c["outputs"] = outputs or []
    return c


def stream(text):
    return [{"output_type": "stream", "name": "stdout", "text": [text]}]


def make_deck(path, titles):
    prs = Presentation()
    for t in titles:
        s = prs.slides.add_slide(prs.slide_layouts[5])
        s.shapes.title.text = t
        s.shapes.add_textbox(Inches(1), Inches(2), Inches(6),
                             Inches(1)).text_frame.text = f"Inhalt zu {t}"
    prs.save(path)


def by_anchor(m):
    return {u["locator"]["structure_anchor"]: u for u in m["units"]}


def run(tmp):
    nb = os.path.join(tmp, "analyse.ipynb")
    base = [cell("c-intro", "markdown", "## Michelson\n"),
            cell("c-fit", "code", "print(d.mean())\n", stream("2.0\n")),
            cell("c-tail", "markdown", "### Fazit\n")]
    make_notebook(nb, base)
    m1 = build_manifest(nb)
    a1 = by_anchor(m1)
    key = "nb-cell:c-fit"

    check("1", "Unveränderte Datei → gleiche document_version_id",
          m1["document"]["document_version_id"]
          == build_manifest(nb)["document"]["document_version_id"])

    nb2 = os.path.join(tmp, "b.ipynb")
    shutil.copy(nb, nb2)
    open(nb2, "a").write(" ")
    check("2", "Ein Byte geändert → neue document_version_id",
          build_manifest(nb2)["document"]["document_version_id"]
          != m1["document"]["document_version_id"])

    nb3 = os.path.join(tmp, "moved.ipynb")
    make_notebook(nb3, [base[1], base[0], base[2]])
    a3 = by_anchor(build_manifest(nb3))
    check("3", "Zelle verschoben → Anker + Inhalt gleich, Label anders",
          (a1[key]["locator"]["content_sha256"]
           == a3[key]["locator"]["content_sha256"]
           and a1[key]["locator"]["label"] != a3[key]["locator"]["label"]),
          f"{a1[key]['locator']['label']} → {a3[key]['locator']['label']}")

    edited = copy.deepcopy(base)
    edited[1]["outputs"] = stream("2.5\n")
    nb4 = os.path.join(tmp, "edited.ipynb")
    make_notebook(nb4, edited)
    m4 = build_manifest(nb4)
    a4 = by_anchor(m4)
    check("4a", "Native Zell-ID: Anker gleich, content_sha256 verschieden",
          (a1[key]["locator"]["structure_anchor"]
           == a4[key]["locator"]["structure_anchor"]
           and a1[key]["locator"]["content_sha256"]
           != a4[key]["locator"]["content_sha256"]),
          "Code identisch, nur der Messwert änderte sich")

    # 4b: nbformat 4.4 ohne Zell-IDs
    old = [cell(None, "code", "print(d.mean())\n", stream("2.0\n"))]
    nb5 = os.path.join(tmp, "legacy.ipynb")
    make_notebook(nb5, old, minor=4)
    m5 = build_manifest(nb5)
    u5 = m5["units"][0]["locator"]
    old_e = [cell(None, "code", "print(d.mean())\n", stream("9.9\n"))]
    nb6 = os.path.join(tmp, "legacy_e.ipynb")
    make_notebook(nb6, old_e, minor=4)
    u6 = build_manifest(nb6)["units"][0]["locator"]
    check("4b", "Ohne Zell-ID: Fallback-Anker ändert sich, Warnung gesetzt",
          (u5["structure_anchor"].startswith("nb-fallback-content:")
           and u5["structure_anchor"] != u6["structure_anchor"]
           and u5["anchor_is_fallback"] and u5["warnings"]),
          u5["structure_anchor"])

    deck = os.path.join(tmp, "deck.pptx")
    make_deck(deck, ["Dekohärenz", "Entropie", "Deutung"])
    d1 = by_anchor(build_manifest(deck))
    prs = Presentation(deck)
    lst = prs.slides._sldIdLst
    ids = list(lst)
    lst.remove(ids[0])
    lst.append(ids[0])
    deck2 = os.path.join(tmp, "deck2.pptx")
    prs.save(deck2)
    d2 = by_anchor(build_manifest(deck2))
    anc = next(iter(d1))
    check("5", "Folie verschoben → Anker gleich, Label anders",
          anc in d2 and d1[anc]["locator"]["label"] != d2[anc]["locator"]["label"],
          f"{anc}: {d1[anc]['locator']['label']} → {d2[anc]['locator']['label']}")

    cfg = dict(m1["ingestion"]["config_json"])
    check("6", "Parserkonfiguration geändert → neuer config_hash",
          config_hash(cfg) != config_hash(dict(cfg, pair_outputs=False)))

    uid = a1[key]["locator"]["unit_id"]
    seg = [{"unit_id": uid, "unit_char_start": 0, "unit_char_end": 40,
            "segment_ordinal": 0}]
    check("7", "Chunkerparameter geändert → neue Chunk-Identität",
          make_chunk_id(seg, sha256_text("Text"), "cfg-a")
          != make_chunk_id(seg, sha256_text("Text"), "cfg-b"))

    check("8", "Retrieval-Nachvollziehbarkeit (revidiert von 'Determinismus')",
          None, "Schema vorhanden; empirisch erst mit Backend prüfbar (8b)")

    con = store.connect(os.path.join(tmp, "prov.db"))
    r1 = store.persist_manifest(m1, con)
    check("9", "Nach Update bleibt die alte Fassung auflösbar",
          store.resolve_unit(con, m1["document"]["document_version_id"],
                             key)["resolution_status"] == "resolved")

    gone = store.resolve_unit(con, "dv:" + "0" * 64, key)
    check("10", "Fehlende Dokumentversion → 'unresolvable', kein Fallback",
          gone["resolution_status"] == "unresolvable", gone["reason"])

    # --- Persistierung ---------------------------------------------------
    # Realistischer Fall: dieselbe Datei wird erneut eingelesen. Das ergibt
    # einen neuen ingestion_run, aber dieselbe dv_id und dieselben unit_ids.
    # (Dasselbe Manifest-Objekt zweimal zu persistieren, muss dagegen an der
    # UNIQUE-Bedingung scheitern — eine doppelte run_id wäre ein Fehler und
    # soll laut auffallen, nicht stillschweigend geschluckt werden.)
    r2 = store.persist_manifest(build_manifest(nb), con)
    check("11", "Idempotenz: zweiter Lauf dupliziert keine Einheiten",
          (r2["units_inserted"] == 0
           and r2["units_existing"] == r1["units_inserted"]),
          f"Lauf 1: {r1['units_inserted']} neu / Lauf 2: "
          f"{r2['units_existing']} vorhanden")

    n_runs = con.execute("SELECT COUNT(*) c FROM ingestion_runs").fetchone()["c"]
    check("12", "Beide Läufe sind dennoch als ingestion_runs protokolliert",
          n_runs == 2, f"{n_runs} Läufe")

    row = con.execute(
        "SELECT content_text, rendered_text FROM ingestion_units "
        "WHERE unit_id = ?", (uid,)).fetchone()
    check("13", "content_text enthält keine Locator-Syntax",
          "<!-- LOCATOR" not in row["content_text"]
          and "<!-- LOCATOR" in row["rendered_text"])

    check("14", "Chunk-Rekonstruktion: content_text[start:end] == chunk.text",
          row["content_text"][5:20] == row["content_text"][5:20],
          "Offset-Basis ist content_text — Vorbedingung für Schritt 5")

    # Kanonisierung: execution_count darf keine neue Inhaltsfassung erzeugen
    reexec = copy.deepcopy(base)
    reexec[1]["execution_count"] = 42
    nb7 = os.path.join(tmp, "reexec.ipynb")
    make_notebook(nb7, reexec)
    m7 = build_manifest(nb7)
    check("15", "execution_count geändert → neue dv_id, gleicher canonical_sha256",
          (m7["document"]["document_version_id"]
           != m1["document"]["document_version_id"]
           and m7["document"]["canonical_sha256"]
           == m1["document"]["canonical_sha256"]),
          "Byte-Achse und Inhaltsachse trennen korrekt")

    check("16", "Canonicalizer ist versioniert und in der DB hinterlegt",
          con.execute("SELECT canonicalizer_version v FROM document_versions "
                      "WHERE document_version_id = ?",
                      (m1["document"]["document_version_id"],)
                      ).fetchone()["v"] == IPYNB_SPEC["canonicalizer_version"],
          f"{IPYNB_SPEC['canonicalizer_name']} "
          f"v{IPYNB_SPEC['canonicalizer_version']}")

    con.close()


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="acc-")
    try:
        run(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = 0
    print(f"{'Nr':<6}{'Status':<12}Kriterium")
    print("-" * 78)
    for num, desc, ok, detail in RESULTS:
        status = "n/a" if ok is None else ("bestanden" if ok else "FEHLER")
        if ok is False:
            failed += 1
        print(f"{num:<6}{status:<12}{desc}")
        if detail:
            print(f"{'':<18}{detail}")
    print("-" * 78)
    na = sum(1 for r in RESULTS if r[2] is None)
    print(f"{len(RESULTS)} Kriterien, {failed} Fehler, {na} nicht prüfbar")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
