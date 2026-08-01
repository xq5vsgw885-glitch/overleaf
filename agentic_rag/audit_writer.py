"""Single Audit Writer (Spezifikation §2, §9, §10).

## Modell

Producer (Hooks, Agentenprozesse, Ingestion) schreiben NICHT. Sie
validieren ein Event mit Pydantic, huellen es in einen `EventEnvelope`,
serialisieren es als UTF-8-JSON-String und legen es in eine
`multiprocessing.Queue`. Genau ein Prozess — der Writer — nimmt es
entgegen, validiert erneut, prueft die Transportintegritaet und schreibt.

    Producer ──validate──> Envelope ──JSON──> mp.Queue ──> Writer ──> SQLite
                                                             │
                                                             └─> audit_writer.log

## Warum ein Dateilock zusaetzlich zur Queue

Die Hooks von Claude Code sind kurzlebige Prozesse: `rag_stop.py` startet,
schreibt, endet. Jeder solche Prozess bringt seinen eigenen Writer mit —
eine prozessuebergreifende `multiprocessing.Queue` gibt es nicht, ohne
einen dauerhaft laufenden Manager einzufuehren, den §2 nicht vorsieht.

Damit trotzdem zu jedem Zeitpunkt hoechstens EINE schreibende Verbindung
auf `audit_trail.db` besteht, serialisiert ein exklusives `flock` auf
`<db>.writer.lock` die Writer. Ein zweiter Writer wartet auf dem Lock,
statt in SQLites `database is locked` zu laufen. Das ist der Unterschied
zwischen Warten und Scheitern — und der Grund, warum parallele Agenten
keinen Sperrfehler mehr erzeugen (§12.4).

## Was der Writer NICHT tut

Keine LLM-Aufrufe, kein Dateiparsing, keine Netzoperation — und nichts
davon innerhalb einer offenen Transaktion (§2). Der Writer kennt nur
Events und SQL.
"""

import json
import logging
import multiprocessing as mp
import os
import queue as queue_mod
import sys
import time
from typing import Iterable, List, Optional

import audit_db
import migrations
from audit_models import (AUDIT_SCHEMA_VERSION, CHANNEL_B_EVENT_TYPES,
                          EVENT_MODELS, ActionEvent, AgentRegisteredEvent,
                          AssertionEvent, AuditEvent, ClaimStatusEvent,
                          EventEnvelope, EvidenceRegisteredEvent,
                          HardFailEvent, RepairAttemptEvent, RunAttemptEvent,
                          RunFinishEvent, RunStartEvent, WriterShutdownEvent,
                          new_id)
from identity import canonical_json, sha256_text
from policy import ErrorClass, RUN_STATUS_BLOCKED, Scope, Status, scope_of

#: Maximale Laenge des protokollierten Rohpayload-Auszugs. §9 verlangt
#: unveraenderte Referenzierbarkeit (dafuer der Hash) und verbietet
#: gleichzeitig unkontrollierten Abfluss sensibler Rohdaten.
RAW_EXCERPT_LIMIT = 512

#: Wartezeit beim Nachdrainen nach dem Shutdown-Sentinel.
DRAIN_POLL_SECONDS = 0.2
DRAIN_IDLE_ROUNDS = 3


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def _build_logger(session_id: str, log_path: Optional[str]) -> logging.Logger:
    log = logging.getLogger(f"audit_writer.{session_id}")
    log.setLevel(logging.INFO)
    log.propagate = False
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s [writer %(name)s pid=%(process)d] %(message)s")
    stream = logging.StreamHandler(sys.stderr)
    stream.setFormatter(fmt)
    log.addHandler(stream)
    if log_path:
        try:
            os.makedirs(os.path.dirname(os.path.abspath(log_path)), exist_ok=True)
            fh = logging.FileHandler(log_path, encoding="utf-8")
            fh.setFormatter(fmt)
            log.addHandler(fh)
        except OSError:
            pass
    return log


# ---------------------------------------------------------------------------
# Prozessuebergreifende Writer-Serialisierung
# ---------------------------------------------------------------------------

class _WriterLock:
    """Exklusives Lock auf `<db>.writer.lock`.

    Auf Plattformen ohne `fcntl` (Windows) faellt der Mechanismus auf ein
    Verzeichnis-Lock zurueck. Der Fallback ist bewusst simpel; das
    Zielsystem ist POSIX.
    """

    def __init__(self, db_path: str, timeout: float = 60.0):
        self.path = db_path + ".writer.lock"
        self.timeout = timeout
        self._fh = None

    def acquire(self) -> None:
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        try:
            import fcntl
        except ImportError:                                   # pragma: no cover
            self._fh = open(self.path, "a", encoding="utf-8")
            return
        self._fh = open(self.path, "a+", encoding="utf-8")
        deadline = time.monotonic() + self.timeout
        while True:
            try:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Writer-Lock {self.path} nicht erhalten "
                        f"({self.timeout}s). Laeuft ein haengender Writer?")
                time.sleep(0.05)

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            import fcntl
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except (ImportError, OSError):                        # pragma: no cover
            pass
        finally:
            self._fh.close()
            self._fh = None


# ---------------------------------------------------------------------------
# Persistenz — laeuft ausschliesslich im Writer-Prozess
# ---------------------------------------------------------------------------

