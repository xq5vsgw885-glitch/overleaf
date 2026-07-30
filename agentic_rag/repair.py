"""Repair Engine (Spezifikation §8).

## Genau eine Aufgabe

Syntax und Format. Nichts sonst. Hoechstens zwei Versuche.

Der Reparaturkontext enthaelt ausschliesslich: urspruengliche Ausgabe,
erwartetes Schema, konkreter Validatorfehler, bereits zulaessige
Evidence-IDs. Es gibt keinen Codepfad, der ihm die Aufgabe, das Transkript
oder Retrievalergebnisse gibt — waere einer vorhanden, koennte die
Reparatur fachlich ergaenzen, und der Unterschied zwischen 'Format
korrigiert' und 'Aussage nachgeliefert' waere im Protokoll nicht mehr
sichtbar.

## Vier Verbote, alle durchgesetzt

1. keine neue fachliche Aussage  -> Claim-Text-Vergleich, CLAIM_MUTATED_BY_REPAIR
2. keine semantische Aenderung   -> desgleichen
3. keine neue Quelle/Evidence-ID -> Mengenvergleich, EVIDENCE_INTRODUCED_BY_REPAIR
4. keine Retrieval-Aktion, kein Kanal-B-Datensatz
                                 -> `AuditSession.format_repair_guard()`
                                    blockiert Kanal-B-Events waehrend des
                                    Reparaturfensters

## Ausgang

Nach zwei erfolglosen reinen Formatreparaturen: `UNVERIFIED` mit
`FORMAT_VALIDATION_EXHAUSTED` — kein Hard Fail, sofern keine
Hard-Fail-Bedingung vorliegt.
"""

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set

from audit_models import (AgentResult, RepairAttempt, RepairKind,
                          ValidationFailure)
from identity import sha256_text
from policy import MAX_FORMAT_REPAIRS, ErrorClass, Status

#: Signatur einer Reparaturfunktion. In der Produktion ein Modellaufruf
#: mit dem eingeschraenkten Kontext, in Tests eine deterministische
#: Funktion — der Engine ist beides gleich (§12: keine Netzaufrufe).
RepairFn = Callable[["RepairContext"], str]


@dataclass(frozen=True)
class RepairContext:
    """Der VOLLSTAENDIGE Kontext einer Formatreparatur. Mehr gibt es nicht."""

    original_output: str
    expected_schema: dict
    validation_error: str
    allowed_evidence_ids: frozenset
    attempt: int


@dataclass
class RepairOutcome:
    result: Optional[AgentResult]
    status: Status
    attempts: List[RepairAttempt] = field(default_factory=list)
    failures: List[ValidationFailure] = field(default_factory=list)
    error_class: Optional[ErrorClass] = None
    reason: str = ""
    final_output: str = ""

    @property
    def repair_count(self) -> int:
        return len([a for a in self.attempts if a.kind is RepairKind.FORMAT])


