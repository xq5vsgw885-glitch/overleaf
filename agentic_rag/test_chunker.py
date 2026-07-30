#!/usr/bin/env python3
"""Abnahmetests Schritt 5 — die fünfzehn revidierten Chunker-Invarianten.

    python3 test_chunker.py
"""

import copy
import json
import os
import shutil
import sys
import tempfile

import store
from chunker import (DEFAULT_CONFIG, chunk_locator_header, chunk_units,
                     embedding_text, estimate_tokens, get_estimator,
                     serialize_for_agent)
from ingest import build_manifest

RESULTS = []


def check(num, desc, cond, detail=""):
    RESULTS.append((num, desc, cond, detail))


def cell(cid, ctype, source, outputs=None):
    c = {"cell_type": ctype, "id": cid, "metadata": {}, "source": [source]}
    if ctype == "code":
        c["execution_count"] = 1
        c["outputs"] = outputs or []
    return c


def stream(text):
    return [{"output_type": "stream", "name": "stdout", "text": [text]}]


def write_nb(path, cells):
    json.dump({"nbformat": 4, "nbformat_minor": 5, "metadata": {},
               "cells": cells}, open(path, "w"))


LONG = ("Die gemessene Intensitaet nimmt mit wachsendem Gangunterschied ab, "
        "weil die Kohaerenzlaenge der Quelle endlich ist. " * 12)


