#!/usr/bin/env python3
"""SubagentStop-Hook — der deterministische Durchsetzungspunkt.

SubagentStop ist eines der wenigen Events, die blockieren KÖNNEN
(decision: "block" hält den Subagenten am Laufen und liefert `reason`
als nächste Instruktion). Genau darauf ruht die Evidenzgarantie.

Ablauf:
  1. Kontext   — RunContext aus der Umgebung, `run_id` deterministisch.
  2. Kanal B   — agent_transcript_path parsen: welche Quellen wurden
                 tatsaechlich geoeffnet? (Aktion, vom Modell nicht
                 fabrizierbar). Wird als ActionEvent gesendet, BEVOR
                 irgendetwas abgeglichen wird.
  3. Kanal A   — strukturierte Ausgabe ueber den Output-Adapter lesen.
                 Formfehler -> Format-Reparatur, hoechstens zwei Versuche.
  4. Abgleich  — Channel Reconciler. Fehlende Evidenz -> EVIDENZ-Reparatur,
                 ein getrennter Zustand mit eigenem Zaehler (§8).
  5. Persistenz— Claim-Status und Laufstatus ueber den Audit Writer.

AENDERUNG gegenueber v1.0 (Spezifikation §2, §6, §7, §8, §9):

* Kein direkter Schreibzugriff mehr; alles laeuft ueber den Audit Writer.
* Format- und Evidenzreparatur sind getrennte Zustaende mit getrennten
  Zaehlern und getrennten Events.
* Eine leere Claim-Liste gilt NICHT mehr als erfolgreicher Lauf (§12.16).
* Erkannte Injektion, fremde run_id und Kontextfehler sind Hard Fails und
  erhalten KEINEN Reparaturversuch (§9).

Loop-Schutz: stop_hook_active + eigene Zaehler (Claude Code kappt zusätzlich
nach 8 aufeinanderfolgenden Blocks).
"""

import json
import os
import re
import sys

import audit_client
import audit_db
from audit_models import AgentResult, HardFailEvent, RepairAttempt, RepairKind
from audit_writer import AuditWriterHandle
from identity import sha256_text
from output_adapter import HybridOutputAdapter, detect_injection
from policy import MAX_FORMAT_REPAIRS, ErrorClass, HardFail, Scope, Status
from reconciler import ChannelBRecord, reconcile

#: Evidenzreparatur: wie oft der Subagent aufgefordert wird, eine
#: behauptete Quelle tatsaechlich zu oeffnen. Wert aus v1.0 uebernommen.
MAX_EVIDENCE_ATTEMPTS = 3

BLOCK_RE = re.compile(r"<<<AUDIT>>>\s*(\{.*?\})\s*<<<END_AUDIT>>>", re.DOTALL)

SOURCE_RE = re.compile(
    r"(?:[\w\-/\.]+\.(?:pdf|epub|docx|pptx|ipynb|md|tex)"
    r"|10\.\d{4,9}/[-._;()/:\w]+)",
    re.IGNORECASE,
)


def block(reason: str) -> int:
    print(json.dumps({"decision": "block", "reason": reason}))
    return 0


def collect_strings(node, out: list) -> None:
    """Alle Strings aus einer beliebig verschachtelten JSON-Struktur sammeln."""
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            collect_strings(v, out)
    elif isinstance(node, list):
        for v in node:
            collect_strings(v, out)


def channel_b(transcript_path: str) -> list:
    """Tatsaechlich beruehrte Quellen aus dem Subagenten-Transkript.

    ANNAHME: Das Transkript ist JSONL. Das interne Zeilenschema ist NICHT
    Teil des dokumentierten Hook-Kontrakts — deshalb wird hier bewusst
    schema-agnostisch über alle Strings gesucht statt feste Pfade zu
    adressieren. Einmalig gegen eine reale Datei kalibrieren.

    AENDERUNG: Der Fund wird UNNORMALISIERT zurueckgegeben. v1.0 normalisierte
    hier sofort mit `normalize_source()` und verlor damit Verzeichnis und
    Endung — zwei verschiedene Dateien konnten so denselben Kanal-B-Eintrag
    erzeugen (§7). Die Schluesselbildung geschieht jetzt zentral in
    `audit_db.source_key()`.
    """
    touched = []
    seen = set()
    path = os.path.expanduser(transcript_path or "")
    if not path or not os.path.exists(path):
        return touched

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            strings = []
            collect_strings(rec, strings)
            for s in strings:
                for hit in SOURCE_RE.findall(s):
                    if hit not in seen:
                        seen.add(hit)
                        touched.append(hit)
    return touched


