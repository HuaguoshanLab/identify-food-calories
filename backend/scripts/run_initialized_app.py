"""Prepare the isolated test database in a fixed order, then start FastAPI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

from sqlalchemy import create_engine, text

from app.core.config import Settings, validate_test_database_configuration


class InitializationStepError(RuntimeError):
    """Expose a stable startup failure without leaking child command arguments."""


def guarded_test_target() -> str:
    """Resolve the only URL that destructive test startup steps may consume."""

    # Pydantic Settings accepts _env_file at runtime; the local mypy setup lacks its plugin.
    return validate_test_database_configuration(Settings(_env_file=None))  # type: ignore[call-arg]


def reset_test_schema(database_url: str) -> None:
    """Clear only the target already approved by the configuration guard."""

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DROP SCHEMA public CASCADE"))
            connection.execute(text("CREATE SCHEMA public"))
    finally:
        engine.dispose()


def _run_for_test_target(command: list[str], database_url: str) -> None:
    """Pass the protected target explicitly without rewriting DATABASE_URL."""

    environment = os.environ.copy()
    environment["TEST_DATABASE_URL"] = database_url
    try:
        subprocess.run(command, check=True, env=environment)
    except subprocess.CalledProcessError:
        # CalledProcessError renders its command, which would expose a URL password.
        raise InitializationStepError("an initialization step failed") from None


def upgrade_alembic(database_url: str) -> None:
    _run_for_test_target([sys.executable, "-m", "alembic", "upgrade", "head"], database_url)


def setup_checkpointer(database_url: str) -> None:
    _run_for_test_target(
        [sys.executable, "scripts/setup_checkpointer.py", "--database-url", database_url],
        database_url,
    )


def apply_seed(database_url: str) -> None:
    for manifest_path in (
        "app/nutrition/data/fdc-seed-v1.json",
        "app/nutrition/data/fdc-seed-v1-rice-fist-v1.json",
        "app/nutrition/data/chili-fried-pork-reference-v2.json",
    ):
        _run_for_test_target(
            [
                sys.executable,
                "-m",
                "app.nutrition.importer",
                "--apply",
                manifest_path,
                "--database-url",
                database_url,
            ],
            database_url,
        )
    _run_for_test_target(
        [
            sys.executable,
            "-m",
            "app.planning.importer",
            "--apply",
            "app/planning/data/controlled-recipes.v1.json",
            "--database-url",
            database_url,
        ],
        database_url,
    )


def launch_uvicorn(_database_url: str, host: str, port: int) -> None:
    """Replace this process so Playwright owns the application lifecycle."""

    os.execvpe(
        sys.executable,
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            host,
            "--port",
            str(port),
        ],
        os.environ.copy(),
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare-only", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    database_url = guarded_test_target()
    reset_test_schema(database_url)
    upgrade_alembic(database_url)
    setup_checkpointer(database_url)
    apply_seed(database_url)
    if arguments.prepare_only:
        return 0
    launch_uvicorn(database_url, arguments.host, arguments.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
