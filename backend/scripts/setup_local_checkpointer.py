"""Create LangGraph Checkpointer tables for the fixed local development database.

This command is intentionally separate from the guarded test bootstrap: it never resets,
migrates, seeds, or accepts a caller-supplied database URL.  Production deployments own
schema provisioning outside the application process.
"""

from __future__ import annotations

import asyncio
import os
import sys

from sqlalchemy.engine import make_url

from app.core.config import ConfigurationError, Settings, runtime_database_url


def guarded_local_database_url() -> str:
    """Return only the conventional loopback development database, never production."""

    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    if settings.app_env != "local":
        raise ConfigurationError("local checkpointer setup requires APP_ENV=local")
    database_url = runtime_database_url(settings)
    parsed = make_url(database_url)
    if parsed.host not in {"localhost", "127.0.0.1", "::1"}:
        raise ConfigurationError("local checkpointer setup requires a loopback PostgreSQL host")
    if parsed.database != "food_agent_dev":
        raise ConfigurationError("local checkpointer setup requires the food_agent_dev database")
    return database_url


async def setup(database_url: str) -> None:
    """Run the idempotent LangGraph-owned DDL without exposing the connection string."""

    os.environ["LANGGRAPH_STRICT_MSGPACK"] = "true"
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

    conninfo = make_url(database_url).set(drivername="postgresql").render_as_string(
        hide_password=False
    )
    serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
    async with AsyncPostgresSaver.from_conn_string(conninfo, serde=serde) as checkpointer:
        await checkpointer.setup()


def main() -> int:
    try:
        asyncio.run(setup(guarded_local_database_url()))
    except (ConfigurationError, ValueError) as error:
        print(f"local checkpointer setup rejected: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
