"""Password recovery behavior; service tests use deterministic in-memory ports."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.accounts.api import get_recovery_service
from app.accounts.repository import SqlAlchemyAccountRecoveryRepository
from app.auth.models import ChallengePurpose, User, UserRole, VerificationChallenge
from app.auth.models import AuthSession, RefreshToken
from app.auth.security import hash_password, password_matches
from app.accounts.service import (
    InvalidRecoveryCode,
    RecoveryCodeExpired,
    RecoveryContextInvalid,
    RecoveryService,
    ResendCooldown,
)
from app.core.config import Settings
from app.main import create_app


class FakeRecoveryRepository:
    def __init__(self) -> None:
        self.users: list[User] = []
        self.challenges: list[VerificationChallenge] = []
        self.revoked_user_ids: list[uuid.UUID] = []

    def get_user_by_email(self, normalized_email: str) -> User | None:
        return next((user for user in self.users if user.email == normalized_email), None)

    def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return next((user for user in self.users if user.id == user_id), None)

    def add_challenge(self, challenge: VerificationChallenge) -> VerificationChallenge:
        self.challenges.append(challenge)
        return challenge

    def get_current_challenge_for_update(
        self, *, context_digest: str, purpose: str
    ) -> VerificationChallenge | None:
        return next(
            (
                challenge
                for challenge in reversed(self.challenges)
                if challenge.context_digest == context_digest
                and challenge.purpose == purpose
                and challenge.consumed_at is None
                and challenge.invalidated_at is None
            ),
            None,
        )

    def get_current_challenge_for_user_for_update(
        self, *, user_id: uuid.UUID, purpose: str
    ) -> VerificationChallenge | None:
        return next(
            (
                challenge
                for challenge in reversed(self.challenges)
                if challenge.user_id == user_id
                and challenge.purpose == purpose
                and challenge.consumed_at is None
                and challenge.invalidated_at is None
            ),
            None,
        )

    def revoke_all_session_families(self, *, user_id: uuid.UUID, revoked_at: datetime) -> None:
        self.revoked_user_ids.append(user_id)


class FakeMailProvider:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, int]] = []

    def send_verification_code(
        self, *, recipient: str, code: str, expires_in_minutes: int
    ) -> None:
        self.messages.append((recipient, code, expires_in_minutes))


class MutableClock:
    def __init__(self) -> None:
        self.current = datetime(2026, 8, 27, 10, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.current

    def advance(self, **kwargs: int) -> None:
        self.current += timedelta(**kwargs)


def sequence(values: list[str]) -> Callable[[], str]:
    iterator: Iterator[str] = iter(values)
    return lambda: next(iterator)


@pytest.fixture
def recovery_protocol() -> tuple[
    RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
]:
    repository = FakeRecoveryRepository()
    clock = MutableClock()
    repository.users.append(
        User(
            id=uuid.uuid4(),
            email="mina@example.com",
            password_hash="$argon2id$placeholder",
            role=UserRole.USER.value,
            is_active=True,
            email_verified_at=clock.now(),
            created_at=clock.now(),
            updated_at=clock.now(),
        )
    )
    mail = FakeMailProvider()
    events: list[str] = []
    service = RecoveryService(
        repository=repository,
        session_family_revoker=repository,
        mail_provider=mail,
        secret_key="test-only-recovery-pepper-at-least-32-bytes",
        now=clock.now,
        code_factory=sequence(["123456", "654321", "222222"]),
        commit=lambda: events.append("commit"),
        rollback=lambda: events.append("rollback"),
    )
    return service, repository, mail, clock, events


def test_recovery_dispatch_uses_shared_digest_only_code_policy(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, repository, mail, clock, _ = recovery_protocol

    dispatch = service.request_reset(email="  Mina@Example.COM ")

    challenge = repository.challenges[0]
    assert challenge.purpose == ChallengePurpose.PASSWORD_RESET.value
    assert challenge.code_digest != "123456"
    assert challenge.context_digest != dispatch.context_token
    assert challenge.expires_at == clock.current + timedelta(minutes=10)
    assert challenge.resend_available_at == clock.current + timedelta(seconds=60)
    assert challenge.max_attempts == 5
    assert mail.messages == [("mina@example.com", "123456", 10)]
    assert "123456" not in repr(dispatch)


def test_unknown_account_keeps_non_enumerating_dispatch_shape(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, repository, mail, _, _ = recovery_protocol

    known = service.request_reset(email="mina@example.com")
    unknown = service.request_reset(email="not-a-user@example.com")

    assert known.__class__ is unknown.__class__
    assert len(repository.challenges) == 1
    assert len(mail.messages) == 1


def test_resend_invalidates_old_code_and_enforces_cooldown(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, repository, mail, clock, _ = recovery_protocol
    first = service.request_reset(email="mina@example.com")

    with pytest.raises(ResendCooldown) as error:
        service.resend(first.context_token)
    assert error.value.retry_after == 60

    clock.advance(seconds=61)
    second = service.resend(first.context_token)
    assert repository.challenges[0].invalidated_at == clock.current
    assert mail.messages[-1] == ("mina@example.com", "654321", 10)
    with pytest.raises(RecoveryContextInvalid):
        service.verify(context_token=first.context_token, code="123456")
    service.verify(context_token=second.context_token, code="654321")


def test_verify_and_reset_are_single_use_and_revoke_all_families(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, repository, _, _, events = recovery_protocol
    dispatch = service.request_reset(email="mina@example.com")

    service.verify(context_token=dispatch.context_token, code="123456")
    service.reset(
        context_token=dispatch.context_token,
        code="123456",
        new_password="a-new-correct-horse-battery",
    )

    assert repository.users[0].password_hash.startswith("$argon2id$")
    assert repository.users[0].password_hash != "a-new-correct-horse-battery"
    assert repository.challenges[0].consumed_at is not None
    assert repository.revoked_user_ids == [repository.users[0].id]
    assert events[-1] == "commit"
    with pytest.raises(RecoveryContextInvalid):
        service.reset(
            context_token=dispatch.context_token,
            code="123456",
            new_password="another-correct-horse-battery",
        )


def test_invalid_and_expired_codes_never_change_password(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, repository, _, clock, _ = recovery_protocol
    dispatch = service.request_reset(email="mina@example.com")
    original_hash = repository.users[0].password_hash

    with pytest.raises(InvalidRecoveryCode):
        service.reset(
            context_token=dispatch.context_token,
            code="000000",
            new_password="a-new-correct-horse-battery",
        )
    clock.advance(minutes=10)
    with pytest.raises(RecoveryCodeExpired):
        service.reset(
            context_token=dispatch.context_token,
            code="123456",
            new_password="a-new-correct-horse-battery",
        )
    assert repository.users[0].password_hash == original_hash


def test_reset_rolls_back_when_session_family_revoke_fails(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, repository, _, _, events = recovery_protocol
    dispatch = service.request_reset(email="mina@example.com")

    def fail_revoke(*, user_id: uuid.UUID, revoked_at: datetime) -> None:
        raise RuntimeError("database failure")

    repository.revoke_all_session_families = fail_revoke  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="database failure"):
        service.reset(
            context_token=dispatch.context_token,
            code="123456",
            new_password="a-new-correct-horse-battery",
        )
    assert events[-1] == "rollback"


def make_client(service: RecoveryService) -> TestClient:
    application = create_app(
        Settings(
            app_env="test",
            database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
            test_database_url=(
                "postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test"
            ),
            secret_key="test-only-recovery-pepper-at-least-32-bytes",
            cors_origins=["http://localhost:5173"],
            smtp_host="localhost",
            smtp_from_email="noreply@local.test",
            _env_file=None,
        )
    )
    application.dependency_overrides[get_recovery_service] = lambda: service
    return TestClient(application)


def test_recovery_api_uses_non_enumerating_202_and_httponly_context(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, _, _, _, _ = recovery_protocol
    client = make_client(service)

    known = client.post(
        "/api/v1/auth/password-recovery/forgot",
        json={"email": "mina@example.com"},
        headers={"Origin": "http://localhost:5173"},
    )
    unknown = client.post(
        "/api/v1/auth/password-recovery/forgot",
        json={"email": "not-a-user@example.com"},
        headers={"Origin": "http://localhost:5173"},
    )

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert known.json()["status"] == "RECOVERY_CODE_DISPATCH_ACCEPTED"
    assert "123456" not in known.text
    cookie = known.headers["set-cookie"]
    assert "password_recovery_context=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie


def test_recovery_api_verifies_then_resets_without_exposing_context(
    recovery_protocol: tuple[
        RecoveryService, FakeRecoveryRepository, FakeMailProvider, MutableClock, list[str]
    ],
) -> None:
    service, _, _, _, _ = recovery_protocol
    client = make_client(service)
    client.post(
        "/api/v1/auth/password-recovery/forgot",
        json={"email": "mina@example.com"},
        headers={"Origin": "http://localhost:5173"},
    )

    context = client.get("/api/v1/auth/password-recovery/context")
    verified = client.post(
        "/api/v1/auth/password-recovery/verify",
        json={"code": "123456"},
        headers={"Origin": "http://localhost:5173"},
    )
    reset = client.post(
        "/api/v1/auth/password-recovery/reset",
        json={"code": "123456", "new_password": "a-new-correct-horse-battery"},
        headers={"Origin": "http://localhost:5173"},
    )

    assert context.status_code == 200
    assert "context_token" not in context.text
    assert verified.json() == {"status": "RECOVERY_CODE_VERIFIED"}
    assert reset.json() == {
        "status": "PASSWORD_RESET",
        "message": "密码已更新，请重新登录。",
    }
    assert 'password_recovery_context=""' in reset.headers["set-cookie"]


REAL_NOW = datetime(2026, 8, 27, 11, 0, tzinfo=UTC)
REAL_SECRET = "recovery-postgres-secret-with-at-least-forty-eight-bytes"


def _seed_recovery_user(test_engine: Engine) -> tuple[uuid.UUID, list[uuid.UUID]]:
    user_id = uuid.uuid4()
    session_ids = [uuid.uuid4(), uuid.uuid4()]
    with Session(test_engine) as setup:
        setup.add(
            User(
                id=user_id,
                email=f"recovery-{uuid.uuid4().hex}@example.com",
                password_hash=hash_password("old-correct-horse-battery"),
                role=UserRole.USER.value,
                is_active=True,
                email_verified_at=REAL_NOW,
                created_at=REAL_NOW,
                updated_at=REAL_NOW,
            )
        )
        for session_id in session_ids:
            setup.add(
                AuthSession(
                    id=session_id,
                    user_id=user_id,
                    family_id=uuid.uuid4(),
                    created_at=REAL_NOW,
                    last_seen_at=REAL_NOW,
                    expires_at=REAL_NOW + timedelta(days=30),
                    revoked_at=None,
                    device_label=None,
                )
            )
            setup.add(
                RefreshToken(
                    id=uuid.uuid4(),
                    session_id=session_id,
                    token_digest=uuid.uuid4().hex,
                    issued_at=REAL_NOW,
                    expires_at=REAL_NOW + timedelta(days=30),
                    consumed_at=None,
                    replaced_by_id=None,
                    revoked_at=None,
                )
            )
        setup.commit()
    return user_id, session_ids


def _real_service(
    session: Session,
    *,
    code: str = "314159",
    session_family_revoker: object | None = None,
) -> RecoveryService:
    repository = SqlAlchemyAccountRecoveryRepository(session)
    return RecoveryService(
        repository=repository,
        session_family_revoker=(
            session_family_revoker
            if session_family_revoker is not None
            else repository
        ),
        mail_provider=FakeMailProvider(),
        secret_key=REAL_SECRET,
        now=lambda: REAL_NOW,
        code_factory=lambda: code,
        commit=session.commit,
        rollback=session.rollback,
    )


def _delete_recovery_user(test_engine: Engine, user_id: uuid.UUID) -> None:
    with Session(test_engine) as cleanup:
        user = cleanup.get(User, user_id)
        if user is not None:
            cleanup.delete(user)
            cleanup.commit()


def test_two_real_postgres_transactions_consume_recovery_challenge_once(
    test_engine: Engine,
) -> None:
    """A row lock, rather than timing, proves one reset winner under PostgreSQL."""

    assert test_engine.url.drivername == "postgresql+psycopg"
    user_id, session_ids = _seed_recovery_user(test_engine)
    try:
        with Session(test_engine) as dispatch_session:
            service = _real_service(dispatch_session)
            user = dispatch_session.get(User, user_id)
            assert user is not None
            dispatch = service.request_reset(email=user.email)

        barrier = Barrier(2)

        def reset_once() -> str:
            with Session(test_engine) as session:
                service = _real_service(session)
                barrier.wait()
                try:
                    service.reset(
                        context_token=dispatch.context_token,
                        code="314159",
                        new_password="new-correct-horse-battery",
                    )
                    return "reset"
                except RecoveryContextInvalid:
                    return "already-consumed"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _index: reset_once(), range(2)))
        assert Counter(outcomes) == {"reset": 1, "already-consumed": 1}

        with Session(test_engine) as inspection:
            challenge = inspection.scalar(
                select(VerificationChallenge).where(
                    VerificationChallenge.user_id == user_id,
                    VerificationChallenge.purpose == ChallengePurpose.PASSWORD_RESET.value,
                )
            )
            user = inspection.get(User, user_id)
            sessions = list(
                inspection.scalars(select(AuthSession).where(AuthSession.id.in_(session_ids)))
            )
            refreshes = list(
                inspection.scalars(
                    select(RefreshToken).where(RefreshToken.session_id.in_(session_ids))
                )
            )
            assert challenge is not None and challenge.consumed_at == REAL_NOW
            assert user is not None and password_matches(
                password="new-correct-horse-battery", password_hash=user.password_hash
            )
            assert all(auth_session.revoked_at == REAL_NOW for auth_session in sessions)
            assert all(refresh.revoked_at == REAL_NOW for refresh in refreshes)
    finally:
        _delete_recovery_user(test_engine, user_id)


def test_real_postgres_reset_rolls_back_password_challenge_and_families(
    test_engine: Engine,
) -> None:
    user_id, session_ids = _seed_recovery_user(test_engine)
    try:
        with Session(test_engine) as dispatch_session:
            service = _real_service(dispatch_session)
            user = dispatch_session.get(User, user_id)
            assert user is not None
            dispatch = service.request_reset(email=user.email)

        with Session(test_engine) as reset_session:
            repository = SqlAlchemyAccountRecoveryRepository(reset_session)

            class FailingRevoker:
                def revoke_all_session_families(
                    self, *, user_id: uuid.UUID, revoked_at: datetime
                ) -> None:
                    repository.revoke_all_session_families(
                        user_id=user_id, revoked_at=revoked_at
                    )
                    raise RuntimeError("injected family revoke failure")

            with pytest.raises(RuntimeError, match="injected family revoke failure"):
                _real_service(
                    reset_session, session_family_revoker=FailingRevoker()
                ).reset(
                    context_token=dispatch.context_token,
                    code="314159",
                    new_password="new-correct-horse-battery",
                )

        with Session(test_engine) as inspection:
            user = inspection.get(User, user_id)
            challenge = inspection.scalar(
                select(VerificationChallenge).where(
                    VerificationChallenge.user_id == user_id,
                    VerificationChallenge.purpose == ChallengePurpose.PASSWORD_RESET.value,
                )
            )
            sessions = list(
                inspection.scalars(select(AuthSession).where(AuthSession.id.in_(session_ids)))
            )
            assert user is not None and password_matches(
                password="old-correct-horse-battery", password_hash=user.password_hash
            )
            assert challenge is not None and challenge.consumed_at is None
            assert all(auth_session.revoked_at is None for auth_session in sessions)
    finally:
        _delete_recovery_user(test_engine, user_id)


def test_real_api_sends_recovery_code_to_local_mailpit(db_session: Session) -> None:
    """The browser never receives a code; Mailpit receives it through the SMTP adapter."""

    recipient = f"mailpit-recovery-{uuid.uuid4().hex}@example.com"
    db_session.add(
        User(
            id=uuid.uuid4(),
            email=recipient,
            password_hash=hash_password("old-correct-horse-battery"),
            role=UserRole.USER.value,
            is_active=True,
            email_verified_at=REAL_NOW,
            created_at=REAL_NOW,
            updated_at=REAL_NOW,
        )
    )
    db_session.commit()
    repository = SqlAlchemyAccountRecoveryRepository(db_session)
    from app.notifications.smtp import SMTPMailProvider

    service = RecoveryService(
        repository=repository,
        session_family_revoker=repository,
        mail_provider=SMTPMailProvider(
            host="localhost", port=1025, from_email="noreply@local.test"
        ),
        secret_key=REAL_SECRET,
        code_factory=lambda: "271828",
        commit=db_session.commit,
        rollback=db_session.rollback,
    )
    client = make_client(service)

    response = client.post(
        "/api/v1/auth/password-recovery/forgot",
        json={"email": recipient},
        headers={"Origin": "http://localhost:5173"},
    )

    assert response.status_code == 202
    assert "271828" not in response.text
    messages = httpx.get("http://localhost:8025/api/v1/messages", timeout=5).json()[
        "messages"
    ]
    matching = [
        message
        for message in messages
        if any(address["Address"] == recipient for address in message["To"])
    ]
    assert matching
    delivered = httpx.get(
        f"http://localhost:8025/api/v1/message/{matching[0]['ID']}", timeout=5
    ).json()
    assert "271828" in delivered["Text"]
