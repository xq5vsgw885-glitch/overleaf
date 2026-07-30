import httpx
import pytest

from verification.adapters.arxiv import ArxivAdapter
from verification.adapters.base import AdapterError
from verification.adapters.crossref import CrossrefAdapter
from verification.adapters.perplexity import PerplexityAdapter
from verification.adapters.semantic_scholar import SemanticScholarAdapter
from verification.models import Claim, ClaimType, SourceType


@pytest.fixture
def claim():
    return Claim(
        document_id="d",
        location="s1",
        text="omega=7.29e-5",
        claim_type=ClaimType.QUANTITATIVE,
        search_query="q",
        extraction_confidence=0.8,
    )


def _client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_crossref_maps_book_metadata(claim):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "message": {
                    "items": [
                        {
                            "title": ["Gerthsen Physik"],
                            "author": [{"given": "Dieter", "family": "Meschede"}],
                            "published-print": {"date-parts": [[2015]]},
                            "DOI": "10.1007/x",
                            "type": "book",
                            "container-title": [],
                            "URL": "https://doi.org/10.1007/x",
                        }
                    ]
                }
            },
        )

    adapter = CrossrefAdapter(contact_email="test@example.com", client=_client(handler))
    sources = adapter.search("Gerthsen Physik", claim)

    assert len(sources) == 1
    assert sources[0].title == "Gerthsen Physik"
    assert sources[0].doi == "10.1007/x"
    assert sources[0].source_type == SourceType.BOOK
    assert sources[0].authors == ["Dieter Meschede"]


def test_crossref_raises_adapter_error_on_5xx(claim):
    def handler(request):
        return httpx.Response(503, text="service unavailable")

    adapter = CrossrefAdapter(contact_email="test@example.com", client=_client(handler))

    with pytest.raises(AdapterError):
        adapter.search("x", claim)


def test_crossref_requires_contact_email():
    with pytest.raises(ValueError):
        CrossrefAdapter(contact_email="")


def test_perplexity_converts_citations_to_sources(claim):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "citations": ["https://en.wikipedia.org/wiki/Earth%27s_rotation"],
                "choices": [{"message": {"content": "..."}}],
            },
        )

    adapter = PerplexityAdapter(api_key="dummy", client=_client(handler))
    sources = adapter.search("Erdrotation", claim)

    assert len(sources) == 1
    assert sources[0].url == "https://en.wikipedia.org/wiki/Earth%27s_rotation"
    assert sources[0].source_type == SourceType.OTHER


def test_perplexity_requires_api_key():
    with pytest.raises(ValueError):
        PerplexityAdapter(api_key="")


def test_semantic_scholar_maps_paper_with_doi(claim):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "title": "Foucault pendulum dynamics",
                        "authors": [{"name": "J. Foucault"}],
                        "year": 1851,
                        "externalIds": {"DOI": "10.1000/y"},
                        "venue": "CRAS",
                        "publicationTypes": ["JournalArticle"],
                    }
                ]
            },
        )

    adapter = SemanticScholarAdapter(client=_client(handler))
    sources = adapter.search("Foucault pendulum", claim)

    assert len(sources) == 1
    assert sources[0].doi == "10.1000/y"
    assert sources[0].source_type == SourceType.PAPER


def test_semantic_scholar_marks_arxiv_only_papers_as_preprint(claim):
    def handler(request):
        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "title": "A preprint",
                        "authors": [],
                        "year": 2024,
                        "externalIds": {"ArXiv": "2401.00001"},
                        "venue": "",
                        "publicationTypes": [],
                    }
                ]
            },
        )

    adapter = SemanticScholarAdapter(client=_client(handler))
    sources = adapter.search("q", claim)

    assert sources[0].source_type == SourceType.PREPRINT


def test_arxiv_adapter_is_inactive_in_v1(claim):
    adapter = ArxivAdapter()
    assert adapter.is_active() is False
    with pytest.raises(NotImplementedError):
        adapter.search("q", claim)
