"""Real PostgreSQL retrieval tests prove SQL tenant/deletion filtering before results leave the repository."""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.agent.models import AgentRun, AgentThread
from app.auth.models import User, UserRole
from app.core.config import Settings, validate_test_database_configuration
from app.memory.providers import FakeMemoryProvider
from app.memory.repository import SqlAlchemyMemoryLedgerRepository
from app.memory.service import MemoryService
from app.nutrition.models import FoodCatalogItem
from app.records.models import MealRecord, PreferenceMemoryLedger
from app.retrieval.models import MealHistoryEmbedding, NutritionKnowledgeEmbedding
from app.retrieval.repository import SqlAlchemyRetrievalRepository
from app.retrieval.service import PersonalContextService


BACKEND_ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 8, 31, 8, 0, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(app_env="test", database_url="postgresql+psycopg://postgres:postgres@localhost:5432/food_agent_dev", test_database_url="postgresql+psycopg://postgres:postgres@localhost:55432/food_agent_test", _env_file=None)


def _user(*, label: str) -> User:
    return User(id=uuid.uuid4(), email=f"retrieval-{label}-{uuid.uuid4().hex}@example.test", password_hash="argon2id-digest", role=UserRole.USER.value, is_active=True, email_verified_at=NOW, created_at=NOW, updated_at=NOW)


def _record(*, user: User, deleted: bool) -> tuple[MealRecord, AgentThread, AgentRun]:
    thread = AgentThread(id=uuid.uuid4(), user_id=user.id, status="completed", revision=1, created_at=NOW, last_activity_at=NOW, deleted_at=None)
    run = AgentRun(id=uuid.uuid4(), thread_id=thread.id, user_id=user.id, command_key=f"run-{uuid.uuid4()}", command_hash="a" * 64, status="completed", graph_version="v1", prompt_version="v1", tool_version="v1", model_provider=None, model_version=None, graph_steps=1, model_calls=1, tool_calls=1, elapsed_ms=1, estimated_cost_usd=Decimal("0"), failure_code=None, created_at=NOW, updated_at=NOW, finished_at=NOW)
    record = MealRecord(id=uuid.uuid4(), user_id=user.id, source_run_id=run.id, agent_thread_id=thread.id, agent_run_id=run.id, command_key=f"save-{uuid.uuid4()}", consumed_at=NOW, nutrition_catalog_version="fdc-v1", calculation_version="per-100g-v1", energy_kcal=Decimal("130"), protein_g=Decimal("2"), fat_g=Decimal("0"), carbohydrate_g=Decimal("28"), created_at=NOW, updated_at=NOW, deleted_at=NOW if deleted else None)
    return record, thread, run


def test_personal_context_has_zero_cross_user_or_soft_deleted_recall() -> None:
    settings = _settings()
    test_url = validate_test_database_configuration(settings)
    test_env = os.environ | {"APP_ENV": "test", "DATABASE_URL": settings.database_url, "TEST_DATABASE_URL": settings.test_database_url or ""}
    subprocess.run([sys.executable, "scripts/run_initialized_app.py", "--prepare-only"], cwd=BACKEND_ROOT, env=test_env, check=True)
    engine = create_engine(test_url)
    try:
        with Session(engine) as session:
            owner, other = _user(label="owner"), _user(label="other")
            owner_record, owner_thread, owner_run = _record(user=owner, deleted=False)
            other_record, other_thread, other_run = _record(user=other, deleted=False)
            deleted_record, deleted_thread, deleted_run = _record(user=owner, deleted=True)
            session.add_all([owner, other])
            session.commit()
            session.add_all([owner_thread, other_thread, deleted_thread])
            session.commit()
            session.add_all([owner_run, other_run, deleted_run])
            session.commit()
            session.add_all([owner_record, other_record, deleted_record])
            session.commit()
            session.add_all([
                MealHistoryEmbedding(id=uuid.uuid4(), user_id=owner.id, meal_record_id=owner_record.id, source_type="meal_history", embedding_model="fake", embedding_version="v1", embedding="[0,0,0]", safe_summary="owner 米饭历史", is_active=True, created_at=NOW, updated_at=NOW, deleted_at=None),
                MealHistoryEmbedding(id=uuid.uuid4(), user_id=other.id, meal_record_id=other_record.id, source_type="meal_history", embedding_model="fake", embedding_version="v1", embedding="[0,0,0]", safe_summary="other 米饭历史", is_active=True, created_at=NOW, updated_at=NOW, deleted_at=None),
                MealHistoryEmbedding(id=uuid.uuid4(), user_id=owner.id, meal_record_id=deleted_record.id, source_type="meal_history", embedding_model="fake", embedding_version="v1", embedding="[0,0,0]", safe_summary="deleted 米饭历史", is_active=True, created_at=NOW, updated_at=NOW, deleted_at=None),
                PreferenceMemoryLedger(id=uuid.uuid4(), user_id=owner.id, category="avoidance", source_kind="user_statement", canonical_text="不吃花生", external_memory_id="owner", is_active=True, created_at=NOW, updated_at=NOW, deleted_at=None),
                PreferenceMemoryLedger(id=uuid.uuid4(), user_id=other.id, category="avoidance", source_kind="user_statement", canonical_text="other 私人偏好", external_memory_id="other", is_active=True, created_at=NOW, updated_at=NOW, deleted_at=None),
                PreferenceMemoryLedger(id=uuid.uuid4(), user_id=owner.id, category="goal", source_kind="user_statement", canonical_text="deleted 私人偏好", external_memory_id="deleted", is_active=False, created_at=NOW, updated_at=NOW, deleted_at=NOW),
            ])
            food = session.scalar(select(FoodCatalogItem).where(FoodCatalogItem.is_qualified.is_(True)).limit(1))
            assert food is not None
            session.add(NutritionKnowledgeEmbedding(id=uuid.uuid4(), food_id=food.id, catalog_version=food.catalog_version.version, source_type="nutrition_knowledge", embedding_model="fake", embedding_version="v1", embedding="[0,0,0]", safe_summary="米饭受控营养知识", is_eligible=True, created_at=NOW, updated_at=NOW, deleted_at=None))
            session.commit()
            context = PersonalContextService(memory_service=MemoryService(repository=SqlAlchemyMemoryLedgerRepository(session), provider=FakeMemoryProvider()), repository=SqlAlchemyRetrievalRepository(session)).retrieve(user_id=owner.id, query="米饭", catalog_version=food.catalog_version.version)
            summaries = [item.summary for item in context]
            assert "已参考你的忌口：不吃花生" in summaries
            assert "owner 米饭历史" in summaries and "米饭受控营养知识" in summaries
            assert all("other" not in summary and "deleted" not in summary for summary in summaries)
    finally:
        engine.dispose()
