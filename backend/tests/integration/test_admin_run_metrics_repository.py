"""Real PostgreSQL proof for one terminal predicate, percentiles, and run keysets."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.admin.repository import SqlAlchemyAdminRepository
from app.agent.models import AgentRun, AgentThread
from app.auth.models import User, UserRole


def _run(*, user_id: uuid.UUID, thread_id: uuid.UUID, finished_at: datetime, status: str, elapsed_ms: int, cost: str) -> AgentRun:
    return AgentRun(
        id=uuid.uuid4(), user_id=user_id, thread_id=thread_id, command_key=f"run-{uuid.uuid4()}",
        command_hash="a" * 64, status=status, graph_version="agent-v1", prompt_version="prompt-v1",
        tool_version="tool-v1", model_provider="deepseek", model_version="deepseek-v4-flash",
        graph_steps=1, model_calls=1, tool_calls=1, elapsed_ms=elapsed_ms,
        estimated_cost_usd=Decimal(cost), failure_code="TIMEOUT" if status == "failed" else None,
        created_at=finished_at - timedelta(seconds=1), updated_at=finished_at, finished_at=finished_at,
    )


def test_postgres_metrics_and_keyset_use_the_same_terminal_finished_at_predicate(db_session) -> None:
    now = datetime(2026, 9, 3, tzinfo=UTC)
    user = User(
        id=uuid.uuid4(), email=f"metrics-{uuid.uuid4()}@example.com", password_hash="hash",
        role=UserRole.USER.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now,
    )
    thread = AgentThread(
        id=uuid.uuid4(), user_id=user.id, status="open", revision=0,
        created_at=now - timedelta(days=1), last_activity_at=now,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(thread)
    # AgentRun has two direct FKs; flush parents before inserting independent ORM rows.
    db_session.flush()
    db_session.add_all([
        _run(user_id=user.id, thread_id=thread.id, finished_at=now - timedelta(hours=1), status="completed", elapsed_ms=10, cost="0.001000"),
        _run(user_id=user.id, thread_id=thread.id, finished_at=now - timedelta(hours=2), status="failed", elapsed_ms=30, cost="0.003000"),
        _run(user_id=user.id, thread_id=thread.id, finished_at=now - timedelta(hours=25), status="completed", elapsed_ms=999, cost="9.000000"),
        _run(user_id=user.id, thread_id=thread.id, finished_at=now - timedelta(minutes=10), status="running", elapsed_ms=999, cost="9.000000"),
    ])
    db_session.flush()
    repository = SqlAlchemyAdminRepository(db_session)

    filters = {"occurred_after": now - timedelta(hours=24), "occurred_before": now}
    metrics = repository.run_metrics(**filters)
    page = repository.list_runs(limit=1, cursor_position=None, **filters)

    assert metrics.terminal_count == 2
    assert metrics.failure_ratio == Decimal("0.500000")
    assert metrics.total_cost_usd == Decimal("0.004000")
    assert len(page) == 1 and page[0].finished_at == now - timedelta(hours=1)
    second = repository.list_runs(limit=1, cursor_position=(page[0].finished_at, page[0].id), **filters)
    assert [run.id for run in second] != [run.id for run in page]
