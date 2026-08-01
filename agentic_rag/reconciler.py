"""Channel Reconciler (Spezifikation §6, §7).

## Zwei-Kanal-Prinzip

* Kanal A — was der Agent BEHAUPTET: Claims und Evidenzreferenzen.
* Kanal B — was tatsaechlich GESCHEHEN ist: protokollierte physische
  Tool-, Datei- und Quellenzugriffe.

Kanal B ist die historische Zugriffswahrheit. Eine Quelle gilt nur als
bestaetigt, wenn sie im SELBEN `run_id` physisch protokolliert wurde — und
bei agentweise getrennten Evidenzraeumen zusaetzlich beim richtigen
`agent_id`.

## Reproduzierbarkeit

`reconcile()` ist eine reine Funktion ueber (Kanal A, Kanal B, Optionen).
`reconcile_run()` liest beide Kanaele aus der Datenbank und ruft dieselbe
Funktion. Damit ist jedes Ergebnis jederzeit neu berechenbar und
vergleichbar — die Forderung aus §7, letzter Punkt.
"""

import json
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Sequence, Set

import audit_db
from audit_models import AgentResult, Claim
from policy import ErrorClass, Status


@dataclass(frozen=True)
class ChannelBRecord:
    """Ein protokollierter physischer Zugriff."""

    run_id: str
    agent_id: Optional[str]
    source_key: str
    evidence_key: Optional[str] = None
    phase: str = "tool_use"


@dataclass
class ClaimVerdict:
    claim_id: str
    claim_text: str
    status: Status
    reason: str = ""
    error_class: Optional[ErrorClass] = None
    repair_count: int = 0
    evidence_free: bool = False
    confirmed_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"claim_id": self.claim_id, "claim_text": self.claim_text,
                "status": self.status.value, "reason": self.reason,
                "error_class": self.error_class.value if self.error_class else None,
                "repair_count": self.repair_count,
                "evidence_free": self.evidence_free,
                "confirmed_evidence": list(self.confirmed_evidence),
                "missing_evidence": list(self.missing_evidence)}


@dataclass
class RunReconciliation:
    run_id: str
    verdicts: List[ClaimVerdict]
    channel_b_keys: List[str]
    agent_scoped: bool
    production: bool
    #: Registrierte Evidenzschluessel dieses Laufs. Ist die Liste leer,
    #: laeuft der Abgleich im Uebergangsmodus (siehe `_verdict`).
    registry_keys: List[str] = field(default_factory=list)

    @property
    def registry_mode(self) -> bool:
        return bool(self.registry_keys)

    def by_status(self, status: Status) -> List[ClaimVerdict]:
        return [v for v in self.verdicts if v.status is status]

    def summary(self) -> Dict[str, int]:
        out = {s.value: 0 for s in Status}
        for verdict in self.verdicts:
            out[verdict.status.value] += 1
        return out


def _index(records: Iterable[ChannelBRecord], run_id: str, agent_scoped: bool):
    """Kanal B nach Laufzugehoerigkeit indizieren."""
    by_key: Dict[str, Set[Optional[str]]] = {}
    evidence_keys: Dict[str, Set[Optional[str]]] = {}
    foreign_evidence: Set[str] = set()
    for rec in records:
        if rec.run_id != run_id:
            # Fremde Runs kommen in den Vergleich NICHT hinein. Ihre
            # Evidence-Keys werden nur gemerkt, um eine runfremde Referenz
            # unterscheidbar von einer schlicht unbekannten zu melden.
            if rec.evidence_key:
                foreign_evidence.add(rec.evidence_key)
            continue
        by_key.setdefault(rec.source_key, set()).add(rec.agent_id)
        if rec.evidence_key:
            evidence_keys.setdefault(rec.evidence_key, set()).add(rec.agent_id)
    return by_key, evidence_keys, foreign_evidence - set(evidence_keys)


