"""LangGraph verification loop with explicit state transitions.

Nodes: prepare -> search -> validate -> {finalize_verified | refine_query |
handle_technical_error | finalize_unverified}. `refine_query` loops back to
`search` with `iteration` incremented (content-refinement budget, default
3). `handle_technical_error` loops back to `search` too, but on its own
`technical_retries` counter — a provider timeout or 5xx must never consume
the same budget as "no valid source found", or an API outage gets
misrecorded as an unverifiable claim.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langgraph.graph import END, StateGraph

from verification.adapters.base import AdapterError, SourceAdapter
from verification.models import (
    Claim,
    SearchAttempt,
    Source,
    ValidationResult,
    VerificationState,
    VerificationStatus,
)

ClaimSupportChecker = Callable[[Claim, Source], tuple[bool, float, str]]
AllowedSourcePolicy = Callable[[Source], bool]
QueryRefiner = Callable[[Claim, str, list[SearchAttempt]], str]
BackoffFn = Callable[[int], float]


def default_allowed_source_policy(source: Source) -> bool:
    """Paper/book/script/preprint are allowed; a bare web citation is not,
    unless it has been resolved to one of those types by an adapter."""
    from verification.models import SourceType

    return source.source_type in {
        SourceType.PAPER,
        SourceType.BOOK,
        SourceType.SCRIPT,
        SourceType.PREPRINT,
    }


def default_claim_support_checker(claim: Claim, source: Source) -> tuple[bool, float, str]:
    """Lexical-overlap placeholder. Replace with an LLM-judge call in
    production; the graph only depends on this callable's signature."""
    claim_terms = set(claim.text.lower().split())
    haystack = f"{source.title} {source.raw_snippet}".lower()
    source_terms = set(haystack.split())
    if not claim_terms:
        return False, 0.0, "leerer Claim-Text"
    overlap = len(claim_terms & source_terms) / len(claim_terms)
    supports = overlap >= 0.2
    reasoning = f"Wortueberlappung {overlap:.2f}"
    return supports, min(overlap, 1.0), reasoning


def default_query_refiner(claim: Claim, current_query: str, failed_attempts: list[SearchAttempt]) -> str:
    """Deterministic placeholder refinement: narrow towards academic
    sources. Replace with an LLM-driven refiner without touching the graph."""
    suffix = "textbook OR lecture notes OR peer-reviewed"
    if suffix in current_query:
        return f"{claim.text} {claim.claim_type.value}"
    return f"{current_query} {suffix}"


def default_backoff(retry_number: int) -> float:
    return 0.0


