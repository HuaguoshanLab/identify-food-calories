"""Real-PostgreSQL evidence for database-authoritative admin RBAC and audit state."""

from __future__ import annotations

import uuid
from contextlib import nullcontext
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect, select, update
from sqlalchemy.orm import Session

from app.admin.api import get_admin_service
from app.admin.cli import main as admin_cli
from app.admin.models import AdminRoleAudit
from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.service import AdminService
from app.auth.api import get_authentication_service
from app.auth.models import AuthSession, User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import issue_access_token, password_matches
from app.auth.service import AuthenticationService
from app.core.config import Settings
from app.main import create_app
from scripts.bootstrap_local_admin import (
    LOCAL_BOOTSTRAP_ADMIN_EMAIL,
    LOCAL_BOOTSTRAP_REASON,
    ensure_local_admin,
)


SECRET = "admin-audit-test-secret-with-at-least-forty-eight-bytes"
ISSUER = "food-agent-api"
AUDIENCE = "food-agent-h5"


@pytest.fixture(autouse=True)
def isolate_existing_admins(db_session: Session):
    # Bootstrap is defined relative to an empty admin population; rollback restores
    # unrelated fixtures instead of relying on a previous suite leaving no admins.
    db_session.execute(update(User).where(User.role == UserRole.ADMIN.value).values(is_active=False))


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        secret_key=SECRET,
        _env_file=None,
    )


def _user(*, role: str, is_active: bool = True, verified: bool = True) -> User:
    now = datetime.now(UTC)
    return User(
        id=uuid.uuid4(),
        email=f"admin-audit-{uuid.uuid4().hex}@example.com",
        password_hash="argon2id-digest",
        role=role,
        is_active=is_active,
        email_verified_at=now if verified else None,
        created_at=now,
        updated_at=now,
    )


def _session(*, user: User) -> AuthSession:
    now = datetime.now(UTC)
    return AuthSession(
        id=uuid.uuid4(),
        user_id=user.id,
        family_id=uuid.uuid4(),
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=30),
    )


def _token(*, user: User, session: AuthSession, claimed_role: str) -> str:
    token, _ = issue_access_token(
        secret_key=SECRET,
        user_id=user.id,
        role=claimed_role,
        issuer=ISSUER,
        audience=AUDIENCE,
        issued_at=datetime.now(UTC),
        session_id=session.id,
    )
    return token


def _client(db_session: Session) -> TestClient:
    application = create_app(_settings())
    auth_service = AuthenticationService(
        repository=SqlAlchemyAuthRepository(db_session),
        secret_key=SECRET,
        issuer=ISSUER,
        audience=AUDIENCE,
        commit=db_session.commit,
        rollback=db_session.rollback,
    )
    admin_service = AdminService(
        repository=SqlAlchemyAdminRepository(db_session),
        commit=db_session.commit,
        rollback=db_session.rollback,
    )
    application.dependency_overrides[get_authentication_service] = lambda: auth_service
    application.dependency_overrides[get_admin_service] = lambda: admin_service
    return TestClient(application)


def test_admin_migration_and_probe_reloads_authoritative_active_role(
    db_session: Session,
) -> None:
    assert "admin_role_audit" in inspect(db_session.bind).get_table_names()  # type: ignore[arg-type]

    regular_user = _user(role=UserRole.USER.value)
    administrator = _user(role=UserRole.ADMIN.value)
    inactive_administrator = _user(role=UserRole.ADMIN.value, is_active=False)
    regular_session = _session(user=regular_user)
    admin_session = _session(user=administrator)
    inactive_session = _session(user=inactive_administrator)
    db_session.add_all(
        [
            regular_user,
            administrator,
            inactive_administrator,
            regular_session,
            admin_session,
            inactive_session,
        ]
    )
    db_session.commit()
    client = _client(db_session)

    forged_admin_claim = _token(
        user=regular_user,
        session=regular_session,
        claimed_role=UserRole.ADMIN.value,
    )
    assert client.get(
        "/api/v1/admin/probe", headers={"Authorization": f"Bearer {forged_admin_claim}"}
    ).status_code == 403

    admin_token = _token(
        user=administrator,
        session=admin_session,
        claimed_role=UserRole.USER.value,
    )
    assert client.get(
        "/api/v1/admin/probe", headers={"Authorization": f"Bearer {admin_token}"}
    ).status_code == 200

    inactive_token = _token(
        user=inactive_administrator,
        session=inactive_session,
        claimed_role=UserRole.ADMIN.value,
    )
    assert client.get(
        "/api/v1/admin/probe", headers={"Authorization": f"Bearer {inactive_token}"}
    ).status_code == 403

    regular_user.role = UserRole.ADMIN.value
    db_session.commit()
    assert client.get(
        "/api/v1/admin/probe", headers={"Authorization": f"Bearer {forged_admin_claim}"}
    ).status_code == 200

    regular_user.role = UserRole.USER.value
    db_session.commit()
    assert client.get(
        "/api/v1/admin/probe", headers={"Authorization": f"Bearer {forged_admin_claim}"}
    ).status_code == 403


