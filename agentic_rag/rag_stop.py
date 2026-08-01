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
from datetime import datetime, timezone

import audit_client
import audit_db
import reconciler
import repair
from audit_models import (AgentResult, HardFailEvent, MetricPhase,
                          RepairAttempt, RepairKind)
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
    """(Versuche bisher, Hash der letzten Ausgabe, deren Baseline)."""
    row = con.execute(
        "SELECT MAX(attempt) AS n FROM repairs "
        "WHERE run_id = ? AND target_id = ? AND kind = ?",
        (run_id, target_id, kind)).fetchone()
    count = (row["n"] or 0) if row else 0
    last = con.execute(
        "SELECT output_sha256, baseline_json FROM repairs "
        "WHERE run_id = ? AND target_id = ? AND kind = ? "
        "ORDER BY attempt DESC LIMIT 1",
        (run_id, target_id, kind)).fetchone()
    baseline = None
    if last is not None and last["baseline_json"]:
        try:
            baseline = json.loads(last["baseline_json"])
        except json.JSONDecodeError:                          # pragma: no cover
            baseline = None
    return count, (last["output_sha256"] if last else None), baseline


def _read_state(run_id: str, target_id: str) -> dict:
    """Bisherigen Reparatur- und Laufzustand lesen. Rein lesend (§2)."""
    state = {"format_attempts": 0, "format_last": None,
             "format_baseline": None, "evidence_attempts": 0, "attempts": 0,
             "started_at": None, "last_attempt_at": None,
             "last_attempt_reason": None, "channel_b": []}
    try:
        con = audit_db.connect_read()
    except Exception:
        return state
    try:
        (state["format_attempts"], state["format_last"],
         state["format_baseline"]) = _repair_state(
            con, run_id, target_id, "format")
        state["evidence_attempts"], _, _ = _repair_state(
            con, run_id, target_id, "evidence")
        row = con.execute(
            "SELECT attempts, started_at FROM runs WHERE run_id = ?",
            (run_id,)).fetchone()
        if row is not None:
            state["attempts"] = row["attempts"]
            state["started_at"] = row["started_at"]
        # Startpunkt der laufenden Phase: das zuletzt protokollierte
        # run_attempt-Ereignis. Ohne eines ist die erste Generierung noch
        # im Gang, und der Bezugspunkt ist runs.started_at.
        last = con.execute(
            "SELECT occurred_at, payload_json FROM audit_events "
            "WHERE run_id = ? AND event_type = 'run_attempt' "
            "ORDER BY seq DESC LIMIT 1", (run_id,)).fetchone()
        if last is not None:
            state["last_attempt_at"] = last["occurred_at"]
            try:
                state["last_attempt_reason"] = json.loads(
                    last["payload_json"]).get("reason")
            except json.JSONDecodeError:                      # pragma: no cover
                pass
        # Bereits persistierter Kanal B — insbesondere die Evidenzregistry
        # aus der Retrieval-Phase. Ohne sie waere jeder registrierte
        # `ev:`-Schluessel aus Sicht dieses Hooks unbekannt und wuerde nach
        # §9.6 blockiert.
        state["channel_b"] = reconciler.channel_b_from_db(con)
    finally:
        con.close()
    return state


def _elapsed_ms(since: str) -> int:
    """Vergangene Zeit seit einem persistierten ISO-Zeitstempel.

    Gemessen, nicht geschaetzt: Bezugspunkt ist immer ein Wert, den der
    Audit Writer selbst geschrieben hat.
    """
    if not since:
        return None
    try:
        start = datetime.fromisoformat(since)
    except ValueError:                                        # pragma: no cover
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    delta = datetime.now(timezone.utc) - start
    return max(int(delta.total_seconds() * 1000), 0)


def _record_elapsed_phase(session, state: dict, agent_id: str) -> None:
    """Die abgeschlossene Phase seit dem letzten Bezugspunkt protokollieren.

    Erster Aufruf  -> `initial_generation` (seit runs.started_at).
    Folgeaufrufe   -> `format_repair` oder `evidence_retrieval`, je nach
                      Grund des vorangegangenen Blocks.

    Token- und Kostenwerte bleiben leer: Der Hook-Kontrakt liefert sie
    nicht, und geschaetzte Werte waeren im Ergebnisbericht von gemessenen
    nicht mehr unterscheidbar.
    """
    reason = state.get("last_attempt_reason")
    if reason is None:
        phase = MetricPhase.INITIAL_GENERATION
        since = state.get("started_at")
        attempt = 1
    elif reason == "evidence_repair":
        phase = MetricPhase.EVIDENCE_RETRIEVAL
        since = state.get("last_attempt_at")
        attempt = state.get("evidence_attempts", 0) + 1
    else:
        phase = MetricPhase.FORMAT_REPAIR
        since = state.get("last_attempt_at")
        attempt = state.get("format_attempts", 0) + 1
    duration = _elapsed_ms(since)
    if duration is None:
        return
    session.record_metrics(phase, duration_ms=duration, attempt=attempt,
                           agent_id=agent_id,
                           detail=f"gemessen seit {since}")