class _HookProvider:
    """Provider-Adapter fuer die bereits vorliegende Agentenausgabe.

    Der 'Provider' ist hier Claude Code selbst: die Ausgabe steht in
    `last_assistant_message`. Der Adapter macht daraus einen einheitlichen
    Pfad fuer beide Enforcement-Modi.
    """

    supports_native = True
    name = "claude-code-subagent"

    def __init__(self, message: str):
        self.message = message or ""

    def generate(self, prompt: str, schema: dict, mode: str):
        if mode == "native":
            try:
                data = json.loads(self.message)
                return self.message, data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return self.message, None
        return self.message, None


def _repair_state(con, run_id: str, target_id: str, kind: str) -> tuple:
    """(Anzahl bisheriger Versuche, Hash der letzten abgelehnten Ausgabe)."""
    row = con.execute(
        "SELECT MAX(attempt) AS n FROM repairs "
        "WHERE run_id = ? AND target_id = ? AND kind = ?",
        (run_id, target_id, kind)).fetchone()
    count = (row["n"] or 0) if row else 0
    last = con.execute(
        "SELECT output_sha256 FROM repairs WHERE run_id = ? AND target_id = ? "
        "AND kind = ? ORDER BY attempt DESC LIMIT 1",
        (run_id, target_id, kind)).fetchone()
    return count, (last["output_sha256"] if last else None)


def _read_state(run_id: str, target_id: str) -> dict:
    """Bisherigen Reparaturzustand lesen. Rein lesend (§2)."""
    state = {"format_attempts": 0, "format_last": None,
             "evidence_attempts": 0, "attempts": 0}
    try:
        con = audit_db.connect_read()
    except Exception:
        return state
    try:
        state["format_attempts"], state["format_last"] = _repair_state(
            con, run_id, target_id, "format")
        state["evidence_attempts"], _ = _repair_state(
            con, run_id, target_id, "evidence")
        row = con.execute("SELECT attempts FROM runs WHERE run_id = ?",
                          (run_id,)).fetchone()
        state["attempts"] = row["attempts"] if row else 0
    finally:
        con.close()
    return state


