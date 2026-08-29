"""Explicitly create LangGraph PostgreSQL Checkpointer tables for the guarded test DB."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy.engine import make_url

from app.core.config import ConfigurationError, Settings, normalize_database_url, validate_test_database_configuration


def _checkpointer_conninfo(database_url: str) -> str:
    """Convert the SQLAlchemy psycopg URL to the driver-neutral psycopg conninfo."""

    url = make_url(database_url)
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def guarded_database_url(requested_url: str) -> str:
    """Accept exactly the already validated test target and never rebind DATABASE_URL."""

    expected_url = validate_test_database_configuration(Settings(_env_file=None))  # type: ignore[call-arg]
    if normalize_database_url(requested_url) != normalize_database_url(expected_url):
        raise ConfigurationError("checkpointer setup must use the validated TEST_DATABASE_URL")
    return expected_url


async def setup(database_url: str) -> None:
    # LangGraph reads this setting during serde construction.  Pickle remains off and
    # no custom allowlist expands the strict built-in safe msgpack types.
    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(
        _checkpointer_conninfo(database_url), serde=serde
    ) as checkpointer:
        await checkpointer.setup()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-url", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        asyncio.run(setup(guarded_database_url(arguments.database_url)))
    except (ConfigurationError, ValueError) as error:
        print(f"checkpointer setup rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
