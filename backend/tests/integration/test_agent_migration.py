"""Real PostgreSQL proof that revision 0004 exactly materializes Agent metadata."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys

from sqlalchemy import create_engine, inspect, text

from app.agent import models as agent_models
from app.auth.models import Base
from app.core.config import Settings, validate_test_database_configuration
from app.nutrition import models as nutrition_models


# Importing both modules is deliberate: one SQLAlchemy metadata object is the schema
# contract.  The migration may not create tables that the ORM does not declare.
_ = (agent_models, nutrition_models)

AGENT_CORE_TABLES = {
    "agent_deletion_intents",
    "agent_events",
    "agent_invocations",
    "agent_leases",
    "agent_runs",
    "agent_threads",
    "food_catalog_aliases",
    "food_catalog_items",
    "food_catalog_portions",
    "nutrition_catalogs",
    "nutrition_catalog_versions",
    "nutrition_sources",
}


def _test_url() -> str:
    settings = Settings(
        app_env=os.environ.get("APP_ENV", ""),
        database_url=os.environ.get("DATABASE_URL", ""),
        test_database_url=os.environ.get("TEST_DATABASE_URL"),
        _env_file=None,
    )
    return validate_test_database_configuration(settings)


def _alembic(*arguments: str) -> None:
    environment = os.environ.copy()
    environment["APP_ENV"] = "test"
    subprocess.run(
        [sys.executable, "-m", "alembic", *arguments], check=True, env=environment
    )


def _schema_fingerprint(database_url: str) -> str:
    """Hash public schema object names without ever writing to the development target."""

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        objects: list[str] = []
        for table in sorted(inspector.get_table_names(schema="public")):
            objects.append(f"table:{table}")
            objects.extend(
                f"column:{table}:{column['name']}:{column['type']}:{column['nullable']}"
                for column in inspector.get_columns(table, schema="public")
            )
            objects.extend(
                f"check:{table}:{constraint['name']}:{constraint['sqltext']}"
                for constraint in inspector.get_check_constraints(table, schema="public")
            )
            objects.extend(
                f"index:{table}:{index['name']}:{index['unique']}:{index['column_names']}"
                for index in inspector.get_indexes(table, schema="public")
            )
        return hashlib.sha256("\n".join(sorted(objects)).encode()).hexdigest()
    finally:
        engine.dispose()


def _metadata_table_names() -> set[str]:
    return set(Base.metadata.tables).intersection(AGENT_CORE_TABLES)


def test_0004_round_trip_matches_agent_and_nutrition_metadata_without_seed_data() -> None:
    test_url = _test_url()
    development_before = _schema_fingerprint(os.environ["DATABASE_URL"])
    try:
        _alembic("downgrade", "base")
        _alembic("upgrade", "0003")
        engine = create_engine(test_url)
        try:
            assert not AGENT_CORE_TABLES.intersection(
                inspect(engine).get_table_names(schema="public")
            )
        finally:
            engine.dispose()

        _alembic("upgrade", "0004")
        engine = create_engine(test_url)
        try:
            inspector = inspect(engine)
            assert _metadata_table_names() == AGENT_CORE_TABLES
            assert AGENT_CORE_TABLES <= set(inspector.get_table_names(schema="public"))
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0004"
                assert connection.scalar(text("SELECT count(*) FROM food_catalog_items")) == 0
        finally:
            engine.dispose()

        _alembic("downgrade", "0003")
        engine = create_engine(test_url)
        try:
            assert not AGENT_CORE_TABLES.intersection(
                inspect(engine).get_table_names(schema="public")
            )
        finally:
            engine.dispose()
    finally:
        _alembic("upgrade", "head")

    assert _schema_fingerprint(os.environ["DATABASE_URL"]) == development_before
