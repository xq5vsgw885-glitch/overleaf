"""Fact-checking / citation-verification pipeline for physics protocol claims.

Scope of this package (v1):
  - Pydantic data contracts shared across all stages (`models.py`).
  - Search/resolver adapters: Perplexity (discovery), Crossref (bibliographic
    resolver), Semantic Scholar (citation graph). arXiv is defined as an
    interface only and stays inactive until v2 (`adapters/`).
  - A LangGraph state machine with explicit transitions for the
    search -> validate -> refine/retry -> verified/unverified loop (`graph.py`).
  - A risk-adaptive review gate deciding auto-approval vs. manual review
    (`review_gate.py`).
  - A normalized SQLite audit schema behind a swappable repository
    interface (`db/`).
"""
