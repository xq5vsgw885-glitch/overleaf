"""Search/resolver adapters, one per external provider.

v1 scope: Perplexity (discovery), Crossref (bibliographic resolver),
Semantic Scholar (citation/relationship adapter). arXiv is defined as an
interface only (`arxiv.py`) and stays inactive until v2.
"""

from verification.adapters.base import AdapterError, SourceAdapter

__all__ = ["AdapterError", "SourceAdapter"]
