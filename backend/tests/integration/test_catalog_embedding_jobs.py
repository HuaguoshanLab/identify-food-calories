"""Real PostgreSQL contracts for publication-scoped embedding job orchestration."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import hashlib
import json
import threading
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogDraftCreateCommand, CatalogEmbeddingRetryCommand, CatalogLifecycleCommand, CatalogVectorSpaceBuildCommand
from app.admin.service import (
    AdminPermissionDenied,
    AdminService,
    CatalogVectorSpaceActivationConflict,
    CatalogVectorSpaceBuildConflict,
)
from app.auth.models import User, UserRole
from app.nutrition.search_models import (
    CatalogActiveVectorSpace,
    CatalogEmbeddingJob,
    CatalogSearchEmbedding,
    CatalogSearchName,
    CatalogVectorSpace,
    CatalogVectorSpaceBuild,
    CatalogVectorSpaceBuildCompletion,
    CatalogVectorSpaceActivationApproval,
)
from app.providers.embedding.fake import FakeEmbeddingProvider
from app.providers.reasoning.dto import ProviderFailureKind


def _vector(value: float = 0.25) -> tuple[float, ...]:
    return (value,) * 1024


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


def _publish(service: AdminService, actor_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID, str]:
    suffix = actor_id.hex
    draft = service.create_catalog_draft(
        actor_user_id=actor_id,
        command=_draft_command(),
        command_key=f"create-embedding-jobs-pg-{suffix}",
    )
    lifecycle = CatalogLifecycleCommand(reason="reviewed", confirm=True)
    service.review_catalog_draft(
        actor_user_id=actor_id,
        draft_id=draft.id,
        expected_revision=1,
        command=lifecycle,
        command_key=f"review-embedding-jobs-pg-{suffix}",
    )
    publication = service.publish_catalog_draft(
        actor_user_id=actor_id,
        draft_id=draft.id,
        expected_revision=1,
        command=lifecycle,
        command_key=f"publish-embedding-jobs-pg-{suffix}",
    )
    return publication.id, draft.id, suffix


def _install_active_space(session: Session, now: datetime) -> CatalogVectorSpace:
    existing = session.scalar(
        select(CatalogVectorSpace)
        .join(
            CatalogActiveVectorSpace,
            CatalogActiveVectorSpace.vector_space_id == CatalogVectorSpace.id,
        )
        .where(CatalogActiveVectorSpace.pointer_key == "catalog")
    )
    if existing is not None:
        return existing
    space = CatalogVectorSpace(
        id=uuid.uuid4(),
        embedding_model="text-embedding-v4",
        embedding_dimension=1024,
        adapter_version="v1",
        retrieval_version="hybrid-v1",
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

    publication_id, draft_id, suffix = _publish(service, actor.id)
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
    replay = service.publish_catalog_draft(
        actor_user_id=actor.id,
        draft_id=draft_id,
        expected_revision=1,
        command=CatalogLifecycleCommand(reason="reviewed", confirm=True),
        command_key=f"publish-embedding-jobs-pg-{suffix}",
    )
    assert replay.id == publication_id
    assert len(
        list(
            db_session.scalars(
                select(CatalogEmbeddingJob).where(
                    CatalogEmbeddingJob.publication_id == publication_id
                )
            )
        )
    ) == 3


def test_publication_retry_is_idempotent_for_partial_failure_and_concurrent_requests(test_engine) -> None:
    now = datetime.now(UTC)
    with Session(test_engine) as session:
        actor = _actor(now)
        actor_id = actor.id
        session.add(actor)
        actor_id = actor.id
        _install_active_space(session, now)
        active_space = CatalogVectorSpace(id=uuid.uuid4(), embedding_model="active-worker", embedding_dimension=1024, adapter_version=f"active-{actor.id.hex}", retrieval_version="active-v1", created_at=now)
        session.add(active_space)
        session.flush()
        pointer = session.scalar(select(CatalogActiveVectorSpace).where(CatalogActiveVectorSpace.pointer_key == "catalog"))
        assert pointer is not None
        pointer.vector_space_id = active_space.id
        session.commit()
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session),
            now=lambda: now,
            commit=session.commit,
            rollback=session.rollback,
        )
        publication_id, _, _ = _publish(service, actor.id)
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


def test_active_publication_worker_retries_without_creating_build_evidence(test_engine) -> None:
    """Activated publication jobs are worker-owned, but never manufacture frozen proof."""
    from app.nutrition.index_worker import CatalogEmbeddingWorker

    now = datetime.now(UTC)
    with Session(test_engine) as session:
        actor = _actor(now)
        session.add(actor)
        _install_active_space(session, now)
        active_space = CatalogVectorSpace(id=uuid.uuid4(), embedding_model="active-worker", embedding_dimension=1024, adapter_version=f"active-{actor.id.hex}", retrieval_version="active-v1", created_at=now)
        session.add(active_space)
        session.flush()
        pointer = session.scalar(select(CatalogActiveVectorSpace).where(CatalogActiveVectorSpace.pointer_key == "catalog"))
        assert pointer is not None
        pointer.vector_space_id = active_space.id
        active_space_id = active_space.id
        session.commit()
        service = AdminService(repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback)
        publication_id, _, _ = _publish(service, actor.id)
        actor_id = actor.id

    provider = FakeEmbeddingProvider()
    provider.queue_result((_vector(),))
    provider.queue_error(kind=ProviderFailureKind.PERMANENT, code="active_publication_failure")
    provider.queue_result((_vector(),))
    worker = CatalogEmbeddingWorker(session_factory=lambda: Session(test_engine), provider=provider, worker_id="active-publication-worker", vector_space_id=active_space_id, now=lambda: now)
    assert [worker.run_once() for _ in range(3)] == ["completed", "failed", "completed"]
    with Session(test_engine) as session:
        service = AdminService(repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback)
        before = service.get_catalog_embedding_status(actor_user_id=actor_id, publication_id=publication_id)
        assert before.status == "partial_failure"
        assert session.scalar(select(CatalogVectorSpaceBuild).where(CatalogVectorSpaceBuild.vector_space_id == active_space_id)) is None
        replay = service.retry_catalog_embedding_jobs(actor_user_id=actor_id, publication_id=publication_id, command=CatalogEmbeddingRetryCommand(reason="provider recovered", idempotency_key="active-publication-retry-0001"))
        assert replay.reset_count == 1
    recovered = FakeEmbeddingProvider()
    recovered.queue_result((_vector(),))
    assert CatalogEmbeddingWorker(session_factory=lambda: Session(test_engine), provider=recovered, worker_id="active-publication-recovery", vector_space_id=active_space_id, now=lambda: now).run_once() == "completed"
    with Session(test_engine) as session:
        status = AdminService(repository=SqlAlchemyAdminRepository(session), now=lambda: now, commit=session.commit, rollback=session.rollback).get_catalog_embedding_status(actor_user_id=actor_id, publication_id=publication_id)
        assert status.status == "ready"
        assert session.scalar(select(CatalogVectorSpaceBuild).where(CatalogVectorSpaceBuild.vector_space_id == active_space_id)) is None


def test_vector_space_build_snapshots_current_eligible_names_and_replays_without_completion(db_session) -> None:
    now = datetime.now(UTC)
    actor = _actor(now)
    user = User(
        id=uuid.uuid4(), email=f"ordinary-{uuid.uuid4().hex}@example.test", password_hash="hash",
        role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    db_session.add_all([actor, user])
    db_session.flush()
    service = AdminService(
        repository=SqlAlchemyAdminRepository(db_session), now=lambda: now,
        commit=db_session.commit, rollback=db_session.rollback,
    )
    publication_id, _, _ = _publish(service, actor.id)
    command = CatalogVectorSpaceBuildCommand(
        embedding_model="text-embedding-v4", embedding_dimension=1024, adapter_version=f"build-{actor.id.hex}",
        retrieval_version="hybrid-v1", reason="controlled catalog backfill", confirm=True,
    )
    build = service.create_catalog_vector_space_build(
        actor_user_id=actor.id, command=command, command_key="vector-space-build-pg-0001",
    )
    replay = service.create_catalog_vector_space_build(
        actor_user_id=actor.id, command=command, command_key="vector-space-build-pg-0001",
    )
    assert replay.model_dump() == build.model_dump()
    assert build.expected_name_count >= 3
    assert build.pending_count == build.expected_name_count
    assert build.status == "pending"
    stored = db_session.scalar(select(CatalogVectorSpaceBuild).where(CatalogVectorSpaceBuild.id == build.id))
    assert stored is not None
    assert len(stored.snapshot_manifest) == build.expected_name_count
    assert sum(item["publication_id"] == str(publication_id) for item in stored.snapshot_manifest) == 3
    assert len(set(item["name_id"] for item in stored.snapshot_manifest)) == build.expected_name_count
    assert db_session.scalar(select(CatalogVectorSpaceBuildCompletion).where(CatalogVectorSpaceBuildCompletion.build_id == build.id)) is None
    assert db_session.scalar(
        select(CatalogActiveVectorSpace).where(
            CatalogActiveVectorSpace.vector_space_id == build.vector_space_id
        )
    ) is None
    assert len(list(db_session.scalars(select(CatalogEmbeddingJob).where(CatalogEmbeddingJob.vector_space_id == build.vector_space_id)))) == build.expected_name_count
    follow_up = service.create_catalog_vector_space_build(
        actor_user_id=actor.id,
        command=command.model_copy(update={"reason": "same identity later snapshot"}),
        command_key="vector-space-build-pg-0004",
    )
    assert follow_up.vector_space_id == build.vector_space_id
    assert follow_up.expected_name_count == build.expected_name_count
    assert len(list(db_session.scalars(select(CatalogEmbeddingJob).where(
        CatalogEmbeddingJob.vector_space_id == build.vector_space_id
    )))) == build.expected_name_count
    separate = service.create_catalog_vector_space_build(
        actor_user_id=actor.id,
        command=command.model_copy(update={"retrieval_version": "hybrid-v2"}),
        command_key="vector-space-build-pg-0003",
    )
    assert separate.vector_space_id != build.vector_space_id
    assert separate.retrieval_version == "hybrid-v2"
    try:
        service.create_catalog_vector_space_build(actor_user_id=user.id, command=command, command_key="vector-space-build-pg-0002")
    except AdminPermissionDenied:
        pass
    else:  # pragma: no cover - guard is the assertion
        raise AssertionError("ordinary user unexpectedly started a provider-costing build")


def test_vector_space_build_rejects_empty_name_snapshot_without_persisting_space(db_session) -> None:
    """空清单不能伪装成已完成，也不能留下无意义的向量空间。"""

    now = datetime.now(UTC)
    actor = _actor(now)
    db_session.add(actor)
    db_session.flush()
    repository = SqlAlchemyAdminRepository(db_session)
    repository.list_current_eligible_catalog_search_names = lambda: []  # type: ignore[method-assign]
    service = AdminService(
        repository=repository,
        now=lambda: now,
        commit=db_session.commit,
        rollback=db_session.rollback,
    )
    before_spaces = len(list(db_session.scalars(select(CatalogVectorSpace))))
    before_builds = len(list(db_session.scalars(select(CatalogVectorSpaceBuild))))

    with pytest.raises(CatalogVectorSpaceBuildConflict, match="backfill the search index"):
        service.create_catalog_vector_space_build(
            actor_user_id=actor.id,
            command=CatalogVectorSpaceBuildCommand(
                embedding_model="text-embedding-v4",
                embedding_dimension=1024,
                adapter_version=f"empty-{actor.id.hex}",
                retrieval_version="hybrid-v1",
                reason="empty build must fail",
                confirm=True,
            ),
            command_key=f"vector-space-empty-pg-{actor.id.hex}",
        )

    assert len(list(db_session.scalars(select(CatalogVectorSpace)))) == before_spaces
    assert len(list(db_session.scalars(select(CatalogVectorSpaceBuild)))) == before_builds


def test_legacy_empty_build_is_projected_as_empty_and_gets_no_completion_evidence(db_session) -> None:
    """历史空构建保持可见，但不能再被当成成功证据。"""

    now = datetime.now(UTC)
    actor = _actor(now)
    space = CatalogVectorSpace(
        id=uuid.uuid4(),
        embedding_model="text-embedding-v4",
        embedding_dimension=1024,
        adapter_version=f"legacy-empty-{actor.id.hex}",
        retrieval_version="hybrid-v1",
        created_at=now,
    )
    build = CatalogVectorSpaceBuild(
        id=uuid.uuid4(),
        vector_space_id=space.id,
        requested_by=str(actor.id),
        reason="legacy empty build",
        command_key=f"legacy-empty-build-{actor.id.hex}",
        retrieval_version="hybrid-v1",
        snapshot_manifest=[],
        snapshot_hash=hashlib.sha256(b"[]").hexdigest(),
        expected_name_count=0,
        requested_at=now,
    )
    db_session.add_all([actor, space, build])
    db_session.flush()
    repository = SqlAlchemyAdminRepository(db_session)

    assert repository.reconcile_catalog_vector_space_build_completion(build=build, now=now) is None
    service = AdminService(
        repository=repository,
        now=lambda: now,
        commit=db_session.commit,
        rollback=db_session.rollback,
    )
    status = service.get_catalog_vector_space_build_status(
        actor_user_id=actor.id,
        build_id=build.id,
    )

    assert status.status == "empty"
    assert status.activation_ready is False
    assert db_session.scalar(
        select(CatalogVectorSpaceBuildCompletion).where(
            CatalogVectorSpaceBuildCompletion.build_id == build.id
        )
    ) is None


def test_worker_claims_build_job_once_and_records_exact_completion_evidence(test_engine) -> None:
    """The lease is committed before I/O, so a second worker cannot double-charge."""
    from app.nutrition.index_worker import CatalogEmbeddingWorker

    now = datetime.now(UTC)
    with Session(test_engine) as session:
        actor = _actor(now)
        actor_id = actor.id
        session.add(actor)
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session), now=lambda: now,
            commit=session.commit, rollback=session.rollback,
        )
        _publish(service, actor_id)
        build = service.create_catalog_vector_space_build(
            actor_user_id=actor_id,
            command=CatalogVectorSpaceBuildCommand(
                embedding_model="text-embedding-v4", embedding_dimension=1024,
                adapter_version=f"worker-{actor_id.hex}", retrieval_version="hybrid-v1",
                reason="worker completion test", confirm=True,
            ),
            command_key=f"vector-space-worker-pg-{actor_id.hex}",
        )
        session.commit()

    provider = FakeEmbeddingProvider()
    for _ in range(build.expected_name_count):
        provider.queue_result((_vector(),))
    worker = CatalogEmbeddingWorker(
        session_factory=lambda: Session(test_engine), provider=provider,
        worker_id="worker-a", vector_space_id=build.vector_space_id, now=lambda: now,
    )
    assert [worker.run_once() for _ in range(build.expected_name_count)] == ["completed"] * build.expected_name_count
    assert worker.run_once() == "idle"
    assert len(provider.calls) == build.expected_name_count

    with Session(test_engine) as session:
        jobs = list(session.scalars(select(CatalogEmbeddingJob).where(
            CatalogEmbeddingJob.vector_space_id == build.vector_space_id
        )))
        assert sum(job.status == "completed" for job in jobs) == build.expected_name_count
        completion = session.scalar(select(CatalogVectorSpaceBuildCompletion).where(
            CatalogVectorSpaceBuildCompletion.build_id == build.id
        ))
        assert completion is not None
        assert completion.completed_name_count == build.expected_name_count
        assert session.scalar(select(CatalogActiveVectorSpace).where(
            CatalogActiveVectorSpace.vector_space_id == build.vector_space_id
        )) is None
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session), now=lambda: now,
            commit=session.commit, rollback=session.rollback,
        )
        replay_build = service.create_catalog_vector_space_build(
            actor_user_id=actor_id,
            command=CatalogVectorSpaceBuildCommand(
                embedding_model="text-embedding-v4", embedding_dimension=1024,
                adapter_version=f"worker-{actor_id.hex}", retrieval_version="hybrid-v1",
                reason="reused completed jobs need new manifest evidence", confirm=True,
            ),
            command_key=f"vector-space-worker-reuse-{actor_id.hex}",
        )
        assert replay_build.vector_space_id == build.vector_space_id
        replay_completion = session.scalar(select(CatalogVectorSpaceBuildCompletion).where(
            CatalogVectorSpaceBuildCompletion.build_id == replay_build.id
        ))
        assert replay_completion is not None
        # Simulate an interrupted prior reconciliation: all immutable rows are
        # complete already, so an idle scoped worker must repair only evidence.
        session.delete(replay_completion)
        session.commit()

    idle_worker = CatalogEmbeddingWorker(
        session_factory=lambda: Session(test_engine), provider=FakeEmbeddingProvider(),
        worker_id="worker-reconcile", vector_space_id=build.vector_space_id, now=lambda: now,
    )
    assert idle_worker.run_once() == "idle"
    with Session(test_engine) as session:
        assert session.scalar(select(CatalogVectorSpaceBuildCompletion).where(
            CatalogVectorSpaceBuildCompletion.build_id == replay_build.id
        )) is not None


def test_activation_requires_complete_hash_bound_build_and_replays_idempotently(test_engine, tmp_path) -> None:
    """An approval is durable evidence; it is never inferred from a CLI claim."""
    from app.nutrition.index_worker import CatalogEmbeddingWorker
    from evals.phase_06_3.evaluate import build_release, verify_release

    release_path = tmp_path / "release.json"
    with Session(test_engine) as evaluation_session:
        build_release(session=evaluation_session, output=release_path)
        evaluation_session.rollback()
    verify_release(release_path)

    now = datetime.now(UTC)
    with Session(test_engine) as session:
        actor = _actor(now)
        actor_id = actor.id
        session.add(actor)
        _install_active_space(session, now)
        old_space = CatalogVectorSpace(
            id=uuid.uuid4(), embedding_model="activation-old", embedding_dimension=1024,
            adapter_version=f"old-{actor_id.hex}", retrieval_version="old-v1", created_at=now,
        )
        session.add(old_space)
        session.flush()
        active_pointer = session.scalar(select(CatalogActiveVectorSpace).where(CatalogActiveVectorSpace.pointer_key == "catalog"))
        assert active_pointer is not None
        active_pointer.vector_space_id = old_space.id
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session), now=lambda: now,
            commit=session.commit, rollback=session.rollback,
        )
        publication_id, _, _ = _publish(service, actor_id)
        space = session.scalar(select(CatalogVectorSpace).where(
            CatalogVectorSpace.embedding_model == "text-embedding-v4",
            CatalogVectorSpace.embedding_dimension == 1024,
            CatalogVectorSpace.adapter_version == "dashscope-text-embedding-v4-1024.v1",
            CatalogVectorSpace.retrieval_version == "retrieval-06-3-v1",
        ))
        if space is None:
            space = CatalogVectorSpace(
                id=uuid.uuid4(), embedding_model="text-embedding-v4", embedding_dimension=1024,
                adapter_version="dashscope-text-embedding-v4-1024.v1", retrieval_version="retrieval-06-3-v1", created_at=now,
            )
            session.add(space)
            session.flush()
        names = list(session.scalars(select(CatalogSearchName).where(CatalogSearchName.publication_id == publication_id)))
        manifest = [
            {"publication_id": str(name.publication_id), "name_id": str(name.id),
             "search_version_id": str(name.search_version_id), "name_kind": name.name_kind}
            for name in names
        ]
        snapshot_hash = hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        build = CatalogVectorSpaceBuild(
            id=uuid.uuid4(), vector_space_id=space.id, requested_by=str(actor_id),
            reason="activation tested frozen release", command_key=f"activation-build-{actor_id.hex}",
            retrieval_version="retrieval-06-3-v1", snapshot_manifest=manifest,
            snapshot_hash=snapshot_hash, expected_name_count=len(manifest), requested_at=now,
        )
        session.add(build)
        session.add_all([
            CatalogEmbeddingJob(
                id=uuid.uuid4(), publication_id=name.publication_id, name_id=name.id,
                vector_space_id=space.id, status="completed", attempt_count=1, max_attempts=5,
                not_before=now, lease_owner=None, leased_at=None, lease_expires_at=None,
                last_error_code=None, created_at=now, updated_at=now,
            ) for name in names
        ])
        build_id = build.id
        vector_space_id = space.id
        session.add_all([
            CatalogSearchEmbedding(
                id=uuid.uuid4(), publication_id=name.publication_id, name_id=name.id,
                vector_space_id=space.id, embedding=list(_vector()), status="ready", created_at=now,
            ) for name in names
        ])
        previous = session.scalar(select(CatalogActiveVectorSpace).where(CatalogActiveVectorSpace.pointer_key == "catalog"))
        assert previous is not None
        previous_id = previous.vector_space_id
        session.commit()

    with Session(test_engine) as session:
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session), now=lambda: now,
            commit=session.commit, rollback=session.rollback,
        )
        with pytest.raises(AdminPermissionDenied):
            service.activate_vector_space(
                actor_user_id=uuid.uuid4(), vector_space_id=vector_space_id, build_id=build_id,
                reason="unknown actor", command_key=f"activation-unknown-{actor_id.hex}",
                release_path=release_path,
            )
        with pytest.raises(CatalogVectorSpaceActivationConflict):
            service.activate_vector_space(
                actor_user_id=actor_id, vector_space_id=vector_space_id, build_id=build_id,
                reason="incomplete build", command_key=f"activation-incomplete-{actor_id.hex}",
                release_path=release_path,
            )
        pointer = session.scalar(select(CatalogActiveVectorSpace).where(CatalogActiveVectorSpace.pointer_key == "catalog"))
        assert pointer is not None and pointer.vector_space_id == previous_id
        session.rollback()

    provider = FakeEmbeddingProvider()
    worker = CatalogEmbeddingWorker(
        session_factory=lambda: Session(test_engine), provider=provider,
        worker_id="activation-worker", vector_space_id=vector_space_id, build_id=build_id, now=lambda: now,
    )
    assert worker.run_once() == "idle"
    assert provider.calls == []

    with Session(test_engine) as session:
        service = AdminService(
            repository=SqlAlchemyAdminRepository(session), now=lambda: now,
            commit=session.commit, rollback=session.rollback,
        )
        approval = service.activate_vector_space(
            actor_user_id=actor_id, vector_space_id=vector_space_id, build_id=build_id,
            reason="frozen release passed", command_key=f"activation-pg-{actor_id.hex}",
            release_path=release_path,
        )
        replay = service.activate_vector_space(
            actor_user_id=actor_id, vector_space_id=vector_space_id, build_id=build_id,
            reason="frozen release passed", command_key=f"activation-pg-{actor_id.hex}",
            release_path=release_path,
        )
        assert replay.id == approval.id
        pointer = session.scalar(select(CatalogActiveVectorSpace).where(CatalogActiveVectorSpace.pointer_key == "catalog"))
        assert pointer is not None and pointer.vector_space_id == vector_space_id
        assert pointer.vector_space_id != previous_id
        stored = session.scalar(select(CatalogVectorSpaceActivationApproval).where(CatalogVectorSpaceActivationApproval.id == approval.id))
        assert stored is not None and stored.build_id == build_id
        assert len(list(session.scalars(select(CatalogVectorSpaceActivationApproval).where(
            CatalogVectorSpaceActivationApproval.command_key == f"activation-pg-{actor_id.hex}"
        )))) == 1
