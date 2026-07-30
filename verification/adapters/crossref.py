"""Crossref adapter — bibliographic resolver.

Crossref indexes DOIs with structured metadata (title, authors, year,
venue). Given a claim's query it returns citation-grade candidates
directly, without needing a further resolution step the way a Perplexity
URL citation does. No API key is required; Crossref asks polite users to
send a contact mailto in the User-Agent, which this adapter does.
"""

from __future__ import annotations

import httpx

from verification.adapters.base import AdapterError, SourceAdapter
from verification.models import Claim, ProviderName, Source, SourceType

API_URL = "https://api.crossref.org/works"

_BOOK_TYPES = {"book", "monograph", "book-chapter", "reference-book", "edited-book"}
_PAPER_TYPES = {"journal-article", "proceedings-article", "posted-content"}


def _map_type(crossref_type: str | None) -> SourceType:
    if crossref_type in _BOOK_TYPES:
        return SourceType.BOOK
    if crossref_type in _PAPER_TYPES:
        return SourceType.PAPER
    return SourceType.OTHER


class CrossrefAdapter(SourceAdapter):
    provider = ProviderName.CROSSREF

    def __init__(
        self,
        contact_email: str,
        client: httpx.Client | None = None,
        rows: int = 5,
        timeout: float = 10.0,
    ) -> None:
        if not contact_email:
            raise ValueError("CrossrefAdapter requires a contact_email for the polite pool")
        self._rows = rows
        self._client = client or httpx.Client(
            timeout=timeout,
            headers={"User-Agent": f"protocol-verification-pipeline (mailto:{contact_email})"},
        )

    def search(self, query: str, claim: Claim) -> list[Source]:
        try:
            response = self._client.get(
                API_URL, params={"query.bibliographic": query, "rows": self._rows}
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AdapterError(f"Crossref timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or status >= 500:
                raise AdapterError(f"Crossref transient error {status}") from exc
            raise AdapterError(f"Crossref error {status}: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"Crossref request failed: {exc}") from exc

        items = response.json().get("message", {}).get("items", [])
        return [self._item_to_source(item) for item in items if item.get("title")]

    @staticmethod
    def _item_to_source(item: dict) -> Source:
        title = " ".join(item.get("title", [""]))
        authors = [
            " ".join(part for part in (a.get("given"), a.get("family")) if part)
            for a in item.get("author", [])
        ]
        year = None
        date_parts = (
            item.get("published-print", {}).get("date-parts")
            or item.get("published", {}).get("date-parts")
            or item.get("published-online", {}).get("date-parts")
        )
        if date_parts and date_parts[0]:
            year = date_parts[0][0]
        venue_list = item.get("container-title") or []
        return Source(
            provider=ProviderName.CROSSREF,
            source_type=_map_type(item.get("type")),
            title=title,
            authors=[a for a in authors if a],
            year=year,
            doi=item.get("DOI"),
            url=item.get("URL"),
            venue=venue_list[0] if venue_list else None,
        )
