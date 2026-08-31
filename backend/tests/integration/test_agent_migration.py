"""Real PostgreSQL proof that revision 0006 exactly materializes Agent metadata."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy.engine.interfaces import Dialect
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
    "agent_images",
    "agent_invocations",
    "agent_leases",
    "agent_runs",
    "agent_threads",
    "agent_vision_invocations",
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


def _type_contract(
    column_type: object, *, dialect: Dialect | None = None
) -> tuple[str, int | None, int | None, int | None, bool | None]:
    """Keep reflection differences honest while preserving type parameters and timezone."""

    rendered_type = (
        column_type.compile(dialect=dialect)  # type: ignore[union-attr]
        if dialect is not None
        else str(column_type)
    )
    rendered = rendered_type.replace(" WITH TIME ZONE", "")
    return (
        rendered,
        getattr(column_type, "length", None),
        getattr(column_type, "precision", None),
        getattr(column_type, "scale", None),
        getattr(column_type, "timezone", None),
    )


def _assert_live_schema_matches_metadata(database_url: str) -> None:
    """Compare every 0005 ORM table's columns, named constraints, indexes and FKs."""

    engine = create_engine(database_url)
    try:
        inspector = inspect(engine)
        for table_name in sorted(AGENT_CORE_TABLES):
            model = Base.metadata.tables[table_name]
            columns = inspector.get_columns(table_name, schema="public")
            assert [
                (column["name"], _type_contract(column["type"]), column["nullable"])
                for column in columns
            ] == [
                (
                    column.name,
                    _type_contract(column.type, dialect=engine.dialect),
                    column.nullable,
                )
                for column in model.columns
            ]
            assert tuple(inspector.get_pk_constraint(table_name)["constrained_columns"]) == tuple(
                column.name for column in model.primary_key.columns
            )

            assert {
                constraint["name"] for constraint in inspector.get_check_constraints(table_name)
            } == {
                constraint.name
                for constraint in model.constraints
                if constraint.__class__.__name__ == "CheckConstraint"
            }
            assert {
                (constraint["name"], tuple(constraint["column_names"]))
                for constraint in inspector.get_unique_constraints(table_name)
            } == {
                (constraint.name, tuple(column.name for column in constraint.columns))
                for constraint in model.constraints
                if constraint.__class__.__name__ == "UniqueConstraint"
            }
            assert {
                (index["name"], tuple(index["column_names"]), index["unique"])
                for index in inspector.get_indexes(table_name)
                if not index["unique"]
            } == {
                (index.name, tuple(column.name for column in index.columns), index.unique)
                for index in model.indexes
            }
            assert {
                (
                    tuple(foreign_key["constrained_columns"]),
                    foreign_key["referred_table"],
                    foreign_key["options"].get("ondelete"),
                )
                for foreign_key in inspector.get_foreign_keys(table_name)
            } == {
                (
                    tuple(element.parent.name for element in foreign_key.elements),
                    foreign_key.elements[0].column.table.name,
                    foreign_key.ondelete,
                )
                for foreign_key in model.foreign_key_constraints
            }
    finally:
        engine.dispose()


def test_0006_round_trip_matches_agent_and_nutrition_metadata_without_seed_data() -> None:
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

        _alembic("upgrade", "0006")
        engine = create_engine(test_url)
        try:
            inspector = inspect(engine)
            assert _metadata_table_names() == AGENT_CORE_TABLES
            assert AGENT_CORE_TABLES <= set(inspector.get_table_names(schema="public"))
            with engine.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0006"
                assert connection.scalar(text("SELECT count(*) FROM food_catalog_items")) == 0
        finally:
            engine.dispose()
        _assert_live_schema_matches_metadata(test_url)

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


def test_0006_is_the_single_head_and_contains_no_seed_statement() -> None:
    migration = Path("migrations/versions/0006_multimodal_images.py")
    script = ScriptDirectory.from_config(Config("alembic.ini"))

    assert script.get_heads() == ["0006"]
    assert "INSERT" not in migration.read_text(encoding="utf-8").upper()
