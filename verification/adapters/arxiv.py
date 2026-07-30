"""arXiv adapter — interface defined for v1, activated in v2.

Kept as a real `SourceAdapter` subclass (not a stray comment) so the graph
and provider-registry code can already reference `ProviderName.ARXIV` and
`ArxivAdapter` without a later interface break. `is_active()` is the single
flag callers must check before including it in a provider list; the graph
wiring in v1 does not add it to the default provider chain.
"""

from __future__ import annotations

from verification.adapters.base import SourceAdapter
from verification.models import Claim, ProviderName, Source


class ArxivAdapter(SourceAdapter):
    provider = ProviderName.ARXIV

    @staticmethod
    def is_active() -> bool:
        """v1 keeps arXiv defined but disabled; flip in v2 once wired up."""
        return False

    def search(self, query: str, claim: Claim) -> list[Source]:
        raise NotImplementedError(
            "ArxivAdapter is a v2 feature — interface only in v1. "
            "See verification/adapters/arxiv.py."
        )