def reconcile(result: AgentResult, channel_b: Sequence[ChannelBRecord],
              run_id: str = None, agent_scoped: bool = False,
              production: bool = False,
              repair_counts: Dict[str, int] = None) -> RunReconciliation:
    """Kanal A gegen Kanal B abgleichen.

    `agent_scoped=True` verlangt, dass der bestaetigende Zugriff vom
    selben Agenten stammt. Das ist die Variante fuer getrennte
    Evidenzraeume (§7); standardmaessig genuegt derselbe Run.
    """
    run_id = run_id or result.run_id
    repair_counts = repair_counts or {}
    by_key, evidence_keys, foreign_evidence = _index(
        channel_b, run_id, agent_scoped)

    verdicts = []
    for claim in result.claims:
        verdicts.append(_verdict(claim, result.agent_id, by_key, evidence_keys,
                                 foreign_evidence, agent_scoped, production,
                                 repair_counts.get(claim.claim_id, 0)))
    return RunReconciliation(run_id=run_id, verdicts=verdicts,
                             channel_b_keys=sorted(by_key),
                             agent_scoped=agent_scoped, production=production,
                             registry_keys=sorted(evidence_keys))


def _verdict(claim: Claim, agent_id: str, by_key, evidence_keys,
             foreign_evidence, agent_scoped: bool, production: bool,
             repair_count: int) -> ClaimVerdict:
    confirmed, missing, unregistered = [], [], []
    #: Sobald der Lauf ueberhaupt eine Registry hat, ist sie die Wahrheit:
    #: der source_ref-Uebergangspfad wird dann abgeschaltet. Andernfalls
    #: koennte ein Agent die Registrierung umgehen, indem er statt des
    #: `ev:`-Schluessels einfach den Dateinamen nennt.
    registry_mode = bool(evidence_keys)

    # (1) Referenzielle Validierung VOR dem Abgleich. Eine unbekannte oder
    #     runfremde Evidence-ID ist ein Hard Fail und keine fehlende Quelle
    #     (§7, §9.6, §12.11).
    for ref in claim.evidence:
        if not _is_registry_id(ref.evidence_id):
            continue
        if ref.evidence_id in evidence_keys:
            continue
        foreign = ref.evidence_id in foreign_evidence
        return ClaimVerdict(
            claim_id=claim.claim_id, claim_text=claim.text,
            status=Status.BLOCKED,
            reason=("Evidence-ID stammt aus einem fremden Run"
                    if foreign else
                    "Evidence-ID ist in diesem Run nicht registriert"),
            error_class=ErrorClass.UNKNOWN_EVIDENCE_ID,
            repair_count=repair_count, evidence_free=claim.evidence_free,
            missing_evidence=[ref.evidence_id])

    required = claim.required_evidence()

    # (2) Evidenzfreier Claim und Claim mit leerer Deklarationsliste.
    #     Beide sind NICHT verifiziert (§6, §12.16) — unterscheidbar bleiben
    #     sie ueber `evidence_free`.
    if not required:
        reason = ("evidenzfreie Aussage (deklariert): keine externe Quelle "
                  "beansprucht" if claim.evidence_free else
                  "keine erforderliche Evidenz deklariert — eine leere "
                  "Deklarationsliste ist kein Beleg")
        return ClaimVerdict(
            claim_id=claim.claim_id, claim_text=claim.text,
            status=Status.UNVERIFIED, reason=reason,
            error_class=ErrorClass.NO_REQUIRED_EVIDENCE,
            repair_count=repair_count, evidence_free=claim.evidence_free)

    # (3) Physischer Abgleich.
    for ref in required:
        if _is_registry_id(ref.evidence_id):
            # Registrierter Beleg — oben bereits gegen die Registry geprueft.
            agents = evidence_keys.get(ref.evidence_id, set())
            if agent_scoped and agent_id not in agents:
                missing.append(ref.evidence_id)
            else:
                confirmed.append(ref.evidence_id)
            continue

        # UEBERGANGSPFAD: Bestaetigung ueber die Quellenangabe statt ueber
        # die Registry. Zulaessig, solange der Lauf keine Registry hat —
        # aber nie ausreichend fuer VERIFIED, weil dabei offenbleibt,
        # WELCHER Ausschnitt welcher Fassung dem Agenten vorlag.
        if registry_mode:
            missing.append(ref.evidence_id)
            continue
        key = audit_db.source_key(ref.source_ref)
        agents = by_key.get(key)
        if agents is None:
            missing.append(ref.evidence_id)
            continue
        if agent_scoped and agent_id not in agents:
            missing.append(ref.evidence_id)
            continue
        confirmed.append(ref.evidence_id)
        unregistered.append(ref.evidence_id)

    if not missing and not unregistered:
        return ClaimVerdict(
            claim_id=claim.claim_id, claim_text=claim.text,
            status=Status.VERIFIED,
            reason="alle erforderlichen Belege sind in der Evidenzregistry "
                   "desselben Runs protokolliert",
            repair_count=repair_count, evidence_free=claim.evidence_free,
            confirmed_evidence=confirmed)

    if not missing:
        # Vollstaendig bestaetigt, aber mindestens einmal nur ueber den
        # Uebergangspfad. §7: der Fallback kann nie VERIFIED ergeben.
        status = Status.PARTIALLY_VERIFIED
        reason = ("Belege nur ueber die Quellenangabe bestaetigt, nicht ueber "
                  "die Evidenzregistry (" + ", ".join(sorted(unregistered))
                  + ") — als Uebergangspfad zulaessig, aber nicht ausreichend "
                  "fuer VERIFIED")
        if production:
            status = Status.UNVERIFIED
            reason += " — im Produktionsmodus unzulaessig, auf UNVERIFIED abgestuft"
        return ClaimVerdict(
            claim_id=claim.claim_id, claim_text=claim.text, status=status,
            reason=reason, error_class=ErrorClass.EVIDENCE_UNREGISTERED,
            repair_count=repair_count, evidence_free=claim.evidence_free,
            confirmed_evidence=confirmed)

    if confirmed:
        status = Status.PARTIALLY_VERIFIED
        reason = ("mindestens eine erforderliche Quelle belegt, mindestens "
                  "eine fehlt oder ist ungueltig")
        error_class = ErrorClass.EVIDENCE_INCOMPLETE
        if production:
            # §6: PARTIALLY_VERIFIED ist im Produktionsmodus nicht
            # zulaessig. Die minimal-invasive Loesung ist die Abstufung auf
            # UNVERIFIED — der Status verschwindet nicht stillschweigend,
            # sondern wird mit Begruendung herabgesetzt. Der Produktionsexport
            # schliesst beides ohnehin aus; entscheidend ist, dass keine
            # halbbelegte Aussage als produktionsfaehig gilt.
            status = Status.UNVERIFIED
            reason += " — im Produktionsmodus unzulaessig, auf UNVERIFIED abgestuft"
        return ClaimVerdict(
            claim_id=claim.claim_id, claim_text=claim.text, status=status,
            reason=reason, error_class=error_class, repair_count=repair_count,
            evidence_free=claim.evidence_free, confirmed_evidence=confirmed,
            missing_evidence=missing)

    return ClaimVerdict(
        claim_id=claim.claim_id, claim_text=claim.text,
        status=Status.UNVERIFIED,
        reason="keine erforderliche Evidenz konnte in Kanal B bestaetigt werden",
        error_class=ErrorClass.EVIDENCE_INCOMPLETE, repair_count=repair_count,
        evidence_free=claim.evidence_free, missing_evidence=missing)