def build_verification_graph(
    adapters: list[SourceAdapter],
    is_allowed_source: AllowedSourcePolicy = default_allowed_source_policy,
    claim_support_checker: ClaimSupportChecker = default_claim_support_checker,
    query_refiner: QueryRefiner = default_query_refiner,
    backoff: BackoffFn = default_backoff,
):
    """Compile the verification StateGraph. `adapters` are queried in the
    given order every search iteration (Perplexity first as the primary
    discovery channel, then Crossref/Semantic Scholar as resolvers, per
    the agreed v1 scope) — a technical failure on one does not skip the
    rest."""

    def prepare(state: VerificationState) -> dict:
        if not state.current_query:
            return {"current_query": state.claim.search_query}
        return {}

    def search(state: VerificationState) -> dict:
        new_attempts = list(state.attempts)
        for adapter in adapters:
            try:
                sources = adapter.search(state.current_query, state.claim)
                new_attempts.append(
                    SearchAttempt(
                        provider=adapter.provider,
                        query=state.current_query,
                        iteration=state.iteration,
                        sources_found=sources,
                    )
                )
            except AdapterError as exc:
                new_attempts.append(
                    SearchAttempt(
                        provider=adapter.provider,
                        query=state.current_query,
                        iteration=state.iteration,
                        error=str(exc),
                    )
                )
        return {"attempts": new_attempts}

    def validate(state: VerificationState) -> dict:
        this_iteration = [a for a in state.attempts if a.iteration == state.iteration]
        already_seen = {s.locator() for s in state.validated_sources}
        candidates: dict[str, Source] = {}
        for attempt in this_iteration:
            for source in attempt.sources_found:
                locator = source.locator()
                if locator not in already_seen:
                    candidates.setdefault(locator, source)

        new_validations = list(state.validations)
        new_validated = list(state.validated_sources)
        for source in candidates.values():
            allowed = is_allowed_source(source)
            supports, confidence, reasoning = (
                claim_support_checker(state.claim, source) if allowed else (False, 0.0, "Quelle nicht zugelassen")
            )
            result = ValidationResult(
                source=source,
                is_allowed_source=allowed,
                supports_claim=supports,
                validation_confidence=confidence,
                reasoning=reasoning,
            )
            new_validations.append(result)
            if result.is_valid:
                new_validated.append(source)

        return {"validations": new_validations, "validated_sources": new_validated}

    def route_after_validate(state: VerificationState) -> Literal["verified", "technical_error", "refine", "unverified"]:
        this_iteration = [a for a in state.attempts if a.iteration == state.iteration]
        this_iteration_locators = {
            s.locator() for a in this_iteration for s in a.sources_found
        }
        found_valid_this_round = any(
            v.is_valid and v.source.locator() in this_iteration_locators for v in state.validations
        )
        if found_valid_this_round:
            return "verified"

        all_errored = bool(this_iteration) and all(a.error is not None for a in this_iteration)
        if all_errored:
            return "technical_error"

        if state.iteration + 1 < state.max_iterations:
            return "refine"
        return "unverified"

    def handle_technical_error(state: VerificationState) -> dict:
        return {"technical_retries": state.technical_retries + 1}

    def route_after_technical_error(state: VerificationState) -> Literal["retry", "give_up"]:
        if state.technical_retries >= state.max_technical_retries:
            return "give_up"
        import time

        time.sleep(backoff(state.technical_retries))
        return "retry"

    def refine_query(state: VerificationState) -> dict:
        this_iteration = [a for a in state.attempts if a.iteration == state.iteration]
        new_query = query_refiner(state.claim, state.current_query, this_iteration)
        return {"current_query": new_query, "iteration": state.iteration + 1}

    def finalize_verified(state: VerificationState) -> dict:
        return {"status": VerificationStatus.VERIFIED}

    def finalize_unverified(state: VerificationState) -> dict:
        return {
            "status": VerificationStatus.UNVERIFIED,
            "failure_reason": state.failure_reason
            or "Iterationslimit erreicht, keine valide Quelle gefunden",
        }

    def finalize_error(state: VerificationState) -> dict:
        return {
            "status": VerificationStatus.ERROR,
            "failure_reason": f"Technischer Fehler nach {state.technical_retries} Wiederholungen",
        }

    graph = StateGraph(VerificationState)
    graph.add_node("prepare", prepare)
    graph.add_node("search", search)
    graph.add_node("validate", validate)
    graph.add_node("handle_technical_error", handle_technical_error)
    graph.add_node("refine_query", refine_query)
    graph.add_node("finalize_verified", finalize_verified)
    graph.add_node("finalize_unverified", finalize_unverified)
    graph.add_node("finalize_error", finalize_error)

    graph.set_entry_point("prepare")
    graph.add_edge("prepare", "search")
    graph.add_edge("search", "validate")
    graph.add_conditional_edges(
        "validate",
        route_after_validate,
        {
            "verified": "finalize_verified",
            "technical_error": "handle_technical_error",
            "refine": "refine_query",
            "unverified": "finalize_unverified",
        },
    )
    graph.add_conditional_edges(
        "handle_technical_error",
        route_after_technical_error,
        {"retry": "search", "give_up": "finalize_error"},
    )
    graph.add_edge("refine_query", "search")
    graph.add_edge("finalize_verified", END)
    graph.add_edge("finalize_unverified", END)
    graph.add_edge("finalize_error", END)

    return graph.compile()


def verify_claim(
    claim: Claim,
    adapters: list[SourceAdapter],
    max_iterations: int = 3,
    max_technical_retries: int = 2,
    is_allowed_source: AllowedSourcePolicy = default_allowed_source_policy,
    claim_support_checker: ClaimSupportChecker = default_claim_support_checker,
    query_refiner: QueryRefiner = default_query_refiner,
    backoff: BackoffFn = default_backoff,
) -> VerificationState:
    """Convenience entry point: run the compiled graph for a single claim."""
    compiled = build_verification_graph(
        adapters, is_allowed_source, claim_support_checker, query_refiner, backoff
    )
    initial = VerificationState(
        claim=claim, max_iterations=max_iterations, max_technical_retries=max_technical_retries
    )
    result = compiled.invoke(initial)
    return VerificationState.model_validate(result)
