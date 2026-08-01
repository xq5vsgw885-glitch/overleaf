"""Typisierte Ereignis-, Kontext- und Ergebnismodelle (Spezifikation §2, §3, §6).

Alles, was zwischen Producer und Audit Writer die Prozessgrenze
ueberquert, ist hier definiert. Der Transport traegt ausschliesslich
UTF-8-JSON; die Struktur wird auf BEIDEN Seiten gegen dieselben Modelle
validiert (§2).

Serialisierung: `identity.canonical_json` — sortierte Schluessel, feste
Separatoren, kein ASCII-Escaping. Dieselbe Funktion, die schon die
Chunk- und Konfigurationsidentitaet traegt; ein zweiter
Serialisierungsbegriff waere ein stiller Provenienz-Eingang.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Any, Dict, List, Literal, Optional, Union
from uuid import uuid4

from pydantic import (BaseModel, BeforeValidator, ConfigDict, Field,
                      PlainSerializer, field_validator)

from identity import canonical_json, sha256_text
from policy import ErrorClass, Scope, Status

#: Version des Audit-Ereignisschemas. Producer und Writer muessen
#: uebereinstimmen; Abweichung ist §9.5 und fuehrt zu BLOCKED.
AUDIT_SCHEMA_VERSION = "2.1.0"


# ---------------------------------------------------------------------------
# Zeit
# ---------------------------------------------------------------------------

def _to_utc_second(value: Any) -> Any:
    """UTC-Zeitstempel mit Sekundenauflösung.

    Die Truncation auf Sekunden geschieht VOR der Hashbildung. Andernfalls
    waere der Payload-Hash von der Mikrosekunden-Darstellung des jeweiligen
    Python-Builds abhaengig und die Revalidierung nach dem Transport nicht
    bitgleich (§12.1).
    """
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        value = datetime.fromisoformat(text)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).replace(microsecond=0)
    return value


UtcTimestamp = Annotated[
    datetime,
    BeforeValidator(_to_utc_second),
    PlainSerializer(lambda d: d.isoformat(), return_type=str),
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}:{uuid4().hex}"


# ---------------------------------------------------------------------------
# Kontrollvariablen (§3)
# ---------------------------------------------------------------------------

class WorkflowCondition(str, Enum):
    A = "A"
    B = "B"
    C = "C"


class Domain(str, Enum):
    PHYSICS = "physics"
    BIOLOGY = "biology"
    CHEMISTRY = "chemistry"


class OutputEnforcement(str, Enum):
    NATIVE = "native"
    PROMPT = "prompt"


class Stance(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    UNCLEAR = "unclear"


class MetricPhase(str, Enum):
    """Verbindliche Phasentrennung fuer Laufzeit-, Token- und Kostenmetrik.

    Die Trennung ist keine Darstellungsfrage: Eine Formatreparatur kostet
    Tokens, ohne fachlichen Ertrag zu liefern, und ein Evidenz-Retrieval
    kostet Zeit, die nicht der Generierung zuzurechnen ist. Wer beides in
    eine Gesamtsumme wirft, kann die Bedingungen A/B/C nicht mehr
    vergleichen.

    `TOTAL` ist die gemessene Gesamtzeit des Laufs, NICHT die Summe der
    Phasen — die Differenz (Hook-Overhead, Wartezeiten, Persistenz) ist
    eine eigene, auswertbare Groesse.
    """

    INITIAL_GENERATION = "initial_generation"
    FORMAT_REPAIR = "format_repair"
    EVIDENCE_RETRIEVAL = "evidence_retrieval"
    TOTAL = "total"


class RepairKind(str, Enum):
    """Format- und Evidenzreparatur sind getrennte Zustaende (§8)."""

    FORMAT = "format"
    EVIDENCE = "evidence"


class _Strict(BaseModel):
    """Basis: unbekannte Felder verboten, Strings getrimmt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True,
                              use_enum_values=False, validate_assignment=True)

    def canonical(self) -> str:
        return canonical_json(self.model_dump(mode="json"))

    def content_hash(self) -> str:
        return sha256_text(self.canonical())