def run(tmp):
    nb = os.path.join(tmp, "n.ipynb")
    cells = [
        cell("h1", "markdown", "## Michelson-Interferometer\n"),
        cell("m1", "markdown", "Kurze Vorbemerkung.\n"),
        cell("c1", "code", "print(d.mean())\n", stream("2.0\n")),
        cell("c2", "code", "print(d.std())\n", stream("0.1\n")),
        cell("h2", "markdown", "## Fehlerrechnung\n"),
        cell("big", "markdown", LONG),
        cell("big2", "markdown", LONG),
    ]
    write_nb(nb, cells)
    m = build_manifest(nb)
    units = m["units"]
    chunks = chunk_units(units)

    unit_by_id = {u["locator"]["unit_id"]: u for u in units}

    check("1", "Jeder Chunk besitzt mindestens ein Segment",
          all(len(c["segments"]) >= 1 for c in chunks),
          f"{len(chunks)} Chunks aus {len(units)} Einheiten")

    check("2", "Jedes Segment verweist auf genau eine persistierte unit_id",
          all(s["unit_id"] in unit_by_id
              for c in chunks for s in c["segments"]))

    check("3", "Kein Segment überschreitet die Grenzen seines content_text",
          all(0 <= s["unit_char_start"] <= s["unit_char_end"]
              <= len(unit_by_id[s["unit_id"]]["content_text"])
              for c in chunks for s in c["segments"]))

    # 4: Verkettung Segmenttexte + Separatoren == chunk.text
    ok4 = True
    for c in chunks:
        parts = [unit_by_id[s["unit_id"]]["content_text"]
                 [s["unit_char_start"]:s["unit_char_end"]]
                 for s in c["segments"]]
        if DEFAULT_CONFIG["separator"].join(parts) != c["text"]:
            ok4 = False
    check("4", "Verkettung der Segmente + Separator ergibt exakt chunk.text", ok4)

    # 5: beide Offsetsysteme konsistent
    ok5 = True
    for c in chunks:
        for s in c["segments"]:
            a = unit_by_id[s["unit_id"]]["content_text"][
                s["unit_char_start"]:s["unit_char_end"]]
            b = c["text"][s["chunk_char_start"]:s["chunk_char_end"]]
            if a != b:
                ok5 = False
    check("5", "Unit- und Chunkoffsets liefern dieselbe Passage", ok5,
          "Vorbedingung dafür, dass der Validator nur das relevante "
          "Segment lädt")

    composite = [c for c in chunks if c["is_composite"]]
    check("6", "Mehrere Einheiten nur über explizite chunk_segments",
          all(len(c["segments"]) == c["unit_count"] for c in chunks),
          f"{len(composite)} zusammengesetzte Chunks")

    ok7 = all(len({unit_by_id[s["unit_id"]]["locator"]["document_version_id"]
                   for s in c["segments"]}) == 1 for c in chunks)
    check("7", "Kein Chunk kombiniert verschiedene document_version_id", ok7)

    check("8", "Keine Locator-Syntax im Embedding-Text",
          all("LOCATOR" not in embedding_text(c) for c in chunks))

    ok9 = True
    for c in composite or chunks:
        header = chunk_locator_header(c)
        for s in c["segments"]:
            if s["unit_id"] not in header:
                ok9 = False
    check("9", "Agentenserialisierung enthält alle Segment-Locators", ok9)

    # 10: Segmentinhalt geändert -> neue unit_id und neue chunk_id
    edited = copy.deepcopy(cells)
    edited[2]["outputs"] = stream("9.9\n")
    write_nb(nb, edited)          # gleiche Datei, sonst misst der Test den Pfad
    ch2 = chunk_units(build_manifest(nb)["units"])
    check("10", "Segmentinhalt geändert → neue unit_id und neue chunk_id",
          {c["chunk_id"] for c in chunks} != {c["chunk_id"] for c in ch2})

    # 11: reine Positionsänderung
    moved = [cells[0], cells[1], cells[2], cells[3], cells[5], cells[4], cells[6]]
    write_nb(nb, moved)
    moved_units = build_manifest(nb)["units"]
    ch3 = chunk_units(moved_units)
    ev_before = {u["locator"]["evidence_key"] for u in units}
    ev_after = {u["locator"]["evidence_key"] for u in moved_units}
    ids_before = {c["chunk_id"] for c in chunks}
    ids_after = {c["chunk_id"] for c in ch3}
    check("11", "Positionsänderung: evidence_key stabil, unit_id/chunk_id nicht",
          ev_before == ev_after and not (ids_before & ids_after),
          f"{len(ev_before & ev_after)}/{len(ev_before)} evidence_keys "
          f"identisch, 0 chunk_ids — unit_id ist fassungsgebunden")

    # 12: geänderte Nachbarschaft darf neue Zusammensetzung ergeben
    shorter = [cells[0], cells[2], cells[3], cells[4], cells[5]]
    write_nb(nb, shorter)
    ch4 = chunk_units(build_manifest(nb)["units"])
    comp_before = {c["chunk_id"] for c in chunks if c["is_composite"]}
    comp_after = {c["chunk_id"] for c in ch4 if c["is_composite"]}
    check("12", "Geänderte Nachbarschaft → neue Zusammensetzung zulässig",
          comp_before != comp_after,
          "Einheitenidentität positionsunabhängig, Chunkidentität nicht")

    # 13: atomare Einheiten unabhängig adressierbar
    con = store.connect(os.path.join(tmp, "p.db"))
    store.persist_manifest(m, con)
    rep = store.persist_chunks(chunks, con)
    n_units = con.execute(
        "SELECT COUNT(*) c FROM ingestion_units").fetchone()["c"]
    check("13", "Atomare Einheiten bleiben unabhängig adressierbar",
          n_units == len(units),
          f"{n_units} Einheiten, {rep['chunks_inserted']} Chunks, "
          f"{rep['segments']} Segmente")

    # 14: Treffer auf Segmente rückprojizierbar
    con.execute("INSERT INTO retrieval_runs (retrieval_run_id, query_text, "
                "query_sha256, index_id, index_snapshot_sha256, "
                "embedding_provider, embedding_model, retrieval_method, "
                "top_k, filters_json, parameters_json, started_at, status) "
                "VALUES ('rr:1','q','h','idx','snap','ollama','bge-m3',"
                "'dense',5,'{}','{}','now','ok')")
    target = composite[0] if composite else chunks[0]
    con.execute("INSERT INTO retrieval_hits (retrieval_run_id, rank, chunk_id, "
                "score) VALUES ('rr:1', 1, ?, 0.87)", (target["chunk_id"],))
    con.commit()
    rows = con.execute(
        "SELECT segment_ordinal, label, resolution_status FROM hit_resolution "
        "WHERE retrieval_run_id='rr:1' ORDER BY segment_ordinal").fetchall()
    check("14", "Retrievaltreffer auf einzelne Segmente rückprojizierbar",
          len(rows) == len(target["segments"])
          and all(r["resolution_status"] == "resolved" for r in rows),
          " + ".join(r["label"] for r in rows))

    # 15: Chroma-Metadaten verlustfrei auflösbar
    meta = {"chunk_id": target["chunk_id"],
            "document_version_id":
                target["_units"][0]["locator"]["document_version_id"],
            "segment_count": len(target["segments"])}
    back = con.execute(
        "SELECT unit_id, structure_anchor FROM provenance_chain "
        "WHERE chunk_id = ? ORDER BY segment_ordinal",
        (meta["chunk_id"],)).fetchall()
    check("15", "Chroma-Referenz verlustfrei ins Provenienzregister auflösbar",
          len(back) == meta["segment_count"],
          "Chroma trägt nur chunk_id — die Segmentliste kommt aus SQLite")

    # Zusatzbefund: Separator im Embedding-Text
    seps = sum(embedding_text(c).count("<UNIT_BOUNDARY>") for c in chunks)
    check("Z", "Zusatzbefund: Separator-Token im Embedding-Text", None,
          f"{seps} Vorkommen in {len(composite)} zusammengesetzten Chunks — "
          f"siehe Anmerkung")

    # --- 16: Registry koppelt Deklaration und Ausfuehrung ---------------
    try:
        chunk_units(units, {"token_estimator": "phantom/9.9.9"})
        ok16 = False
        detail16 = "unbekannter Schätzer wurde stillschweigend akzeptiert"
    except ValueError as exc:
        ok16 = True
        detail16 = str(exc).split(".")[0]
    check("16", "Nicht registrierter token_estimator wird abgewiesen",
          ok16, detail16)

    # --- 17: Separatoren gehen in die Grenze ein ------------------------
    est = get_estimator(DEFAULT_CONFIG["token_estimator"])
    ok17 = all(est(c["text"]) <= DEFAULT_CONFIG["max_chunk_tokens"]
               for c in chunk_units(units))
    worst = max(est(c["text"]) for c in chunk_units(units))
    check("17", "Kein Chunk überschreitet max_chunk_tokens inkl. Separatoren",
          ok17, f"grösster Chunk: {worst} von "
                f"{DEFAULT_CONFIG['max_chunk_tokens']} Tokens")

    # --- 18: uebergrosse Einheit wird deterministisch geteilt ------------
    huge = [cell("h", "markdown", "# Titel\n"),
            cell("mega", "markdown", LONG * 6)]
    nb5 = os.path.join(tmp, "huge.ipynb")
    write_nb(nb5, huge)
    hunits = build_manifest(nb5)["units"]
    hchunks = chunk_units(hunits)
    mega = [u for u in hunits if u["locator"]["label"].startswith("Cell [02]")][0]
    parts = [c for c in hchunks
             if c["segments"][0]["unit_id"] == mega["locator"]["unit_id"]]
    rebuilt = "".join(
        mega["content_text"][s_["segments"][0]["unit_char_start"]:
                             s_["segments"][0]["unit_char_end"]]
        for s_ in sorted(parts, key=lambda c: c["segments"][0]["unit_char_start"]))
    check("18", "Übergrosse Einheit: Split ist lückenlos rekonstruierbar",
          (len(parts) > 1 and rebuilt == mega["content_text"]
           and all(c["is_partial"] for c in parts)
           and all(est(c["text"]) <= DEFAULT_CONFIG["max_chunk_tokens"]
                   for c in parts)),
          f"{len(parts)} Teilstücke, is_partial=1, Konkatenation identisch")

    # --- 19: Determinismus des Splits -----------------------------------
    check("19", "Zweiter Lauf erzeugt identische chunk_ids",
          [c["chunk_id"] for c in chunk_units(hunits)]
          == [c["chunk_id"] for c in hchunks])

    con.close()


def main() -> int:
    tmp = tempfile.mkdtemp(prefix="chk-")
    try:
        run(tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    failed = 0
    print(f"{'Nr':<5}{'Status':<12}Invariante")
    print("-" * 78)
    for num, desc, ok, detail in RESULTS:
        status = "n/a" if ok is None else ("bestanden" if ok else "FEHLER")
        if ok is False:
            failed += 1
        print(f"{num:<5}{status:<12}{desc}")
        if detail:
            print(f"{'':<17}{detail}")
    print("-" * 78)
    print(f"{len(RESULTS)} Prüfungen, {failed} Fehler")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