class _Persister:
    """Die Schreiblogik. Eine Transaktion je Event, kurz gehalten."""

    def __init__(self, con, session_id: str, log: logging.Logger):
        self.con = con
        self.session_id = session_id
        self.log = log
        self.stats = {"received": 0, "persisted": 0, "duplicate": 0,
                      "rejected": 0, "hard_fails": 0}
        #: Kettenglied des gerade verarbeiteten Events; Projektionen
        #: uebernehmen es, statt ein eigenes zu bilden.
        self._current_link = ("GENESIS", "GENESIS")

    # -- Hilfen ------------------------------------------------------------
    def _run_row(self, run_id: str):
        return self.con.execute(
            "SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()

    def _agent_run(self, agent_id: str):
        row = self.con.execute(
            "SELECT run_id FROM run_agents WHERE agent_id = ?",
            (agent_id,)).fetchone()
        return row["run_id"] if row else None

    def _append_event(self, envelope: EventEnvelope, agent_id: Optional[str]):
        """Ereigniszeile anhaengen und die Hash-Kette fortschreiben.

        WICHTIG: Ausschliesslich `audit_events` schreibt die Kette fort.
        Die Zeilen in `actions` und `assertions` sind Projektionen
        DESSELBEN Events und uebernehmen dessen Kettenglied. Wuerden sie
        ein eigenes Glied bilden, waere die Kette nur noch als Verschraenkung
        mehrerer Tabellen nachrechenbar — und ihre Reihenfolge damit von der
        Projektionslogik abhaengig statt von der Ereignisfolge. Genau dieser
        Determinismus wird in §10 verlangt.
        """
        prev = audit_db.head(self.con)
        row_hash = audit_db.advance(self.con, prev, envelope.payload)
        self._current_link = (prev, row_hash)
        self.con.execute(
            "INSERT INTO audit_events (event_id, event_type, schema_version, "
            " run_id, agent_id, occurred_at, received_at, payload_json, "
            " payload_sha256, prev_hash, row_hash, writer_session_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (envelope.event_id, envelope.event_type, envelope.schema_version,
             envelope.run_id, agent_id, envelope.occurred_at.isoformat(),
             audit_db.now(), canonical_json(envelope.payload),
             envelope.payload_sha256, prev, row_hash, self.session_id))
        return prev, row_hash

    def _escalate(self, error_class: ErrorClass, scope: Scope,
                  run_id: Optional[str], claim_id: Optional[str]) -> None:
        """Deterministische Eskalation (§9, letzter Absatz)."""
        if scope in (Scope.RUN, Scope.WRITER) and run_id:
            if self._run_row(run_id) is not None:
                self.con.execute(
                    "UPDATE runs SET status = ? WHERE run_id = ?",
                    (RUN_STATUS_BLOCKED, run_id))
        elif scope is Scope.CLAIM and run_id and claim_id:
            self.con.execute(
                "UPDATE claims SET status = ?, error_class = ?, updated_at = ? "
                "WHERE run_id = ? AND claim_id = ?",
                (Status.BLOCKED.value, error_class.value, audit_db.now(),
                 run_id, claim_id))
        elif scope is Scope.AGENT and run_id:
            # Ein agentweiter Hard Fail entwertet die Aussagen dieses
            # Agenten, nicht die des Runs. Der Run bleibt auswertbar,
            # wird aber nicht als 'verified' abgeschlossen.
            self.con.execute(
                "UPDATE runs SET status = ? WHERE run_id = ? AND status = 'open'",
                ("degraded", run_id))

    def record_hard_fail(self, error_class: ErrorClass, cause: str,
                         run_id: str = None, agent_id: str = None,
                         claim_id: str = None, raw: str = None,
                         scope: Scope = None) -> None:
        """Hard Fail protokollieren — selbst wieder ein Audit-Event."""
        scope = scope or scope_of(error_class)
        raw_sha = sha256_text(raw) if raw is not None else None
        excerpt = None
        if raw is not None:
            excerpt = raw[:RAW_EXCERPT_LIMIT]
            if len(raw) > RAW_EXCERPT_LIMIT:
                excerpt += f"… [{len(raw)} Zeichen, sha256={raw_sha[:16]}]"
        event = HardFailEvent(run_id=run_id, error_class=error_class,
                              scope=scope, cause=cause, agent_id=agent_id,
                              claim_id=claim_id, raw_payload_sha256=raw_sha,
                              raw_payload_excerpt=excerpt)
        envelope = EventEnvelope.wrap(event, producer_pid=os.getpid())
        try:
            self.con.execute("BEGIN IMMEDIATE")
            self._append_event(envelope, agent_id)
            self.con.execute(
                "INSERT INTO hard_fails (event_id, run_id, agent_id, claim_id, "
                " error_class, scope, cause, raw_payload_sha256, "
                " raw_payload_excerpt, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (event.event_id, run_id, agent_id, claim_id,
                 error_class.value, scope.value, cause, raw_sha, excerpt,
                 audit_db.now()))
            self._escalate(error_class, scope, run_id, claim_id)
            self.con.execute("COMMIT")
        except Exception:
            self.con.execute("ROLLBACK")
            raise
        self.stats["hard_fails"] += 1
        self.log.error("HARD FAIL %s [%s] run=%s claim=%s: %s",
                       error_class.value, scope.value, run_id, claim_id, cause)

    # -- Eintrittspunkt ----------------------------------------------------
    def handle_raw(self, raw: str) -> Optional[AuditEvent]:
        """Eine Queue-Payload verarbeiten. Gibt das Event zurueck oder None."""
        self.stats["received"] += 1

        # (1) Transportformat
        try:
            data = json.loads(raw)
            envelope = EventEnvelope.model_validate(data)
        except Exception as exc:                              # §9.8
            self.stats["rejected"] += 1
            run_id = None
            if isinstance(locals().get("data"), dict):
                candidate = data.get("run_id")
                run_id = candidate if isinstance(candidate, str) else None
            self.record_hard_fail(
                ErrorClass.CORRUPT_QUEUE_PAYLOAD,
                f"Queue-Payload nicht parsebar oder nicht schemakonform: {exc}",
                run_id=run_id, raw=raw)
            return None

        # (2) Schemaversion Producer <-> Writer
        if envelope.schema_version != AUDIT_SCHEMA_VERSION:    # §9.5
            self.stats["rejected"] += 1
            self.record_hard_fail(
                ErrorClass.SCHEMA_VERSION_CONFLICT,
                f"Producer sendet schema_version={envelope.schema_version!r}, "
                f"Writer erwartet {AUDIT_SCHEMA_VERSION!r}",
                run_id=envelope.run_id, raw=raw)
            return None

        # (3) Payload-Hash
        if envelope.recomputed_hash() != envelope.payload_sha256:   # §9.9
            self.stats["rejected"] += 1
            self.record_hard_fail(
                ErrorClass.PAYLOAD_HASH_MISMATCH,
                "payload_sha256 stimmt nicht mit dem Eventinhalt ueberein",
                run_id=envelope.run_id, raw=raw)
            return None

        # (4) Revalidierung gegen dasselbe Modell wie beim Producer
        try:
            event = envelope.unwrap()
        except Exception as exc:                              # §9.8
            self.stats["rejected"] += 1
            self.record_hard_fail(
                ErrorClass.CORRUPT_QUEUE_PAYLOAD,
                f"Revalidierung fehlgeschlagen: {exc}",
                run_id=envelope.run_id, raw=raw)
            return None

        # (5) Idempotenz und Event-ID-Konflikt
        existing = self.con.execute(
            "SELECT payload_sha256 FROM audit_events WHERE event_id = ?",
            (envelope.event_id,)).fetchone()
        if existing is not None:
            if existing["payload_sha256"] == envelope.payload_sha256:  # §2
                self.stats["duplicate"] += 1
                self.log.info("Doppelte Zustellung ignoriert: %s",
                              envelope.event_id)
                return event
            self.stats["rejected"] += 1
            self.record_hard_fail(                            # §9.10
                ErrorClass.EVENT_ID_CONFLICT,
                f"event_id {envelope.event_id} bereits mit anderem Inhalt "
                f"persistiert (gespeichert={existing['payload_sha256'][:16]}…, "
                f"empfangen={envelope.payload_sha256[:16]}…)",
                run_id=envelope.run_id, raw=raw)
            return None

        # (6) Projektion
        try:
            self.con.execute("BEGIN IMMEDIATE")
            agent_id = getattr(event, "agent_id", None)
            self._append_event(envelope, agent_id)
            verdict = self._project(event)
            self.con.execute("COMMIT")
        except _Rejected as rej:
            self.con.execute("ROLLBACK")
            self.stats["rejected"] += 1
            self.record_hard_fail(rej.error_class, rej.cause,
                                  run_id=rej.run_id or envelope.run_id,
                                  agent_id=rej.agent_id, claim_id=rej.claim_id,
                                  raw=raw)
            return None
        except Exception as exc:                              # §9.12
            self.con.execute("ROLLBACK")
            self.stats["rejected"] += 1
            self.record_hard_fail(
                ErrorClass.INTERNAL_NONREPRODUCIBLE,
                f"{type(exc).__name__} beim Persistieren von "
                f"{envelope.event_type}: {exc}",
                run_id=envelope.run_id, raw=raw)
            return None

        self.stats["persisted"] += 1
        if verdict:
            self.log.info("%s persistiert (%s)", envelope.event_type, verdict)
        return event

    # -- Projektionen ------------------------------------------------------
    def _project(self, event: AuditEvent) -> str:
        handler = {
            "run_started": self._on_run_started,
            "agent_registered": self._on_agent_registered,
            "action_recorded": self._on_action,
            "evidence_registered": self._on_evidence_registered,
            "assertion_declared": self._on_assertion,
            "claim_status": self._on_claim_status,
            "repair_attempt": self._on_repair,
            "hard_fail": self._on_hard_fail_event,
            "run_attempt": self._on_run_attempt,
            "phase_metrics": self._on_phase_metrics,
            "run_finished": self._on_run_finished,
            "writer_shutdown": lambda e: "sentinel",
        }[event.event_type]
        return handler(event)

    def _require_run(self, run_id: str, agent_id: str = None):
        row = self._run_row(run_id)
        if row is None:                                       # §9.6
            raise _Rejected(ErrorClass.FOREIGN_RUN_REFERENCE,
                            f"Event verweist auf unbekannte run_id {run_id!r}",
                            run_id=run_id, agent_id=agent_id)
        if agent_id:
            owner = self._agent_run(agent_id)
            if owner is None:
                raise _Rejected(
                    ErrorClass.FOREIGN_RUN_REFERENCE,
                    f"agent_id {agent_id!r} ist in keinem Run registriert",
                    run_id=run_id, agent_id=agent_id)
            if owner != run_id:
                raise _Rejected(
                    ErrorClass.FOREIGN_RUN_REFERENCE,
                    f"agent_id {agent_id!r} gehoert zu Run {owner!r}, "
                    f"nicht zu {run_id!r}",
                    run_id=run_id, agent_id=agent_id)
        return row

    def _on_run_started(self, event: RunStartEvent) -> str:
        context = event.context
        context_json = context.canonical()
        context_sha = context.context_hash()
        existing = self._run_row(event.run_id)
        if existing is not None:
            if existing["is_legacy"]:
                raise _Rejected(
                    ErrorClass.FOREIGN_RUN_REFERENCE,
                    f"run_id {event.run_id!r} ist ein migrierter Legacy-Run "
                    f"und darf nicht neu gestartet werden",
                    run_id=event.run_id, agent_id=event.agent_id)
            if (existing["output_enforcement"]
                    and existing["output_enforcement"]
                    != context.output_enforcement.value):     # §9.13
                raise _Rejected(
                    ErrorClass.OUTPUT_ENFORCEMENT_SWITCH,
                    f"output_enforcement wechselt innerhalb von "
                    f"{event.run_id}: {existing['output_enforcement']} -> "
                    f"{context.output_enforcement.value}",
                    run_id=event.run_id, agent_id=event.agent_id)
            if existing["context_sha256"] != context_sha:      # §9.4
                raise _Rejected(
                    ErrorClass.CONTEXT_MUTATION,
                    f"RunContext von {event.run_id} weicht vom persistierten "
                    f"Kontext ab (gespeichert={existing['context_sha256'][:16]}…, "
                    f"empfangen={context_sha[:16]}…)",
                    run_id=event.run_id, agent_id=event.agent_id)
            self._register_agent(event.run_id, event.agent_id, event.agent_type)
            return "run bereits vorhanden, Kontext identisch"

        self.con.execute(
            "INSERT INTO runs (run_id, experiment_id, workflow_condition, "
            " domain, provider, model_version, output_enforcement, "
            " schema_version, task_id, replicate, seed, batch_id, "
            " context_json, context_sha256, context_state, "
            " is_legacy, primary_agent_id, parent_session_id, agent_type, cwd, "
            " started_at, attempts, status) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'complete',0,?,?,?,?,?,0,'open')",
            (event.run_id, context.experiment_id,
             context.workflow_condition.value, context.domain.value,
             context.provider, context.model_version,
             context.output_enforcement.value, context.schema_version,
             context.task_id, context.replicate, context.seed,
             context.batch_id, context_json, context_sha, event.agent_id,
             event.parent_session_id, event.agent_type, event.cwd,
             event.started_at.isoformat()))
        self._register_agent(event.run_id, event.agent_id, event.agent_type)
        return f"run {event.run_id} angelegt"

    def _register_agent(self, run_id: str, agent_id: str, agent_type: str) -> None:
        owner = self._agent_run(agent_id)
        if owner is not None and owner != run_id:              # §9.6
            raise _Rejected(
                ErrorClass.FOREIGN_RUN_REFERENCE,
                f"agent_id {agent_id!r} ist bereits Run {owner!r} zugeordnet",
                run_id=run_id, agent_id=agent_id)
        self.con.execute(
            "INSERT OR IGNORE INTO run_agents (run_id, agent_id, agent_type, "
            " registered_at) VALUES (?,?,?,?)",
            (run_id, agent_id, agent_type, audit_db.now()))

    def _on_agent_registered(self, event: AgentRegisteredEvent) -> str:
        self._require_run(event.run_id)
        self._register_agent(event.run_id, event.agent_id, event.agent_type)
        return f"agent {event.agent_id} -> {event.run_id}"

    def _on_action(self, event: ActionEvent) -> str:
        self._require_run(event.run_id, event.agent_id)
        prev, row_hash = self._current_link
        self.con.execute(
            "INSERT INTO actions (event_id, run_id, agent_id, tool_name, "
            " source_id, source_key, raw_ref, evidence_key, phase, "
            " recorded_at, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            # `source_id` traegt in v2 denselben stabilen Schluessel wie
            # `source_key`. Die v1.0-Normalisierung ueber Basename und
            # Endung wird fuer NEUE Zeilen nicht mehr verwendet; die alten
            # Werte bleiben unveraendert stehen (§10).
            (event.event_id, event.run_id, event.agent_id, event.tool_name,
             event.source_key, event.source_key,
             event.raw_ref, event.evidence_key, event.phase,
             event.occurred_at.isoformat(), prev, row_hash))
        return f"Kanal B: {event.source_key}"

    def _on_evidence_registered(self, event: EvidenceRegisteredEvent) -> str:
        """KANAL B — ein ausgelieferter Beleg (§7).

        Aus EINEM Ereignis entstehen ZWEI Projektionen in derselben
        Transaktion und mit demselben Kettenglied: der Registryeintrag und
        die zugehoerige `actions`-Zeile. Damit bleibt Kanal B eine einzige
        Zugriffswahrheit — jede vorhandene Abfrage ueber `actions` sieht
        den Retrieval-Zugriff, ohne die Registry kennen zu muessen.
        """
        self._require_run(event.run_id, event.agent_id or None)

        existing = self.con.execute(
            "SELECT chunk_text_sha256, content_sha256, unit_id "
            "FROM evidence_registry WHERE run_id = ? AND evidence_key = ?",
            (event.run_id, event.evidence_key)).fetchone()
        if existing is not None:
            if existing["chunk_text_sha256"] == event.chunk_text_sha256:
                # Derselbe Beleg erneut ausgeliefert: idempotent.
                return f"evidence {event.evidence_key[:16]}… bereits registriert"
            raise _Rejected(
                ErrorClass.EVIDENCE_KEY_COLLISION,
                f"evidence_key {event.evidence_key} steht in Run "
                f"{event.run_id} bereits fuer einen anderen Inhalt "
                f"(registriert={existing['chunk_text_sha256'][:16]}…, "
                f"empfangen={event.chunk_text_sha256[:16]}…). Die "
                f"Evidenzidentitaet dieses Laufs ist damit nicht eindeutig.",
                run_id=event.run_id, agent_id=event.agent_id or None)

        prev, row_hash = self._current_link
        self.con.execute(
            "INSERT INTO evidence_registry (event_id, run_id, agent_id, "
            " evidence_key, source_key, source_id, document_version_id, "
            " unit_id, chunk_id, structure_anchor, label, locator_json, "
            " anchor_is_fallback, content_sha256, chunk_text_sha256, "
            " retrieval_run_id, parser_name, parser_version, chunker_name, "
            " chunker_version, retrieved_at, recorded_at, prev_hash, row_hash) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event.event_id, event.run_id, event.agent_id or None,
             event.evidence_key, event.source_key, event.source_id,
             event.document_version_id, event.unit_id, event.chunk_id,
             event.structure_anchor, event.label, event.locator_json,
             int(event.anchor_is_fallback), event.content_sha256,
             event.chunk_text_sha256, event.retrieval_run_id,
             event.parser_name, event.parser_version, event.chunker_name,
             event.chunker_version, event.retrieved_at.isoformat(),
             audit_db.now(), prev, row_hash))
        self.con.execute(
            "INSERT INTO actions (event_id, run_id, agent_id, tool_name, "
            " source_id, source_key, raw_ref, evidence_key, phase, "
            " recorded_at, prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"{event.event_id}:action", event.run_id, event.agent_id or None,
             "retrieval", event.source_key, event.source_key, event.source_id,
             event.evidence_key, "retrieval",
             event.retrieved_at.isoformat(), prev, row_hash))
        return f"Registry: {event.evidence_key[:16]}… ({event.source_key})"

    def _on_assertion(self, event: AssertionEvent) -> str:
        self._require_run(event.run_id, event.agent_id)
        prev, row_hash = self._current_link
        self.con.execute(
            "INSERT INTO assertions (event_id, run_id, agent_id, claim_id, "
            " claim, evidence_id, source_id, source_key, raw_source_ref, "
            " locator, quote, stance, required, reconciled, recorded_at, "
            " prev_hash, row_hash) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event.event_id, event.run_id, event.agent_id, event.claim_id,
             event.claim, event.evidence_id,
             event.source_key or "",
             event.source_key, event.raw_source_ref, event.locator, event.quote,
             event.stance.value, int(event.required), int(event.reconciled),
             event.occurred_at.isoformat(), prev, row_hash))
        return f"Kanal A: {event.claim_id}"

    def _on_claim_status(self, event: ClaimStatusEvent) -> str:
        self._require_run(event.run_id, event.agent_id)
        stamp = audit_db.now()
        self.con.execute(
            "INSERT INTO claims (run_id, claim_id, agent_id, claim_text, "
            " status, status_reason, error_class, evidence_free, repair_count, "
            " confirmed_evidence_json, missing_evidence_json, first_seen_at, "
            " updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(run_id, claim_id) DO UPDATE SET "
            " status = excluded.status, status_reason = excluded.status_reason, "
            " error_class = excluded.error_class, "
            " evidence_free = excluded.evidence_free, "
            " repair_count = excluded.repair_count, "
            " confirmed_evidence_json = excluded.confirmed_evidence_json, "
            " missing_evidence_json = excluded.missing_evidence_json, "
            " claim_text = excluded.claim_text, updated_at = excluded.updated_at",
            (event.run_id, event.claim_id, event.agent_id, event.claim_text,
             event.status.value, event.reason,
             event.error_class.value if event.error_class else None,
             int(event.evidence_free), event.repair_count,
             canonical_json(event.confirmed_evidence),
             canonical_json(event.missing_evidence), stamp, stamp))
        return f"{event.claim_id} -> {event.status.value}"

    def _on_repair(self, event: RepairAttemptEvent) -> str:
        self._require_run(event.run_id)
        attempt = event.attempt
        self.con.execute(
            "INSERT INTO repairs (event_id, run_id, agent_id, target_id, "
            " attempt, kind, error_class, input_sha256, output_sha256, "
            " validated, validation_detail, occurred_at, baseline_json) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event.event_id, event.run_id, event.agent_id or None,
             event.target_id, attempt.attempt, attempt.kind.value,
             attempt.error_class.value, attempt.input_sha256,
             attempt.output_sha256, int(attempt.validated),
             attempt.validation_detail, attempt.occurred_at.isoformat(),
             canonical_json(event.baseline) if event.baseline else None))
        self.con.execute(
            "UPDATE claims SET repair_count = ?, updated_at = ? "
            "WHERE run_id = ? AND claim_id = ?",
            (attempt.attempt, audit_db.now(), event.run_id, event.target_id))
        return f"repair {attempt.kind.value} #{attempt.attempt}"

    def _on_hard_fail_event(self, event: HardFailEvent) -> str:
        """Hard Fail, den ein Producer gemeldet hat (z. B. §9.7)."""
        self.con.execute(
            "INSERT INTO hard_fails (event_id, run_id, agent_id, claim_id, "
            " error_class, scope, cause, raw_payload_sha256, "
            " raw_payload_excerpt, recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (event.event_id, event.run_id, event.agent_id, event.claim_id,
             event.error_class.value, event.scope.value, event.cause,
             event.raw_payload_sha256, event.raw_payload_excerpt,
             audit_db.now()))
        self._escalate(event.error_class, event.scope, event.run_id,
                       event.claim_id)
        self.stats["hard_fails"] += 1
        return f"hard_fail {event.error_class.value}"

    def _on_run_attempt(self, event: RunAttemptEvent) -> str:
        self._require_run(event.run_id)
        self.con.execute(
            "UPDATE runs SET attempts = attempts + 1, status = ? "
            "WHERE run_id = ?", (event.status, event.run_id))
        return f"attempt++ ({event.status})"

    def _on_phase_metrics(self, event) -> str:
        self._require_run(event.run_id)
        self.con.execute(
            "INSERT INTO phase_metrics (event_id, run_id, agent_id, phase, "
            " attempt, duration_ms, input_tokens, output_tokens, "
            " cached_input_tokens, cost_usd, model_version, detail, "
            " recorded_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (event.event_id, event.run_id, event.agent_id or None,
             event.phase.value, event.attempt, event.duration_ms,
             event.input_tokens, event.output_tokens,
             event.cached_input_tokens, event.cost_usd, event.model_version,
             event.detail, audit_db.now()))
        return f"metrik {event.phase.value} #{event.attempt}"

    def _on_run_finished(self, event: RunFinishEvent) -> str:
        row = self._require_run(event.run_id)
        status = event.status
        # Ein Run mit laufweitem Hard Fail wird nie als erfolgreich
        # abgeschlossen — auch dann nicht, wenn der Producer 'verified'
        # meldet (§9, §12.7).
        blocking = self.con.execute(
            "SELECT COUNT(*) AS n FROM hard_fails WHERE run_id = ? "
            "AND scope IN ('run','writer')", (event.run_id,)).fetchone()["n"]
        if blocking or row["status"] == RUN_STATUS_BLOCKED:
            status = RUN_STATUS_BLOCKED
        elif row["is_legacy"] and status == "verified":
            # Migrierte Altdaten haben keinen RunContext, keine
            # kollisionsfreie Quellenidentitaet und keinen Claim-Status. Sie
            # koennen nachtraeglich nicht verifiziert werden (§4).
            status = "legacy_unverified"
        self.con.execute(
            "UPDATE runs SET finished_at = ?, status = ?, attempts = ? "
            "WHERE run_id = ?",
            (event.finished_at.isoformat(), status,
             max(event.attempts, row["attempts"]), event.run_id))
        return f"run {event.run_id} -> {status}"


