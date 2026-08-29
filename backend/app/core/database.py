"""Application database factories; test fixtures create their own guarded engine."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings, get_settings, runtime_database_url


def create_application_engine(settings: Settings | None = None) -> Engine:
    """Create an engine only from DATABASE_URL for normal application runtime."""

    active_settings = settings or get_settings()
    return create_engine(runtime_database_url(active_settings), pool_pre_ping=True)


def create_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=create_application_engine(settings),
        autoflush=False,
        expire_on_commit=False,
    )


_application_session_factory: sessionmaker[Session] | None = None


def get_application_session_factory() -> sessionmaker[Session]:
    """Create the process-wide pool once; requests receive separate Sessions."""

    global _application_session_factory
    if _application_session_factory is None:
        _application_session_factory = create_session_factory()
    return _application_session_factory


def get_session() -> Generator[Session, None, None]:
    """FastAPI dependency for normal runtime sessions."""

    with get_application_session_factory()() as session:
        yield session
