"""Fehlerklassen, Statuswerte und Hard-Fail-Eskalation (Spezifikation §6, §9).

Diese Datei enthaelt bewusst keine Logik mit Datenbank- oder
Prozessabhaengigkeit: Sie ist die stabile Vokabelliste, auf die Writer,
Reconciler, Repair Engine, Renderer und Tests sich beziehen. Eine
Fehlerklasse ist ein VERTRAG — ihr String wird persistiert und darf
nachtraeglich nicht umbenannt werden.
"""

from enum import Enum


class Status(str, Enum):
    """Genau ein Status pro Claim und pro daraus erzeugtem Chunk (§6)."""

    VERIFIED = "VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"


class ExportMode(str, Enum):
    EVALUATION = "evaluation"
    PRODUCTION = "production"


class Scope(str, Enum):
    """Geltungsbereich einer Eskalation. Ableitung deterministisch, siehe
    HARD_FAIL_SCOPE."""

    CLAIM = "claim"
    AGENT = "agent"
    RUN = "run"
    WRITER = "writer"


class ErrorClass(str, Enum):
    """Stabile Fehlerklassen.

    Die ersten 14 Eintraege entsprechen 1:1 den Hard-Fail-Bedingungen aus
    §9 in der dortigen Reihenfolge. Danach folgen Klassen, die entweder
    einen Hard Fail spezialisieren oder ausdruecklich KEIN Hard Fail sind.
    """

    # --- §9.1 bis §9.14 ---------------------------------------------------
    PROMPT_INJECTION = "PROMPT_INJECTION"                     # 1
    MISSING_RUN_ID = "MISSING_RUN_ID"                         # 2
    INVALID_RUN_CONTEXT = "INVALID_RUN_CONTEXT"               # 3
    CONTEXT_MUTATION = "CONTEXT_MUTATION"                     # 4
    SCHEMA_VERSION_CONFLICT = "SCHEMA_VERSION_CONFLICT"       # 5
    FOREIGN_RUN_REFERENCE = "FOREIGN_RUN_REFERENCE"           # 6
    HOOK_ACCESS_DENIED = "HOOK_ACCESS_DENIED"                 # 7
    CORRUPT_QUEUE_PAYLOAD = "CORRUPT_QUEUE_PAYLOAD"           # 8
    PAYLOAD_HASH_MISMATCH = "PAYLOAD_HASH_MISMATCH"           # 9
    EVENT_ID_CONFLICT = "EVENT_ID_CONFLICT"                   # 10
    CHANNEL_B_MUTATION = "CHANNEL_B_MUTATION"                 # 11
    INTERNAL_NONREPRODUCIBLE = "INTERNAL_NONREPRODUCIBLE"     # 12
    OUTPUT_ENFORCEMENT_SWITCH = "OUTPUT_ENFORCEMENT_SWITCH"   # 13
    WRITER_FAILURE = "WRITER_FAILURE"                         # 14

    # --- Spezialisierungen ------------------------------------------------
    # §6/§7: eine Evidence-ID, die in diesem Run nie physisch protokolliert
    # wurde, ist eine nachtraeglich konstruierte Referenz (§9.6).
    UNKNOWN_EVIDENCE_ID = "UNKNOWN_EVIDENCE_ID"
    # §8: die Reparatur hat eine Quelle eingefuehrt — Manipulation (§9.1).
    EVIDENCE_INTRODUCED_BY_REPAIR = "EVIDENCE_INTRODUCED_BY_REPAIR"
    # §8: die Reparatur hat den Claim semantisch veraendert.
    CLAIM_MUTATED_BY_REPAIR = "CLAIM_MUTATED_BY_REPAIR"
    # §8: Format-Reparatur hat einen Kanal-B-Datensatz erzeugen wollen.
    CHANNEL_B_WRITE_DURING_REPAIR = "CHANNEL_B_WRITE_DURING_REPAIR"

    # --- ausdruecklich KEIN Hard Fail -------------------------------------
    # §8: zwei erfolglose reine Formatreparaturen -> UNVERIFIED.
    FORMAT_VALIDATION_EXHAUSTED = "FORMAT_VALIDATION_EXHAUSTED"
    # §6: erforderliche Evidenz fehlt teilweise -> PARTIALLY_VERIFIED.
    EVIDENCE_INCOMPLETE = "EVIDENCE_INCOMPLETE"
    # §6/§12.16: Claim ohne erforderliche Evidenz -> UNVERIFIED.
    NO_REQUIRED_EVIDENCE = "NO_REQUIRED_EVIDENCE"


#: Fehlerklassen, die sofort und ohne Reparaturversuch zu BLOCKED fuehren.
HARD_FAIL_CLASSES = frozenset({
    ErrorClass.PROMPT_INJECTION,
    ErrorClass.MISSING_RUN_ID,
    ErrorClass.INVALID_RUN_CONTEXT,
    ErrorClass.CONTEXT_MUTATION,
    ErrorClass.SCHEMA_VERSION_CONFLICT,
    ErrorClass.FOREIGN_RUN_REFERENCE,
    ErrorClass.HOOK_ACCESS_DENIED,
    ErrorClass.CORRUPT_QUEUE_PAYLOAD,
    ErrorClass.PAYLOAD_HASH_MISMATCH,
    ErrorClass.EVENT_ID_CONFLICT,
    ErrorClass.CHANNEL_B_MUTATION,
    ErrorClass.INTERNAL_NONREPRODUCIBLE,
    ErrorClass.OUTPUT_ENFORCEMENT_SWITCH,
    ErrorClass.WRITER_FAILURE,
    ErrorClass.UNKNOWN_EVIDENCE_ID,
    ErrorClass.EVIDENCE_INTRODUCED_BY_REPAIR,
    ErrorClass.CLAIM_MUTATED_BY_REPAIR,
    ErrorClass.CHANNEL_B_WRITE_DURING_REPAIR,
})

