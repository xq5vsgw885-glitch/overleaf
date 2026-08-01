#!/usr/bin/env python3
"""Bedienoberflaeche des Audit-Systems.

    python3 audit_ctl.py init                    # migrieren (mit Sicherung)
    python3 audit_ctl.py status [--run RUN_ID]   # Laeufe und Zaehlstaende
    python3 audit_ctl.py verify [--run RUN_ID]   # Kette, FK, Integritaet
    python3 audit_ctl.py recompute --run RUN_ID  # Reconciliation neu rechnen
    python3 audit_ctl.py export --run RUN_ID [--mode evaluation|production]
    python3 audit_ctl.py metrics [--run RUN_ID]  # Phasenmetrik
    python3 audit_ctl.py dump-schema             # tatsaechlicher Stand
    python3 audit_ctl.py selftest                # Writer starten und stoppen

Alle Unterbefehle ausser `init` und `selftest` sind rein lesend.

## Warum es kein `start` und `stop` gibt

Der Audit Writer ist an eine `multiprocessing.Queue` gebunden (§2). Eine
Queue existiert nur innerhalb der Prozessgruppe, die sie erzeugt hat — ein
per CLI gestarteter Dauerlaeufer waere fuer die Hooks nicht erreichbar.
Der Writer wird deshalb von dem Prozess gestartet, der Events erzeugt, und
mit ihm geordnet beendet. `selftest` fuehrt genau diesen Zyklus einmal aus
und weist ihn nach.
"""

import argparse
import json
import os
import sys

import audit_db
import migrations
from policy import ExportMode


def _print(data) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False, default=str))


def cmd_init(args) -> int:
    report = migrations.migrate_audit(args.db)
    prov = args.provenance or os.environ.get(
        "PROVENANCE_DB_PATH",
        os.path.join(os.path.dirname(os.path.abspath(args.db)),
                     "provenance.db"))
    prov_report = migrations.migrate_provenance(prov)
    _print({"audit": report, "provenance": prov_report})
    return 0 if report["integrity"]["ok"] and prov_report["integrity"]["ok"] else 1


def cmd_status(args) -> int:
    con = audit_db.connect_read(args.db)
    try:
        where, params = ("WHERE run_id = ?", (args.run,)) if args.run else ("", ())
        runs = [dict(r) for r in con.execute(
            f"SELECT * FROM run_overview {where} ORDER BY started_at DESC "
            f"LIMIT ?", params + (args.limit,)).fetchall()]
        sessions = [dict(r) for r in con.execute(
            "SELECT writer_session_id, pid, status, shutdown_reason, "
            " events_received, events_persisted, events_duplicate, "
            " events_rejected FROM writer_sessions "
            "ORDER BY started_at DESC LIMIT 5").fetchall()]
        _print({"schema_version": migrations.current_version(con),
                "runs": runs, "recent_writer_sessions": sessions})
    finally:
        con.close()
    return 0


def cmd_verify(args) -> int:
    con = audit_db.connect_read(args.db)
    try:
        chain = audit_db.verify_chain(con)
        integrity = migrations.integrity_report(con)
        incomplete = [dict(r) for r in con.execute(
            "SELECT writer_session_id, status, shutdown_reason "
            "FROM writer_sessions WHERE status != 'closed'").fetchall()]
        report = {"chain": chain, "integrity": integrity,
                  "unclean_writer_sessions": incomplete}
        if args.run:
            report["reconciliation_reproducible"] = _reproducible(con, args.run)
        _print(report)
        ok = chain["ok"] and integrity["ok"] and not incomplete
        return 0 if ok else 1
    finally:
        con.close()


def _reproducible(con, run_id: str) -> dict:
    import reconciler
    recomputed = {v.claim_id: v.status.value
                  for v in reconciler.reconcile_run(con, run_id).verdicts}
    stored = {v.claim_id: v.status.value
              for v in reconciler.stored_verdicts(con, run_id)}
    differing = {cid: {"gespeichert": stored.get(cid),
                       "neu_berechnet": recomputed.get(cid)}
                 for cid in set(stored) | set(recomputed)
                 if stored.get(cid) != recomputed.get(cid)}
    return {"ok": not differing, "abweichungen": differing}


