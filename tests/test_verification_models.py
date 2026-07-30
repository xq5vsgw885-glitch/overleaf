import pytest
from pydantic import ValidationError

from verification.models import Claim, ClaimType, ProviderName, Source, SourceType


def _claim(**overrides):
    defaults = dict(
        document_id="doc1",
        location="slide-3",
        text="Die Winkelgeschwindigkeit der Erdrotation betraegt 7.29e-5 rad/s",
        claim_type=ClaimType.QUANTITATIVE,
        search_query="Winkelgeschwindigkeit Erdrotation",
        extraction_confidence=0.9,
    )
    defaults.update(overrides)
    return Claim(**defaults)


def test_claim_cache_key_stable_for_same_text():
    a = _claim()
    b = _claim()
    assert a.id != b.id
    assert a.cache_key() == b.cache_key()


def test_claim_cache_key_differs_by_claim_type():
    a = _claim(claim_type=ClaimType.QUANTITATIVE)
    b = _claim(claim_type=ClaimType.FACT)
    assert a.cache_key() != b.cache_key()


def test_claim_rejects_blank_text():
    with pytest.raises(ValidationError):
        _claim(text="   ")


def test_claim_confidence_out_of_range_rejected():
    with pytest.raises(ValidationError):
        _claim(extraction_confidence=1.5)


def test_source_locator_prefers_doi_then_url_then_title():
    doi_source = Source(
        provider=ProviderName.CROSSREF, source_type=SourceType.BOOK, title="X", doi="10.1/ABC"
    )
    assert doi_source.locator() == "doi:10.1/abc"

    url_source = Source(
        provider=ProviderName.PERPLEXITY, source_type=SourceType.OTHER, title="X", url="https://a.b/c"
    )
    assert url_source.locator() == "url:https://a.b/c"

    title_source = Source(provider=ProviderName.CROSSREF, source_type=SourceType.BOOK, title="  My   Title ")
    assert title_source.locator() == "title:my title"
