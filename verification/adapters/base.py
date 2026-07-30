"""Shared adapter contract.

Every provider adapter implements `search()` and raises `AdapterError` for
technical failures (timeout, rate limit, 5xx) so the LangGraph loop can
route those to retry-with-backoff instead of treating them as "no source
found" (which would consume the content-refinement iteration budget).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from verification.models import Claim, ProviderName, Source


class AdapterError(Exception):
    """Technical failure talking to a provider (timeout, rate limit, 5xx).

    Distinct from a legitimate empty result, which is just `search()`
    returning `[]`.
    """


class SourceAdapter(ABC):
    provider: ProviderName

    @abstractmethod
    def search(self, query: str, claim: Claim) -> list[Source]:
        """Return candidate sources for `query`.

        Must raise `AdapterError` on technical failure rather than
        returning an empty list, so callers can distinguish "provider is
        down" from "provider found nothing".
        """
        raise NotImplementedError