def cmd_recompute(args) -> int:
    import reconciler
    con = audit_db.connect_read(args.db)
    try:
        result = reconciler.reconcile_run(con, args.run,
                                          agent_scoped=args.agent_scoped)
        _print({"run_id": args.run, "summary": result.summary(),
                "verdicts": [v.to_dict() for v in result.verdicts]})
    finally:
        con.close()
    return 0


def cmd_export(args) -> int:
    import renderer
    from policy import assert_export_mode_allowed
    # Pilot und Hauptevaluation laufen ausschliesslich im Evaluationsmodus.
    assert_export_mode_allowed(args.mode, args.purpose)
    con = audit_db.connect_read(args.db)
    try:
        rendered = renderer.render_run(con, args.run, mode=ExportMode(args.mode))
    finally:
        con.close()
    if args.sidecar:
        with open(args.sidecar, "w", encoding="utf-8") as fh:
            fh.write(rendered.sidecar_json())
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(rendered.markdown)
        _print({"markdown": args.out, "sidecar": args.sidecar,
                "mode": rendered.mode.value,
                "excluded": rendered.excluded_claim_ids})
    else:
        print(rendered.markdown)
        if not args.sidecar:
            print("\n<!-- SIDECAR\n" + rendered.sidecar_json() + "\n-->")
    return 0


def cmd_metrics(args) -> int:
    con = audit_db.connect_read(args.db)
    try:
        where, params = ("WHERE run_id = ?", (args.run,)) if args.run else ("", ())
        rows = [dict(r) for r in con.execute(
            f"SELECT * FROM run_phase_metrics {where} "
            f"ORDER BY run_id, phase", params).fetchall()]
        _print({"phase_metrics": rows})
    finally:
        con.close()
    return 0


def cmd_dump_schema(args) -> int:
    print(migrations.live_schema(args.db))
    return 0


def cmd_selftest(args) -> int:
    """Writer starten, ein Ereignis schreiben, geordnet stoppen."""
    from audit_models import RunContext, RunStartEvent
    from audit_writer import AuditWriterHandle

    migrations.migrate_audit(args.db)
    context = RunContext(experiment_id="selftest", workflow_condition="A",
                         domain="physics", model_version="selftest",
                         output_enforcement="prompt", provider="selftest",
                         task_id="selftest", replicate=1)
    handle = AuditWriterHandle(args.db).start()
    handle.send(RunStartEvent(
        run_id=f"run:selftest-{os.getpid()}", agent_id=f"selftest-{os.getpid()}",
        parent_session_id="selftest", agent_type="selftest", cwd=os.getcwd(),
        context=context))
    report = handle.shutdown(reason="selftest")
    _print(report)
    return 0 if report.get("clean") else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("--db", default=None, help="Pfad zu audit_trail.db")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("init", help="Schema migrieren (mit Sicherung)")
    p.add_argument("--provenance", default=None)
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("status")
    p.add_argument("--run", default=None)
    p.add_argument("--limit", type=int, default=20)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("verify")
    p.add_argument("--run", default=None)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("recompute")
    p.add_argument("--run", required=True)
    p.add_argument("--agent-scoped", action="store_true")
    p.set_defaults(func=cmd_recompute)

    p = sub.add_parser("export")
    p.add_argument("--run", required=True)
    p.add_argument("--mode", default="evaluation",
                   choices=[m.value for m in ExportMode])
    p.add_argument("--purpose", default="delivery",
                   help="pilot|main|evaluation|study erzwingen "
                        "export_mode=evaluation")
    p.add_argument("--out", default=None)
    p.add_argument("--sidecar", default=None)
    p.set_defaults(func=cmd_export)

    p = sub.add_parser("metrics")
    p.add_argument("--run", default=None)
    p.set_defaults(func=cmd_metrics)

    p = sub.add_parser("dump-schema")
    p.set_defaults(func=cmd_dump_schema)

    p = sub.add_parser("selftest")
    p.set_defaults(func=cmd_selftest)
    return parser


def main(argv=None) -> int:
    from policy import ExportModeNotAllowed
    args = build_parser().parse_args(argv)
    args.db = args.db or audit_db.db_path()
    try:
        return args.func(args)
    except ExportModeNotAllowed as exc:
        print(f"[AUDIT] {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"[AUDIT] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
