"""Public registration-to-memory contract; no forged identity or seeded account is allowed."""

from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import uuid
from pathlib import Path

import httpx
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app


BACKEND_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ORIGIN = "http://127.0.0.1:5178"


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:55432/food_agent_test",
        secret_key="direct-memory-public-api-secret-with-at-least-forty-eight-bytes",
        cors_origins=[FRONTEND_ORIGIN],
        smtp_host="127.0.0.1",
        smtp_port=1025,
        smtp_from_email="noreply@local.test",
        _env_file=None,
    )


def _prepare_database() -> None:
    subprocess.run(
        [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"],
        cwd=BACKEND_ROOT,
        env=os.environ.copy(),
        check=True,
    )


def _mailpit_code(*, email: str) -> str:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        messages = httpx.get("http://127.0.0.1:8025/api/v1/messages", timeout=2).json().get("messages", [])
        matching = next(
            (
                message
                for message in messages
                if any(address.get("Address", "").casefold() == email.casefold() for address in message.get("To", []))
            ),
            None,
        )
        if matching is not None:
            body = httpx.get(
                f"http://127.0.0.1:8025/api/v1/message/{matching['ID']}", timeout=2
            ).json().get("Text", "")
            code = re.search(r"\b(\d{6})\b", body)
            if code is not None:
                return code.group(1)
        time.sleep(0.05)
    raise AssertionError("Mailpit did not deliver a registration code")


def _register_verify_and_login(client: TestClient, *, label: str) -> str:
    email = f"direct-memory-public-{label}-{uuid.uuid4().hex}@example.test"
    password = "correct-horse-battery-staple"
    registered = client.post(
        "/api/v1/auth/register",
        headers={"Origin": FRONTEND_ORIGIN},
        json={"email": email, "password": password},
    )
    assert registered.status_code == 202, registered.text
    verified = client.post(
        "/api/v1/auth/register/verify",
        headers={"Origin": FRONTEND_ORIGIN},
        json={"code": _mailpit_code(email=email)},
    )
    assert verified.status_code == 200, verified.text
    logged_in = client.post(
        "/api/v1/auth/login",
        headers={"Origin": FRONTEND_ORIGIN},
        json={"email": email, "password": password},
    )
    assert logged_in.status_code == 200, logged_in.text
    return str(logged_in.json()["access_token"])


def test_public_registration_mailpit_login_and_memory_tenant_boundary() -> None:
    """A/B identity comes only from public cookies and login-issued Bearer tokens."""

    if os.environ.get("APP_ENV") != "test":
        return
    _prepare_database()
    httpx.delete("http://127.0.0.1:8025/api/v1/messages", timeout=2).raise_for_status()
    with TestClient(create_app(_settings()), base_url=FRONTEND_ORIGIN) as client_a, TestClient(
        create_app(_settings()), base_url=FRONTEND_ORIGIN
    ) as client_b:
        preflight = client_a.options(
            "/api/v1/memories",
            headers={"Origin": FRONTEND_ORIGIN, "Access-Control-Request-Method": "GET"},
        )
        assert preflight.headers["access-control-allow-origin"] == FRONTEND_ORIGIN
        token_a = _register_verify_and_login(client_a, label="a")
        token_b = _register_verify_and_login(client_b, label="b")
        headers_a = {"Authorization": f"Bearer {token_a}", "Origin": FRONTEND_ORIGIN}
        headers_b = {"Authorization": f"Bearer {token_b}", "Origin": FRONTEND_ORIGIN}

        analyzed = client_a.post(
            "/api/v1/agent/threads",
            headers=headers_a,
            json={"input_text": "米饭 100 克，我不吃辣"},
        )
        assert analyzed.status_code == 201, analyzed.text
        memories = client_a.get("/api/v1/memories", headers=headers_a)
        assert memories.status_code == 200, memories.text
        assert len(memories.json()) == 1
        memory = memories.json()[0]
        assert memory["category"] == "avoidance"
        assert memory["canonical_text"] == "不吃辣"
        assert memory["source_kind"] == "user_statement"
        assert set(memory) == {"id", "category", "canonical_text", "source_kind", "created_at", "updated_at"}

        memory_id = memory["id"]
        assert client_b.get(f"/api/v1/memories/{memory_id}", headers=headers_b).status_code == 404
        assert client_b.patch(
            f"/api/v1/memories/{memory_id}", headers=headers_b, json={"canonical_text": "不吃辣"}
        ).status_code == 404
        assert client_b.delete(f"/api/v1/memories/{memory_id}", headers=headers_b).status_code == 404
        assert client_a.get("/api/v1/memories", headers=headers_a).json()[0]["canonical_text"] == "不吃辣"

        updated = client_a.patch(
            f"/api/v1/memories/{memory_id}", headers=headers_a, json={"canonical_text": "不吃微辣"}
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["source_kind"] == "user_maintained"
        deleted = client_a.delete(f"/api/v1/memories/{memory_id}", headers=headers_a)
        assert deleted.status_code == 204, deleted.text
        assert client_a.get("/api/v1/memories", headers=headers_a).json() == []

        after_delete = client_a.post(
            "/api/v1/agent/threads", headers=headers_a, json={"input_text": "米饭 100 克"}
        )
        assert after_delete.status_code == 201, after_delete.text
        assert after_delete.json()["report"]["context_references"] == []
