"""Shared Pydantic data contracts for the verification pipeline.

Every stage (adapters, LangGraph nodes, review gate, repository) reads and
writes these models. None of them contain I/O or business logic; they are
pure data contracts so that stages stay independently testable.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field, field_validator

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class ClaimType(StrEnum):
    FORMULA = "formula"
    FACT = "fact"
    ATTRIBUTION = "attribution"
    QUANTITATIVE = "quantitative"


class SourceType(StrEnum):
    PAPER = "paper"
    BOOK = "book"
    SCRIPT = "script"
    PREPRINT = "preprint"
    OTHER = "other"


class ProviderName(StrEnum):
    PERPLEXITY = "perplexity"
    CROSSREF = "crossref"
    SEMANTIC_SCHOLAR = "semantic_scholar"
    ARXIV = "arxiv"


class VerificationStatus(StrEnum):
    PENDING = "pending"
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    ERROR = "error"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReviewDecision(StrEnum):
    AUTO_APPROVED = "auto_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


class Claim(BaseModel):
    """A single physical claim extracted from a protocol document."""

    id: str = Field(default_factory=lambda: new_id("claim"))
    document_id: str
    location: str  # e.g. slide/section id, so the claim can be traced back
    text: str = Field(min_length=1)
    claim_type: ClaimType
    search_query: str = Field(min_length=1)
    extraction_confidence: Confidence
    context: str = ""

    @field_validator("text", "search_query")
    @classmethod
    def _strip_and_require_nonblank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be blank")
        return stripped

    def cache_key(self) -> str:
        """Stable key for cache/dedup lookups, independent of claim.id."""
        import hashlib

        normalized = " ".join(self.text.lower().split())
        digest = hashlib.sha256(f"{self.claim_type}:{normalized}".encode()).hexdigest()
        return digest[:32]


class Source(BaseModel):
    """A bibliographic source returned or resolved by an adapter."""

    id: str = Field(default_factory=lambda: new_id("src"))
    provider: ProviderName
    source_type: SourceType
    title: str
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    doi: str | None = None
    url: str | None = None
    venue: str | None = None
    raw_snippet: str = ""

    def locator(self) -> str:
        """The most authoritative identifier available, for dedup/citation keys."""
        if self.doi:
            return f"doi:{self.doi.lower()}"
        if self.url:
            return f"url:{self.url}"
        return f"title:{' '.join(self.title.lower().split())}"


class SearchAttempt(BaseModel):
    """Record of a single provider query within a verification run."""

    provider: ProviderName
    query: str
    iteration: int
    sources_found: list[Source] = Field(default_factory=list)
    error: str | None = None
    queried_at: datetime = Field(default_factory=_utcnow)


class ValidationResult(BaseModel):
    """Outcome of checking whether a source actually supports a claim."""

    source: Source
    is_allowed_source: bool
    supports_claim: bool
    validation_confidence: Confidence
    reasoning: str = ""

    @property
    def is_valid(self) -> bool:
        return self.is_allowed_source and self.supports_claim


class VerificationState(BaseModel):
    """LangGraph state for verifying a single claim."""

    claim: Claim
    iteration: int = 0
    max_iterations: int = 3
    current_query: str = ""
    technical_retries: int = 0
    max_technical_retries: int = 2
    attempts: list[SearchAttempt] = Field(default_factory=list)
    validations: list[ValidationResult] = Field(default_factory=list)
    validated_sources: list[Source] = Field(default_factory=list)
    status: VerificationStatus = VerificationStatus.PENDING
    failure_reason: str | None = None
    cache_hit: bool = False

    @property
    def has_conflicting_sources(self) -> bool:
        return len(self.validated_sources) > 1

    @property
    def technical_error_count(self) -> int:
        return sum(1 for a in self.attempts if a.error is not None)


class RiskAssessment(BaseModel):
    """Output of the risk-adaptive review gate for one verification run."""

    risk_level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    requires_review: bool

    @classmethod
    def low(cls) -> "RiskAssessment":
        return cls(risk_level=RiskLevel.LOW, reasons=[], requires_review=False)


class ReviewRecord(BaseModel):
    """Persisted human (or auto) decision for a verification run."""

    id: str = Field(default_factory=lambda: new_id("review"))
    run_id: str
    decision: ReviewDecision
    risk_level: RiskLevel
    reasons: list[str] = Field(default_factory=list)
    reviewer: str | None = None
    notes: str = ""
    decided_at: datetime = Field(default_factory=_utcnow)


class VerificationRun(BaseModel):
    """Top-level audit record tying a claim to its final outcome."""

    id: str = Field(default_factory=lambda: new_id("run"))
    claim: Claim
    status: VerificationStatus
    validated_sources: list[Source] = Field(default_factory=list)
    failure_reason: str | None = None
    iteration_count: int = 0
    cache_hit: bool = False
    providers_used: list[ProviderName] = Field(default_factory=list)
    risk_assessment: RiskAssessment | None = None
    review: ReviewRecord | None = None
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime | None = None

    @classmethod
    def from_state(cls, state: VerificationState) -> "VerificationRun":
        providers = sorted({a.provider for a in state.attempts}, key=lambda p: p.value)
        return cls(
            claim=state.claim,
            status=state.status,
            validated_sources=state.validated_sources,
            failure_reason=state.failure_reason,
            iteration_count=state.iteration,
            cache_hit=state.cache_hit,
            providers_used=list(providers),
            completed_at=_utcnow(),
        )
