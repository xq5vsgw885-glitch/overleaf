"""SQLite audit-store repository, behind a swappable ABC.

`VerificationRepository` is the contract the rest of the pipeline (LangGraph
nodes, review gate) depends on. `SQLiteRepository` is the v1 implementation.
A future `PostgresRepository` can implement the same ABC without touching
callers, per the "no architecture break on migration" requirement.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from pathlib import Path

from verification.models import (
    Claim,
    ClaimType,
    ProviderName,
    ReviewDecision,
    ReviewRecord,
    RiskAssessment,
    RiskLevel,
    SearchAttempt,
    Source,
    SourceType,
    ValidationResult,
    VerificationRun,
    VerificationState,
    VerificationStatus,
    new_id,
)

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def apply_migrations(conn: sqlite3.Connection, migrations_dir: Path = MIGRATIONS_DIR) -> None:
    """Apply any migration in `migrations_dir` not yet recorded, in filename order."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    applied = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
    for path in sorted(migrations_dir.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        conn.executescript(path.read_text())
        conn.execute(
            "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
            (version, datetime.now(timezone.utc).isoformat()),
        )
    conn.commit()


class VerificationRepository(ABC):
    """Storage contract the pipeline depends on."""

    @abstractmethod
    def get_cached_run(self, cache_key: str, ttl: timedelta | None = None) -> VerificationRun | None: ...

    @abstractmethod
    def save_run(self, state: VerificationState) -> VerificationRun: ...

    @abstractmethod
    def save_risk_assessment(self, run_id: str, risk: RiskAssessment) -> None: ...

    @abstractmethod
    def save_review(self, review: ReviewRecord) -> None: ...

    @abstractmethod
    def get_run(self, run_id: str) -> VerificationRun | None: ...

    @abstractmethod
    def list_runs_requiring_review(self) -> list[VerificationRun]: ...


class SQLiteRepository(VerificationRepository):
    def __init__(self, db_path: str | Path = ":memory:") -> None:
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        apply_migrations(self._conn)

    def close(self) -> None:
        self._conn.close()

    # -- writes ---------------------------------------------------------

    def _upsert_claim(self, claim: Claim) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO claims "
            "(id, document_id, location, text, claim_type, search_query, "
            " extraction_confidence, context, cache_key, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                claim.id,
                claim.document_id,
                claim.location,
                claim.text,
                claim.claim_type.value,
                claim.search_query,
                claim.extraction_confidence,
                claim.context,
                claim.cache_key(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )

    def _upsert_source(self, source: Source) -> str:
        existing = self._conn.execute(
            "SELECT id FROM sources WHERE locator = ?", (source.locator(),)
        ).fetchone()
        if existing is not None:
            return existing["id"]
        self._conn.execute(
            "INSERT INTO sources "
            "(id, provider, source_type, title, authors_json, year, doi, url, "
            " venue, raw_snippet, locator, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                source.id,
                source.provider.value,
                source.source_type.value,
                source.title,
                json.dumps(source.authors),
                source.year,
                source.doi,
                source.url,
                source.venue,
                source.raw_snippet,
                source.locator(),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        return source.id

    def save_run(self, state: VerificationState) -> VerificationRun:
        run = VerificationRun.from_state(state)
        self._upsert_claim(state.claim)
        self._conn.execute(
            "INSERT INTO verification_runs "
            "(id, claim_id, status, failure_reason, iteration_count, cache_hit, "
            " providers_used_json, started_at, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run.id,
                run.claim.id,
                run.status.value,
                run.failure_reason,
                run.iteration_count,
                int(run.cache_hit),
                json.dumps([p.value for p in run.providers_used]),
                run.started_at.isoformat(),
                run.completed_at.isoformat() if run.completed_at else None,
            ),
        )
        for source in state.validated_sources:
            source_id = self._upsert_source(source)
            self._conn.execute(
                "INSERT OR IGNORE INTO run_sources (run_id, source_id) VALUES (?, ?)",
                (run.id, source_id),
            )
        for attempt in state.attempts:
            attempt_id = new_id("attempt")
            self._conn.execute(
                "INSERT INTO search_attempts "
                "(id, run_id, provider, query, iteration, error, queried_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    attempt_id,
                    run.id,
                    attempt.provider.value,
                    attempt.query,
                    attempt.iteration,
                    attempt.error,
                    attempt.queried_at.isoformat(),
                ),
            )
            for source in attempt.sources_found:
                source_id = self._upsert_source(source)
                self._conn.execute(
                    "INSERT OR IGNORE INTO attempt_sources (attempt_id, source_id) VALUES (?, ?)",
                    (attempt_id, source_id),
                )
        for validation in state.validations:
            source_id = self._upsert_source(validation.source)
            self._conn.execute(
                "INSERT INTO validations "
                "(id, run_id, source_id, is_allowed_source, supports_claim, "
                " validation_confidence, reasoning) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    new_id("validation"),
                    run.id,
                    source_id,
                    int(validation.is_allowed_source),
                    int(validation.supports_claim),
                    validation.validation_confidence,
                    validation.reasoning,
                ),
            )
        self._conn.commit()
        return run

    def save_risk_assessment(self, run_id: str, risk: RiskAssessment) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO risk_assessments "
            "(run_id, risk_level, reasons_json, requires_review) VALUES (?, ?, ?, ?)",
            (run_id, risk.risk_level.value, json.dumps(risk.reasons), int(risk.requires_review)),
        )
        self._conn.commit()

    def save_review(self, review: ReviewRecord) -> None:
        self._conn.execute(
            "INSERT INTO review_decisions "
            "(id, run_id, decision, risk_level, reasons_json, reviewer, notes, decided_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                review.id,
                review.run_id,
                review.decision.value,
                review.risk_level.value,
                json.dumps(review.reasons),
                review.reviewer,
                review.notes,
                review.decided_at.isoformat(),
            ),
        )
        self._conn.commit()

    # -- reads ------------------------------------------------------------

    def _sources_for_run(self, run_id: str) -> list[Source]:
        rows = self._conn.execute(
            "SELECT s.* FROM sources s "
            "JOIN run_sources rs ON rs.source_id = s.id "
            "WHERE rs.run_id = ?",
            (run_id,),
        ).fetchall()
        return [self._row_to_source(row) for row in rows]

    @staticmethod
    def _row_to_source(row: sqlite3.Row) -> Source:
        return Source(
            id=row["id"],
            provider=ProviderName(row["provider"]),
            source_type=SourceType(row["source_type"]),
            title=row["title"],
            authors=json.loads(row["authors_json"]),
            year=row["year"],
            doi=row["doi"],
            url=row["url"],
            venue=row["venue"],
            raw_snippet=row["raw_snippet"],
        )

    def _row_to_run(self, row: sqlite3.Row) -> VerificationRun:
        claim_row = self._conn.execute(
            "SELECT * FROM claims WHERE id = ?", (row["claim_id"],)
        ).fetchone()
        claim = Claim(
            id=claim_row["id"],
            document_id=claim_row["document_id"],
            location=claim_row["location"],
            text=claim_row["text"],
            claim_type=ClaimType(claim_row["claim_type"]),
            search_query=claim_row["search_query"],
            extraction_confidence=claim_row["extraction_confidence"],
            context=claim_row["context"],
        )
        risk_row = self._conn.execute(
            "SELECT * FROM risk_assessments WHERE run_id = ?", (row["id"],)
        ).fetchone()
        risk = None
        if risk_row is not None:
            risk = RiskAssessment(
                risk_level=RiskLevel(risk_row["risk_level"]),
                reasons=json.loads(risk_row["reasons_json"]),
                requires_review=bool(risk_row["requires_review"]),
            )
        review_row = self._conn.execute(
            "SELECT * FROM review_decisions WHERE run_id = ? ORDER BY decided_at DESC LIMIT 1",
            (row["id"],),
        ).fetchone()
        review = None
        if review_row is not None:
            review = ReviewRecord(
                id=review_row["id"],
                run_id=review_row["run_id"],
                decision=ReviewDecision(review_row["decision"]),
                risk_level=RiskLevel(review_row["risk_level"]),
                reasons=json.loads(review_row["reasons_json"]),
                reviewer=review_row["reviewer"],
                notes=review_row["notes"],
                decided_at=datetime.fromisoformat(review_row["decided_at"]),
            )
        return VerificationRun(
            id=row["id"],
            claim=claim,
            status=VerificationStatus(row["status"]),
            validated_sources=self._sources_for_run(row["id"]),
            failure_reason=row["failure_reason"],
            iteration_count=row["iteration_count"],
            cache_hit=bool(row["cache_hit"]),
            providers_used=[ProviderName(p) for p in json.loads(row["providers_used_json"])],
            risk_assessment=risk,
            review=review,
            started_at=datetime.fromisoformat(row["started_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"]) if row["completed_at"] else None
            ),
        )

    def get_cached_run(self, cache_key: str, ttl: timedelta | None = None) -> VerificationRun | None:
        row = self._conn.execute(
            "SELECT vr.* FROM verification_runs vr "
            "JOIN claims c ON c.id = vr.claim_id "
            "WHERE c.cache_key = ? AND vr.status IN ('verified', 'unverified') "
            "AND vr.completed_at IS NOT NULL "
            "ORDER BY vr.completed_at DESC LIMIT 1",
            (cache_key,),
        ).fetchone()
        if row is None:
            return None
        if ttl is not None:
            completed_at = datetime.fromisoformat(row["completed_at"])
            if datetime.now(timezone.utc) - completed_at > ttl:
                return None
        return self._row_to_run(row)

    def get_run(self, run_id: str) -> VerificationRun | None:
        row = self._conn.execute(
            "SELECT * FROM verification_runs WHERE id = ?", (run_id,)
        ).fetchone()
        if row is None:
            return None
        return self._row_to_run(row)

    def list_runs_requiring_review(self) -> list[VerificationRun]:
        rows = self._conn.execute(
            "SELECT vr.* FROM verification_runs vr "
            "JOIN risk_assessments ra ON ra.run_id = vr.id "
            "WHERE ra.requires_review = 1 "
            "AND vr.id NOT IN (SELECT run_id FROM review_decisions "
            "                  WHERE decision IN ('approved', 'rejected'))"
        ).fetchall()
        return [self._row_to_run(row) for row in rows]