def validate_output(raw: str) -> tuple:
    """Rohausgabe gegen `AgentResult` validieren.

    Gibt `(result_or_None, ValidationFailure_or_None)` zurueck. Ein
    JSON-Syntaxfehler und ein Schemaverstoss sind beide `format_only` —
    beides ist ohne fachliche Ergaenzung korrigierbar. Alles andere ist es
    nicht.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, ValidationFailure(
            error_class=ErrorClass.FORMAT_VALIDATION_EXHAUSTED,
            message=f"kein gueltiges JSON: {exc}", location="$",
            format_only=True)
    if not isinstance(data, dict):
        return None, ValidationFailure(
            error_class=ErrorClass.FORMAT_VALIDATION_EXHAUSTED,
            message="Wurzelobjekt ist kein JSON-Objekt", location="$",
            format_only=True)
    try:
        return AgentResult.model_validate(data), None
    except Exception as exc:
        return None, ValidationFailure(
            error_class=ErrorClass.FORMAT_VALIDATION_EXHAUSTED,
            message=f"Schemaverstoss: {exc}", location="$", format_only=True)


def _evidence_ids(data: dict) -> Set[str]:
    ids = set()
    for claim in (data or {}).get("claims") or []:
        for ref in (claim or {}).get("evidence") or []:
            value = (ref or {}).get("evidence_id")
            if isinstance(value, str):
                ids.add(value)
            source = (ref or {}).get("source_ref")
            if isinstance(source, str):
                ids.add("source:" + source)
    return ids


def _claim_texts(data: dict) -> Dict[str, str]:
    out = {}
    for claim in (data or {}).get("claims") or []:
        if isinstance(claim, dict) and isinstance(claim.get("claim_id"), str):
            out[claim["claim_id"]] = str(claim.get("text", ""))
    return out


def _safe_load(raw: str) -> dict:
    try:
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


#: Tolerante Extraktion aus einer NICHT parsebaren Ausgabe.
_EVIDENCE_ID_RE = re.compile(r'"evidence_id"\s*:\s*"((?:[^"\\]|\\.)*)"')
_SOURCE_REF_RE = re.compile(r'"source_ref"\s*:\s*"((?:[^"\\]|\\.)*)"')
_CLAIM_RE = re.compile(
    r'"claim_id"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"')


def baseline_of(raw: str) -> dict:
    """Was in der urspruenglichen Ausgabe NACHWEISLICH stand.

    DEFEKT, den diese Funktion behebt: Die erste Fassung las die Baseline
    ausschliesslich mit `json.loads`. Der haeufigste Reparaturfall ist aber
    gerade die nicht parsebare Ausgabe — dort lieferte die Baseline eine
    leere Menge, und die drei Verbote aus §8 (keine neue Quelle, keine neue
    Aussage, keine semantische Aenderung) waren wirkungslos: Gegen eine
    leere Referenzmenge ist jede Ergaenzung erlaubt.

    Jetzt wird die Baseline notfalls lexikalisch gewonnen. Sie ist dann
    unvollstaendig — ein abgeschnittener Claim fehlt darin —, aber nie
    falsch: Was hier steht, stand auch in der Ausgabe.
    """
    data = _safe_load(raw)
    if data:
        return {"parseable": True, "evidence": _evidence_ids(data),
                "claims": _claim_texts(data)}
    evidence = set(_EVIDENCE_ID_RE.findall(raw or ""))
    evidence |= {"source:" + s for s in _SOURCE_REF_RE.findall(raw or "")}
    return {"parseable": False, "evidence": evidence,
            "claims": dict(_CLAIM_RE.findall(raw or ""))}


def repair_format(raw_output: str, repair_fn: RepairFn,
                  allowed_evidence_ids: Set[str] = None,
                  max_attempts: int = MAX_FORMAT_REPAIRS,
                  original_claim_texts: Dict[str, str] = None) -> RepairOutcome:
    """Formatreparatur mit hoechstens `max_attempts` Versuchen.

    Der Vergleich der erlaubten Evidence-IDs geschieht gegen die Menge, die
    VOR der Reparatur zulaessig war. Wer `allowed_evidence_ids` nicht setzt,
    bekommt die IDs aus der urspruenglichen Ausgabe — eine Reparatur darf
    dann nichts hinzufuegen, aber weglassen darf sie.
    """
    outcome = RepairOutcome(result=None, status=Status.UNVERIFIED,
                            final_output=raw_output)

    result, failure = validate_output(raw_output)
    if result is not None:
        outcome.result = result
        outcome.status = Status.UNVERIFIED  # Statusfindung macht der Reconciler
        outcome.reason = "Ausgabe war formal gueltig; keine Reparatur noetig"
        return outcome
    outcome.failures.append(failure)

    if not failure.format_only:
        outcome.error_class = failure.error_class
        outcome.reason = "kein reiner Formatfehler — Reparatur unzulaessig"
        return outcome

    baseline = baseline_of(raw_output)
    allowed = set(allowed_evidence_ids) if allowed_evidence_ids is not None \
        else set(baseline["evidence"])
    claim_baseline = dict(original_claim_texts or baseline["claims"])

    current = raw_output
    for attempt_no in range(1, max_attempts + 1):
        context = RepairContext(
            original_output=current,
            expected_schema=AgentResult.model_json_schema(),
            validation_error=outcome.failures[-1].message,
            allowed_evidence_ids=frozenset(allowed),
            attempt=attempt_no,
        )
        repaired = repair_fn(context)
        repaired_data = _safe_load(repaired)

        attempt = RepairAttempt(
            attempt=attempt_no, kind=RepairKind.FORMAT,
            error_class=ErrorClass.FORMAT_VALIDATION_EXHAUSTED,
            input_sha256=sha256_text(current),
            output_sha256=sha256_text(repaired), validated=False)

        # --- Verbot 3: keine neue Quelle oder Evidence-ID ------------------
        introduced = _evidence_ids(repaired_data) - allowed
        if introduced:
            attempt.error_class = ErrorClass.EVIDENCE_INTRODUCED_BY_REPAIR
            attempt.validation_detail = (
                "Reparatur fuehrt neue Evidenzreferenzen ein: "
                + ", ".join(sorted(introduced)))
            outcome.attempts.append(attempt)
            outcome.status = Status.BLOCKED
            outcome.error_class = ErrorClass.EVIDENCE_INTRODUCED_BY_REPAIR
            outcome.reason = attempt.validation_detail
            outcome.final_output = repaired
            return outcome

        # --- Verbote 1 und 2: keine fachliche Aenderung --------------------
        # Sichtbare Claim-Texte muessen bytegleich bleiben. Neue claim_ids
        # sind nur zulaessig, wenn die Baseline nachweislich unvollstaendig
        # war (abgeschnittene Ausgabe) — dann ist nicht entscheidbar, ob der
        # Claim vorher schon dastand. Neue QUELLEN bleiben auch in diesem
        # Fall ausgeschlossen; ein so ergaenzter Claim ist ohne Evidenz und
        # wird vom Reconciler ohnehin UNVERIFIED (§6).
        mutated = [cid for cid, text in _claim_texts(repaired_data).items()
                   if cid in claim_baseline and text != claim_baseline[cid]]
        added = ([cid for cid in _claim_texts(repaired_data)
                  if cid not in claim_baseline] if baseline["parseable"] else [])
        if mutated or added:
            attempt.error_class = ErrorClass.CLAIM_MUTATED_BY_REPAIR
            attempt.validation_detail = (
                "Reparatur veraendert oder ergaenzt fachliche Aussagen: "
                + ", ".join(sorted(set(mutated) | set(added))))
            outcome.attempts.append(attempt)
            outcome.status = Status.BLOCKED
            outcome.error_class = ErrorClass.CLAIM_MUTATED_BY_REPAIR
            outcome.reason = attempt.validation_detail
            outcome.final_output = repaired
            return outcome

        result, failure = validate_output(repaired)
        if result is not None:
            attempt.validated = True
            attempt.validation_detail = "Ausgabe validiert"
            outcome.attempts.append(attempt)
            outcome.result = result
            outcome.status = Status.UNVERIFIED  # weiter zum Reconciler
            outcome.reason = f"Formatreparatur im Versuch {attempt_no} erfolgreich"
            outcome.final_output = repaired
            return outcome

        attempt.validation_detail = failure.message
        outcome.attempts.append(attempt)
        outcome.failures.append(failure)
        current = repaired

    outcome.status = Status.UNVERIFIED
    outcome.error_class = ErrorClass.FORMAT_VALIDATION_EXHAUSTED
    outcome.reason = (f"{max_attempts} Formatreparaturen erschoepft, Ausgabe "
                      f"bleibt formal ungueltig")
    outcome.final_output = current
    return outcome