class RunContext(_Strict):
    """Unveraenderlicher Laufkontext (§3).

    `frozen=True` erzwingt die Laufzeit-Unveraenderlichkeit auf
    Objektebene; die Persistenzseite prueft zusaetzlich den
    `context_hash` gegen den bereits gespeicherten Wert (§9.4). Beides ist
    notwendig: das eine verhindert das Versehen im Prozess, das andere die
    Umdeutung zwischen Prozessen.
    """

    model_config = ConfigDict(extra="forbid", frozen=True,
                              str_strip_whitespace=True,
                              validate_assignment=True)

    experiment_id: str = Field(min_length=1)
    workflow_condition: WorkflowCondition
    domain: Domain
    model_version: str = Field(min_length=1)
    output_enforcement: OutputEnforcement
    provider: str = Field(min_length=1)
    schema_version: str = Field(default=AUDIT_SCHEMA_VERSION, min_length=1)

    # --- experimentelle Kontrollvariablen ---------------------------------
    #: Aufgabe innerhalb des Experiments. Ohne sie ist ein Vergleich der
    #: Bedingungen A/B/C nicht aufgabenweise auswertbar.
    task_id: str = Field(min_length=1)
    #: Wiederholung derselben (task_id, workflow_condition)-Kombination.
    #: 1-basiert; `0` waere zweideutig gegenueber 'nicht gesetzt'.
    replicate: int = Field(ge=1)
    #: Zufallssaat, sofern der Lauf eine kennt. `None` heisst 'nicht
    #: gesetzt' und wird NICHT auf 0 normalisiert — ein erfundener Seed
    #: waere eine erfundene Reproduzierbarkeit.
    seed: Optional[int] = None
    #: Auswertungsstapel (z. B. Pilot vs. Hauptlauf). Optional.
    batch_id: Optional[str] = None

    def context_hash(self) -> str:
        return self.content_hash()


# ---------------------------------------------------------------------------
# Fachliche Modelle (§6)
# ---------------------------------------------------------------------------

class EvidenceReference(_Strict):
    """Kanal-A-Referenz auf eine Quelle.

    `source_ref` ist die Rohangabe des Agenten und wird unveraendert
    protokolliert. `source_key` ist der Vergleichsschluessel; er wird
    NICHT vom Agenten gesetzt, sondern von `audit_db.source_key()`
    abgeleitet (siehe Reconciler).
    """

    evidence_id: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    locator: Optional[str] = None
    quote: Optional[str] = None
    required: bool = True


class Claim(_Strict):
    """Eine gestuetzte Aussage.

    `evidence_free` ist die explizite evidenzfreie Kategorie aus §6: eine
    Aussage, die per Deklaration keine externe Quelle beansprucht
    (Definition, Rechenweg, Zwischenergebnis). Sie ist NICHT `VERIFIED` —
    sie ist `UNVERIFIED` mit der Fehlerklasse NO_REQUIRED_EVIDENCE — aber
    sie ist von einem Claim mit vergessener Evidenzliste unterscheidbar.
    Ohne dieses Feld waere die leere Liste zweideutig (§12.16).
    """

    claim_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    stance: Stance = Stance.UNCLEAR
    evidence: List[EvidenceReference] = Field(default_factory=list)
    evidence_free: bool = False

    @field_validator("evidence")
    @classmethod
    def _unique_evidence_ids(cls, value):
        ids = [e.evidence_id for e in value]
        if len(ids) != len(set(ids)):
            raise ValueError("evidence_id innerhalb eines Claims nicht eindeutig")
        return value

    def required_evidence(self) -> List[EvidenceReference]:
        return [e for e in self.evidence if e.required]


class AgentResult(_Strict):
    """Strukturiertes Endergebnis eines Subagenten (Kanal A)."""

    schema_version: str = Field(default=AUDIT_SCHEMA_VERSION, min_length=1)
    run_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    summary: Optional[str] = None
    claims: List[Claim] = Field(default_factory=list)

    @field_validator("claims")
    @classmethod
    def _unique_claim_ids(cls, value):
        ids = [c.claim_id for c in value]
        if len(ids) != len(set(ids)):
            raise ValueError("claim_id nicht eindeutig")
        return value

    def evidence_ids(self) -> set:
        return {e.evidence_id for c in self.claims for e in c.evidence}


class ValidationFailure(_Strict):
    """Ein Validatorbefund.

    `format_only` trennt die reparierbare Syntaxklasse von allem anderen.
    Nur `format_only=True` darf ueberhaupt in die Repair Engine (§8).
    """

    error_class: ErrorClass
    message: str
    location: Optional[str] = None
    format_only: bool = False


