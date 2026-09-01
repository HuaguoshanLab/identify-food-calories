"""Public PostgreSQL contract for owner-scoped, minimal planning profiles."""

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
PROFILE_PATH = "/api/v1/planning/profile"


def _settings() -> Settings:
    return Settings(
        app_env="test",
        database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:5432/food_agent_dev",
        test_database_url="postgresql+psycopg://postgres:postgres@127.0.0.1:55432/food_agent_test",
        secret_key="planning-profile-public-api-secret-with-at-least-forty-eight-bytes",
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
    email = f"planning-profile-public-{label}-{uuid.uuid4().hex}@example.test"
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


def _profile_payload() -> dict[str, object]:
    return {
        "height_cm": "170.0",
        "weight_kg": "65.0",
        "age_years": 30,
        "formula_variant": "mifflin_st_jeor_female",
        "activity_level": "moderate",
        "goal": "loss",
        "goal_speed": "gradual_loss",
    }


def test_planning_profile_public_crud_is_owner_scoped_minimal_and_soft_deleted() -> None:
    """A/B users only reach a profile through public auth, never a supplied user ID."""

    if os.environ.get("APP_ENV") != "test":
        return
    _prepare_database()
    httpx.delete("http://127.0.0.1:8025/api/v1/messages", timeout=2).raise_for_status()
    with TestClient(create_app(_settings()), base_url=FRONTEND_ORIGIN) as client_a, TestClient(
        create_app(_settings()), base_url=FRONTEND_ORIGIN
    ) as client_b:
        assert client_a.get(PROFILE_PATH).status_code == 401
        token_a = _register_verify_and_login(client_a, label="a")
        token_b = _register_verify_and_login(client_b, label="b")
        headers_a = {"Authorization": f"Bearer {token_a}", "Origin": FRONTEND_ORIGIN}
        headers_b = {"Authorization": f"Bearer {token_b}", "Origin": FRONTEND_ORIGIN}

        created = client_a.put(PROFILE_PATH, headers=headers_a, json=_profile_payload())
        assert created.status_code == 200, created.text
        assert created.json() == {
            "height_cm": "170.0",
            "weight_kg": "65.0",
            "age_years": 30,
            "formula_variant": "mifflin_st_jeor_female",
            "activity_level": "moderate",
            "goal": "loss",
            "goal_speed": "gradual_loss",
            "target_policy_version": "target-policy.v1",
            "formula_version": "mifflin-st-jeor.v1",
        }
        assert client_a.get(PROFILE_PATH, headers=headers_a).json() == created.json()

        for request in (
            lambda: client_b.get(PROFILE_PATH, headers=headers_b),
            lambda: client_b.patch(PROFILE_PATH, headers=headers_b, json={"goal": "gain"}),
            lambda: client_b.delete(PROFILE_PATH, headers=headers_b),
        ):
            assert request().status_code == 404

        updated = client_a.patch(PROFILE_PATH, headers=headers_a, json={"goal": "gain", "goal_speed": "gradual_gain"})
        assert updated.status_code == 200, updated.text
        assert updated.json()["goal"] == "gain"
        assert updated.json()["goal_speed"] == "gradual_gain"
        assert client_a.delete(PROFILE_PATH, headers=headers_a).status_code == 204
        assert client_a.get(PROFILE_PATH, headers=headers_a).status_code == 404
        assert client_a.patch(PROFILE_PATH, headers=headers_a, json={"goal": "loss"}).status_code == 404


def test_planning_profile_rejects_extra_preference_identity_and_policy_inputs_without_writing() -> None:
    """Closed request DTOs preserve the profile/memory boundary before persistence."""

    if os.environ.get("APP_ENV") != "test":
        return
    _prepare_database()
    httpx.delete("http://127.0.0.1:8025/api/v1/messages", timeout=2).raise_for_status()
    with TestClient(create_app(_settings()), base_url=FRONTEND_ORIGIN) as client:
        token = _register_verify_and_login(client, label="invalid")
        headers = {"Authorization": f"Bearer {token}", "Origin": FRONTEND_ORIGIN}
        invalid_payloads = (
            _profile_payload() | {"avoidances": ["spicy"]},
            _profile_payload() | {"taste_preferences": ["light"]},
            _profile_payload() | {"user_id": str(uuid.uuid4())},
            _profile_payload() | {"formula_variant": "guessed_formula"},
            _profile_payload() | {"goal_speed": "extreme_loss"},
        )
        for payload in invalid_payloads:
            rejected = client.put(PROFILE_PATH, headers=headers, json=payload)
            assert rejected.status_code == 422, rejected.text
            assert client.get(PROFILE_PATH, headers=headers).status_code == 404
