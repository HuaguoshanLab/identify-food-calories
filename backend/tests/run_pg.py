"""Run a PostgreSQL test child only after validating the committed test contract."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from sqlalchemy.engine import URL, make_url


class TestDatabaseContractError(ValueError):
    """Raised before a child can receive an unsafe database configuration."""


REQUIRED_VARIABLES = ("APP_ENV", "DATABASE_URL", "TEST_DATABASE_URL")
EXPECTED_TEST_HOSTS = {"127.0.0.1", "localhost", "::1"}
EXPECTED_TEST_PORT = 55432
EXPECTED_TEST_DATABASE = "food_agent_test"


def _parse_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise TestDatabaseContractError("test environment file is required")

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise TestDatabaseContractError("test environment file contains an invalid assignment")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in values:
            raise TestDatabaseContractError("test environment file contains an invalid variable")
        values[key] = value

    missing = [name for name in REQUIRED_VARIABLES if not values.get(name)]
    if missing:
        raise TestDatabaseContractError("test environment file is missing required variables")
    return values


def _database_url(value: str) -> URL:
    try:
        return make_url(value)
    except Exception as error:
        raise TestDatabaseContractError("database URL must be a valid PostgreSQL URL") from error


def _target(url: URL) -> tuple[str, str | None, int | None, str | None]:
    return (url.drivername, url.host, url.port, url.database)


def _validate_contract(values: dict[str, str]) -> None:
    if values["APP_ENV"] != "test":
        raise TestDatabaseContractError("APP_ENV must be test")

    database_url = _database_url(values["DATABASE_URL"])
    test_url = _database_url(values["TEST_DATABASE_URL"])
    if database_url.drivername != "postgresql+psycopg" or test_url.drivername != "postgresql+psycopg":
        raise TestDatabaseContractError("database URLs must use psycopg PostgreSQL")
    if _target(database_url) == _target(test_url):
        raise TestDatabaseContractError("DATABASE_URL and TEST_DATABASE_URL must not target the same database")
    if test_url.host not in EXPECTED_TEST_HOSTS:
        raise TestDatabaseContractError("TEST_DATABASE_URL must target a loopback host")
    if test_url.port != EXPECTED_TEST_PORT:
        raise TestDatabaseContractError("TEST_DATABASE_URL must use the compose test port 55432")
    if test_url.database != EXPECTED_TEST_DATABASE:
        raise TestDatabaseContractError("TEST_DATABASE_URL must use the compose food_agent_test database")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args(argv)
    if not arguments.command or arguments.command[0] != "--" or len(arguments.command) == 1:
        parser.error("a child command is required after --")
    arguments.command = arguments.command[1:]
    return arguments


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        values = _parse_env_file(arguments.env_file)
        _validate_contract(values)
    except TestDatabaseContractError as error:
        print(f"test database contract rejected: {error}", file=sys.stderr)
        return 2

    child_environment = os.environ.copy()
    child_environment.update({name: values[name] for name in REQUIRED_VARIABLES})
    return subprocess.run(arguments.command, env=child_environment, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
