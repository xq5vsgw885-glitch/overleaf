#!/usr/bin/env python3
"""SubagentStart-Hook.

Zweck: (1) Lauf-Datensatz anlegen, (2) dem frisch gestarteten Subagenten den
Ausgabekontrakt in den Kontext injizieren.

Der Subagent startet mit leerem Kontextfenster und kennt weder die Session
noch seine agent_id. additionalContext ist der einzige dokumentierte Weg,
ihm beides mitzugeben.

SubagentStart kann NICHT blockieren (Exit 2 zeigt nur stderr). Das ist hier
unkritisch: die Durchsetzung sitzt in rag_stop.py.

AENDERUNG gegenueber v1.0 (Spezifikation §2, §3, §5):

* Der Hook schreibt nicht mehr selbst. Er startet einen Audit Writer,
  sendet ein `RunStartEvent` und fahrt ihn geordnet herunter.
* Der Lauf hat eine `run_id` und einen vollstaendigen `RunContext`. Fehlt
  eine Kontrollvariable, wird sie NICHT geraten — der Lauf wird als
  Hard Fail (§9.3) protokolliert.
* Der `<<<AUDIT>>>`-Freitextvertrag wird nur noch injiziert, wenn
  `output_enforcement=prompt` gilt. Er ist der dokumentierte Fallback,
  nicht mehr der primaere Audit-Transport.
"""

import json
import sys

import audit_client
from audit_models import HardFailEvent
from audit_writer import AuditWriterHandle
from output_adapter import PROMPT_CONTRACT
from policy import ErrorClass, HardFail, Scope

NATIVE_CONTRACT = """\
AUDIT-PFLICHT (nicht verhandelbar, wird maschinell geprueft):

Dieser Lauf verwendet strukturierte Modellausgaben (output_enforcement=native).
Gib dein Endergebnis als AgentResult-Struktur zurueck:

  run_id   = "{run_id}"
  agent_id = "{agent_id}"

Regeln:
- Jede Evidenzreferenz nennt eine Quelle, die du in DIESEM Lauf tatsaechlich
  geoeffnet hast — mit Verzeichnis und Dateiendung bzw. als DOI.
- Eine Aussage ohne externe Quelle markierst du mit "evidence_free": true.
- Eine leere claims-Liste ist zulaessig. Eine erfundene Quelle nicht.
- Schreibe NICHT selbst in die Audit-Datenbank. Der Schreibzugriff liegt
  ausschliesslich beim Audit-Writer-Prozess.
"""


def _emit(context: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": context,
        }
    }))


def main() -> int:
    payload = json.load(sys.stdin)
    agent_id = payload.get("agent_id", "")
    session_id = payload.get("session_id", "")

    # --- Kontext ----------------------------------------------------------
    try:
        context = audit_client.context_from_env()
    except HardFail as failure:
        # Ohne gueltigen Kontext gibt es keinen auswertbaren Lauf. Der
        # Befund wird protokolliert, der Subagent erfaehrt es im Klartext.
        handle = AuditWriterHandle().start()
        try:
            handle.send(HardFailEvent(
                run_id=None, error_class=ErrorClass.INVALID_RUN_CONTEXT,
                scope=Scope.RUN, cause=f"{failure.cause} (agent {agent_id})",
                agent_id=agent_id))
        finally:
            handle.shutdown(reason="invalid_run_context")
        print(f"[AUDIT] {failure}", file=sys.stderr)
        _emit("AUDIT-WARNUNG: Der Laufkontext ist unvollstaendig; dieser Lauf "
              "ist nicht auswertbar und wird als BLOCKED protokolliert. "
              f"Ursache: {failure.cause}")
        return 0

    session = audit_client.open_session(agent_id, session_id)
    with session:
        session.start_run(parent_session_id=session_id,
                          agent_type=payload.get("agent_type", ""),
                          cwd=payload.get("cwd", ""))

    if context.output_enforcement.value == "prompt":
        contract = PROMPT_CONTRACT.format(run_id=session.run_id,
                                          agent_id=agent_id)
    else:
        contract = NATIVE_CONTRACT.format(run_id=session.run_id,
                                          agent_id=agent_id)
    _emit(contract)
    return 0


if __name__ == "__main__":
    sys.exit(main())
