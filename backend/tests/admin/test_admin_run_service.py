"""RED contracts for safe, database-authoritative agent run administration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.admin.schemas import AdminRunDetailResponse, AdminRunMetricsResponse, AdminRunPageResponse
from app.admin.service import AdminPermissionDenied, AdminService
from app.auth.models import User, UserRole


NOW = datetime(2026, 9, 3, tzinfo=UTC)


def _user(*, role: str) -> User:
    return User(
        id=uuid.uuid4(), email="admin-run@example.com", password_hash="hash", role=role,
        is_active=True, email_verified_at=NOW, created_at=NOW, updated_at=NOW,
    )


class FakeRunRepository:
    def __init__(self, user: User) -> None:
        self.user = user
        self.metric_filters: dict[str, object] | None = None
        self.list_filters: dict[str, object] | None = None

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.user if user_id == self.user.id else None

    def run_metrics(self, **filters: object) -> AdminRunMetricsResponse:
        self.metric_filters = filters
        return AdminRunMetricsResponse(
            terminal_count=4, failure_ratio=Decimal("0.25"), p50_elapsed_ms=120,
            p95_elapsed_ms=250, total_cost_usd=Decimal("0.004200"), from_=filters["occurred_after"], to=filters["occurred_before"],
        )

    def list_runs(self, **filters: object) -> list[AdminRunDetailResponse]:
        self.list_filters = filters
        return [
            AdminRunDetailResponse(
                id=uuid.uuid4(), status="completed", graph_version="agent-v1",
                model_provider="deepseek", model_version="deepseek-v4-flash", graph_steps=3,
                model_calls=1, tool_calls=2, elapsed_ms=120, estimated_cost_usd=Decimal("0.001000"),
                failure_code=None, finished_at=NOW,
            )
        ]


def test_metrics_and_list_share_terminal_window_and_filters() -> None:
    admin = _user(role=UserRole.ADMIN.value)
    repository = FakeRunRepository(admin)
    service = AdminService(repository=repository, cursor_secret="test-secret", now=lambda: NOW)

    metrics = service.get_run_metrics(
        actor_user_id=admin.id, occurred_after=NOW, occurred_before=NOW,
        status="completed", graph_version="agent-v1", model="deepseek:deepseek-v4-flash",
        failure_node="tool", failure_code="TIMEOUT",
    )
    page = service.list_agent_runs(
        actor_user_id=admin.id, limit=1, cursor=None, occurred_after=NOW, occurred_before=NOW,
        status="completed", graph_version="agent-v1", model="deepseek:deepseek-v4-flash",
        failure_node="tool", failure_code="TIMEOUT",
    )

    assert metrics.terminal_count == 4
    assert metrics.from_ == NOW
    assert metrics.to == NOW
    assert isinstance(page, AdminRunPageResponse)
    assert repository.metric_filters == {k: v for k, v in repository.list_filters.items() if k != "limit" and k != "cursor_position"}


def test_run_reads_require_current_database_admin_role() -> None:
    user = _user(role=UserRole.USER.value)
    service = AdminService(repository=FakeRunRepository(user), cursor_secret="test-secret", now=lambda: NOW)

    with pytest.raises(AdminPermissionDenied):
        service.get_run_metrics(actor_user_id=user.id)


def test_metrics_default_window_is_server_owned_utc_24_hours() -> None:
    admin = _user(role=UserRole.ADMIN.value)
    repository = FakeRunRepository(admin)
    service = AdminService(repository=repository, cursor_secret="test-secret", now=lambda: NOW)

    metrics = service.get_run_metrics(actor_user_id=admin.id)

    assert metrics.from_ == NOW - timedelta(hours=24)
    assert metrics.to == NOW
    assert repository.metric_filters is not None
    assert repository.metric_filters["occurred_after"] == metrics.from_
    assert repository.metric_filters["occurred_before"] == metrics.to
