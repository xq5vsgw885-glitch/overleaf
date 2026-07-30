"""Semantic Scholar adapter — citation and relationship graph.

Beyond plain keyword search (`search`), this adapter exposes the citation
graph via `get_citing_papers`/`get_references`, which the validation step
can use to check whether a Crossref/Perplexity candidate is actually
connected to sources already accepted for a claim, rather than validating
title-similarity alone.
"""

from __future__ import annotations

import httpx

from verification.adapters.base import AdapterError, SourceAdapter
from verification.models import Claim, ProviderName, Source, SourceType

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
FIELDS = "title,authors,year,externalIds,venue,publicationTypes"


class SemanticScholarAdapter(SourceAdapter):
    provider = ProviderName.SEMANTIC_SCHOLAR

    def __init__(
        self,
        api_key: str | None = None,
        client: httpx.Client | None = None,
        limit: int = 5,
        timeout: float = 10.0,
    ) -> None:
        self._limit = limit
        headers = {"x-api-key": api_key} if api_key else {}
        self._client = client or httpx.Client(timeout=timeout, headers=headers)

    def search(self, query: str, claim: Claim) -> list[Source]:
        data = self._get(SEARCH_URL, params={"query": query, "limit": self._limit, "fields": FIELDS})
        return [self._paper_to_source(paper) for paper in data.get("data", []) if paper.get("title")]

    def get_references(self, paper_id: str) -> list[Source]:
        """Papers this paper cites — useful to confirm a claim's lineage."""
        data = self._get(
            PAPER_URL.format(paper_id=paper_id) + "/references", params={"fields": FIELDS}
        )
        return [
            self._paper_to_source(item["citedPaper"])
            for item in data.get("data", [])
            if item.get("citedPaper", {}).get("title")
        ]

    def get_citing_papers(self, paper_id: str) -> list[Source]:
        """Papers that cite this paper — useful to check ongoing acceptance."""
        data = self._get(
            PAPER_URL.format(paper_id=paper_id) + "/citations", params={"fields": FIELDS}
        )
        return [
            self._paper_to_source(item["citingPaper"])
            for item in data.get("data", [])
            if item.get("citingPaper", {}).get("title")
        ]

    def _get(self, url: str, params: dict) -> dict:
        try:
            response = self._client.get(url, params=params)
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AdapterError(f"Semantic Scholar timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or status >= 500:
                raise AdapterError(f"Semantic Scholar transient error {status}") from exc
            raise AdapterError(f"Semantic Scholar error {status}: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"Semantic Scholar request failed: {exc}") from exc
        return response.json()

    @staticmethod
    def _paper_to_source(paper: dict) -> Source:
        external_ids = paper.get("externalIds") or {}
        publication_types = paper.get("publicationTypes") or []
        source_type = SourceType.PREPRINT if "ArXiv" in external_ids else SourceType.PAPER
        if "Book" in publication_types:
            source_type = SourceType.BOOK
        return Source(
            provider=ProviderName.SEMANTIC_SCHOLAR,
            source_type=source_type,
            title=paper.get("title", ""),
            authors=[a.get("name", "") for a in paper.get("authors", []) if a.get("name")],
            year=paper.get("year"),
            doi=external_ids.get("DOI"),
            venue=paper.get("venue") or None,
        )
