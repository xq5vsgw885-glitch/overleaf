"""Producer-Fassade: Kontextaufbau, Laufidentitaet, Event-Erzeugung.

Alles, was ein Hook oder ein Agentenprozess braucht, um Audit-Daten
loszuwerden, ohne selbst eine Schreibverbindung zu besitzen (§2).

## Woher `run_id` kommt

`SubagentStart` und `SubagentStop` sind zwei getrennte Prozesse ohne
gemeinsamen Speicher. Der Lauf muss in beiden dieselbe Identitaet haben,
ohne dass der erste dem zweiten etwas uebergeben kann (der einzige Kanal
ist `additionalContext`, also der Modellkontext — und damit nichts, worauf
sich eine Audit-Identitaet stuetzen darf).

Deshalb ist `run_id` DETERMINISTISCH abgeleitet:

    run_id = "run:" + sha256(experiment_id | parent_session_id | agent_id)[:32]

Eigenschaften: in beiden Hooks identisch, ohne Zustand, ohne Datenbank,
und nicht vom Modell beeinflussbar. `AUDIT_RUN_ID` uebersteuert das
explizit — fuer Faelle, in denen mehrere Subagenten zu EINEM
auswertbaren Lauf gehoeren.
"""

import os
import time
from typing import Iterable, List

import audit_db
from audit_models import (ActionEvent, AgentRegisteredEvent, AgentResult,
                          AssertionEvent, ClaimStatusEvent,
                          EvidenceRegisteredEvent, HardFailEvent, MetricPhase,
                          PhaseMetricsEvent, RepairAttempt, RepairAttemptEvent,
                          RunAttemptEvent, RunContext, RunFinishEvent,
                          RunStartEvent)
from audit_writer import AuditWriterHandle
from identity import canonical_json, sha256_text
from policy import ErrorClass, HardFail, Scope, scope_of

#: Umgebungsvariablen der Kontrollvariablen. Sie stehen in der
#: Experimentkonfiguration, nicht im Modellkontext — ein Agent kann seine
#: eigenen Kontrollvariablen damit nicht setzen.
ENV_MAP = {
    "experiment_id": "AUDIT_EXPERIMENT_ID",
    "workflow_condition": "AUDIT_WORKFLOW_CONDITION",
    "domain": "AUDIT_DOMAIN",
    "model_version": "AUDIT_MODEL_VERSION",
    "output_enforcement": "AUDIT_OUTPUT_ENFORCEMENT",
    "provider": "AUDIT_PROVIDER",
    "task_id": "AUDIT_TASK_ID",
    "replicate": "AUDIT_REPLICATE",
}

#: Optionale Kontrollvariablen. `None` heisst 'nicht gesetzt' und wird
#: nicht durch einen Ersatzwert ueberdeckt.
OPTIONAL_ENV_MAP = {
    "seed": "AUDIT_SEED",
    "batch_id": "AUDIT_BATCH_ID",
}


def make_run_id(experiment_id: str, parent_session_id: str,
                agent_id: str) -> str:
    return "run:" + sha256_text(
        f"{experiment_id}|{parent_session_id}|{agent_id}")[:32]


def context_from_env(env: dict = None) -> RunContext:
    """RunContext aus der Umgebung. Fehlt etwas, ist das §9.3."""
    env = env if env is not None else os.environ
    missing = [var for var in ENV_MAP.values() if not (env.get(var) or "").strip()]
    if missing:
        raise HardFail(
            ErrorClass.INVALID_RUN_CONTEXT,
            "Kontrollvariablen fehlen: " + ", ".join(sorted(missing))
            + ". Der Kontext wird NICHT geraten (§4).")
    fields = {field: env[var].strip() for field, var in ENV_MAP.items()}
    for field, var in OPTIONAL_ENV_MAP.items():
        value = (env.get(var) or "").strip()
        if value:
            fields[field] = value
    try:
        return RunContext(**fields)
    except Exception as exc:
        raise HardFail(ErrorClass.INVALID_RUN_CONTEXT,
                       f"RunContext ungueltig: {exc}")


def _jsonable(baseline):
    """`repair.baseline_of` liefert Mengen; JSON kennt nur Listen."""
    if baseline is None:
        return None
    return {"parseable": bool(baseline.get("parseable")),
            "evidence": sorted(baseline.get("evidence") or ()),
            "claims": dict(baseline.get("claims") or {})}