class _Rejected(Exception):
    """Interne Ablehnung mit Fehlerklasse; wird zu einem Hard Fail."""

    def __init__(self, error_class: ErrorClass, cause: str, run_id=None,
                 agent_id=None, claim_id=None):
        self.error_class = error_class
        self.cause = cause
        self.run_id = run_id
        self.agent_id = agent_id
        self.claim_id = claim_id
        super().__init__(cause)


# ---------------------------------------------------------------------------
# Writer-Prozess
# ---------------------------------------------------------------------------

def _writer_main(q, db_path: str, session_id: str, ready, log_path: str) -> None:
    """Eintrittspunkt des Writer-Prozesses. Modulebene wegen `spawn`."""
    audit_db.mark_writer_process()
    log = _build_logger(session_id, log_path)
    lock = _WriterLock(db_path)
    con = None
    persister = None
    reason = "unbekannt"
    try:
        log.info("START warte auf Writer-Lock %s", lock.path)
        lock.acquire()
        migrations.migrate_audit(db_path)
        con = audit_db.connect_write(db_path)
        persister = _Persister(con, session_id, log)
        con.execute(
            "INSERT INTO writer_sessions (writer_session_id, pid, db_path, "
            " started_at, status) VALUES (?,?,?,?, 'running')",
            (session_id, os.getpid(), db_path, audit_db.now()))
        log.info("BETRIEB Writer-Sitzung %s aktiv auf %s", session_id, db_path)
        if ready is not None:
            ready.set()

        shutdown = None
        while shutdown is None:
            try:
                raw = q.get(timeout=0.5)
            except queue_mod.Empty:
                continue
            if raw is None:
                # Nur der typisierte Sentinel beendet den Writer (§2).
                # Ein None waere ein untypisiertes magisches Objekt und wird
                # als beschaedigte Payload behandelt.
                persister.handle_raw("null")
                continue
            event = persister.handle_raw(raw)
            if isinstance(event, WriterShutdownEvent):
                shutdown = event

        reason = shutdown.reason
        log.info("SHUTDOWN Sentinel empfangen (%s) — draine Queue", reason)
        idle = 0
        while idle < DRAIN_IDLE_ROUNDS:
            try:
                raw = q.get(timeout=DRAIN_POLL_SECONDS)
            except queue_mod.Empty:
                idle += 1
                continue
            idle = 0
            if raw is not None:
                persister.handle_raw(raw)

        con.execute(
            "UPDATE writer_sessions SET finished_at = ?, status = 'closed', "
            " shutdown_reason = ?, events_received = ?, events_persisted = ?, "
            " events_duplicate = ?, events_rejected = ? "
            "WHERE writer_session_id = ?",
            (audit_db.now(), reason, persister.stats["received"],
             persister.stats["persisted"], persister.stats["duplicate"],
             persister.stats["rejected"], session_id))
        log.info("SHUTDOWN abgeschlossen: %s", persister.stats)
    except Exception as exc:                                  # pragma: no cover
        log.exception("FEHLER Writer bricht ab: %s", exc)
        if con is not None:
            try:
                con.execute("ROLLBACK")
            except Exception:
                pass
            try:
                con.execute(
                    "UPDATE writer_sessions SET finished_at = ?, "
                    " status = 'failed', shutdown_reason = ? "
                    "WHERE writer_session_id = ?",
                    (audit_db.now(), f"{type(exc).__name__}: {exc}", session_id))
            except Exception:
                pass
        if ready is not None:
            ready.set()
        raise SystemExit(1)
    finally:
        if con is not None:
            try:
                con.close()
            except Exception:                                 # pragma: no cover
                pass
        lock.release()
        logging.shutdown()