def test_public_user_management_demotes_immediately_without_revoking_user_session(db_session: Session) -> None:
    actor = _user(role=UserRole.ADMIN.value)
    target = _user(role=UserRole.ADMIN.value)
    actor_session = _session(user=actor)
    target_session = _session(user=target)
    db_session.add_all([actor, target, actor_session, target_session])
    db_session.commit()
    client = _client(db_session)
    actor_token = _token(user=actor, session=actor_session, claimed_role=UserRole.ADMIN.value)
    target_token = _token(user=target, session=target_session, claimed_role=UserRole.ADMIN.value)

    listed = client.get("/api/v1/admin/users?role=admin", headers={"Authorization": f"Bearer {actor_token}"})
    assert listed.status_code == 200
    assert {item["email"] for item in listed.json()["items"]} >= {actor.email, target.email}

    changed = client.patch(
        f"/api/v1/admin/users/{target.id}/role",
        headers={"Authorization": f"Bearer {actor_token}", "Idempotency-Key": "integration-role-command-0001"},
        json={"role": "user", "reason": "职责调整", "confirm": True},
    )
    assert changed.status_code == 200
    assert client.get("/api/v1/admin/probe", headers={"Authorization": f"Bearer {target_token}"}).status_code == 403
    me = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {target_token}"})
    assert me.status_code == 200 and me.json()["role"] == "user"
    assert db_session.get(AuthSession, target_session.id) is not None


def test_first_admin_bootstrap_changes_role_and_audits_in_one_commit(
    db_session: Session,
) -> None:
    target = _user(role=UserRole.USER.value)
    db_session.add(target)
    db_session.commit()
    service = AdminService(
        repository=SqlAlchemyAdminRepository(db_session),
        commit=db_session.commit,
        rollback=db_session.rollback,
    )

    audit = service.bootstrap_first_admin(
        target_user_id=target.id,
        reason="initial production administrator",
    )

    persisted = db_session.scalar(
        select(AdminRoleAudit).where(AdminRoleAudit.id == audit.id)
    )
    assert persisted is not None
    assert target.role == UserRole.ADMIN.value
    assert persisted.actor_identifier == "system:bootstrap"
    assert persisted.target_user_id == target.id
    assert persisted.before_role == UserRole.USER.value
    assert persisted.after_role == UserRole.ADMIN.value
    assert persisted.occurred_at.tzinfo is not None
    assert persisted.reason == "initial production administrator"


def test_local_admin_bootstrap_creates_audited_fixed_account_once(
    db_session: Session,
) -> None:
    created = ensure_local_admin(
        db_session,
        email=LOCAL_BOOTSTRAP_ADMIN_EMAIL,
        password="local-bootstrap-password",
    )

    user = db_session.scalar(select(User).where(User.email == LOCAL_BOOTSTRAP_ADMIN_EMAIL))
    assert user is not None
    audit = db_session.scalar(
        select(AdminRoleAudit).where(AdminRoleAudit.target_user_id == user.id)
    )
    assert created is True
    assert user.role == UserRole.ADMIN.value
    assert user.is_active is True
    assert user.email_verified_at is not None
    assert password_matches(password="local-bootstrap-password", password_hash=user.password_hash)
    assert audit is not None
    assert audit.actor_identifier == "system:bootstrap"
    assert audit.reason == LOCAL_BOOTSTRAP_REASON
    assert ensure_local_admin(
        db_session,
        email=LOCAL_BOOTSTRAP_ADMIN_EMAIL,
        password="different-local-bootstrap-password",
    ) is False


