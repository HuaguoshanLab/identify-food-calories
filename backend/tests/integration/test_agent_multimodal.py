"""Real PostgreSQL checks for the minimal image lifecycle and tenant-safe upload surface."""

from __future__ import annotations

from io import BytesIO
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.agent.models import AgentImage, AgentVisionInvocation
from app.auth.api import get_authentication_service
from app.auth.models import AuthSession, User, UserRole
from app.auth.repository import SqlAlchemyAuthRepository
from app.auth.security import issue_access_token
from app.auth.service import AuthenticationService
from app.core.config import Settings, validate_test_database_configuration
from app.main import create_app


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SECRET = "agent-multimodal-test-secret-with-at-least-forty-eight-bytes"


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test",
        secret_key=SECRET,
        image_temporary_directory=tmp_path / "images",
        _env_file=None,
    )


def _user(session: Session, label: str) -> tuple[User, str]:
    now = datetime.now(UTC)
    user = User(
        id=uuid.uuid4(),
        email=f"multimodal-{label}-{uuid.uuid4().hex}@example.test",
        password_hash="argon2id-digest",
        role=UserRole.USER.value,
        is_active=True,
        email_verified_at=now,
        created_at=now,
        updated_at=now,
    )
    auth_session = AuthSession(
        id=uuid.uuid4(), user_id=user.id, family_id=uuid.uuid4(), created_at=now,
        last_seen_at=now, expires_at=now + timedelta(days=30),
    )
    session.add_all([user, auth_session])
    session.commit()
    token, _ = issue_access_token(
        secret_key=SECRET, user_id=user.id, role=UserRole.USER.value,
        issuer="food-agent-api", audience="food-agent-h5", issued_at=now, session_id=auth_session.id,
    )
    return user, token


def _jpeg() -> bytes:
    output = BytesIO()
    Image.new("RGB", (12, 8), color="red").save(output, format="JPEG")
    return output.getvalue()


def test_upload_ownership_and_deletion_erases_the_normalized_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    test_url = validate_test_database_configuration(settings)
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT, env=os.environ.copy(), check=True,
    )
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            owner, owner_token = _user(session, "owner")
            _other, other_token = _user(session, "other")
            authentication = AuthenticationService(
                repository=SqlAlchemyAuthRepository(session), secret_key=SECRET,
                issuer="food-agent-api", audience="food-agent-h5", commit=session.commit, rollback=session.rollback,
            )
            application = create_app(settings)
            application.dependency_overrides[get_authentication_service] = lambda: authentication
            with TestClient(application) as client:
                headers = {"Authorization": f"Bearer {owner_token}"}
                created = client.post("/api/v1/agent/threads", json={"input_text": "米饭"}, headers=headers)
                assert created.status_code == 201, created.text
                thread_id = created.json()["thread_id"]
                denied = client.post(
                    f"/api/v1/agent/threads/{thread_id}/images",
                    headers={"Authorization": f"Bearer {other_token}", "Idempotency-Key": "foreign-image"},
                    files={"image": ("meal.jpg", _jpeg(), "image/jpeg")},
                )
                assert denied.status_code == 404
                uploaded = client.post(
                    f"/api/v1/agent/threads/{thread_id}/images",
                    headers={**headers, "Idempotency-Key": "owner-image"},
                    files={"image": ("meal.jpg", _jpeg(), "image/jpeg")},
                )
                assert uploaded.status_code == 202, uploaded.text
                image_id = uuid.UUID(uploaded.json()["image_id"])
                repeated = client.post(
                    f"/api/v1/agent/threads/{thread_id}/images",
                    headers={**headers, "Idempotency-Key": "owner-image"},
                    files={"image": ("meal.jpg", _jpeg(), "image/jpeg")},
                )
                assert repeated.status_code == 202, repeated.text
                assert repeated.json()["image_id"] == str(image_id)

            session.expire_all()
            image = session.get(AgentImage, image_id)
            assert image is not None and image.user_id == owner.id
            assert image.status == "deleted" and image.deleted_at is not None
            assert not (tmp_path / "images" / image.locator).exists()
            invocation = session.query(AgentVisionInvocation).filter_by(image_id=image_id).one()
            assert invocation.user_id == owner.id
            assert invocation.status == "failed"
            assert session.query(AgentImage).filter_by(user_id=owner.id).count() == 1
            assert session.query(AgentVisionInvocation).filter_by(user_id=owner.id).count() == 1
            persisted_columns = set(AgentImage.__table__.columns.keys()) | set(AgentVisionInvocation.__table__.columns.keys())
            assert not {"base64", "exif", "original_filename", "public_url", "prompt", "raw_response"}.intersection(persisted_columns)
    finally:
        engine.dispose()