class AuditSession:
    """Ein Producer mit genau einem Writer fuer die Dauer seines Prozesses.

    Der Writer ist prozesslokal, die Serialisierung ueber alle Prozesse
    besorgt das Writer-Lock (siehe `audit_writer`).
    """

    def __init__(self, context: RunContext, run_id: str, agent_id: str,
                 db_path: str = None):
        self.context = context
        self.run_id = run_id
        self.agent_id = agent_id
        self.handle = AuditWriterHandle(db_path or audit_db.db_path())
        self._started = False

    # -- Lebenszyklus ------------------------------------------------------
    def __enter__(self) -> "AuditSession":
        self.handle.start()
        self._started = True
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        reason = "context_exit" if exc is None else f"error:{exc_type.__name__}"
        if exc is not None:
            # Ein abbrechender Producer darf keinen sauberen Run hinterlassen.
            try:
                self.hard_fail(ErrorClass.INTERNAL_NONREPRODUCIBLE,
                               f"Producer-Ausnahme {exc_type.__name__}: {exc}")
            except Exception:                                 # pragma: no cover
                pass
        self.report = self.handle.shutdown(reason=reason)
        return False

    def shutdown(self, reason: str = "requested") -> dict:
        return self.handle.shutdown(reason=reason)

    # -- Events ------------------------------------------------------------
    def start_run(self, parent_session_id: str, agent_type: str,
                  cwd: str = "") -> str:
        return self.handle.send(RunStartEvent(
            run_id=self.run_id, agent_id=self.agent_id,
            parent_session_id=parent_session_id, agent_type=agent_type,
            cwd=cwd, context=self.context))

    def register_agent(self, agent_id: str, agent_type: str = "") -> str:
        return self.handle.send(AgentRegisteredEvent(
            run_id=self.run_id, agent_id=agent_id, agent_type=agent_type))

    def record_action(self, raw_ref: str, tool_name: str = None,
                     phase: str = "tool_use", evidence_key: str = None,
                     agent_id: str = None) -> str:
        """KANAL B. Der `source_key` wird hier gebildet, nicht vom Agenten
        geliefert — Kanal B ist die Zugriffswahrheit und darf nicht von der
        Deklaration abhaengen (§7)."""
        return self.handle.send(ActionEvent(
            run_id=self.run_id, agent_id=agent_id or self.agent_id,
            tool_name=tool_name, raw_ref=raw_ref,
            source_key=audit_db.source_key(raw_ref), phase=phase,
            evidence_key=evidence_key))

    def record_actions(self, refs: Iterable[str], tool_name: str = None,
                       phase: str = "tool_use") -> List[str]:
        return [self.record_action(ref, tool_name=tool_name, phase=phase)
                for ref in refs]

    # -- Retrieval-Phase (§7) ---------------------------------------------
    def register_evidence(self, *, evidence_key: str, source_id: str,
                          document_version_id: str, unit_id: str,
                          structure_anchor: str, content_sha256: str,
                          chunk_text: str = None, chunk_text_sha256: str = None,
                          chunk_id: str = None, label: str = "",
                          locator: dict = None, anchor_is_fallback: bool = False,
                          source_ref: str = None, retrieval_run_id: str = None,
                          parser_name: str = "", parser_version: str = "",
                          chunker_name: str = "", chunker_version: str = "",
                          agent_id: str = None) -> str:
        """Einen ausgelieferten Beleg als Kanal-B-Ereignis registrieren.

        Erst diese Registrierung macht einen `ev:`-Schluessel zitierfaehig.
        Der Locator-Header zeigt dem Agenten den Schluessel an; ohne
        Registrierung ist er per Definition unbekannt und fuehrt nach §9.6
        zu BLOCKED.

        `chunk_text_sha256` beschreibt den TATSAECHLICH ausgelieferten Text.
        Wird stattdessen `chunk_text` uebergeben, wird der Hash hier
        gebildet — nie geraten.
        """
        if chunk_text_sha256 is None:
            if chunk_text is None:
                raise ValueError(
                    "chunk_text oder chunk_text_sha256 ist erforderlich: der "
                    "Hash des ausgelieferten Textes wird nicht geraten.")
            chunk_text_sha256 = sha256_text(chunk_text)
        return self.handle.send(EvidenceRegisteredEvent(
            run_id=self.run_id, agent_id=agent_id or self.agent_id,
            evidence_key=evidence_key,
            source_key=audit_db.source_key(source_ref or source_id),
            source_id=source_id, document_version_id=document_version_id,
            unit_id=unit_id, chunk_id=chunk_id,
            structure_anchor=structure_anchor, label=label,
            locator_json=canonical_json(locator) if locator else None,
            anchor_is_fallback=anchor_is_fallback,
            content_sha256=content_sha256,
            chunk_text_sha256=chunk_text_sha256,
            retrieval_run_id=retrieval_run_id, parser_name=parser_name,
            parser_version=parser_version, chunker_name=chunker_name,
            chunker_version=chunker_version))

    def record_retrieval(self, chunks: Iterable[dict],
                         retrieval_run_id: str = None,
                         agent_id: str = None) -> List[str]:
        """Eine ganze Retrieval-Auslieferung protokollieren.

        Erwartet die Chunkstruktur aus `chunker.chunk_units()`: `segments`
        mit Offsets und `_units` mit den Locator-Angaben. Registriert wird
        pro SEGMENT, nicht pro Chunk — die Provenienzeinheit ist das
        Segment (siehe `schema_provenance.sql`), und ein zusammengesetzter
        Chunk stuetzt in der Regel nur teilweise.

        Die Dauer wird als Phase `evidence_retrieval` gemessen.
        """
        event_ids: List[str] = []
        with self.phase_timer(MetricPhase.EVIDENCE_RETRIEVAL,
                              agent_id=agent_id) as timer:
            for chunk in chunks:
                units = {u["locator"]["unit_id"]: u for u in chunk.get("_units", [])}
                for segment in chunk.get("segments", []):
                    unit = units.get(segment["unit_id"])
                    if unit is None:
                        raise ValueError(
                            f"Segment verweist auf unbekannte unit_id "
                            f"{segment['unit_id']!r}; die Auslieferung ist "
                            f"nicht provenienzfaehig.")
                    loc = unit["locator"]
                    delivered = chunk["text"][segment["chunk_char_start"]:
                                              segment["chunk_char_end"]]
                    event_ids.append(self.register_evidence(
                        evidence_key=loc["evidence_key"],
                        source_id=loc["source_id"],
                        document_version_id=loc["document_version_id"],
                        unit_id=loc["unit_id"], chunk_id=chunk.get("chunk_id"),
                        structure_anchor=loc["structure_anchor"],
                        label=loc.get("label", ""), locator=loc,
                        anchor_is_fallback=bool(loc.get("anchor_is_fallback")),
                        content_sha256=loc["content_sha256"],
                        chunk_text=delivered,
                        retrieval_run_id=retrieval_run_id,
                        chunker_name=chunk.get("chunker_name", ""),
                        chunker_version=chunk.get("chunker_version", ""),
                        agent_id=agent_id))
            timer.record(detail=f"{len(event_ids)} Segmente registriert")
        return event_ids

    def declare_result(self, result: AgentResult) -> List[str]:
        """KANAL A. Jede Evidenzreferenz wird als eigene Assertion
        protokolliert; ein Claim ohne Evidenz erhaelt eine Assertion ohne
        Quelle, damit er im Protokoll nicht fehlt."""
        ids = []
        for claim in result.claims:
            if not claim.evidence:
                ids.append(self.handle.send(AssertionEvent(
                    run_id=self.run_id, agent_id=result.agent_id,
                    claim_id=claim.claim_id, claim=claim.text,
                    evidence_id=None, raw_source_ref="", source_key="",
                    locator=None, quote=None, stance=claim.stance,
                    required=not claim.evidence_free, reconciled=False)))
                continue
            for ref in claim.evidence:
                ids.append(self.handle.send(AssertionEvent(
                    run_id=self.run_id, agent_id=result.agent_id,
                    claim_id=claim.claim_id, claim=claim.text,
                    evidence_id=ref.evidence_id, raw_source_ref=ref.source_ref,
                    source_key=audit_db.source_key(ref.source_ref),
                    locator=ref.locator, quote=ref.quote, stance=claim.stance,
                    required=ref.required, reconciled=False)))
        return ids

    def record_claim_status(self, verdict, agent_id: str = None) -> str:
        """`verdict` ist ein `reconciler.ClaimVerdict`."""
        return self.handle.send(ClaimStatusEvent(
            run_id=self.run_id, agent_id=agent_id or self.agent_id,
            claim_id=verdict.claim_id, status=verdict.status,
            reason=verdict.reason, error_class=verdict.error_class,
            repair_count=verdict.repair_count,
            evidence_free=verdict.evidence_free,
            confirmed_evidence=list(verdict.confirmed_evidence),
            missing_evidence=list(verdict.missing_evidence),
            claim_text=verdict.claim_text))

    def record_repair(self, target_id: str, attempt: RepairAttempt,
                      agent_id: str = None, baseline: dict = None) -> str:
        return self.handle.send(RepairAttemptEvent(
            run_id=self.run_id, agent_id=agent_id or self.agent_id,
            target_id=target_id, attempt=attempt,
            baseline=_jsonable(baseline)))

    def hard_fail(self, error_class, cause: str, claim_id: str = None,
                  raw: str = None, scope: Scope = None) -> str:
        excerpt = None
        raw_sha = None
        if raw is not None:
            raw_sha = sha256_text(raw)
            excerpt = raw[:512]
        return self.handle.send(HardFailEvent(
            run_id=self.run_id, error_class=ErrorClass(error_class),
            scope=scope or scope_of(error_class), cause=cause,
            agent_id=self.agent_id, claim_id=claim_id,
            raw_payload_sha256=raw_sha, raw_payload_excerpt=excerpt))

    def record_metrics(self, phase, duration_ms: int = None,
                       input_tokens: int = None, output_tokens: int = None,
                       cached_input_tokens: int = None, cost_usd: float = None,
                       attempt: int = 1, detail: str = "",
                       agent_id: str = None) -> str:
        """Metrik EINER Phase. Die Phasentrennung ist verbindlich:
        initial_generation | format_repair | evidence_retrieval | total."""
        return self.handle.send(PhaseMetricsEvent(
            run_id=self.run_id, agent_id=agent_id or self.agent_id,
            phase=MetricPhase(phase), attempt=attempt,
            duration_ms=duration_ms, input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_input_tokens, cost_usd=cost_usd,
            model_version=self.context.model_version, detail=detail))

    def phase_timer(self, phase, attempt: int = 1, agent_id: str = None):
        """Kontextmanager, der die Dauer einer Phase misst und sendet.

        Token- und Kostenwerte werden NICHT geschaetzt; sie koennen ueber
        `timer.record(input_tokens=…, cost_usd=…)` nachgereicht werden.
        """
        return _PhaseTimer(self, phase, attempt, agent_id)

    def bump_attempt(self, status: str = "open", reason: str = "") -> str:
        return self.handle.send(RunAttemptEvent(
            run_id=self.run_id, status=status, reason=reason))

    def finish_run(self, status: str, attempts: int = 0) -> str:
        return self.handle.send(RunFinishEvent(
            run_id=self.run_id, status=status, attempts=attempts))

    # -- Reparaturfenster --------------------------------------------------
    def format_repair_guard(self):
        """Kontextmanager, der Kanal-B-Events waehrend einer
        Format-Reparatur unmoeglich macht (§8)."""
        return _RepairGuard(self.handle)