def main() -> int:
    payload = json.load(sys.stdin)
    agent_id = payload.get("agent_id", "")
    session_id = payload.get("session_id", "")
    message = payload.get("last_assistant_message", "") or ""
    target_id = f"output:{agent_id}"

    # --- (1) Kontext ------------------------------------------------------
    try:
        context = audit_client.context_from_env()
    except HardFail as failure:
        handle = AuditWriterHandle().start()
        try:
            handle.send(HardFailEvent(
                run_id=None, error_class=ErrorClass.INVALID_RUN_CONTEXT,
                scope=Scope.RUN, cause=f"{failure.cause} (agent {agent_id})",
                agent_id=agent_id))
        finally:
            handle.shutdown(reason="invalid_run_context")
        print(f"[AUDIT] {failure}", file=sys.stderr)
        return 0

    session = audit_client.open_session(agent_id, session_id)
    state = _read_state(session.run_id, target_id)
    decision = 0

    with session:
        # Idempotent: identischer Kontext auf bestehendem Run ist erlaubt,
        # abweichender Kontext ist §9.4 und wird vom Writer abgelehnt.
        session.start_run(parent_session_id=session_id,
                          agent_type=payload.get("agent_type", ""),
                          cwd=payload.get("cwd", ""))

        # --- (2) Injektionspruefung — Hard Fail ohne Reparatur (§9.1) -----
        injection = detect_injection(message)
        if injection:
            session.hard_fail(
                ErrorClass.PROMPT_INJECTION,
                f"Injektions- oder Manipulationsmuster in der Agentenausgabe: "
                f"{injection!r}", raw=message)
            session.finish_run("blocked", attempts=state["attempts"])
            print("[AUDIT] Injektionsmuster erkannt; Lauf ist BLOCKED.",
                  file=sys.stderr)
            return 0

        # --- (3) Kanal B zuerst ------------------------------------------
        refs = channel_b(payload.get("agent_transcript_path", ""))
        session.record_actions(refs, tool_name=None, phase="transcript_scan")
        records = [ChannelBRecord(run_id=session.run_id, agent_id=agent_id,
                                  source_key=audit_db.source_key(ref))
                   for ref in refs]

        # --- (4) Kanal A ueber den Output-Adapter -------------------------
        try:
            adapter = HybridOutputAdapter(_HookProvider(message), context)
        except HardFail as failure:                           # §9.13
            session.hard_fail(failure.error_class, failure.cause)
            session.finish_run("blocked", attempts=state["attempts"])
            return 0
        outcome = adapter.generate("")

        result = None
        format_error = outcome.parse_error
        if outcome.structured is not None:
            declared = dict(outcome.structured)
            declared.setdefault("run_id", session.run_id)
            declared.setdefault("agent_id", agent_id)
            if declared.get("run_id") != session.run_id:      # §9.6
                session.hard_fail(
                    ErrorClass.FOREIGN_RUN_REFERENCE,
                    f"Agentenausgabe deklariert run_id "
                    f"{declared.get('run_id')!r}, tatsaechlich laeuft "
                    f"{session.run_id!r}", raw=message)
                session.finish_run("blocked", attempts=state["attempts"])
                return 0
            try:
                result = AgentResult.model_validate(declared)
            except Exception as exc:
                format_error = f"Schemaverstoss: {exc}"

        if result is None:
            # --- Format-Reparatur, hoechstens zwei Versuche (§8) ----------
            attempts = state["format_attempts"]
            current_sha = sha256_text(message)
            session.record_repair(target_id, RepairAttempt(
                attempt=attempts + 1, kind=RepairKind.FORMAT,
                error_class=ErrorClass.FORMAT_VALIDATION_EXHAUSTED,
                input_sha256=state["format_last"] or current_sha,
                output_sha256=current_sha, validated=False,
                validation_detail=str(format_error)[:500]))
            if attempts + 1 > MAX_FORMAT_REPAIRS:
                # Zwei Formatreparaturen erschoepft -> UNVERIFIED, kein
                # Hard Fail, kein weiterer Block (§8).
                session.finish_run("unverified", attempts=state["attempts"] + 1)
                print(f"[AUDIT] Formatvalidierung nach {MAX_FORMAT_REPAIRS} "
                      f"Reparaturen erschoepft: {format_error}", file=sys.stderr)
                return 0
            session.bump_attempt(status="open", reason="format_repair")
            decision = block(
                "Deine Ausgabe ist formal nicht verwertbar "
                f"({format_error}). Gib das Endergebnis erneut im vereinbarten "
                "Format aus. Ergaenze dabei KEINE neue Aussage und KEINE neue "
                "Quelle — es geht ausschliesslich um die Form. Eine leere "
                "claims-Liste ist zulaessig.")
            return decision

        if state["format_attempts"]:
            # Der vorangegangene Block hat gewirkt: Erfolg protokollieren.
            session.record_repair(target_id, RepairAttempt(
                attempt=state["format_attempts"] + 1, kind=RepairKind.FORMAT,
                error_class=ErrorClass.FORMAT_VALIDATION_EXHAUSTED,
                input_sha256=state["format_last"] or sha256_text(message),
                output_sha256=sha256_text(message), validated=True,
                validation_detail="Ausgabe validiert"))

        # --- (5) Abgleich -------------------------------------------------
        reconciliation = reconcile(result, records, run_id=session.run_id,
                                   agent_scoped=False, production=False)
        unconfirmed = [v for v in reconciliation.verdicts
                       if v.missing_evidence and v.status is not Status.BLOCKED]

        if unconfirmed and state["evidence_attempts"] < MAX_EVIDENCE_ATTEMPTS:
            # Evidenzreparatur ist eine EIGENE Phase: neue Quellen muessen
            # tatsaechlich geoeffnet werden und erzeugen neue Kanal-B-Events.
            # Ein Format-Retry legitimiert fehlenden Zugriff nicht (§7).
            missing_ids = {e for v in unconfirmed for e in v.missing_evidence}
            session.record_repair(target_id, RepairAttempt(
                attempt=state["evidence_attempts"] + 1,
                kind=RepairKind.EVIDENCE,
                error_class=ErrorClass.EVIDENCE_INCOMPLETE,
                input_sha256=sha256_text(message),
                output_sha256=sha256_text(message), validated=False,
                validation_detail=("unbelegte Evidenzreferenzen: "
                                   + ", ".join(sorted(missing_ids)))[:500]))
            session.bump_attempt(status="open", reason="evidence_repair")
            names = sorted({ref.source_ref
                            for claim in result.claims
                            for ref in claim.evidence
                            if ref.evidence_id in missing_ids})
            decision = block(
                "Diese zitierten Quellen tauchen in deinem Arbeitsverlauf "
                f"nicht auf: {', '.join(names)}. Oeffne sie und belege die "
                "Aussage, oder entferne die Assertion. Zitate aus dem "
                "Gedaechtnis sind hier unzulaessig.")
            return decision

        # --- (6) Persistenz ----------------------------------------------
        session.declare_result(result)
        for verdict in reconciliation.verdicts:
            session.record_claim_status(verdict, agent_id=agent_id)

        summary = reconciliation.summary()
        if summary[Status.BLOCKED.value]:
            status = "blocked"
        elif not result.claims:
            # §12.16: Eine leere Claim-Liste ist ein zulaessiges Ergebnis,
            # aber kein evidenzgesicherter Lauf.
            status = "unverified"
        elif summary[Status.VERIFIED.value] == len(result.claims):
            status = "verified"
        elif summary[Status.VERIFIED.value]:
            status = "degraded"
        else:
            status = "unverified"
        session.finish_run(status, attempts=state["attempts"])

    report = getattr(session, "report", {}) or {}
    if not report.get("clean", True):                         # §9.14
        print(f"[AUDIT] Writer-Shutdown nicht nachweislich vollstaendig: "
              f"{report}", file=sys.stderr)
    return decision


if __name__ == "__main__":
    sys.exit(main())