def test_admin_cli_requires_explicit_reason_and_verified_active_admin_actor(
    db_session: Session,
) -> None:
    first_target = _user(role=UserRole.USER.value)
    second_target = _user(role=UserRole.USER.value)
    rejected_target = _user(role=UserRole.USER.value)
    non_admin_actor = _user(role=UserRole.USER.value)
    inactive_admin_actor = _user(role=UserRole.ADMIN.value, is_active=False)
    unverified_admin_actor = _user(role=UserRole.ADMIN.value, verified=False)
    db_session.add_all(
        [
            first_target,
            second_target,
            rejected_target,
            non_admin_actor,
            inactive_admin_actor,
        ]
    )
    db_session.commit()
    def session_factory() -> object:
        return nullcontext(db_session)

    assert admin_cli(
        [
            "bootstrap",
            "--email",
            first_target.email,
            "--reason",
            "initial production administrator",
        ],
        session_factory=session_factory,
    ) == 0
    db_session.add(unverified_admin_actor)
    db_session.commit()
    assert admin_cli(
        [
            "promote",
            "--actor-email",
            first_target.email,
            "--email",
            second_target.email,
            "--reason",
            "delegated operational access",
        ],
        session_factory=session_factory,
    ) == 0

    events = list(
        db_session.scalars(
            select(AdminRoleAudit).where(AdminRoleAudit.target_user_id.in_((first_target.id, second_target.id))).order_by(AdminRoleAudit.occurred_at, AdminRoleAudit.id)
        )
    )
    assert [(event.actor_identifier, event.target_user_id) for event in events] == [
        ("system:bootstrap", first_target.id),
        (str(first_target.id), second_target.id),
    ]
    assert all(event.before_role == UserRole.USER.value for event in events)
    assert all(event.after_role == UserRole.ADMIN.value for event in events)
    assert all(event.reason for event in events)
    assert all(event.occurred_at.tzinfo is not None for event in events)

    before_failures = len(list(db_session.scalars(select(AdminRoleAudit))))
    assert admin_cli(
        [
            "bootstrap",
            "--email",
            non_admin_actor.email,
            "--reason",
            "a second bootstrap is forbidden",
        ],
        session_factory=session_factory,
    ) == 2
    assert admin_cli(
        [
            "promote",
            "--actor-email",
            non_admin_actor.email,
            "--email", rejected_target.email,
            "--reason",
            "non-admin actors are forbidden",
        ],
        session_factory=session_factory,
    ) == 2
    assert admin_cli(
        [
            "promote",
            "--actor-email",
            inactive_admin_actor.email,
            "--email", rejected_target.email,
            "--reason",
            "inactive admins are forbidden",
        ],
        session_factory=session_factory,
    ) == 2
    assert admin_cli(
        [
            "promote",
            "--actor-email",
            unverified_admin_actor.email,
            "--email", rejected_target.email,
            "--reason",
            "unverified admins are forbidden",
        ],
        session_factory=session_factory,
    ) == 2
    assert admin_cli(
        [
            "promote",
            "--actor-email",
            non_admin_actor.email,
            "--email",
            non_admin_actor.email,
            "--reason",
            "self promotion is forbidden",
        ],
        session_factory=session_factory,
    ) == 2
    assert admin_cli(
        [
            "promote",
            "--actor-email",
            first_target.email,
            "--email",
            non_admin_actor.email,
            "--reason",
            "   ",
        ],
        session_factory=session_factory,
    ) == 2
    assert len(list(db_session.scalars(select(AdminRoleAudit)))) == before_failures
    assert non_admin_actor.role == UserRole.USER.value
    assert rejected_target.role == UserRole.USER.value


def test_vector_build_cli_uses_database_admin_and_replays_idempotently(
    db_session: Session, capsys: pytest.CaptureFixture[str]
) -> None:
    administrator = _user(role=UserRole.ADMIN.value)
    regular_user = _user(role=UserRole.USER.value)
    db_session.add_all([administrator, regular_user])
    db_session.commit()

    def session_factory() -> object:
        return nullcontext(db_session)

    from tests.integration.test_hybrid_food_search import _publish, _index_name
    publication = _publish(db_session, canonical_name="CLI 测试菜", aliases=["CLI 测试菜"])
    _index_name(db_session, publication, "cli 测试菜")

    command = [
        "vector-build",
        "--actor-user-id",
        str(administrator.id),
        "--reason",
        "isolated E2E vector-space preparation",
        "--idempotency-key",
        "e2e-vector-build-cli-0001",
    ]
    assert admin_cli(command, session_factory=session_factory) == 0
    first = capsys.readouterr().out.strip().split()
    assert len(first) == 2
    assert admin_cli(command, session_factory=session_factory) == 0
    assert capsys.readouterr().out.strip().split() == first

    email_command = [
        "vector-build",
        "--actor-email",
        administrator.email,
        "--reason",
        "isolated E2E vector-space preparation by audited email lookup",
        "--idempotency-key",
        "e2e-vector-build-cli-email-0001",
    ]
    assert admin_cli(email_command, session_factory=session_factory) == 0
    assert len(capsys.readouterr().out.strip().split()) == 2

    assert admin_cli(
        [
            "vector-build",
            "--actor-email",
            regular_user.email,
            "--reason",
            "regular user is forbidden",
            "--idempotency-key",
            "e2e-vector-build-cli-email-denied-0001",
        ],
        session_factory=session_factory,
    ) == 2


def test_role_and_audit_roll_back_together_when_persistence_commit_fails(
    db_session: Session,
) -> None:
    target = _user(role=UserRole.USER.value)
    db_session.add(target)
    db_session.commit()
    service = AdminService(
        repository=SqlAlchemyAdminRepository(db_session),
        commit=lambda: (_ for _ in ()).throw(RuntimeError("simulated commit failure")),
        rollback=db_session.rollback,
    )

    with pytest.raises(RuntimeError, match="simulated commit failure"):
        service.bootstrap_first_admin(
            target_user_id=target.id,
            reason="commit failure must not leave an audit orphan",
        )

    db_session.expire_all()
    reloaded = db_session.get(User, target.id)
    assert reloaded is not None
    assert reloaded.role == UserRole.USER.value
    assert db_session.scalar(
        select(AdminRoleAudit).where(AdminRoleAudit.target_user_id == target.id)
    ) is None