class RepairAttempt(_Strict):
    """Protokollpflichtige Felder je Reparaturversuch (§8)."""

    attempt: int = Field(ge=1, le=99)
    kind: RepairKind
    error_class: ErrorClass
    input_sha256: str = Field(min_length=64, max_length=64)
    output_sha256: str = Field(min_length=64, max_length=64)
    validated: bool
    validation_detail: Optional[str] = None
    occurred_at: UtcTimestamp = Field(default_factory=utc_now)


# ---------------------------------------------------------------------------
# Ereignisse (§2)
# ---------------------------------------------------------------------------

class AuditEvent(_Strict):
    """Basis aller Audit-Ereignisse.

    Transportintegritaet nach §2: `event_id`, `event_type`,
    `schema_version`, `run_id` (soweit zutreffend) und UTC-Zeitstempel
    sind Pflicht. Der Integritaetswert liegt nicht im Event selbst,
    sondern im `EventEnvelope` — sonst muesste der Hash sich selbst
    enthalten.
    """

    event_id: str = Field(default_factory=lambda: new_id("ev"), min_length=1)
    event_type: str
    schema_version: str = Field(default=AUDIT_SCHEMA_VERSION, min_length=1)
    run_id: Optional[str] = None
    occurred_at: UtcTimestamp = Field(default_factory=utc_now)


class RunStartEvent(AuditEvent):
    event_type: Literal["run_started"] = "run_started"
    run_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    parent_session_id: str = Field(min_length=1)
    agent_type: str = Field(min_length=1)
    cwd: str = ""
    started_at: UtcTimestamp = Field(default_factory=utc_now)
    context: RunContext


class AgentRegisteredEvent(AuditEvent):
    """Weiterer Subagent innerhalb eines bestehenden Runs."""

    event_type: Literal["agent_registered"] = "agent_registered"
    run_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    agent_type: str = ""


class ActionEvent(AuditEvent):
    """KANAL B — tatsaechlich protokollierter physischer Zugriff.

    Append-only. Ein Kanal-B-Datensatz wird nie korrigiert, nie
    umgedeutet, nie geloescht (§10).
    """

    event_type: Literal["action_recorded"] = "action_recorded"
    run_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    tool_name: Optional[str] = None
    raw_ref: str = Field(min_length=1)
    source_key: str = Field(min_length=1)
    evidence_key: Optional[str] = None
    phase: Literal["retrieval", "tool_use", "transcript_scan"] = "tool_use"


class EvidenceRegisteredEvent(AuditEvent):
    """KANAL B — ein ausgelieferter Retrieval-Beleg (§7).

    Dies ist der Ereignistyp, der die Evidenzregistry eines Laufs fuellt.
    Ohne ihn kann ein Agent keinen `ev:`-Schluessel belegen: Der Locator-
    Header zeigt ihm den Schluessel zwar an, aber erst die Registrierung
    macht daraus einen protokollierten physischen Zugriff.

    Der Unterschied zu `ActionEvent` ist die Aufloesung. Ein `ActionEvent`
    sagt 'diese Quelle wurde beruehrt'; ein `EvidenceRegisteredEvent` sagt
    'genau dieser Textausschnitt aus genau dieser Dokumentfassung wurde zu
    genau diesem Zeitpunkt ausgeliefert'. Der Writer erzeugt aus diesem
    einen Ereignis beide Projektionen, damit Kanal B eine einzige
    Zugriffswahrheit bleibt.

    `chunk_text_sha256` ist der Hash des tatsaechlich ausgelieferten
    Textes. Er ist die Sperre gegen die stille Umdeutung eines Belegs:
    Derselbe `evidence_key` mit anderem Inhalt ist eine Kollision und
    damit ein Hard Fail.
    """

    event_type: Literal["evidence_registered"] = "evidence_registered"
    run_id: str = Field(min_length=1)
    agent_id: str = ""
    #: fassungsfreie Evidenzidentitaet, `identity.make_evidence_key`
    evidence_key: str = Field(min_length=1)
    #: Vergleichsschluessel fuer den Kanal-A-Abgleich (`audit_db.source_key`)
    source_key: str = Field(min_length=1)
    #: Dokumentidentitaet
    source_id: str = Field(min_length=1)
    document_version_id: str = Field(min_length=1)
    unit_id: str = Field(min_length=1)
    chunk_id: Optional[str] = None
    #: Fundstelle
    structure_anchor: str = Field(min_length=1)
    label: str = ""
    locator_json: Optional[str] = None
    anchor_is_fallback: bool = False
    #: Inhaltsidentitaet
    content_sha256: str = Field(min_length=64, max_length=64)
    chunk_text_sha256: str = Field(min_length=64, max_length=64)
    #: Herkunft der Auslieferung
    retrieval_run_id: Optional[str] = None
    parser_name: str = ""
    parser_version: str = ""
    chunker_name: str = ""
    chunker_version: str = ""
    retrieved_at: UtcTimestamp = Field(default_factory=utc_now)