def _is_registry_id(evidence_id: str) -> bool:
    """Ist die Evidence-ID ein Registryschluessel oder nur ein lokales Label?

    `identity.make_evidence_key` erzeugt `ev:<sha256>`. Nur solche IDs
    koennen gegen die Kanal-B-Registry geprueft werden. Lokale Labels wie
    `e1` sind Deklarationsnummern und werden ueber `source_ref` bestaetigt,
    nicht ueber die Registry. Wer eine `ev:`-ID nennt, behauptet dagegen
    einen konkreten registrierten Beleg — und muss ihn haben.
    """
    return isinstance(evidence_id, str) and evidence_id.startswith("ev:")


# ---------------------------------------------------------------------------
# Neuberechnung aus der Datenbank
# ---------------------------------------------------------------------------

def channel_b_from_db(con) -> List[ChannelBRecord]:
    """ALLE Kanal-B-Zeilen laden, nicht nur die des betrachteten Runs.

    Der Filter auf den Run sitzt in `_index()`. Wuerde hier schon gefiltert,
    waere eine runfremde Evidence-ID von einer schlicht unbekannten nicht
    mehr unterscheidbar — beide fuehren zu BLOCKED, aber die Fehlerursache
    ist eine andere, und der Auditbefund lautet anders.
    """
    rows = con.execute(
        "SELECT run_id, agent_id, source_key, evidence_key, phase "
        "FROM actions WHERE source_key IS NOT NULL").fetchall()
    return [ChannelBRecord(run_id=r["run_id"], agent_id=r["agent_id"],
                           source_key=r["source_key"],
                           evidence_key=r["evidence_key"], phase=r["phase"])
            for r in rows]


