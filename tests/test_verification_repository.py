from datetime import timedelta

import pytest

from verification.db.repository import SQLiteRepository
from verification.models import (
    Claim,
    ClaimType,
    ProviderName,
    ReviewDecision,
    ReviewRecord,
    RiskAssessment,
    RiskLevel,
    SearchAttempt,
    Source,
    SourceType,
    ValidationResult,
    VerificationState,
    VerificationStatus,
)


@pytest.fixture
def repo():
    r = SQLiteRepository(":memory:")
    yield r
    r.close()


def _verified_state(location="slide-3"):
    claim = Claim(
        document_id="doc1",
        location=location,
        text="Die Winkelgeschwindigkeit der Erdrotation betraegt 7.29e-5 rad/s",
        claim_type=ClaimType.QUANTITATIVE,
        search_query="Winkelgeschwindigkeit Erdrotation",
        extraction_confidence=0.92,
    )
    source = Source(
        provider=ProviderName.CROSSREF,
        source_type=SourceType.BOOK,
        title="Gerthsen Physik",
        authors=["Dieter Meschede"],
        year=2015,
        doi="10.1007/978-3-662-45977-5",
    )
    attempt = SearchAttempt(
        provider=ProviderName.PERPLEXITY, query=claim.search_query, iteration=0, sources_found=[source]
    )
    validation = ValidationResult(
        source=source,
        is_allowed_source=True,
        supports_claim=True,
        validation_confidence=0.88,
        reasoning="Formel exakt uebereinstimmend",
    )
    return VerificationState(
        claim=claim,
        iteration=1,
        attempts=[attempt],
        validations=[validation],
        validated_sources=[source],
        status=VerificationStatus.VERIFIED,
    )


def test_save_and_get_run_round_trips(repo):
    state = _verified_state()
    run = repo.save_run(state)

    fetched = repo.get_run(run.id)

    assert fetched is not None
    assert fetched.status == VerificationStatus.VERIFIED
    assert [s.title for s in fetched.validated_sources] == ["Gerthsen Physik"]
    assert fetched.claim.text == state.claim.text


def test_cache_lookup_finds_run_by_claim_cache_key(repo):
    state = _verified_state()
    run = repo.save_run(state)

    cached = repo.get_cached_run(state.claim.cache_key())

    assert cached is not None
    assert cached.id == run.id


def test_cache_lookup_respects_ttl(repo):
    state = _verified_state()
    repo.save_run(state)

    expired = repo.get_cached_run(state.claim.cache_key(), ttl=timedelta(seconds=0))

    assert expired is None


def test_source_dedup_by_locator_across_runs(repo):
    state_a = _verified_state(location="slide-3")
    state_b = _verified_state(location="slide-7")  # same source (same DOI), different claim

    repo.save_run(state_a)
    repo.save_run(state_b)

    row_count = repo._conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
    assert row_count == 1


def test_review_queue_lifecycle(repo):
    state = _verified_state()
    run = repo.save_run(state)
    repo.save_risk_assessment(
        run.id, RiskAssessment(risk_level=RiskLevel.HIGH, reasons=["keine Evidenz"], requires_review=True)
    )

    assert [r.id for r in repo.list_runs_requiring_review()] == [run.id]

    repo.save_review(
        ReviewRecord(
            run_id=run.id,
            decision=ReviewDecision.APPROVED,
            risk_level=RiskLevel.HIGH,
            reasons=["manuell geprueft"],
            reviewer="tester",
        )
    )

    assert repo.list_runs_requiring_review() == []


def test_migrations_are_idempotent_on_reopen(tmp_path):
    db_path = tmp_path / "audit.db"
    repo1 = SQLiteRepository(db_path)
    repo1.save_run(_verified_state())
    repo1.close()

    repo2 = SQLiteRepository(db_path)  # re-applying migrations must not error
    assert len(repo2._conn.execute("SELECT * FROM claims").fetchall()) == 1
    repo2.close()
