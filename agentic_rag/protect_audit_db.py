#!/usr/bin/env python3
"""PreToolUse-Hook — Schreibschutz auf die Audit-Datenbank.

Ohne diesen Hook ist die gesamte Integritätsargumentation hinfällig: ein Agent,
der in audit_trail.db schreiben darf, kann sein eigenes Protokoll umschreiben.
Die DB ist ausschliesslich vom Audit-Writer-Prozess zu beschreiben.

PreToolUse ist eines der Events, die tatsächlich BLOCKIEREN können
(Exit 2 verhindert den Tool-Call). PostToolUse könnte hier nichts ausrichten,
da die Schreiboperation dann bereits erfolgt wäre.

AENDERUNG gegenueber v1.0 (Spezifikation §10):

1. BEFUND: Die alte Erkennung war eine Verbotsliste auf dem kleingeschriebenen
   Kommando ('insert', 'update', '>' …). Alles, was nicht auf der Liste stand,
   galt als lesend — `python3 -c "..."`, `sqlite3 .restore`, `truncate`,
   `tee`, `dd`, `install` also inbegriffen. Eine Verbotsliste ist an dieser
   Stelle der falsche Mechanismus: Sie muss vollstaendig sein, um zu wirken.
   Ersetzt durch eine ERLAUBNISLISTE — was nicht erkennbar lesend ist, wird
   verweigert.

2. Geschuetzt sind jetzt auch `provenance.db` und die Seitendateien beider
   Datenbanken sowie das Lock des Writers.

3. Eine Verweigerung ist §9.7 und wird als Hard Fail protokolliert — mit
   Scope 'agent', nicht 'run': ein abgewehrter Schreibversuch entwertet den
   Lauf nicht, muss aber sichtbar sein.
"""

import os
import json
import re
import sys

GUARDED = (
    "audit_trail.db", "audit_trail.db-wal", "audit_trail.db-shm",
    "audit_trail.db.writer.lock",
    "provenance.db", "provenance.db-wal", "provenance.db-shm",
)

#: Kommandoformen, die nachweislich nur lesen. Alles andere wird
#: verweigert. Bewusst kurz gehalten — jede Erweiterung ist eine
#: Entscheidung ueber die Integritaet des Protokolls.
READONLY_PATTERNS = (
    # sqlite3 <datei> "SELECT …" / .schema / .tables / .dump / .headers
    re.compile(r"""^\s*sqlite3\s+(-\w+\s+)*[^\s;|&><]+\s+
                   (["']?\s*(select|with)\b|\.(schema|tables|dump|databases|
                    indexes|indices|headers|mode|once|read\s+/dev/null))""",
               re.IGNORECASE | re.VERBOSE),
    # Auswertungs-CLI dieses Projekts (nur lesende Unterbefehle)
    re.compile(r"^\s*python3?\s+\S*audit_ctl\.py\s+"
               r"(status|verify|export|dump-schema|show)\b", re.IGNORECASE),
    # Dateimetadaten
    re.compile(r"^\s*(ls|stat|file|wc|du|sha256sum|md5sum)\s", re.IGNORECASE),
)

#: Umleitungen und Pipes machen jede Erlaubnis wertlos: `sqlite3 db "select 1"
#: > db` liest und schreibt zugleich.
DISQUALIFIERS = re.compile(r"[>]|\|\s*(tee|dd|sqlite3)\b|&&|;|\$\(|`")


def is_readonly_command(command: str) -> bool:
    if DISQUALIFIERS.search(command or ""):
        return False
    return any(p.search(command or "") for p in READONLY_PATTERNS)


def _record_denial(payload: dict, detail: str) -> None:
    """§9.7 — Zugriffsverweigerung protokollieren.

    Fehlschlaege beim Protokollieren duerfen die Verweigerung NICHT
    aufheben; deshalb faengt der Aufrufer alles ab.
    """
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import audit_client
    from audit_models import HardFailEvent
    from audit_writer import AuditWriterHandle
    from policy import ErrorClass, Scope

    agent_id = payload.get("agent_id") or ""
    session_id = payload.get("session_id") or ""
    run_id = None
    try:
        context = audit_client.context_from_env()
        run_id = audit_client.make_run_id(context.experiment_id, session_id,
                                          agent_id) if agent_id else None
    except Exception:
        run_id = None

    handle = AuditWriterHandle().start()
    try:
        handle.send(HardFailEvent(
            run_id=run_id, error_class=ErrorClass.HOOK_ACCESS_DENIED,
            scope=Scope.AGENT,
            cause=f"Schreibzugriff auf geschuetzte Audit-Datei verweigert: {detail}",
            agent_id=agent_id or None,
            raw_payload_excerpt=detail[:512]))
    finally:
        handle.shutdown(reason="access_denied_recorded")


def main() -> int:
    payload = json.load(sys.stdin)
    tool = payload.get("tool_name", "")
    inp = payload.get("tool_input", {}) or {}

    haystack = " ".join(
        str(v) for v in inp.values() if isinstance(v, (str, int, float))
    )
    if tool in ("Write", "Edit", "NotebookEdit"):
        haystack += " " + str(inp.get("file_path", ""))

    hit = any(name in haystack for name in GUARDED)
    if hit and tool == "Bash":
        if is_readonly_command(str(inp.get("command", ""))):
            return 0

    if hit:
        try:
            _record_denial(payload, f"{tool}: {haystack[:200]}")
        except Exception as exc:                              # pragma: no cover
            print(f"[AUDIT] Verweigerung konnte nicht protokolliert werden: "
                  f"{exc}", file=sys.stderr)
        print(
            "Schreibzugriff auf die Audit-Datenbank verweigert. Das Protokoll "
            "wird ausschliesslich vom Audit-Writer-Prozess geschrieben; gib "
            "deine Evidenz im vereinbarten Ergebnisformat aus. Lesende "
            "Abfragen sind ueber 'python3 audit_ctl.py status|verify|export' "
            "moeglich.",
            file=sys.stderr,
        )
        return 2  # blockiert den Tool-Call

    return 0


if __name__ == "__main__":
    sys.exit(main())