class AssertionEvent(AuditEvent):
    """KANAL A — Behauptung des Agenten, unveraendert protokolliert."""

    event_type: Literal["assertion_declared"] = "assertion_declared"
    run_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    evidence_id: Optional[str] = None
    raw_source_ref: str = ""
    source_key: str = ""
    locator: Optional[str] = None
    quote: Optional[str] = None
    stance: Stance = Stance.UNCLEAR
    required: bool = True
    reconciled: bool = False


class ClaimStatusEvent(AuditEvent):
    event_type: Literal["claim_status"] = "claim_status"
    run_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    status: Status
    reason: str = ""
    error_class: Optional[ErrorClass] = None
    repair_count: int = Field(default=0, ge=0)
    evidence_free: bool = False
    confirmed_evidence: List[str] = Field(default_factory=list)
    missing_evidence: List[str] = Field(default_factory=list)
    claim_text: str = ""


class RepairAttemptEvent(AuditEvent):
    event_type: Literal["repair_attempt"] = "repair_attempt"
    run_id: str = Field(min_length=1)
    agent_id: str = ""
    target_id: str = Field(min_length=1)     # claim_id oder Objektbezeichner
    attempt: RepairAttempt
    #: Was in der verworfenen Ausgabe nachweislich stand (aus
    #: `repair.baseline_of`). Der naechste Durchgang prueft die neue
    #: Ausgabe dagegen — ohne diese Mitschrift waeren die Verbote aus §8
    #: auf dem Hook-Pfad nicht pruefbar.
    baseline: Optional[Dict[str, Any]] = None


class HardFailEvent(AuditEvent):
    event_type: Literal["hard_fail"] = "hard_fail"
    error_class: ErrorClass
    scope: Scope
    cause: str = Field(min_length=1)
    agent_id: Optional[str] = None
    claim_id: Optional[str] = None
    #: Referenz auf die unveraendert vorliegende Rohpayload. Persistiert
    #: wird der Hash plus ein begrenzter, bereinigter Auszug — §9 verlangt
    #: unveraenderte Referenzierbarkeit, verbietet aber unkontrollierten
    #: Abfluss sensibler Rohdaten in Enddokumente.
    raw_payload_sha256: Optional[str] = None
    raw_payload_excerpt: Optional[str] = None


class RunFinishEvent(AuditEvent):
    event_type: Literal["run_finished"] = "run_finished"
    run_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    attempts: int = Field(default=0, ge=0)
    finished_at: UtcTimestamp = Field(default_factory=utc_now)


class RunAttemptEvent(AuditEvent):
    """Zaehlt einen Durchsetzungsversuch (SubagentStop-Block) hoch."""

    event_type: Literal["run_attempt"] = "run_attempt"
    run_id: str = Field(min_length=1)
    status: str = "open"
    reason: str = ""


class PhaseMetricsEvent(AuditEvent):
    """Laufzeit-, Token- und Kostenmetrik EINER Phase (§ Zusatzvorgabe).

    Jede Messung haengt eindeutig an `run_id`; `agent_id` und `attempt`
    ordnen sie zusaetzlich zu. Kosten werden als Dezimalbetrag in USD
    gefuehrt und NICHT aus Tokenzahlen geschaetzt — eine geschaetzte
    Kostenangabe waere im Ergebnisbericht von einer gemessenen nicht mehr
    unterscheidbar. Fehlt die Angabe, bleibt sie `None`.
    """

    event_type: Literal["phase_metrics"] = "phase_metrics"
    run_id: str = Field(min_length=1)
    agent_id: str = ""
    phase: MetricPhase
    #: 1-basierter Versuchszaehler innerhalb der Phase (Reparaturen).
    attempt: int = Field(default=1, ge=1)
    duration_ms: Optional[int] = Field(default=None, ge=0)
    input_tokens: Optional[int] = Field(default=None, ge=0)
    output_tokens: Optional[int] = Field(default=None, ge=0)
    cached_input_tokens: Optional[int] = Field(default=None, ge=0)
    cost_usd: Optional[float] = Field(default=None, ge=0)
    model_version: str = ""
    detail: str = ""


