#!/usr/bin/env python3
"""Ingestion-CLI — Manifest und Persistierung (Schritt 3 + 4).

    python3 ingest.py datei.ipynb                 # gerenderte Ausgabe
    python3 ingest.py deck.pptx --manifest        # JSON-Manifest
    python3 ingest.py datei.ipynb --persist       # in provenance.db schreiben

Das Manifest bleibt die testbare Zwischenstufe: Es enthaelt genau das,
was persistiert wird, laesst sich aber ohne Datenbank diffen.
"""

import json
import sys
import uuid
from datetime import datetime, timezone

from identity import config_hash
from ipynb_parser import parse_notebook
from pptx_parser import parse_pptx


def build_manifest(path: str) -> dict:
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if path.endswith(".ipynb"):
        docver, units, config = parse_notebook(path)
    elif path.endswith(".pptx"):
        docver, units, config = parse_pptx(path)
    else:
        raise ValueError("Nicht unterstuetztes Format: " + path)

    warning_count = sum(len(u["locator"]["warnings"]) for u in units)

    return {
        "manifest_version": "1.1",
        "document": docver,
        "ingestion": {
            "ingestion_run_id": "ir:" + uuid.uuid4().hex,
            "document_version_id": docver["document_version_id"],
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "status": "ok",
            "parser_name": docver["parser_name"],
            "parser_version": docver["parser_version"],
            "config_json": config,
            "config_hash": config_hash(config),
            "unit_count": len(units),
            "warning_count": warning_count,
        },
        "units": units,
    }


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 1

    manifest = build_manifest(argv[1])

    for unit in manifest["units"]:
        for w in unit["locator"]["warnings"]:
            print("[WARN " + unit["locator"]["label"] + "] " + w,
                  file=sys.stderr)

    if "--persist" in argv:
        import store
        con = store.connect()
        report = store.persist_manifest(manifest, con)
        con.close()
        print(json.dumps(report, indent=2, ensure_ascii=False))
    elif "--manifest" in argv or "--json" in argv:
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    else:
        print("\n\n".join(u["rendered_text"] for u in manifest["units"]))

    ing = manifest["ingestion"]
    doc = manifest["document"]
    print("\n[INFO] {n} Einheiten, {w} Warnungen, dv={dv}..., canon={c}...".format(
        n=ing["unit_count"], w=ing["warning_count"],
        dv=doc["document_version_id"][:16],
        c=(doc.get("canonical_sha256") or "-")[:12]), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
