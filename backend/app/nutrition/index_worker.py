"""Bounded worker for immutable catalog vector-space build jobs.

The worker never creates work, changes a build manifest, or changes the active
vector-space pointer.  PostgreSQL remains the source of truth before and after
the (only) external side effect: generating an embedding for one controlled name.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from app.nutrition.search_repository import SqlAlchemyHybridFoodSearchRepository
from app.providers.embedding.dto import EmbeddingRequest
from app.providers.embedding.ports import EmbeddingProvider
from app.providers.reasoning.dto import ProviderCallError, ProviderFailureKind


_LEASE_SECONDS = 60
_MAX_BACKOFF_SECONDS = 300


@dataclass(frozen=True, slots=True)
class _LeasedJob:
    job_id: uuid.UUID
    lease_token: str


class CatalogEmbeddingWorker:
    """Execute one immutable build job at a time with a short, durable lease."""

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        provider: EmbeddingProvider,
        worker_id: str,
        vector_space_id: uuid.UUID | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        self._session_factory = session_factory
        self._provider = provider
        self._worker_id = worker_id.strip()
        self._vector_space_id = vector_space_id
        self._now = now or (lambda: datetime.now(UTC))

    def run_once(self) -> str:
        """Claim at most one due build job and return a safe operational outcome."""

        claimed = self._claim()
        if claimed is None:
            self._reconcile_reused_space_if_scoped()
            return "idle"
        document_name = self._recheck_before_io(claimed)
        if document_name is None:
            return "cancelled"
        try:
            result = asyncio.run(
                self._provider.embed(
                    EmbeddingRequest(
                        names=(document_name,),
                        text_type="document",
                        model_alias="catalog-embedding-worker-v1",
                    )
                )
            )
        except ProviderCallError as error:
            return self._record_provider_failure(claimed, error)
        except (ConnectionError, TimeoutError):
            return self._record_transient_failure(claimed, "provider_unavailable")
        return self._write_back(claimed, tuple(result.vectors[0].values))

    def _claim(self) -> _LeasedJob | None:
        now = self._now()
        token = uuid.uuid4().hex
        with self._session_factory() as session:
            repository = SqlAlchemyHybridFoodSearchRepository(session)
            job = repository.claim_due_build_embedding_job(
                due_at=now,
                now=now,
                lease_owner=f"{self._worker_id}:{token}",
                lease_expires_at=now + timedelta(seconds=_LEASE_SECONDS),
                vector_space_id=self._vector_space_id,
            )
            if job is None:
                session.commit()
                return None
            session.commit()
            return _LeasedJob(job_id=job.id, lease_token=token)

    def _recheck_before_io(self, claimed: _LeasedJob) -> str | None:
        with self._session_factory() as session:
            repository = SqlAlchemyHybridFoodSearchRepository(session)
            name = repository.recheck_leased_build_embedding_job(
                job_id=claimed.job_id,
                lease_owner=self._lease_owner(claimed),
                now=self._now(),
            )
            session.commit()
            return name

    def _write_back(self, claimed: _LeasedJob, vector: tuple[float, ...]) -> str:
        with self._session_factory() as session:
            repository = SqlAlchemyHybridFoodSearchRepository(session)
            completed = repository.complete_leased_build_embedding_job(
                job_id=claimed.job_id,
                lease_owner=self._lease_owner(claimed),
                vector=vector,
                now=self._now(),
            )
            session.commit()
            return "completed" if completed else "cancelled"

    def _record_provider_failure(
        self, claimed: _LeasedJob, error: ProviderCallError
    ) -> str:
        if error.kind in {ProviderFailureKind.TRANSIENT, ProviderFailureKind.OUTCOME_UNKNOWN}:
            return self._record_transient_failure(claimed, error.code)
        return self._record_permanent_failure(claimed, error.code)

    def _record_transient_failure(self, claimed: _LeasedJob, code: str) -> str:
        with self._session_factory() as session:
            repository = SqlAlchemyHybridFoodSearchRepository(session)
            retrying = repository.fail_leased_build_embedding_job(
                job_id=claimed.job_id,
                lease_owner=self._lease_owner(claimed),
                error_code=code,
                retryable=True,
                now=self._now(),
                max_backoff_seconds=_MAX_BACKOFF_SECONDS,
            )
            session.commit()
            return "retry_scheduled" if retrying else "failed"

    def _record_permanent_failure(self, claimed: _LeasedJob, code: str) -> str:
        with self._session_factory() as session:
            repository = SqlAlchemyHybridFoodSearchRepository(session)
            repository.fail_leased_build_embedding_job(
                job_id=claimed.job_id,
                lease_owner=self._lease_owner(claimed),
                error_code=code,
                retryable=False,
                now=self._now(),
                max_backoff_seconds=_MAX_BACKOFF_SECONDS,
            )
            session.commit()
            return "failed"

    def _lease_owner(self, claimed: _LeasedJob) -> str:
        return f"{self._worker_id}:{claimed.lease_token}"

    def _reconcile_reused_space_if_scoped(self) -> None:
        """An idle scoped worker can prove a reused snapshot without Provider I/O."""

        if self._vector_space_id is None:
            return
        with self._session_factory() as session:
            SqlAlchemyHybridFoodSearchRepository(session).reconcile_vector_space_build_completions(
                vector_space_id=self._vector_space_id, now=self._now()
            )
            session.commit()


def completion_hash(*, snapshot_hash: str, manifest: list[dict[str, str]]) -> str:
    """Hash only immutable identifiers; embeddings and controlled names stay out."""

    payload = {"snapshot_hash": snapshot_hash, "manifest": manifest}
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