def channel_a_from_db(con, run_id: str) -> AgentResult:
    """Kanal A aus `assertions` rekonstruieren.

    Die Rekonstruktion ist verlustfrei fuer alles, was der Reconciler
    braucht: Claim-Text, Evidenzreferenz, `required`. Sie ist damit die
    Grundlage der Neuberechnung (§7).
    """
    from audit_models import Claim, EvidenceReference, Stance

    rows = con.execute(
        "SELECT agent_id, claim_id, claim, evidence_id, raw_source_ref, "
        " source_key, locator, quote, stance, required "
        "FROM assertions WHERE run_id = ? ORDER BY id", (run_id,)).fetchall()
    claims: Dict[str, Claim] = {}
    agent_id = None
    for row in rows:
        agent_id = agent_id or row["agent_id"] or "unknown"
        claim_id = row["claim_id"] or f"legacy:{row['claim'][:32]}"
        claim = claims.get(claim_id)
        if claim is None:
            claim = Claim(claim_id=claim_id, text=row["claim"],
                          stance=Stance(row["stance"])
                          if row["stance"] in {s.value for s in Stance}
                          else Stance.UNCLEAR,
                          evidence=[], evidence_free=False)
            claims[claim_id] = claim
        if row["raw_source_ref"]:
            claim.evidence.append(EvidenceReference(
                evidence_id=row["evidence_id"] or f"e{len(claim.evidence) + 1}",
                source_ref=row["raw_source_ref"], locator=row["locator"],
                quote=row["quote"], required=bool(row["required"])))
    return AgentResult(run_id=run_id, agent_id=agent_id or "unknown",
                       claims=list(claims.values()))


def repair_counts_from_db(con, run_id: str) -> Dict[str, int]:
    rows = con.execute(
        "SELECT target_id, MAX(attempt) AS n FROM repairs "
        "WHERE run_id = ? AND kind = 'format' GROUP BY target_id",
        (run_id,)).fetchall()
    return {r["target_id"]: r["n"] for r in rows}


def reconcile_run(con, run_id: str, agent_scoped: bool = False,
                  production: bool = False) -> RunReconciliation:
    """Reconciliation vollstaendig aus der Datenbank neu berechnen."""
    result = channel_a_from_db(con, run_id)
    records = channel_b_from_db(con)
    return reconcile(result, records, run_id=run_id, agent_scoped=agent_scoped,
                     production=production,
                     repair_counts=repair_counts_from_db(con, run_id))


def stored_verdicts(con, run_id: str) -> List[ClaimVerdict]:
    """Persistierte Statuswerte lesen (ohne Neuberechnung)."""
    rows = con.execute(
        "SELECT claim_id, claim_text, status, status_reason, error_class, "
        " repair_count, evidence_free, confirmed_evidence_json, "
        " missing_evidence_json FROM claims WHERE run_id = ? "
        "ORDER BY claim_id", (run_id,)).fetchall()
    out = []
    for row in rows:
        out.append(ClaimVerdict(
            claim_id=row["claim_id"], claim_text=row["claim_text"],
            status=Status(row["status"]), reason=row["status_reason"] or "",
            error_class=ErrorClass(row["error_class"])
            if row["error_class"] else None,
            repair_count=row["repair_count"],
            evidence_free=bool(row["evidence_free"]),
            confirmed_evidence=json.loads(row["confirmed_evidence_json"]),
            missing_evidence=json.loads(row["missing_evidence_json"])))
    return out
