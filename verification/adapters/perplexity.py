"""Perplexity adapter — the discovery step.

Perplexity is a general web-search aggregator, not an academic index. Its
job in this pipeline is narrow: turn a claim's search query into a short
list of candidate URLs worth resolving further. It is deliberately not
treated as a citation-grade source on its own — `validate_source` in the
graph still checks the result against the allowed-source policy, and
Crossref/Semantic Scholar are preferred for anything that needs a DOI.
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from verification.adapters.base import AdapterError, SourceAdapter
from verification.models import Claim, ProviderName, Source, SourceType

API_URL = "https://api.perplexity.ai/chat/completions"

SYSTEM_PROMPT = (
    "You verify physics claims against academic sources (papers, textbooks, "
    "lecture scripts). Given a claim, respond with a short factual answer "
    "and rely on your search citations; do not fabricate sources."
)


class PerplexityAdapter(SourceAdapter):
    provider = ProviderName.PERPLEXITY

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        model: str = "sonar",
        timeout: float = 15.0,
    ) -> None:
        if not api_key:
            raise ValueError("PerplexityAdapter requires an api_key")
        self._api_key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=timeout)

    def search(self, query: str, claim: Claim) -> list[Source]:
        try:
            response = self._client.post(
                API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": query},
                    ],
                },
            )
            response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise AdapterError(f"Perplexity timeout: {exc}") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 429 or status >= 500:
                raise AdapterError(f"Perplexity transient error {status}") from exc
            raise AdapterError(f"Perplexity error {status}: {exc.response.text[:200]}") from exc
        except httpx.HTTPError as exc:
            raise AdapterError(f"Perplexity request failed: {exc}") from exc

        payload = response.json()
        citations: list[str] = payload.get("citations", []) or []
        return [self._citation_to_source(url) for url in citations]

    @staticmethod
    def _citation_to_source(url: str) -> Source:
        domain = urlparse(url).netloc or url
        return Source(
            provider=ProviderName.PERPLEXITY,
            source_type=SourceType.OTHER,
            title=domain,
            url=url,
        )
