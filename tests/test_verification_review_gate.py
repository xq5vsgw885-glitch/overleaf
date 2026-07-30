import pytest

from verification.db.repository import SQLiteRepository
from verification.models import (
    Claim,
    ClaimType,
    ProviderName,
    ReviewDecision,
    RiskLevel,
    Source,
    SourceType,
    ValidationResult,
    VerificationState,
    VerificationStatus,
)
from verification.review_gate import apply_review_gate, assess_risk


@pytest.fixture
def repo():
    r = SQLiteRepository(":memory:")
    yield r
    r.close()


def _claim(location="s1"):
    return Claim(
        document_id="d",
        location=location,
        text="c",
        claim_type=ClaimType.FACT,
        search_query="q",
        extraction_confidence=0.9,
    )


def test_clean_verified_run_is_auto_approved(repo):
    claim = _claim()
    source = Source(provider=ProviderName.CROSSREF, source_type=SourceType.BOOK, title="Buch", doi="10.1/a")
    validation = ValidationResult(source=source, is_allowed_source=True, supports_claim=True, validation_confidence=0.9)
    state = VerificationState(
        claim=claim, status=VerificationStatus.VERIFIED, validated_sources=[source], validations=[validation]
    )
    run = repo.save_run(state)

    review = apply_review_gate(run.id, state, repo)

    assert review.decision == ReviewDecision.AUTO_APPROVED
    assert review.risk_level == RiskLevel.LOW
    assert repo.list_runs_requiring_review() == []


def test_source_without_doi_or_url_triggers_review(repo):
    claim = _claim()
    source = Source(provider=ProviderName.PERPLEXITY, source_type=SourceType.SCRIPT, title="Skript ohne DOI")
    validation = ValidationResult(source=source, is_allowed_source=True, supports_claim=True, validation_confidence=0.9)
    state = VerificationState(
        claim=claim, status=VerificationStatus.VERIFIED, validated_sources=[source], validations=[validation]
    )
    run = repo.save_run(state)

    review = apply_review_gate(run.id, state, repo)

    assert review.decision == ReviewDecision.PENDING
    assert review.risk_level == RiskLevel.MEDIUM
    assert "reproduzierbar" in review.reasons[0]


def test_conflicting_valid_sources_trigger_review(repo):
    claim = _claim()
    s1 = Source(provider=ProviderName.CROSSREF, source_type=SourceType.BOOK, title="Buch1", doi="10.1/c1")
    s2 = Source(provider=ProviderName.SEMANTIC_SCHOLAR, source_type=SourceType.PAPER, title="Paper2", doi="10.1/c2")
    validations = [
        ValidationResult(source=s1, is_allowed_source=True, supports_claim=True, validation_confidence=0.9),
        ValidationResult(source=s2, is_allowed_source=True, supports_claim=True, validation_confidence=0.9),
    ]
    state = VerificationState(
        claim=claim, status=VerificationStatus.VERIFIED, validated_sources=[s1, s2], validations=validations
    )
    run = repo.save_run(state)

    review = apply_review_gate(run.id, state, repo)

    assert review.decision == ReviewDecision.PENDING
    assert any("Quellenkonflikt" in r for r in review.reasons)


def test_weak_validation_confidence_flags_uncovered_synthesis(repo):
    claim = _claim()
    source = Source(provider=ProviderName.CROSSREF, source_type=SourceType.PAPER, title="Paper", doi="10.1/w")
    validation = ValidationResult(
        source=source, is_allowed_source=True, supports_claim=True, validation_confidence=0.3
    )
    state = VerificationState(
        claim=claim, status=VerificationStatus.VERIFIED, validated_sources=[source], validations=[validation]
    )
    run = repo.save_run(state)

    review = apply_review_gate(run.id, state, repo, min_validation_confidence=0.5)

    assert review.decision == ReviewDecision.PENDING
    assert any("Synthese" in r for r in review.reasons)


def test_unverified_status_is_high_risk_missing_evidence(repo):
    claim = _claim()
    state = VerificationState(claim=claim, status=VerificationStatus.UNVERIFIED, failure_reason="Limit erreicht")
    run = repo.save_run(state)

    review = apply_review_gate(run.id, state, repo)

    assert review.decision == ReviewDecision.PENDING
    assert review.risk_level == RiskLevel.HIGH
    assert "fehlende Evidenz" in review.reasons[0]


def test_review_queue_reflects_all_pending_runs(repo):
    for i in range(3):
        claim = _claim(location=f"s{i}")
        state = VerificationState(claim=claim, status=VerificationStatus.UNVERIFIED, failure_reason="x")
        run = repo.save_run(state)
        apply_review_gate(run.id, state, repo)

    assert len(repo.list_runs_requiring_review()) == 3


def test_assess_risk_is_pure_and_side_effect_free():
    claim = _claim()
    state = VerificationState(claim=claim, status=VerificationStatus.VERIFIED)
    risk = assess_risk(state)
    assert risk.risk_level == RiskLevel.LOW
    assert risk.requires_review is False
