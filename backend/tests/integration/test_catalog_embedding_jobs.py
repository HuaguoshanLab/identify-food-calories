"""Real PostgreSQL contracts for publication-scoped embedding job orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import threading
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogDraftCreateCommand, CatalogEmbeddingRetryCommand, CatalogLifecycleCommand
from app.admin.service import AdminService
from app.auth.models import User, UserRole
from app.nutrition.search_models import (
    CatalogActiveVectorSpace,
    CatalogEmbeddingJob,
    CatalogSearchName,
    CatalogVectorSpace,
)


def _actor(now: datetime) -> User:
    return User(
        id=uuid.uuid4(),
        email=f"embedding-{uuid.uuid4().hex}@example.test",
        password_hash="hash",
        role=UserRole.ADMIN.value,
        is_active=True,
        email_verified_at=now,
        created_at=now,
        updated_at=now,
    )


def _draft_command() -> CatalogDraftCreateCommand:
    return CatalogDraftCreateCommand(
        canonical_name="番茄炒蛋",
        aliases=["西红柿炒鸡蛋", "tomato egg"],
        energy_kcal_per_100g=Decimal("89"),
        protein_g_per_100g=Decimal("5"),
        fat_g_per_100g=Decimal("6"),
        carbohydrate_g_per_100g=Decimal("4"),
        source_name="USDA",
        source_url="https://fdc.nal.usda.gov/",
        authorization_status="authorized",
        reason="publication test fixture",
    )


def _publish(service: AdminService, actor_id: uuid.UUID) -> uuid.UUID:
    draft = service.create_catalog_draft(
        actor_user_id=actor_id,
        command=_draft_command(),
        command_key="create-embedding-jobs-pg-0001",
    )
    lifecycle = CatalogLifecycleCommand(reason="reviewed", confirm=True)
    service.review_catalog_draft(
        actor_user_id=actor_id,
        draft_id=draft.id,
        expected_revision=1,
        command=lifecycle,
        command_key="review-embedding-jobs-pg-0001",
    )
    return service.publish_catalog_draft(
        actor_user_id=actor_id,
        draft_id=draft.id,
        expected_revision=1,
        command=lifecycle,
        command_key="publish-embedding-jobs-pg-0001",
    ).id


def _install_active_space(session: Session, now: datetime) -> CatalogVectorSpace:
    space = CatalogVectorSpace(
        id=uuid.uuid4(),
        embedding_model="text-embedding-v4",
        embedding_dimension=1024,
        adapter_version="v1",
        created_at=now,
    )
    session.add(space)
    session.flush()
    session.add(
        CatalogActiveVectorSpace(
            pointer_key="catalog",
            vector_space_id=space.id,
            advanced_at=now,
        )
    )
    session.flush()
    return space


def test_publish_creates_one_job_per_name_and_active_space_and_exposes_safe_aggregate(db_session) -> None:
    now = datetime.now(UTC)
    actor = _actor(now)
    db_session.add(actor)
    _install_active_space(db_session, now)
    db_session.flush()
    service = AdminService(
        repository=SqlAlchemyAdminRepository(db_session),
        now=lambda: now,
        commit=db_session.commit,
        rollback=db_session.rollback,
    )

    publication_id = _publish(service, actor.id)
    status = service.get_catalog_embedding_status(
        actor_user_id=actor.id, publication_id=publication_id
    )

    jobs = list(
        db_session.scalars(
            select(CatalogEmbeddingJob).where(
                CatalogEmbeddingJob.publication_id == publication_id
            )
        )
    )
    names = list(
        db_session.scalars(
            select(CatalogSearchName).where(
                CatalogSearchName.publication_id == publication_id
            )
        )
    )
    assert len(names) == 3
    assert len(jobs) == 3
    assert status.status == "pending"
    assert status.pending_count == 3
    assert all(item.status == "pending" for item in status.jobs)
    assert all("display_name" not in item.model_dump() for item in status.jobs)


def test_publication_retry_is_idempotent_for_partial_failure_and_concurrent_requests(test_engine) -> None:
    now = datetime.now(UTC)
    with Session(test_engine) as session:
        actor = _actor(now)
        session.add(actor)
        _install_active_space(session, now)
        session.commit()
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session),
            now=lambda: now,
            commit=session.commit,
            rollback=session.rollback,
        )
        publication_id = _publish(service, actor.id)
        jobs = list(session.scalars(select(CatalogEmbeddingJob).where(CatalogEmbeddingJob.publication_id == publication_id)))
        jobs[0].status = "completed"
        jobs[1].status = "failed"
        jobs[1].attempt_count = 1
        jobs[1].last_error_code = "provider_unavailable"
        jobs[2].status = "failed"
        jobs[2].attempt_count = jobs[2].max_attempts
        jobs[2].last_error_code = "retry_exhausted"
        session.commit()
        actor_id = actor.id

    barrier = threading.Barrier(2)
    results = []
    errors: list[BaseException] = []

    def retry() -> None:
        try:
            with Session(test_engine) as session:
                barrier.wait(timeout=5)
                response = AdminService(
                    repository=SqlAlchemyAdminRepository(session),
                    now=lambda: now + timedelta(minutes=1),
                    commit=session.commit,
                    rollback=session.rollback,
                ).retry_catalog_embedding_jobs(
                    actor_user_id=actor_id,
                    publication_id=publication_id,
                    command=CatalogEmbeddingRetryCommand(
                        reason="provider recovered", idempotency_key="retry-embedding-jobs-pg-0001"
                    ),
                )
                results.append(response)
        except BaseException as error:  # pragma: no cover - assertion reports worker failures
            errors.append(error)

    workers = [threading.Thread(target=retry) for _ in range(2)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(timeout=10)

    assert not errors
    assert len(results) == 2
    assert results[0].model_dump() == results[1].model_dump()
    assert results[0].reset_count == 1
    assert results[0].status == "partial_failure"
    with Session(test_engine) as session:
        rows = list(session.scalars(select(CatalogEmbeddingJob).where(CatalogEmbeddingJob.publication_id == publication_id)))
        assert [row.status for row in rows].count("pending") == 1
        assert [row.status for row in rows].count("completed") == 1
        assert [row.status for row in rows].count("failed") == 1