class WriterFailure(RuntimeError):
    """§9.14 — Writer-Ausfall oder unvollstaendiger Shutdown."""


class WriterClosed(RuntimeError):
    """Es werden keine neuen fachlichen Events mehr angenommen (§2)."""


class AuditWriterHandle:
    """Producerseitiger Griff auf den Writer.

    Der Prozess ist ausdruecklich KEIN Daemon: ein Daemon wuerde beim Ende
    des Elternprozesses hart terminiert und koennte akzeptierte Events
    verlieren (§2).
    """

    def __init__(self, db_path: str = None, log_path: str = None,
                 recovery: bool = False):
        self.db_path = db_path or audit_db.db_path()
        self.log_path = log_path or os.path.join(
            os.path.dirname(os.path.abspath(self.db_path)), "audit_writer.log")
        self.session_id = new_id("ws")
        self._recovery = recovery
        try:
            self._ctx = mp.get_context("fork")
        except ValueError:                                    # pragma: no cover
            self._ctx = mp.get_context("spawn")
        self._queue = self._ctx.Queue()
        self._ready = self._ctx.Event()
        self._process = None
        self._accepting = False
        self._channel_b_blocked = False
        self._sent: List[dict] = []
        self.report = None

    # -- Lebenszyklus ------------------------------------------------------
    def start(self, timeout: float = 30.0) -> "AuditWriterHandle":
        if self._process is not None:
            raise RuntimeError("Writer laeuft bereits")
        self._process = self._ctx.Process(
            target=_writer_main,
            args=(self._queue, self.db_path, self.session_id, self._ready,
                  self.log_path),
            name=f"audit-writer-{self.session_id}",
            daemon=False,
        )
        self._process.start()
        if not self._ready.wait(timeout):
            self._process.terminate()
            raise WriterFailure(
                f"Writer {self.session_id} wurde nicht betriebsbereit "
                f"({timeout}s).")
        if not self._process.is_alive():
            raise WriterFailure(f"Writer {self.session_id} sofort beendet "
                                f"(exitcode={self._process.exitcode}).")
        self._accepting = True
        return self

    @property
    def pid(self) -> Optional[int]:
        return self._process.pid if self._process else None

    def __enter__(self) -> "AuditWriterHandle":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.shutdown(reason="context_exit" if exc is None else f"error:{exc_type.__name__}")
        return False

    # -- Senden ------------------------------------------------------------
    def send(self, event) -> str:
        """Event validieren, huellen und in die Queue legen.

        Die Validierung geschieht hier — beim Producer — und im Writer
        erneut (§2). Doppelte Arbeit mit Absicht: der Producer soll seinen
        eigenen Fehler sofort sehen, der Writer darf keinem Producer
        vertrauen.
        """
        if not self._accepting and not isinstance(event, WriterShutdownEvent):
            raise WriterClosed(
                "Es werden keine neuen fachlichen Events angenommen; "
                "der Shutdown hat begonnen.")
        if isinstance(event, dict):
            model = EVENT_MODELS.get(event.get("event_type"))
            if model is None:
                raise ValueError(f"unbekannter event_type: {event!r}")
            event = model.model_validate(event)
        if not isinstance(event, AuditEvent):
            raise TypeError(f"kein AuditEvent: {type(event).__name__}")
        if self._channel_b_blocked and event.event_type in CHANNEL_B_EVENT_TYPES:
            raise WriterClosed(
                "Format-Reparatur darf keinen Kanal-B-Datensatz erzeugen (§8).")
        envelope = EventEnvelope.wrap(event, producer_pid=os.getpid())
        raw = envelope.to_json()
        self._sent.append({"event_id": envelope.event_id,
                           "event_type": envelope.event_type,
                           "run_id": envelope.run_id,
                           "payload_sha256": envelope.payload_sha256,
                           "raw_sha256": sha256_text(raw)})
        self._queue.put(raw)
        return envelope.event_id

    def send_raw(self, raw: str) -> None:
        """Rohe Payload senden — ausschliesslich fuer Integritaetstests."""
        self._sent.append({"event_id": f"raw:{sha256_text(raw)[:16]}",
                           "event_type": "raw", "run_id": None,
                           "payload_sha256": None,
                           "raw_sha256": sha256_text(raw)})
        self._queue.put(raw)

    def block_channel_b(self, blocked: bool = True) -> None:
        self._channel_b_blocked = blocked

    def stop_accepting(self) -> None:
        """Schritt 1 der Shutdown-Reihenfolge (§2)."""
        self._accepting = False

    # -- Shutdown ----------------------------------------------------------
    def shutdown(self, reason: str = "requested", timeout: float = 30.0) -> dict:
        """Geordnetes Herunterfahren in der vorgeschriebenen Reihenfolge.

        1. keine neuen fachlichen Events annehmen,
        2. typisiertes Sentinel senden; der Writer arbeitet die Queue leer,
        3. Transaktion committen bzw. kontrolliert zurueckrollen,
        4. SQLite-Verbindung schliessen  (beides im Writer, `finally`),
        5. Prozess mit join() beenden.
        """
        if self._process is None:
            return {"status": "not_started"}
        if self.report is not None:
            return self.report

        self.stop_accepting()
        sentinel_sent = False
        if self._process.is_alive():
            try:
                self._queue.put(
                    EventEnvelope.wrap(WriterShutdownEvent(reason=reason),
                                       producer_pid=os.getpid()).to_json())
                sentinel_sent = True
            except Exception:                                 # pragma: no cover
                sentinel_sent = False

        self._process.join(timeout)
        killed = False
        if self._process.is_alive():                          # pragma: no cover
            self._process.terminate()
            self._process.join(5)
            killed = True

        exitcode = self._process.exitcode
        report = {"writer_session_id": self.session_id,
                  "exitcode": exitcode, "killed": killed,
                  "sentinel_sent": sentinel_sent,
                  "events_sent": len(self._sent), "reason": reason}
        report.update(self._verify_persistence())
        report["clean"] = bool(
            exitcode == 0 and not killed and sentinel_sent
            and not report["missing_event_ids"]
            and report["writer_session_status"] == "closed")

        if not report["clean"] and not self._recovery:
            self._escalate_writer_failure(report)
        self.report = report
        return report

    def _verify_persistence(self) -> dict:
        """Nachweis der Persistenzvollstaendigkeit (§9.14)."""
        expected = [s["event_id"] for s in self._sent]
        result = {"missing_event_ids": expected[:],
                  "writer_session_status": "unknown",
                  "persisted_event_ids": 0}
        if not os.path.exists(self.db_path):
            return result
        try:
            con = audit_db.connect_read(self.db_path)
        except Exception:                                     # pragma: no cover
            return result
        try:
            present = set()
            for chunk_start in range(0, len(expected), 400):
                chunk = expected[chunk_start:chunk_start + 400]
                marks = ",".join("?" * len(chunk))
                present.update(
                    r["event_id"] for r in con.execute(
                        f"SELECT event_id FROM audit_events "
                        f"WHERE event_id IN ({marks})", chunk).fetchall())
            # Abgelehnte Events sind ebenfalls dokumentiert — als hard_fail
            # mit demselben Rohpayload-Hash. Sie fehlen also nicht.
            rejected = {r["raw_payload_sha256"] for r in con.execute(
                "SELECT raw_payload_sha256 FROM hard_fails "
                "WHERE raw_payload_sha256 IS NOT NULL").fetchall()}
            missing = []
            for sent in self._sent:
                if sent["event_id"] in present:
                    continue
                if self._raw_hash(sent) in rejected:
                    continue
                missing.append(sent["event_id"])
            row = con.execute(
                "SELECT status FROM writer_sessions WHERE writer_session_id = ?",
                (self.session_id,)).fetchone()
            result["missing_event_ids"] = missing
            result["persisted_event_ids"] = len(present)
            result["writer_session_status"] = row["status"] if row else "missing"
        finally:
            con.close()
        return result

    def _raw_hash(self, sent: dict) -> str:
        """Hash der rohen Queue-Payload.

        Ein vom Writer abgelehntes Event steht nicht in `audit_events`,
        aber sein Rohpayload-Hash steht in `hard_fails`. Es ist damit
        dokumentiert und gilt nicht als verloren — der Unterschied zwischen
        'bewusst abgelehnt' und 'unbemerkt verschwunden'.
        """
        return sent.get("raw_sha256") or ""

    def _escalate_writer_failure(self, report: dict) -> None:
        """Ein Writer-Ausfall darf nicht als erfolgreicher Run erscheinen."""
        run_ids = sorted({s["run_id"] for s in self._sent if s["run_id"]})
        cause = (f"Writer-Sitzung {self.session_id} nicht nachweislich "
                 f"vollstaendig: exitcode={report['exitcode']}, "
                 f"killed={report['killed']}, "
                 f"session_status={report['writer_session_status']}, "
                 f"fehlende Events={len(report['missing_event_ids'])}")
        try:
            recovery = AuditWriterHandle(self.db_path, self.log_path,
                                         recovery=True).start()
        except Exception as exc:                              # pragma: no cover
            raise WriterFailure(f"{cause}; Recovery-Writer nicht startbar: {exc}")
        try:
            for run_id in run_ids or [None]:
                recovery.send(HardFailEvent(
                    run_id=run_id, error_class=ErrorClass.WRITER_FAILURE,
                    scope=Scope.WRITER, cause=cause,
                    raw_payload_sha256=sha256_text(cause)))
        finally:
            recovery.shutdown(reason="writer_failure_recorded")
        report["writer_failure_recorded"] = True
        report["affected_runs"] = run_ids


def record_writer_failure(db_path: str, run_ids: Iterable[str],
                          cause: str) -> None:
    """Writer-Ausfall von aussen protokollieren (z. B. aus einem Supervisor)."""
    handle = AuditWriterHandle(db_path, recovery=True).start()
    try:
        for run_id in list(run_ids) or [None]:
            handle.send(HardFailEvent(
                run_id=run_id, error_class=ErrorClass.WRITER_FAILURE,
                scope=Scope.WRITER, cause=cause,
                raw_payload_sha256=sha256_text(cause)))
    finally:
        handle.shutdown(reason="writer_failure_recorded")