class WriterShutdownEvent(AuditEvent):
    """Typisiertes Sentinel (§2). Ausdruecklich kein magisches Objekt:
    dasselbe Modell, dieselbe Validierung, derselbe Payload-Hash wie jedes
    fachliche Event."""

    event_type: Literal["writer_shutdown"] = "writer_shutdown"
    reason: str = "requested"
    requested_at: UtcTimestamp = Field(default_factory=utc_now)


#: Registry fuer die Revalidierung nach Empfang. Ein Event-Typ, der hier
#: nicht steht, ist eine nicht vertrauenswuerdige Payload (§9.8).
EVENT_MODELS: Dict[str, type] = {
    "run_started": RunStartEvent,
    "agent_registered": AgentRegisteredEvent,
    "action_recorded": ActionEvent,
    "evidence_registered": EvidenceRegisteredEvent,
    "assertion_declared": AssertionEvent,
    "claim_status": ClaimStatusEvent,
    "repair_attempt": RepairAttemptEvent,
    "hard_fail": HardFailEvent,
    "run_finished": RunFinishEvent,
    "run_attempt": RunAttemptEvent,
    "phase_metrics": PhaseMetricsEvent,
    "writer_shutdown": WriterShutdownEvent,
}

AnyEvent = Union[
    RunStartEvent, AgentRegisteredEvent, ActionEvent, EvidenceRegisteredEvent,
    AssertionEvent,
    ClaimStatusEvent, RepairAttemptEvent, HardFailEvent, RunFinishEvent,
    RunAttemptEvent, PhaseMetricsEvent, WriterShutdownEvent,
]

#: Ereignisse, die den Kanal-B-Bestand veraendern. Waehrend einer
#: Format-Reparatur sind sie verboten (§8).
CHANNEL_B_EVENT_TYPES = frozenset({"action_recorded", "evidence_registered"})


# ---------------------------------------------------------------------------
# Transport (§2)
# ---------------------------------------------------------------------------

def payload_hash(payload: dict) -> str:
    return sha256_text(canonical_json(payload))


class EventEnvelope(_Strict):
    """Transporthuelle mit Integritaetswert.

    Der `payload_sha256` wird vom Producer gebildet und vom Writer
    nachgerechnet. Abweichung ist §9.9, dieselbe `event_id` mit anderem
    Hash ist §9.10.
    """

    event_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    schema_version: str = Field(min_length=1)
    run_id: Optional[str] = None
    occurred_at: UtcTimestamp
    payload: Dict[str, Any]
    payload_sha256: str = Field(min_length=64, max_length=64)
    producer_pid: int = 0

    @classmethod
    def wrap(cls, event: AuditEvent, producer_pid: int = 0) -> "EventEnvelope":
        payload = event.model_dump(mode="json")
        return cls(
            event_id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            run_id=event.run_id,
            occurred_at=event.occurred_at,
            payload=payload,
            payload_sha256=payload_hash(payload),
            producer_pid=producer_pid,
        )

    def to_json(self) -> str:
        """UTF-8-kompatibler JSON-String — das einzige Queue-Format (§2)."""
        return canonical_json(self.model_dump(mode="json"))

    def recomputed_hash(self) -> str:
        return payload_hash(self.payload)

    def unwrap(self) -> AuditEvent:
        """Revalidierung gegen dasselbe Modell wie beim Producer."""
        model = EVENT_MODELS.get(self.event_type)
        if model is None:
            raise ValueError(f"unbekannter event_type: {self.event_type!r}")
        event = model.model_validate(self.payload)
        if event.event_id != self.event_id:
            raise ValueError("event_id in Huelle und Payload weichen ab")
        if event.schema_version != self.schema_version:
            raise ValueError("schema_version in Huelle und Payload weichen ab")
        if event.run_id != self.run_id:
            raise ValueError("run_id in Huelle und Payload weichen ab")
        return event
