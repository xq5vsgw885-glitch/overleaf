import pytest

from verification.adapters.base import AdapterError, SourceAdapter
from verification.graph import verify_claim
from verification.models import Claim, ClaimType, ProviderName, Source, SourceType, VerificationStatus


@pytest.fixture
def claim():
    return Claim(
        document_id="d1",
        location="s3",
        text="Die Praezessionsperiode des Foucaultschen Pendels am Pol betraegt 24 Stunden",
        claim_type=ClaimType.FACT,
        search_query="Foucault Pendel Praezession",
        extraction_confidence=0.85,
    )


class _FixedResultAdapter(SourceAdapter):
    provider = ProviderName.CROSSREF

    def __init__(self, sources):
        self._sources = sources

    def search(self, query, claim):
        return self._sources


class _AlwaysErrors(SourceAdapter):
    provider = ProviderName.PERPLEXITY

    def search(self, query, claim):
        raise AdapterError("simulated timeout")


class _ErrorsThenSucceeds(SourceAdapter):
    provider = ProviderName.PERPLEXITY

    def __init__(self, sources):
        self._sources = sources
        self.calls = 0

    def search(self, query, claim):
        self.calls += 1
        if self.calls == 1:
            raise AdapterError("simulated 503")
        return self._sources


def _relevant_source(**overrides):
    defaults = dict(
        provider=ProviderName.CROSSREF,
        source_type=SourceType.BOOK,
        title="Gerthsen Physik betraegt 24 stunden pendel praezession pol foucaultschen die",
        doi="10.1/x",
    )
    defaults.update(overrides)
    return Source(**defaults)


def _irrelevant_source():
    return Source(
        provider=ProviderName.PERPLEXITY, source_type=SourceType.OTHER, title="irrelevant blog post", url="https://x.example"
    )


def test_verified_immediately_when_valid_source_found(claim):
    adapter = _FixedResultAdapter([_relevant_source()])

    state = verify_claim(claim, [adapter], max_iterations=3)

    assert state.status == VerificationStatus.VERIFIED
    assert state.iteration == 0
    assert len(state.validated_sources) == 1


def test_unverified_after_exhausting_iterations_without_valid_source(claim):
    adapter = _FixedResultAdapter([_irrelevant_source()])

    state = verify_claim(claim, [adapter], max_iterations=2)

    assert state.status == VerificationStatus.UNVERIFIED
    assert state.failure_reason is not None
    assert state.iteration == 1  # 0-indexed, 2 iterations consumed


def test_error_status_after_exhausting_technical_retries(claim):
    adapter = _AlwaysErrors()

    state = verify_claim(claim, [adapter], max_iterations=3, max_technical_retries=2)

    assert state.status == VerificationStatus.ERROR
    assert state.technical_retries == 2
    assert "Technischer Fehler" in state.failure_reason


def test_technical_retry_does_not_consume_content_iteration_budget(claim):
    adapter = _ErrorsThenSucceeds([_relevant_source()])

    state = verify_claim(claim, [adapter], max_iterations=3, max_technical_retries=2)

    assert state.status == VerificationStatus.VERIFIED
    assert state.technical_retries == 1
    assert state.iteration == 0  # content iteration budget untouched


def test_one_provider_error_does_not_block_another_providers_result(claim):
    ok_adapter = _FixedResultAdapter([_relevant_source()])
    broken_adapter = _AlwaysErrors()

    state = verify_claim(claim, [broken_adapter, ok_adapter], max_iterations=3)

    assert state.status == VerificationStatus.VERIFIED
    errored_attempts = [a for a in state.attempts if a.error is not None]
    assert len(errored_attempts) == 1