#: Deterministische Eskalation (§9, letzter Absatz). Der Geltungsbereich
#: folgt aus der Fehlerklasse, nicht aus der Aufrufstelle.
#:
#: Leitregel: Betrifft der Defekt die Vertrauenswuerdigkeit des
#: Laufkontexts, des Transports oder der Persistenz, ist der ganze Run
#: blockiert. Betrifft er eine einzelne Aussage, bleibt der Rest des Runs
#: auswertbar.
HARD_FAIL_SCOPE = {
    ErrorClass.PROMPT_INJECTION: Scope.RUN,
    ErrorClass.MISSING_RUN_ID: Scope.RUN,
    ErrorClass.INVALID_RUN_CONTEXT: Scope.RUN,
    ErrorClass.CONTEXT_MUTATION: Scope.RUN,
    ErrorClass.SCHEMA_VERSION_CONFLICT: Scope.RUN,
    ErrorClass.FOREIGN_RUN_REFERENCE: Scope.RUN,
    ErrorClass.HOOK_ACCESS_DENIED: Scope.AGENT,
    ErrorClass.CORRUPT_QUEUE_PAYLOAD: Scope.RUN,
    ErrorClass.PAYLOAD_HASH_MISMATCH: Scope.RUN,
    ErrorClass.EVENT_ID_CONFLICT: Scope.RUN,
    ErrorClass.CHANNEL_B_MUTATION: Scope.RUN,
    ErrorClass.INTERNAL_NONREPRODUCIBLE: Scope.RUN,
    ErrorClass.OUTPUT_ENFORCEMENT_SWITCH: Scope.RUN,
    ErrorClass.WRITER_FAILURE: Scope.WRITER,
    ErrorClass.UNKNOWN_EVIDENCE_ID: Scope.CLAIM,
    ErrorClass.EVIDENCE_INTRODUCED_BY_REPAIR: Scope.CLAIM,
    ErrorClass.CLAIM_MUTATED_BY_REPAIR: Scope.CLAIM,
    ErrorClass.CHANNEL_B_WRITE_DURING_REPAIR: Scope.RUN,
}

#: Reparaturversuche sind ausschliesslich fuer Syntax- und Formatfehler
#: zulaessig, hoechstens zwei (§8).
MAX_FORMAT_REPAIRS = 2

#: Laufstatus in `runs.status`. `open` und `degraded` sind Altwerte aus
#: Schema v1.0 und bleiben lesbar erhalten.
RUN_STATUS_OPEN = "open"
RUN_STATUS_VERIFIED = "verified"
RUN_STATUS_DEGRADED = "degraded"
RUN_STATUS_ABANDONED = "abandoned"
RUN_STATUS_BLOCKED = "blocked"
RUN_STATUS_UNVERIFIED = "unverified"

#: Ein Run mit einem dieser Status darf NIE als erfolgreicher Lauf gelten.
NON_SUCCESS_RUN_STATUS = frozenset({
    RUN_STATUS_BLOCKED, RUN_STATUS_ABANDONED, RUN_STATUS_UNVERIFIED,
    RUN_STATUS_DEGRADED, RUN_STATUS_OPEN,
})


#: Auswertungszwecke, die AUSSCHLIESSLICH im Evaluationsmodus exportiert
#: werden duerfen. Ein Produktionsexport blendet PARTIALLY_VERIFIED,
#: UNVERIFIED und BLOCKED kommentarlos aus — genau die drei Klassen, deren
#: Haeufigkeit die Studie misst. Ein Pilot mit Produktionsexport wuerde
#: seine eigene Zielgroesse loeschen.
EVALUATION_ONLY_PURPOSES = frozenset({"pilot", "main", "evaluation", "study"})


class ExportModeNotAllowed(RuntimeError):
    pass


def assert_export_mode_allowed(mode, purpose: str) -> None:
    if (purpose or "").lower() in EVALUATION_ONLY_PURPOSES \
            and ExportMode(mode) is not ExportMode.EVALUATION:
        raise ExportModeNotAllowed(
            f"Zweck {purpose!r} verlangt export_mode='evaluation'. Im "
            f"Produktionsmodus sind PARTIALLY_VERIFIED, UNVERIFIED und "
            f"BLOCKED nicht mehr messbar.")


def is_hard_fail(error_class) -> bool:
    return ErrorClass(error_class) in HARD_FAIL_CLASSES


def scope_of(error_class) -> Scope:
    """Eskalationsbereich einer Fehlerklasse. Unbekannte Klassen sind
    bewusst nicht tolerant behandelt: eine nicht klassifizierbare
    Ausnahme ist §9.12 und blockiert den Run."""
    ec = ErrorClass(error_class)
    return HARD_FAIL_SCOPE.get(ec, Scope.RUN)


class HardFail(Exception):
    """Anwendungsseitige Hard-Fail-Bedingung.

    Wird dort geworfen, wo der Kontrollfluss abbrechen MUSS. Wo der
    Kontrollfluss weiterlaufen soll (Writer-Schleife), wird stattdessen
    ein HardFailEvent persistiert.
    """

    def __init__(self, error_class, cause: str, run_id: str = None,
                 agent_id: str = None, claim_id: str = None,
                 raw_payload_sha256: str = None):
        self.error_class = ErrorClass(error_class)
        self.scope = scope_of(self.error_class)
        self.cause = cause
        self.run_id = run_id
        self.agent_id = agent_id
        self.claim_id = claim_id
        self.raw_payload_sha256 = raw_payload_sha256
        super().__init__(f"{self.error_class.value} [{self.scope.value}]: {cause}")
