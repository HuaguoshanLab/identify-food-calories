"""Tenant-filtered, flush-only SQLAlchemy adapter for meal records."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.agent.models import AgentEvent, AgentRun
from app.records.models import DashboardTimezoneBackfillAudit, DashboardTimezonePreference, MealRecord


class SqlAlchemyMealRecordRepository:
    """All user-facing record reads prove ownership inside SQL, never after loading a UUID."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_completed_run_for_thread_for_user(
        self, *, thread_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> AgentRun | None:
        statement = (
            select(AgentRun)
            .where(
                AgentRun.thread_id == thread_id,
                AgentRun.user_id == user_id,
                AgentRun.status == "completed",
            )
            .order_by(AgentRun.finished_at.desc(), AgentRun.id.desc())
        )
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def get_completed_report_for_run_for_user(
        self, *, run_id: uuid.UUID, user_id: uuid.UUID
    ) -> AgentEvent | None:
        return self._session.scalar(
            select(AgentEvent)
            .where(
                AgentEvent.run_id == run_id,
                AgentEvent.user_id == user_id,
                # AgentService persists the report only after deterministic validation;
                # accepting another terminal event would allow an unvalidated snapshot to
                # become a user record.
                AgentEvent.event_type == "completed_validated",
            )
            .order_by(AgentEvent.seq.desc())
        )

    def get_record_for_command_for_user(
        self, *, command_key: str, user_id: uuid.UUID, include_deleted: bool = False
    ) -> MealRecord | None:
        return self._session.scalar(self._record_statement(user_id=user_id, include_deleted=include_deleted).where(MealRecord.command_key == command_key))

    def get_record_for_source_run_for_user(
        self, *, source_run_id: uuid.UUID, user_id: uuid.UUID, include_deleted: bool = False
    ) -> MealRecord | None:
        return self._session.scalar(self._record_statement(user_id=user_id, include_deleted=include_deleted).where(MealRecord.source_run_id == source_run_id))

    def add_record(self, record: MealRecord) -> MealRecord:
        self._session.add(record)
        self._session.flush()
        return record

    def get_record_for_user(
        self, *, record_id: uuid.UUID, user_id: uuid.UUID, for_update: bool = False
    ) -> MealRecord | None:
        statement = self._record_statement(user_id=user_id).where(MealRecord.id == record_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def list_records_for_user(self, *, user_id: uuid.UUID) -> list[MealRecord]:
        return list(
            self._session.scalars(
                self._record_statement(user_id=user_id).order_by(MealRecord.consumed_at.desc(), MealRecord.id.desc())
            )
        )

    def get_dashboard_time_zone_preference_for_user(
        self, *, user_id: uuid.UUID, for_update: bool = False
    ) -> DashboardTimezonePreference | None:
        statement = select(DashboardTimezonePreference).where(DashboardTimezonePreference.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return self._session.scalar(statement)

    def add_dashboard_time_zone_preference(
        self, preference: DashboardTimezonePreference
    ) -> DashboardTimezonePreference:
        self._session.add(preference)
        self._session.flush()
        return preference

    def list_records_without_local_date_for_user(self, *, user_id: uuid.UUID) -> list[MealRecord]:
        return list(
            self._session.scalars(
                self._record_statement(user_id=user_id).where(MealRecord.consumed_local_date.is_(None))
            )
        )

    def add_timezone_backfill_audit(
        self, audit: DashboardTimezoneBackfillAudit
    ) -> DashboardTimezoneBackfillAudit:
        self._session.add(audit)
        self._session.flush()
        return audit

    @staticmethod
    def _record_statement(*, user_id: uuid.UUID, include_deleted: bool = False):
        statement = select(MealRecord).options(selectinload(MealRecord.items)).where(MealRecord.user_id == user_id)
        if not include_deleted:
            statement = statement.where(MealRecord.deleted_at.is_(None))
        return statement
