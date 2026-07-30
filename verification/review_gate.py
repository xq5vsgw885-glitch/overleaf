"""Risk-adaptive review gate.

Unrisky runs are auto-approved; anything matching one of the four trigger
conditions agreed with the user gets queued for manual review instead:
missing evidence, a non-reproducible locator, conflicting valid sources,
or an uncovered synthesis (a valid match with weak validation confidence,
i.e. the source plausibly relates to the claim but does not clearly state
it).
"""

from __future__ import annotations

from verification.db.repository import VerificationRepository
from verification.models import (
    ReviewDecision,
    ReviewRecord,
    RiskAssessment,
    RiskLevel,
    VerificationState,
    VerificationStatus,
)

_RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}


def _escalate(current: RiskLevel, candidate: RiskLevel) -> RiskLevel:
    return candidate if _RISK_ORDER[candidate] > _RISK_ORDER[current] else current


def assess_risk(state: VerificationState, min_validation_confidence: float = 0.5) -> RiskAssessment:
    risk = RiskLevel.LOW
    reasons: list[str] = []

    if state.status in (VerificationStatus.UNVERIFIED, VerificationStatus.ERROR):
        reasons.append(f"fehlende Evidenz (Status={state.status.value})")
        risk = _escalate(risk, RiskLevel.HIGH)

    if state.status == VerificationStatus.VERIFIED:
        non_reproducible = [s for s in state.validated_sources if not s.doi and not s.url]
        if non_reproducible:
            reasons.append(
                f"{len(non_reproducible)} valide Quelle(n) ohne DOI/URL - Locator nicht reproduzierbar"
            )
            risk = _escalate(risk, RiskLevel.MEDIUM)

        if state.has_conflicting_sources:
            reasons.append(
                f"{len(state.validated_sources)} valide Quellen fuer denselben Claim - moeglicher Quellenkonflikt"
            )
            risk = _escalate(risk, RiskLevel.MEDIUM)

        weak_validations = [
            v
            for v in state.validations
            if v.is_valid and v.validation_confidence < min_validation_confidence
        ]
        if weak_validations:
            reasons.append(
                f"{len(weak_validations)} valide Quelle(n) mit Validierungs-Konfidenz "
                f"< {min_validation_confidence} - moeglicherweise ungedeckte Synthese statt direkter Beleg"
            )
            risk = _escalate(risk, RiskLevel.MEDIUM)

    return RiskAssessment(risk_level=risk, reasons=reasons, requires_review=risk != RiskLevel.LOW)


def apply_review_gate(
    run_id: str,
    state: VerificationState,
    repository: VerificationRepository,
    min_validation_confidence: float = 0.5,
) -> ReviewRecord:
    """Persist the risk assessment and resulting decision for `run_id`.

    Low-risk runs are auto-approved immediately. Everything else gets a
    PENDING record and shows up via `repository.list_runs_requiring_review()`
    until a human calls `repository.save_review(...)` with an
    APPROVED/REJECTED decision.
    """
    risk = assess_risk(state, min_validation_confidence)
    repository.save_risk_assessment(run_id, risk)

    decision = ReviewDecision.AUTO_APPROVED if not risk.requires_review else ReviewDecision.PENDING
    review = ReviewRecord(
        run_id=run_id,
        decision=decision,
        risk_level=risk.risk_level,
        reasons=risk.reasons,
    )
    repository.save_review(review)
    return review