def _record_total(session, state: dict, agent_id: str) -> None:
    """Gesamtdauer des Laufs. Eigene Messung, nicht die Phasensumme."""
    duration = _elapsed_ms(state.get("started_at"))
    if duration is not None:
        session.record_metrics(MetricPhase.TOTAL, duration_ms=duration,
                               agent_id=agent_id,
                               detail="gemessen seit runs.started_at")


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

        # Die soeben abgeschlossene Phase messen (§ Zusatzvorgabe).
        _record_elapsed_phase(session, state, agent_id)

        # --- (2) Injektionspruefung — Hard Fail ohne Reparatur (§9.1) -----
        injection = detect_injection(message)
        if injection:
            session.hard_fail(
                ErrorClass.PROMPT_INJECTION,
                f"Injektions- oder Manipulationsmuster in der Agentenausgabe: "
                f"{injection!r}", raw=message)
            _record_total(session, state, agent_id)
            session.finish_run("blocked", attempts=state["attempts"])
            print("[AUDIT] Injektionsmuster erkannt; Lauf ist BLOCKED.",
                  file=sys.stderr)
            return 0

        # --- (3) Kanal B zuerst ------------------------------------------
        refs = channel_b(payload.get("agent_transcript_path", ""))
        session.record_actions(refs, tool_name=None, phase="transcript_scan")
        # Frisch gescannte Zugriffe plus der bereits persistierte Kanal B.
        # Die soeben gesendeten Ereignisse sind noch nicht in der Datenbank
        # (der Writer arbeitet asynchron), deshalb die Vereinigung.
        records = list(state["channel_b"]) + [
            ChannelBRecord(run_id=session.run_id, agent_id=agent_id,
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

        # --- §8-Verbote auf dem Hook-Reparaturpfad ------------------------
        # Der Subagent hat nach einem Block eine voellig neue Antwort
        # erzeugt. Ohne Vergleich mit der verworfenen Ausgabe koennte er
        # dabei eine Quelle nachschieben oder eine Aussage umschreiben —
        # die Verbote aus §8 gelten aber fuer JEDE Reparatur, nicht nur
        # fuer die der Engine.
        if state["format_baseline"] is not None:
            # Die geparste Struktur, wenn der Adapter eine gewinnen konnte —
            # sonst der Rohtext, den `check_repair_guards` lexikalisch liest.
            violation = repair.check_repair_guards(
                state["format_baseline"],
                outcome.structured if outcome.structured is not None
                else outcome.raw_text)
            if violation is not None:
                error_class, detail = violation
                session.record_repair(target_id, RepairAttempt(
                    attempt=state["format_attempts"] + 1,
                    kind=RepairKind.FORMAT, error_class=error_class,
                    input_sha256=state["format_last"] or sha256_text(message),
                    output_sha256=sha256_text(message), validated=False,
                    validation_detail=detail[:500]))
                session.hard_fail(error_class, detail, raw=message)
                session.finish_run("blocked", attempts=state["attempts"])
                print(f"[AUDIT] Reparaturverstoss: {detail}", file=sys.stderr)
                return 0

        if result is None:
            # --- Format-Reparatur, hoechstens zwei Versuche (§8) ----------
            attempts = state["format_attempts"]
            current_sha = sha256_text(message)
            session.record_repair(target_id, RepairAttempt(
                attempt=attempts + 1, kind=RepairKind.FORMAT,
                error_class=ErrorClass.FORMAT_VALIDATION_EXHAUSTED,
                input_sha256=state["format_last"] or current_sha,
                output_sha256=current_sha, validated=False,
                validation_detail=str(format_error)[:500]),
                baseline=repair.baseline_of(message))
            if attempts + 1 > MAX_FORMAT_REPAIRS:
                # Zwei Formatreparaturen erschoepft -> UNVERIFIED, kein
                # Hard Fail, kein weiterer Block (§8).
                _record_total(session, state, agent_id)
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
        elif (summary[Status.VERIFIED.value]
              or summary[Status.PARTIALLY_VERIFIED.value]):
            # Teilweise belegt: der Lauf ist auswertbar, aber nicht
            # produktionsfaehig. 'degraded' unterscheidet ihn von einem
            # Lauf ganz ohne bestaetigte Evidenz.
            status = "degraded"
        else:
            status = "unverified"
        _record_total(session, state, agent_id)
        session.finish_run(status, attempts=state["attempts"])

    report = getattr(session, "report", {}) or {}
    if not report.get("clean", True):                         # §9.14
        print(f"[AUDIT] Writer-Shutdown nicht nachweislich vollstaendig: "
              f"{report}", file=sys.stderr)
    return decision


if __name__ == "__main__":
    sys.exit(main())
