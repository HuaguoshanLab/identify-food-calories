"""Real PostgreSQL proof for the fixed migration → checkpoint → seed chain."""

from __future__ import annotations

import os
import subprocess
import sys
import asyncio
from pathlib import Path

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.agent.supervisor import PostgresLeaseSupervisor
from app.core.config import Settings, validate_test_database_configuration


BACKEND_ROOT = Path(__file__).resolve().parents[2]
SEED_HASH = "9009d03d802589038efc7fe996fcf62f8ff2424f7a555f8ba6d86c378794a91f"


def test_prepare_only_is_idempotent_and_keeps_database_targets_distinct() -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    test_url = validate_test_database_configuration(settings)
    development_url = make_url(settings.database_url)
    isolated_url = make_url(test_url)
    assert development_url.port == 5432
    assert development_url.database == "food_agent_dev"
    assert isolated_url.port == 55432
    assert isolated_url.database == "food_agent_test"
    assert development_url.render_as_string(hide_password=False) != isolated_url.render_as_string(
        hide_password=False
    )

    command = [sys.executable, "scripts/run_initialized_app.py", "--prepare-only"]
    for _ in range(2):
        subprocess.run(command, cwd=BACKEND_ROOT, env=os.environ.copy(), check=True)

    engine = create_engine(test_url)
    try:
        supervisor = PostgresLeaseSupervisor(
            session_factory=sessionmaker(engine), holder_id="bootstrap-test"
        )
        asyncio.run(supervisor.start())
        assert supervisor.started is True
        asyncio.run(supervisor.stop())
        table_names = set(inspect(engine).get_table_names())
        assert {"checkpoints", "checkpoint_blobs", "checkpoint_writes"} <= table_names
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
            assert connection.scalar(
                text(
                    "SELECT content_hash FROM nutrition_catalog_versions "
                    "WHERE version = 'foundation-foods-2025-04'"
                )
            ) == SEED_HASH
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM food_catalog_items "
                    "WHERE stable_id = 'fdc:169756' AND is_qualified"
                )
            ) == 1
            assert connection.scalar(
                text(
                    "SELECT count(*) FROM food_catalog_items "
                    "WHERE stable_id = 'recipe:chili-fried-pork-v1' AND is_qualified"
                )
            ) == 1
    finally:
        engine.dispose()