class _PhaseTimer:
    """Misst die Dauer einer Phase und sendet die Metrik beim Verlassen."""

    def __init__(self, session: "AuditSession", phase, attempt: int,
                 agent_id: str = None):
        self.session = session
        self.phase = MetricPhase(phase)
        self.attempt = attempt
        self.agent_id = agent_id
        self.extra = {}
        self._start = None

    def record(self, **fields) -> None:
        """Token- oder Kostenwerte nachreichen (gemessen, nicht geschaetzt)."""
        self.extra.update(fields)

    def __enter__(self) -> "_PhaseTimer":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        duration_ms = int((time.monotonic() - self._start) * 1000)
        detail = self.extra.pop("detail", "")
        if exc is not None:
            detail = (detail + f" [abgebrochen: {exc_type.__name__}]").strip()
        self.session.record_metrics(
            self.phase, duration_ms=duration_ms, attempt=self.attempt,
            detail=detail, agent_id=self.agent_id, **self.extra)
        return False


class _RepairGuard:
    def __init__(self, handle: AuditWriterHandle):
        self.handle = handle

    def __enter__(self):
        self.handle.block_channel_b(True)
        return self

    def __exit__(self, *exc):
        self.handle.block_channel_b(False)
        return False


def open_session(agent_id: str, parent_session_id: str, env: dict = None,
                 db_path: str = None) -> AuditSession:
    """Session mit Kontext aus der Umgebung und abgeleiteter `run_id`."""
    env = env if env is not None else os.environ
    context = context_from_env(env)
    run_id = (env.get("AUDIT_RUN_ID") or "").strip() or make_run_id(
        context.experiment_id, parent_session_id, agent_id)
    return AuditSession(context, run_id, agent_id, db_path=db_path)
