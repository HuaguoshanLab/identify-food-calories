"""Admin authorization and role-elevation policy over a repository port."""

from __future__ import annotations

import uuid
import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

from app.admin.models import (
    AdminAuditEvent,
    AdminRoleAudit,
    CatalogDraft,
    CatalogDraftChangeSet,
    CatalogDraftReview,
    CatalogDraftRevision,
    CatalogPublication,
    CatalogPublicationEligibility,
)
from app.agent.models import AgentInvocation, AgentRun, AgentRuntimeConfigVersion
from app.agent.ports import RuntimeConfigAdmission
from app.agent.service import AgentRuntimeAdmissionDenied
from app.admin.ports import AdminRepository
from app.admin.catalog_csv import (
    MAX_EXPORT_ROWS,
    CatalogCsvInvalid,
    parse_catalog_csv,
    write_catalog_csv,
)
from app.admin.recipe_csv import (
    RecipeCandidateCsvInvalid,
    parse_recipe_candidate_csv,
    write_recipe_candidate_csv,
)
from app.admin.schemas import (
    AdminAuditEventResponse,
    AdminAuditPageResponse,
    AdminRunDetailResponse,
    AdminRunInvocationResponse,
    AdminRunMetricsResponse,
    AdminRunPageResponse,
    CatalogDraftCreateCommand,
    CatalogDraftDiffField,
    CatalogDraftFieldDiff,
    CatalogDraftPatchCommand,
    CatalogDraftPreviewCommand,
    CatalogDraftPreviewResponse,
    CatalogDraftResponse,
    CatalogListQuery,
    CatalogListItem,
    CatalogListResponse,
    CatalogCsvPreview,
    CatalogCsvImportCommand,
    CatalogCsvImportResponse,
    CatalogLifecycleCommand,
    CatalogLifecycleFieldDiff,
    CatalogLifecycleImpact,
    CatalogLifecyclePreviewResponse,
    CatalogLifecyclePublicationResponse,
    CatalogPublicationResponse,
    RuntimeConfigCommand,
    RuntimeConfigResponse,
    RecipeCandidateBulkCommand,
    RecipeCandidateCsvPreview,
    RecipeCandidateImportCommand,
    RecipeCandidateImportResponse,
    RecipeCandidateListQuery,
    RecipeCandidateListResponse,
    RecipeCandidateResponse,
)
from app.auth.models import User, UserRole
from app.planning.models import ManagedRecipeCandidate


class AdminPermissionDenied(PermissionError):
    """Authenticated users without the current database role cannot continue."""


class AdminRoleChangeDenied(ValueError):
    """A role mutation did not meet the explicit CLI-only safety policy."""


class AdminAuditCursorInvalid(ValueError):
    """A client-supplied cursor failed its integrity or shape validation."""


class CatalogDraftConflict(ValueError):
    """A stale revision or incompatible idempotency replay cannot overwrite a draft."""


RecipeCandidateConflict = CatalogDraftConflict


class RuntimeConfigConflict(ValueError):
    """A configuration idempotency key was reused for a different command."""


class AdminRunCursorInvalid(ValueError):
    """A supplied run cursor did not pass integrity or shape validation."""


RuntimeAdmissionDenied = AgentRuntimeAdmissionDenied


_CATALOG_LIFECYCLE_FIELDS: tuple[CatalogDraftDiffField, ...] = (
    "canonical_name",
    "aliases",
    "energy_kcal_per_100g",
    "protein_g_per_100g",
    "fat_g_per_100g",
    "carbohydrate_g_per_100g",
    "source_name",
    "source_url",
    "authorization_status",
)


class AdminService:
    """Keeps RBAC truth and audit mutations inside one application transaction."""

    def __init__(
        self,
        *,
        repository: AdminRepository,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
        cursor_secret: str | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)
        self._cursor_secret = cursor_secret.encode("utf-8") if cursor_secret else None
        self._last_lifecycle_at: datetime | None = None

    def require_role(self, *, user_id: uuid.UUID, required_role: UserRole) -> User:
        """Read the active role from PostgreSQL; JWT claims are never authorization truth."""

        user = self._repository.get_user_by_id(user_id)
        if user is None or not user.is_active or user.role != required_role.value:
            raise AdminPermissionDenied("database role does not permit this operation")
        return user

    def configure_runtime(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: RuntimeConfigCommand,
        command_key: str,
        expected_version: int | None = None,
    ) -> RuntimeConfigResponse:
        """Append a non-secret policy version; old runs keep their prior snapshots."""

        payload = command.model_dump(exclude={"reason", "confirm"})
        request_hash = self._request_hash(
            "runtime_config", payload | {"reason": command.reason}
        )
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_runtime_config_lock()
        active = self._repository.get_active_runtime_config()
        if expected_version is not None and expected_version != (
            active.version if active else 0
        ):
            raise RuntimeConfigConflict("runtime config version conflict")
        existing = self._repository.get_runtime_config_command(command_key)
        if existing is not None:
            if self._runtime_request_hash(existing) != request_hash:
                raise RuntimeConfigConflict(
                    "runtime config idempotency key payload mismatch"
                )
            return self._runtime_response(existing)
        now = self._now()
        version = AgentRuntimeConfigVersion(
            id=uuid.uuid4(),
            version=self._repository.next_runtime_config_version(),
            **payload,
            reason=command.reason,
            actor_user_id=actor.id,
            command_key=command_key,
            created_at=now,
        )
        self._repository.add_runtime_config_version(version)
        self._repository.add_audit_event(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_identifier=str(actor.id),
                occurred_at=now,
                action="runtime_config.configure",
                object_type="agent_runtime_config_version",
                object_id=str(version.id),
                reason=command.reason,
                before_diff={},
                after_diff=self._runtime_audit_payload(version),
                related_version=str(version.version),
                command_key=command_key,
            )
        )
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        return self._runtime_response(version)

    def read_runtime_config(self, *, actor_user_id: uuid.UUID) -> RuntimeConfigResponse:
        """Return the current safe policy only after a fresh database role read."""

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        active = self._repository.get_active_runtime_config()
        if active is None:
            raise KeyError("runtime config not found")
        return self._runtime_response(active)

    def admit_runtime_call(self) -> RuntimeConfigAdmission:
        """Freeze the active policy before a new Agent run reaches provider work.

        This is intentionally not an admin command: ordinary authenticated users may
        use an already-approved service policy, while only configuration mutation
        requires DB-RBAC.
        """

        self._repository.acquire_runtime_config_lock()
        active = self._repository.get_active_runtime_config()
        if active is None or not active.enabled:
            raise RuntimeAdmissionDenied("reasoning provider is disabled")
        if active.single_call_cap_usd <= 0 or active.period_cap_usd <= 0:
            raise RuntimeAdmissionDenied("reasoning provider has no callable budget")
        response = self._runtime_response(active)
        return RuntimeConfigAdmission(
            version_id=response.id, snapshot=self.runtime_snapshot(response)
        )

    @staticmethod
    def runtime_snapshot(config: RuntimeConfigResponse) -> dict[str, object]:
        """The only ledger payload admissible for an already-approved future call."""

        return {
            "version": config.version,
            "provider": config.provider,
            "model_alias": config.model_alias,
            "enabled": config.enabled,
            "single_call_cap_usd": str(config.single_call_cap_usd),
            "period_cap_usd": str(config.period_cap_usd),
            "input_usd_per_m": str(config.input_usd_per_m),
            "output_usd_per_m": str(config.output_usd_per_m),
        }

    @staticmethod
    def _runtime_request_hash(version: AgentRuntimeConfigVersion) -> str:
        return AdminService._request_hash(
            "runtime_config",
            {
                "provider": version.provider,
                "model_alias": version.model_alias,
                "enabled": version.enabled,
                "single_call_cap_usd": version.single_call_cap_usd,
                "period_cap_usd": version.period_cap_usd,
                "input_usd_per_m": version.input_usd_per_m,
                "output_usd_per_m": version.output_usd_per_m,
                "reason": version.reason,
            },
        )

    @staticmethod
    def _runtime_audit_payload(version: AgentRuntimeConfigVersion) -> dict[str, object]:
        return {
            "version": version.version,
            "provider": version.provider,
            "model_alias": version.model_alias,
            "enabled": version.enabled,
            "single_call_cap_usd": str(version.single_call_cap_usd),
            "period_cap_usd": str(version.period_cap_usd),
            "input_usd_per_m": str(version.input_usd_per_m),
            "output_usd_per_m": str(version.output_usd_per_m),
        }

    @staticmethod
    def _runtime_response(version: AgentRuntimeConfigVersion) -> RuntimeConfigResponse:
        return RuntimeConfigResponse(
            id=version.id,
            version=version.version,
            provider=cast(Literal["deepseek"], version.provider),
            model_alias=cast(Literal["deepseek-v4-flash"], version.model_alias),
            enabled=version.enabled,
            single_call_cap_usd=version.single_call_cap_usd,
            period_cap_usd=version.period_cap_usd,
            input_usd_per_m=version.input_usd_per_m,
            output_usd_per_m=version.output_usd_per_m,
            created_at=version.created_at,
        )

    def bootstrap_first_admin(
        self, *, target_user_id: uuid.UUID, reason: str
    ) -> AdminRoleAudit:
        """Promote only when the system has no active admin, recording the system actor."""

        # A transaction-scoped PostgreSQL advisory lock closes the check-then-promote
        # race: concurrent bootstrap processes cannot both observe an empty admin set.
        self._repository.acquire_bootstrap_lock()
        if self._repository.has_active_admin():
            raise AdminRoleChangeDenied(
                "bootstrap is only available before an active admin exists"
            )
        target = self._promotion_target(target_user_id)
        return self._commit_promotion(
            actor_identifier="system:bootstrap", target=target, reason=reason
        )

    def promote_admin(
        self, *, actor_user_id: uuid.UUID, target_user_id: uuid.UUID, reason: str
    ) -> AdminRoleAudit:
        """Require a verified, active, already-admin actor for later elevations."""

        if actor_user_id == target_user_id:
            raise AdminRoleChangeDenied("an actor cannot promote itself")
        actor = self._repository.get_user_for_update(actor_user_id)
        if (
            actor is None
            or not actor.is_active
            or actor.email_verified_at is None
            or actor.role != UserRole.ADMIN.value
        ):
            raise AdminRoleChangeDenied("actor must be a verified active administrator")
        target = self._promotion_target(target_user_id)
        return self._commit_promotion(
            actor_identifier=str(actor.id), target=target, reason=reason
        )

    def record_command_audit(
        self,
        *,
        actor_user_id: uuid.UUID,
        action: str,
        object_type: str,
        object_id: str,
        reason: str,
        before: dict[str, object],
        after: dict[str, object],
        related_version: str | None,
        command_key: str,
    ) -> AdminAuditEvent:
        """Append evidence in the caller's command transaction after current DB RBAC.

        Concrete admin mutations call this helper before their sole commit.  The
        helper is deliberately unable to accept raw HTTP or Provider data.
        """

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        normalized = self._normalized_command_fields(
            action=action,
            object_type=object_type,
            object_id=object_id,
            reason=reason,
            command_key=command_key,
        )
        event = self._repository.add_audit_event(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_identifier=str(actor.id),
                occurred_at=self._now(),
                action=normalized["action"],
                object_type=normalized["object_type"],
                object_id=normalized["object_id"],
                reason=normalized["reason"],
                before_diff=self._safe_diff(before),
                after_diff=self._safe_diff(after),
                related_version=related_version.strip() if related_version else None,
                command_key=normalized["command_key"],
            )
        )
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        return event

    def list_audit_events(
        self,
        *,
        limit: int,
        cursor: str | None,
        action: str | None = None,
        object_type: str | None = None,
        object_id: str | None = None,
        actor_identifier: str | None = None,
        reason: str | None = None,
        occurred_after: datetime | None = None,
        occurred_before: datetime | None = None,
    ) -> AdminAuditPageResponse:
        """Return an allowlisted, signed keyset page for a previously authorized read."""

        cursor_position = self._decode_cursor(cursor) if cursor else None
        events = self._repository.list_audit_events(
            limit=limit + 1,
            cursor_position=cursor_position,
            action=action,
            object_type=object_type,
            object_id=object_id,
            actor_identifier=actor_identifier,
            reason=reason,
            occurred_after=occurred_after,
            occurred_before=occurred_before,
        )
        has_more = len(events) > limit
        visible = events[:limit]
        next_cursor = self._encode_cursor(visible[-1]) if has_more and visible else None
        return AdminAuditPageResponse(
            items=[self._audit_response(event) for event in visible],
            next_cursor=next_cursor,
        )

    def get_run_metrics(
        self, *, actor_user_id: uuid.UUID, **filters: object
    ) -> AdminRunMetricsResponse:
        """Read aggregate evidence with an explicit server-owned UTC window."""

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        upper = filters.get("occurred_before") or self._now()
        lower = filters.get("occurred_after") or (upper - timedelta(hours=24))
        if not isinstance(lower, datetime) or not isinstance(upper, datetime):
            raise ValueError("run metric window must contain datetime values")
        normalized_filters = {
            **filters,
            "occurred_after": lower,
            "occurred_before": upper,
        }
        return cast(
            AdminRunMetricsResponse,
            self._repository.run_metrics(**normalized_filters),
        )

    def list_agent_runs(
        self,
        *,
        actor_user_id: uuid.UUID,
        limit: int,
        cursor: str | None,
        **filters: object,
    ) -> AdminRunPageResponse:
        """Page terminal runs by signed finished-at/UUID position, never offset."""

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        position = self._decode_run_cursor(cursor) if cursor else None
        runs = self._repository.list_runs(
            limit=limit + 1, cursor_position=position, **filters
        )
        has_more = len(runs) > limit
        visible = runs[:limit]
        return AdminRunPageResponse(
            items=[
                self._run_response(run, include_invocations=False) for run in visible
            ],
            next_cursor=self._encode_run_cursor(visible[-1])
            if has_more and visible
            else None,
        )

    def get_agent_run(
        self, *, actor_user_id: uuid.UUID, run_id: uuid.UUID
    ) -> AdminRunDetailResponse:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        run = self._repository.get_run(run_id)
        if run is None:
            raise KeyError("agent run not found")
        return self._run_response(run, include_invocations=True)

    def list_catalog_drafts(
        self, *, actor_user_id: uuid.UUID, query: CatalogListQuery
    ) -> CatalogListResponse:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        drafts, total = self._repository.list_catalog_drafts(
            query=query,
            limit=query.page_size,
            offset=(query.page - 1) * query.page_size,
        )
        return CatalogListResponse(
            items=[
                CatalogListItem(
                    **self._catalog_response(draft).model_dump(),
                    updated_at=draft.updated_at,
                )
                for draft in drafts
            ],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def list_recipe_candidates(
        self, *, actor_user_id: uuid.UUID, query: RecipeCandidateListQuery
    ) -> RecipeCandidateListResponse:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        rows, total = self._repository.list_recipe_candidates(
            search=query.search,
            meal_slot=query.meal_slot,
            status=query.status,
            limit=query.page_size,
            offset=(query.page - 1) * query.page_size,
        )
        return RecipeCandidateListResponse(
            items=[self._recipe_candidate_response(row) for row in rows],
            total=total,
            page=query.page,
            page_size=query.page_size,
        )

    def preview_recipe_candidate_csv(
        self, *, actor_user_id: uuid.UUID, csv_text: str
    ) -> RecipeCandidateCsvPreview:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        return parse_recipe_candidate_csv(csv_text)

    def recipe_candidate_csv_template(self, *, actor_user_id: uuid.UUID) -> bytes:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        return write_recipe_candidate_csv([])

    def export_recipe_candidate_csv(
        self, *, actor_user_id: uuid.UUID, query: RecipeCandidateListQuery
    ) -> bytes:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        rows, total = self._repository.list_recipe_candidates(
            search=query.search,
            meal_slot=query.meal_slot,
            status=query.status,
            limit=MAX_EXPORT_ROWS + 1,
            offset=0,
        )
        if total > MAX_EXPORT_ROWS or len(rows) > MAX_EXPORT_ROWS:
            raise RecipeCandidateCsvInvalid("每次最多导出 10000 条，请缩小筛选范围。")
        return write_recipe_candidate_csv(
            [self._recipe_candidate_response(row) for row in rows]
        )

    def import_recipe_candidates(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: RecipeCandidateImportCommand,
        command_key: str,
    ) -> RecipeCandidateImportResponse:
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        preview = parse_recipe_candidate_csv(command.csv_text)
        if preview.errors:
            raise RecipeCandidateCsvInvalid("文件存在错误，请修正全部错误后再导入。")
        self._repository.acquire_recipe_candidate_lock(command_key)
        batch_key = f"recipe-import-batch:{command_key}"
        request_hash = self._request_hash("recipe-import", command.model_dump())
        replay = self._repository.get_audit_event_by_command_key(batch_key)
        if replay is not None:
            if replay.after_diff.get("request_hash") != request_hash:
                raise RecipeCandidateConflict(
                    "Idempotency-Key was reused for a different command"
                )
            return RecipeCandidateImportResponse(
                imported_count=len(replay.after_diff["candidate_ids"]),
                candidate_ids=[
                    uuid.UUID(value) for value in replay.after_diff["candidate_ids"]
                ],
            )
        now = self._now()
        ids: list[uuid.UUID] = []
        try:
            for row in preview.rows:
                foods = self._repository.resolve_qualified_food_by_name(
                    row.catalog_food_name
                )
                if len(foods) != 1:
                    raise RecipeCandidateCsvInvalid(
                        "目录菜品必须唯一且当前合格，无法自动创建或猜测关联。"
                    )
                candidate = ManagedRecipeCandidate(
                    id=uuid.uuid4(),
                    food_catalog_item_id=foods[0].id,
                    meal_slot=row.meal_slot,
                    portion_grams=row.portion_grams,
                    portion_description=row.portion_description,
                    method_tags="|".join(row.method_tags),
                    flavour_tags="|".join(row.flavour_tags),
                    status=row.status,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
                self._repository.add_recipe_candidate(candidate)
                ids.append(candidate.id)
                self._repository.add_audit_event(
                    AdminAuditEvent(
                        id=uuid.uuid4(),
                        actor_identifier=str(actor.id),
                        occurred_at=now,
                        action="recipe_candidate.import",
                        object_type="managed_recipe_candidate",
                        object_id=str(candidate.id),
                        reason=command.reason,
                        before_diff={},
                        after_diff={
                            "food_catalog_item_id": str(candidate.food_catalog_item_id),
                            "meal_slot": candidate.meal_slot,
                            "status": candidate.status,
                            "revision": 1,
                        },
                        related_version=None,
                        command_key=f"recipe-import:{command_key}:{candidate.id}",
                    )
                )
            self._repository.add_audit_event(
                AdminAuditEvent(
                    id=uuid.uuid4(),
                    actor_identifier=str(actor.id),
                    occurred_at=now,
                    action="recipe_candidate.import_batch",
                    object_type="managed_recipe_candidate_batch",
                    object_id=command_key,
                    reason=command.reason,
                    before_diff={},
                    after_diff={
                        "request_hash": request_hash,
                        "candidate_ids": [str(candidate_id) for candidate_id in ids],
                    },
                    related_version=None,
                    command_key=batch_key,
                )
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return RecipeCandidateImportResponse(imported_count=len(ids), candidate_ids=ids)

    def change_recipe_candidate_status(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: RecipeCandidateBulkCommand,
        status: Literal["enabled", "disabled", "deleted"],
        command_key: str,
    ) -> list[RecipeCandidateResponse]:
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_recipe_candidate_lock(command_key)
        batch_key = f"recipe-status-batch:{command_key}"
        request_hash = self._request_hash(
            "recipe-status", {"status": status, **command.model_dump()}
        )
        replay = self._repository.get_audit_event_by_command_key(batch_key)
        if replay is not None:
            if replay.after_diff.get("request_hash") != request_hash:
                raise RecipeCandidateConflict(
                    "Idempotency-Key was reused for a different command"
                )
            return [
                self._recipe_candidate_response(
                    self._repository.get_recipe_candidate(uuid.UUID(value))
                )
                for value in replay.after_diff["candidate_ids"]
                if self._repository.get_recipe_candidate(uuid.UUID(value)) is not None
            ]
        now = self._now()
        changed = []
        try:
            for candidate_id in command.ids:
                candidate = self._repository.get_recipe_candidate(
                    candidate_id, for_update=True
                )
                if candidate is None or candidate.deleted_at is not None:
                    raise KeyError("recipe candidate not found")
                before = {"status": candidate.status, "revision": candidate.revision}
                if status == "deleted":
                    candidate.deleted_at = now
                else:
                    candidate.status = status
                candidate.revision += 1
                candidate.updated_at = now
                self._repository.add_audit_event(
                    AdminAuditEvent(
                        id=uuid.uuid4(),
                        actor_identifier=str(actor.id),
                        occurred_at=now,
                        action=f"recipe_candidate.{status}",
                        object_type="managed_recipe_candidate",
                        object_id=str(candidate.id),
                        reason=command.reason,
                        before_diff=before,
                        after_diff={
                            "status": candidate.status,
                            "deleted": candidate.deleted_at is not None,
                            "revision": candidate.revision,
                        },
                        related_version=None,
                        command_key=f"recipe-status:{command_key}:{candidate.id}",
                    )
                )
                changed.append(self._recipe_candidate_response(candidate))
            self._repository.add_audit_event(
                AdminAuditEvent(
                    id=uuid.uuid4(),
                    actor_identifier=str(actor.id),
                    occurred_at=now,
                    action=f"recipe_candidate.{status}_batch",
                    object_type="managed_recipe_candidate_batch",
                    object_id=command_key,
                    reason=command.reason,
                    before_diff={},
                    after_diff={
                        "request_hash": request_hash,
                        "candidate_ids": [str(candidate.id) for candidate in changed],
                    },
                    related_version=None,
                    command_key=batch_key,
                )
            )
            self._commit()
        except Exception:
            self._rollback()
            raise
        return changed

    def export_catalog_csv(
        self, *, actor_user_id: uuid.UUID, query: CatalogListQuery
    ) -> bytes:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        drafts, total = self._repository.list_catalog_drafts(
            query=query, limit=MAX_EXPORT_ROWS + 1, offset=0
        )
        if total > MAX_EXPORT_ROWS or len(drafts) > MAX_EXPORT_ROWS:
            raise CatalogCsvInvalid("每次最多导出 10000 条，请缩小筛选范围。")
        return write_catalog_csv([self._catalog_response(draft) for draft in drafts])

    def catalog_csv_template(self, *, actor_user_id: uuid.UUID) -> bytes:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        return write_catalog_csv([])

    def preview_catalog_csv(
        self, *, actor_user_id: uuid.UUID, csv_text: str
    ) -> CatalogCsvPreview:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        return parse_catalog_csv(csv_text)

    def import_catalog_csv(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: CatalogCsvImportCommand,
        command_key: str,
    ) -> CatalogCsvImportResponse:
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        preview = parse_catalog_csv(command.csv_text)
        if preview.errors:
            raise CatalogCsvInvalid("文件存在错误，请修正全部错误后再导入。")
        # Reuse append-only draft commands for atomic batch replay; no second ledger.
        batch_key = hashlib.sha256(f"{actor.id}:{command_key}".encode()).hexdigest()
        request_hash = self._request_hash("csv_import", command.model_dump())
        self._repository.acquire_catalog_import_lock(batch_key)
        ids: list[uuid.UUID] = []
        try:
            for index, candidate in enumerate(preview.rows):
                row_key = f"csv:{batch_key}:{index}"
                replay = self._catalog_replay(row_key, request_hash)
                if replay is not None:
                    ids.append(replay.id)
                    continue
                payload = self._catalog_payload(candidate)
                now = self._now()
                draft = CatalogDraft(
                    id=uuid.uuid4(),
                    **payload,
                    revision=1,
                    created_at=now,
                    updated_at=now,
                )
                self._repository.add_catalog_draft(draft)
                self._record_catalog_mutation(
                    actor_identifier=str(actor.id),
                    draft=draft,
                    command_key=row_key,
                    operation="create",
                    reason=command.reason,
                    before={"revision": 0},
                    after=self._audit_catalog_payload(draft),
                    request_hash=request_hash,
                    revision_before=0,
                )
                ids.append(draft.id)
            self._commit_catalog_mutation()
        except Exception:
            self._rollback()
            raise
        return CatalogCsvImportResponse(imported_count=len(ids), draft_ids=ids)

    def create_catalog_draft(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: CatalogDraftCreateCommand,
        command_key: str,
    ) -> CatalogDraftResponse:
        """Create a mutable draft and its evidence in one service-owned transaction."""

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        payload = self._catalog_payload(command)
        replay = self._catalog_replay(
            command_key, self._request_hash("create", payload)
        )
        if replay is not None:
            return self._catalog_response(replay)
        now = self._now()
        draft = CatalogDraft(
            id=uuid.uuid4(), **payload, revision=1, created_at=now, updated_at=now
        )
        self._repository.add_catalog_draft(draft)
        self._record_catalog_mutation(
            actor_identifier=str(actor.id),
            draft=draft,
            command_key=command_key,
            operation="create",
            reason=command.reason,
            revision_before=0,
            before={field: None for field in payload} | {"revision": 0},
            after=self._audit_catalog_payload(draft),
            request_hash=self._request_hash("create", payload),
        )
        self._commit_catalog_mutation()
        return self._catalog_response(draft)

    def patch_catalog_draft(
        self,
        *,
        actor_user_id: uuid.UUID,
        draft_id: uuid.UUID,
        expected_revision: int,
        command: CatalogDraftPatchCommand,
        command_key: str,
    ) -> CatalogDraftResponse:
        """Apply an optimistic, server-diffed patch; no client diff is accepted."""

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        patch = self._catalog_payload(command, partial=True)
        replay = self._catalog_replay(
            command_key,
            self._request_hash(
                "patch",
                {
                    "draft_id": str(draft_id),
                    "expected_revision": expected_revision,
                    **patch,
                },
            ),
        )
        if replay is not None:
            return self._catalog_response(replay)
        draft = self._repository.get_catalog_draft(draft_id)
        if draft is None:
            raise KeyError("catalog draft not found")
        if expected_revision != draft.revision:
            raise CatalogDraftConflict("catalog draft revision does not match If-Match")
        before_all = self._audit_catalog_payload(draft)
        before = {
            name: before_all[name]
            for name in patch
            if before_all[name] != self._audit_scalar(patch[name])
        }
        if not before:
            raise CatalogDraftConflict("catalog draft patch makes no change")
        for name, value in patch.items():
            setattr(draft, name, value)
        revision_before = draft.revision
        draft.revision += 1
        draft.updated_at = self._now()
        after_all = self._audit_catalog_payload(draft)
        after = {name: after_all[name] for name in before}
        self._record_catalog_mutation(
            actor_identifier=str(actor.id),
            draft=draft,
            command_key=command_key,
            operation="patch",
            reason=command.reason,
            revision_before=revision_before,
            before=before,
            after=after,
            request_hash=self._request_hash(
                "patch",
                {
                    "draft_id": str(draft_id),
                    "expected_revision": expected_revision,
                    **patch,
                },
            ),
        )
        self._commit_catalog_mutation()
        return self._catalog_response(draft)

    def read_catalog_draft(
        self, *, actor_user_id: uuid.UUID, draft_id: uuid.UUID
    ) -> CatalogDraftResponse:
        """Return only the safe current projection after a fresh database RBAC check."""

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        draft = self._repository.get_catalog_draft(draft_id)
        if draft is None:
            raise KeyError("catalog draft not found")
        return self._catalog_response(draft)

    def preview_catalog_draft(
        self, *, actor_user_id: uuid.UUID, command: CatalogDraftPreviewCommand
    ) -> CatalogDraftPreviewResponse:
        """Compute display-safe diffs from the current database record, without mutation.

        The browser sends a candidate only.  It cannot select a base revision,
        declare an impact, or manufacture the before side of a difference.
        """

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        candidate = self._catalog_payload(command)
        draft = (
            self._repository.get_catalog_draft(command.draft_id)
            if command.draft_id is not None
            else None
        )
        if command.draft_id is not None and draft is None:
            raise KeyError("catalog draft not found")

        before = (
            self._audit_catalog_payload(draft)
            if draft is not None
            else {field: None for field in candidate}
        )
        diffs = [
            CatalogDraftFieldDiff(
                field=cast(CatalogDraftDiffField, field),
                before=cast(str | None, before[field]),
                after=str(self._audit_scalar(candidate[field])),
            )
            for field in candidate
            if before[field] != self._audit_scalar(candidate[field])
        ]
        if not diffs:
            raise CatalogDraftConflict("catalog draft preview makes no change")
        impacts = self._catalog_preview_impacts(diffs)
        return CatalogDraftPreviewResponse(
            draft_id=command.draft_id,
            base_revision=draft.revision if draft is not None else 0,
            field_diffs=diffs,
            impact_categories=impacts,
        )

    def preview_catalog_lifecycle(
        self, *, actor_user_id: uuid.UUID, draft_id: uuid.UUID
    ) -> CatalogLifecyclePreviewResponse:
        """Project only server-held immutable/current values for a risky command.

        The browser cannot select a historical baseline, claim publication
        eligibility, or send a diff.  Reading the current DB role before either
        projection prevents an expired or demoted session from receiving audit
        evidence.
        """

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        draft = self._repository.get_catalog_draft(draft_id)
        if draft is None:
            raise KeyError("catalog draft not found")
        publication = self._repository.get_active_catalog_publication(draft_id)
        publication_response: CatalogLifecyclePublicationResponse | None = None
        before: dict[str, object | None]
        if publication is None:
            before = {field: None for field in _CATALOG_LIFECYCLE_FIELDS}
            description = "首次发布后，新分析和新餐单将使用此不可变版本；历史已确认餐食不会被改写。"
        else:
            eligibility = self._repository.get_latest_catalog_eligibility(
                publication.id
            )
            if eligibility is None:
                raise CatalogDraftConflict(
                    "active publication has no eligibility state"
                )
            before = {
                field: publication.snapshot.get(field)
                for field in _CATALOG_LIFECYCLE_FIELDS
            }
            publication_response = CatalogLifecyclePublicationResponse(
                id=publication.id,
                draft_revision=publication.draft_revision,
                eligibility=cast(
                    Literal["eligible", "disqualified"], eligibility.status
                ),
                related_version=publication.content_hash,
            )
            description = (
                "发布后，新分析和新餐单将使用此不可变版本；历史已确认餐食不会被改写。"
            )

        candidate = self._publication_snapshot(draft)
        field_diffs = [
            CatalogLifecycleFieldDiff(
                field=field,
                before=self._lifecycle_scalar(before[field]),
                after=self._lifecycle_scalar(candidate[field]),
                change=self._lifecycle_change(before[field], candidate[field]),
            )
            for field in _CATALOG_LIFECYCLE_FIELDS
        ]
        return CatalogLifecyclePreviewResponse(
            draft=self._catalog_response(draft),
            publication=publication_response,
            field_diffs=field_diffs,
            impact=CatalogLifecycleImpact(
                affected_catalog_items=1, description=description
            ),
        )

    def review_catalog_draft(
        self,
        *,
        actor_user_id: uuid.UUID,
        draft_id: uuid.UUID,
        expected_revision: int,
        command: CatalogLifecycleCommand,
        command_key: str,
    ) -> CatalogPublicationResponse:
        """Freeze a server-derived candidate; publication may only consume this review."""

        self._repository.acquire_catalog_publication_lock(draft_id)
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        draft = self._repository.get_catalog_draft(draft_id, for_update=True)
        if draft is None:
            raise KeyError("catalog draft not found")
        if draft.revision != expected_revision:
            raise CatalogDraftConflict("catalog draft revision does not match If-Match")
        existing = self._repository.get_catalog_review(
            draft_id=draft_id, revision=draft.revision
        )
        if existing is not None:
            if existing.command_key != command_key.strip():
                raise CatalogDraftConflict("draft revision has already been reviewed")
            return self._review_response(existing)
        snapshot = self._publication_snapshot(draft)
        content_hash = self._content_hash(snapshot)
        review = self._repository.add_catalog_review(
            CatalogDraftReview(
                id=uuid.uuid4(),
                draft_id=draft.id,
                draft_revision=draft.revision,
                snapshot=snapshot,
                content_hash=content_hash,
                actor_identifier=str(actor.id),
                reason=command.reason,
                command_key=command_key.strip(),
                reviewed_at=self._now(),
            )
        )
        self._record_catalog_lifecycle_audit(
            actor_identifier=str(actor.id),
            action="catalog.review",
            object_id=str(draft.id),
            reason=command.reason,
            command_key=command_key,
            before={"revision": draft.revision},
            after={"content_hash": content_hash, "revision": draft.revision},
            related_version=content_hash,
        )
        self._commit_catalog_mutation()
        return self._review_response(review)

    def publish_catalog_draft(
        self,
        *,
        actor_user_id: uuid.UUID,
        draft_id: uuid.UUID,
        expected_revision: int,
        command: CatalogLifecycleCommand,
        command_key: str,
    ) -> CatalogPublicationResponse:
        """Atomically advance one pointer to a reviewed immutable publication."""

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_catalog_publication_lock(draft_id)
        replay = self._repository.get_catalog_publication_command(command_key.strip())
        if replay is not None:
            return self._publication_response(replay, eligibility="eligible")
        draft = self._repository.get_catalog_draft(draft_id, for_update=True)
        if draft is None:
            raise KeyError("catalog draft not found")
        if draft.revision != expected_revision:
            raise CatalogDraftConflict("catalog draft revision does not match If-Match")
        if draft.authorization_status != "authorized":
            raise CatalogDraftConflict("only authorized drafts may be published")
        review = self._repository.get_catalog_review(
            draft_id=draft_id, revision=draft.revision
        )
        if review is None:
            raise CatalogDraftConflict(
                "a current immutable review is required before publication"
            )
        snapshot = self._publication_snapshot(draft)
        content_hash = self._content_hash(snapshot)
        if content_hash != review.content_hash or snapshot != review.snapshot:
            raise CatalogDraftConflict("draft changed after review")
        publication = self._repository.add_catalog_publication(
            CatalogPublication(
                id=uuid.uuid4(),
                draft_id=draft.id,
                review_id=review.id,
                draft_revision=draft.revision,
                snapshot=dict(review.snapshot),
                content_hash=review.content_hash,
                actor_identifier=str(actor.id),
                reason=command.reason,
                command_key=command_key.strip(),
                published_at=self._now(),
            )
        )
        self._repository.advance_active_catalog_publication(
            draft_id=draft.id, publication_id=publication.id
        )
        self._repository.add_catalog_eligibility(
            CatalogPublicationEligibility(
                id=uuid.uuid4(),
                publication_id=publication.id,
                status="eligible",
                actor_identifier=str(actor.id),
                reason=command.reason,
                command_key=f"eligibility-{command_key.strip()}",
                occurred_at=self._lifecycle_now(),
            )
        )
        self._record_catalog_lifecycle_audit(
            actor_identifier=str(actor.id),
            action="catalog.publish",
            object_id=str(publication.id),
            reason=command.reason,
            command_key=command_key,
            before={"draft_revision": draft.revision},
            after={
                "content_hash": publication.content_hash,
                "publication_id": str(publication.id),
            },
            related_version=publication.content_hash,
        )
        self._commit_catalog_mutation()
        return self._publication_response(publication, eligibility="eligible")

    def disqualify_catalog_publication(
        self,
        *,
        actor_user_id: uuid.UUID,
        publication_id: uuid.UUID,
        command: CatalogLifecycleCommand,
        command_key: str,
    ) -> CatalogPublicationResponse:
        """Append a blocking future-use overlay; historical meal snapshots are untouched."""

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        publication = self._repository.get_catalog_publication(publication_id)
        if publication is None:
            raise KeyError("catalog publication not found")
        self._repository.acquire_catalog_publication_lock(publication.draft_id)
        replay = self._repository.get_catalog_eligibility_command(command_key.strip())
        if replay is not None:
            return self._publication_response(
                publication,
                eligibility=cast(Literal["eligible", "disqualified"], replay.status),
            )
        self._repository.add_catalog_eligibility(
            CatalogPublicationEligibility(
                id=uuid.uuid4(),
                publication_id=publication.id,
                status="disqualified",
                actor_identifier=str(actor.id),
                reason=command.reason,
                command_key=command_key.strip(),
                occurred_at=self._lifecycle_now(),
            )
        )
        self._record_catalog_lifecycle_audit(
            actor_identifier=str(actor.id),
            action="catalog.disqualify",
            object_id=str(publication.id),
            reason=command.reason,
            command_key=command_key,
            before={"eligibility": "eligible"},
            after={"eligibility": "disqualified"},
            related_version=publication.content_hash,
        )
        self._commit_catalog_mutation()
        return self._publication_response(publication, eligibility="disqualified")

    def _record_catalog_mutation(
        self,
        *,
        actor_identifier: str,
        draft: CatalogDraft,
        command_key: str,
        operation: str,
        reason: str,
        revision_before: int,
        before: dict[str, object],
        after: dict[str, object],
        request_hash: str,
    ) -> None:
        """Persist only server-derived scalars and a historical revision snapshot."""

        now = self._now()
        normalized_command_key = self._normalized_command_fields(
            action=f"catalog_draft.{operation}",
            object_type="catalog_draft",
            object_id=str(draft.id),
            reason=reason,
            command_key=command_key,
        )["command_key"]
        change_set = self._repository.add_catalog_draft_change_set(
            CatalogDraftChangeSet(
                id=uuid.uuid4(),
                draft_id=draft.id,
                actor_identifier=actor_identifier,
                occurred_at=now,
                reason=reason.strip(),
                command_key=normalized_command_key,
                request_hash=request_hash,
                revision_before=revision_before,
                revision_after=draft.revision,
                before_diff=self._safe_diff(before),
                after_diff=self._safe_diff(after),
            )
        )
        self._repository.add_catalog_draft_revision(
            CatalogDraftRevision(
                id=uuid.uuid4(),
                draft_id=draft.id,
                change_set_id=change_set.id,
                revision=draft.revision,
                snapshot=self._audit_catalog_payload(draft),
                created_at=now,
            )
        )
        self._repository.add_audit_event(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_identifier=actor_identifier,
                occurred_at=now,
                action=f"catalog_draft.{operation}",
                object_type="catalog_draft",
                object_id=str(draft.id),
                reason=reason.strip(),
                before_diff=self._safe_diff(before),
                after_diff=self._safe_diff(after),
                related_version=None,
                command_key=f"audit-{normalized_command_key}",
            )
        )

    def _catalog_replay(
        self, command_key: str, request_hash: str
    ) -> CatalogDraft | None:
        existing = self._repository.get_catalog_draft_command(command_key.strip())
        if existing is None:
            return None
        if existing.request_hash != request_hash:
            raise CatalogDraftConflict(
                "Idempotency-Key was reused for a different command"
            )
        draft = self._repository.get_catalog_draft(existing.draft_id)
        if draft is None:
            raise CatalogDraftConflict("idempotent command has no draft")
        return draft

    def _commit_catalog_mutation(self) -> None:
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise

    @staticmethod
    def _catalog_payload(
        command: CatalogDraftCreateCommand
        | CatalogDraftPatchCommand
        | CatalogDraftPreviewCommand,
        *,
        partial: bool = False,
    ) -> dict[str, object]:
        excluded = {"reason", "draft_id"}
        raw = command.model_dump(exclude=excluded, exclude_none=partial)
        if "source_url" in raw:
            raw["source_url"] = str(raw["source_url"])
        return raw

    @staticmethod
    def _audit_scalar(value: object) -> object:
        if isinstance(value, list):
            return ", ".join(value)
        return str(value) if hasattr(value, "as_tuple") else value

    @classmethod
    def _audit_catalog_payload(cls, draft: CatalogDraft) -> dict[str, object]:
        return {
            "canonical_name": draft.canonical_name,
            "aliases": cls._audit_scalar(draft.aliases),
            "energy_kcal_per_100g": cls._audit_scalar(draft.energy_kcal_per_100g),
            "protein_g_per_100g": cls._audit_scalar(draft.protein_g_per_100g),
            "fat_g_per_100g": cls._audit_scalar(draft.fat_g_per_100g),
            "carbohydrate_g_per_100g": cls._audit_scalar(draft.carbohydrate_g_per_100g),
            "source_name": draft.source_name,
            "source_url": draft.source_url,
            "authorization_status": draft.authorization_status,
            "revision": draft.revision,
        }

    @staticmethod
    def _publication_snapshot(draft: CatalogDraft) -> dict[str, object]:
        """Keep typed content immutable; audit diffs intentionally remain scalar-only."""

        return {
            "canonical_name": draft.canonical_name,
            "aliases": list(draft.aliases),
            "energy_kcal_per_100g": str(draft.energy_kcal_per_100g),
            "protein_g_per_100g": str(draft.protein_g_per_100g),
            "fat_g_per_100g": str(draft.fat_g_per_100g),
            "carbohydrate_g_per_100g": str(draft.carbohydrate_g_per_100g),
            "source_name": draft.source_name,
            "source_url": draft.source_url,
            "authorization_status": draft.authorization_status,
            "revision": draft.revision,
        }

    @staticmethod
    def _catalog_preview_impacts(
        diffs: list[CatalogDraftFieldDiff],
    ) -> list[
        Literal[
            "catalog_identity",
            "nutrition_per_100g",
            "source_evidence",
            "authorization_status",
        ]
    ]:
        """Classify only known catalog fields; no raw request payload reaches the UI."""

        changed = {diff.field for diff in diffs}
        impacts: list[
            Literal[
                "catalog_identity",
                "nutrition_per_100g",
                "source_evidence",
                "authorization_status",
            ]
        ] = []
        if changed & {"canonical_name", "aliases"}:
            impacts.append("catalog_identity")
        if changed & {
            "energy_kcal_per_100g",
            "protein_g_per_100g",
            "fat_g_per_100g",
            "carbohydrate_g_per_100g",
        }:
            impacts.append("nutrition_per_100g")
        if changed & {"source_name", "source_url"}:
            impacts.append("source_evidence")
        if "authorization_status" in changed:
            impacts.append("authorization_status")
        return impacts

    @staticmethod
    def _lifecycle_scalar(value: object | None) -> str | None:
        return None if value is None else str(AdminService._audit_scalar(value))

    @staticmethod
    def _lifecycle_change(
        before: object | None, after: object | None
    ) -> Literal["added", "modified", "removed", "unchanged"]:
        if before is None and after is not None:
            return "added"
        if before is not None and after is None:
            return "removed"
        return (
            "unchanged"
            if AdminService._lifecycle_scalar(before)
            == AdminService._lifecycle_scalar(after)
            else "modified"
        )

    @staticmethod
    def _request_hash(operation: str, payload: dict[str, object]) -> str:
        normalized = json.dumps(
            {"operation": operation, "payload": payload},
            sort_keys=True,
            default=str,
            separators=(",", ":"),
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _catalog_response(draft: CatalogDraft) -> CatalogDraftResponse:
        return CatalogDraftResponse(
            id=draft.id,
            canonical_name=draft.canonical_name,
            aliases=list(draft.aliases),
            energy_kcal_per_100g=draft.energy_kcal_per_100g,
            protein_g_per_100g=draft.protein_g_per_100g,
            fat_g_per_100g=draft.fat_g_per_100g,
            carbohydrate_g_per_100g=draft.carbohydrate_g_per_100g,
            source_name=draft.source_name,
            source_url=draft.source_url,
            authorization_status=cast(
                Literal["authorized", "pending", "revoked"], draft.authorization_status
            ),
            revision=draft.revision,
        )

    @staticmethod
    def _recipe_candidate_response(
        candidate: ManagedRecipeCandidate,
    ) -> RecipeCandidateResponse:
        food = candidate.food_catalog_item
        return RecipeCandidateResponse(
            id=candidate.id,
            catalog_food_name=food.canonical_name,
            meal_slot=cast(
                Literal["breakfast", "lunch", "dinner", "snack"], candidate.meal_slot
            ),
            portion_grams=candidate.portion_grams,
            portion_description=candidate.portion_description,
            method_tags=tuple(tag for tag in candidate.method_tags.split("|") if tag),
            flavour_tags=tuple(tag for tag in candidate.flavour_tags.split("|") if tag),
            status=cast(Literal["pending", "enabled", "disabled"], candidate.status),
            revision=candidate.revision,
        )

    @staticmethod
    def _content_hash(snapshot: dict[str, object]) -> str:
        """Hash the exact server-derived snapshot, never a client-provided diff."""

        normalized = json.dumps(
            snapshot, sort_keys=True, default=str, separators=(",", ":")
        )
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _lifecycle_now(self) -> datetime:
        """Give append-only overlay events a deterministic total order per command flow."""

        current = self._now()
        if self._last_lifecycle_at is not None and current <= self._last_lifecycle_at:
            current = self._last_lifecycle_at + timedelta(microseconds=1)
        self._last_lifecycle_at = current
        return current

    @staticmethod
    def _review_response(review: CatalogDraftReview) -> CatalogPublicationResponse:
        return CatalogPublicationResponse(
            id=review.id,
            draft_id=review.draft_id,
            draft_revision=review.draft_revision,
            content_hash=review.content_hash,
            eligibility="eligible",
        )

    @staticmethod
    def _publication_response(
        publication: CatalogPublication,
        *,
        eligibility: Literal["eligible", "disqualified"],
    ) -> CatalogPublicationResponse:
        return CatalogPublicationResponse(
            id=publication.id,
            draft_id=publication.draft_id,
            draft_revision=publication.draft_revision,
            content_hash=publication.content_hash,
            eligibility=eligibility,
        )

    def _record_catalog_lifecycle_audit(
        self,
        *,
        actor_identifier: str,
        action: str,
        object_id: str,
        reason: str,
        command_key: str,
        before: dict[str, object],
        after: dict[str, object],
        related_version: str,
    ) -> None:
        self._repository.add_audit_event(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_identifier=actor_identifier,
                occurred_at=self._now(),
                action=action,
                object_type="catalog_publication",
                object_id=object_id,
                reason=reason.strip(),
                before_diff=self._safe_diff(before),
                after_diff=self._safe_diff(after),
                related_version=related_version,
                command_key=f"audit-{command_key.strip()}",
            )
        )

    def _promotion_target(self, target_user_id: uuid.UUID) -> User:
        target = self._repository.get_user_for_update(target_user_id)
        if target is None or not target.is_active or target.email_verified_at is None:
            raise AdminRoleChangeDenied("target must be an active verified user")
        if target.role != UserRole.USER.value:
            raise AdminRoleChangeDenied("target is already an administrator")
        return target

    def _commit_promotion(
        self, *, actor_identifier: str, target: User, reason: str
    ) -> AdminRoleAudit:
        normalized_reason = reason.strip()
        if not normalized_reason:
            raise AdminRoleChangeDenied("a non-empty reason is required")

        previous_role = target.role
        target.role = UserRole.ADMIN.value
        target.updated_at = self._now()
        audit = self._repository.add_audit(
            AdminRoleAudit(
                id=uuid.uuid4(),
                actor_identifier=actor_identifier,
                target_user_id=target.id,
                before_role=previous_role,
                after_role=UserRole.ADMIN.value,
                occurred_at=self._now(),
                reason=normalized_reason,
            )
        )
        self._repository.add_audit_event(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_identifier=actor_identifier,
                occurred_at=self._now(),
                action="role.promote",
                object_type="user",
                object_id=str(target.id),
                reason=normalized_reason,
                before_diff={"role": previous_role},
                after_diff={"role": UserRole.ADMIN.value},
                related_version=None,
                command_key=f"role-promote-{uuid.uuid4()}",
            )
        )
        try:
            self._commit()
        except Exception:
            # The role mutation and audit row share one session transaction: neither
            # may escape if persistence rejects either write.
            self._rollback()
            raise
        return audit

    @staticmethod
    def _normalized_command_fields(**values: str) -> dict[str, str]:
        normalized = {key: value.strip() for key, value in values.items()}
        if any(not value for value in normalized.values()):
            raise AdminRoleChangeDenied(
                "action, object, reason and idempotency key must be non-empty"
            )
        return normalized

    @staticmethod
    def _safe_diff(value: dict[str, object]) -> dict[str, object]:
        """Require a shallow, scalar field diff rather than an opaque payload blob."""

        if not value or any(
            not isinstance(key, str) or not key.strip() for key in value
        ):
            raise AdminRoleChangeDenied("audit diff must contain named fields")
        prohibited = {
            "email",
            "password",
            "secret",
            "token",
            "image",
            "base64",
            "provider",
            "state",
            "prompt",
        }
        if any(any(term in key.casefold() for term in prohibited) for key in value):
            raise AdminRoleChangeDenied(
                "audit diff contains a prohibited sensitive field"
            )
        if any(
            isinstance(item, (dict, list, tuple, set, bytes)) for item in value.values()
        ):
            raise AdminRoleChangeDenied("audit diff values must be scalar")
        return dict(value)

    @staticmethod
    def _audit_response(event: AdminAuditEvent) -> AdminAuditEventResponse:
        return AdminAuditEventResponse(
            id=event.id,
            actor_identifier=event.actor_identifier,
            occurred_at=event.occurred_at,
            action=event.action,
            object_type=event.object_type,
            object_id=event.object_id,
            reason=event.reason,
            before=event.before_diff,
            after=event.after_diff,
            related_version=event.related_version,
            command_key=event.command_key,
        )

    def _run_response(
        self, run: AgentRun, *, include_invocations: bool
    ) -> AdminRunDetailResponse:
        # Do not add User, Event, image, Provider, or graph State fields here: this
        # boundary is the explicit ledger minimisation gate for admin UI consumers.
        invocations = (
            self._repository.list_run_invocations(run.id) if include_invocations else []
        )
        return AdminRunDetailResponse(
            id=run.id,
            status=cast(Literal["completed", "failed", "limit_reached"], run.status),
            graph_version=run.graph_version,
            model_provider=run.model_provider,
            model_version=run.model_version,
            graph_steps=run.graph_steps,
            model_calls=run.model_calls,
            tool_calls=run.tool_calls,
            elapsed_ms=run.elapsed_ms,
            estimated_cost_usd=run.estimated_cost_usd,
            failure_code=run.failure_code,
            finished_at=cast(datetime, run.finished_at),
            invocations=[
                self._invocation_response(invocation) for invocation in invocations
            ],
        )

    @staticmethod
    def _invocation_response(invocation: AgentInvocation) -> AdminRunInvocationResponse:
        return AdminRunInvocationResponse(
            node_name=invocation.node_name,
            status=cast(
                Literal["prepared", "completed", "failed", "outcome_unknown"],
                invocation.status,
            ),
            attempt=invocation.attempt,
            cost_usd=invocation.cost_usd,
            failure_code=invocation.failure_code,
            safe_result_digest=invocation.safe_result_digest,
        )

    def _encode_run_cursor(self, run: AgentRun) -> str:
        if self._cursor_secret is None or run.finished_at is None:
            raise AdminRunCursorInvalid("run cursor is unavailable")
        payload = f"{run.finished_at.isoformat()}|{run.id}".encode("utf-8")
        signature = hmac.new(self._cursor_secret, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(payload + b"." + signature).decode("ascii")

    def _decode_run_cursor(self, cursor: str) -> tuple[datetime, uuid.UUID]:
        if self._cursor_secret is None:
            raise AdminRunCursorInvalid("run cursor is unavailable")
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
            payload, signature = decoded.rsplit(b".", 1)
            expected = hmac.new(self._cursor_secret, payload, hashlib.sha256).digest()
            finished_raw, run_raw = payload.decode("utf-8").split("|", 1)
            finished_at, run_id = (
                datetime.fromisoformat(finished_raw),
                uuid.UUID(run_raw),
            )
        except (ValueError, UnicodeDecodeError, TypeError):
            raise AdminRunCursorInvalid("invalid run cursor") from None
        if finished_at.tzinfo is None or not hmac.compare_digest(signature, expected):
            raise AdminRunCursorInvalid("invalid run cursor")
        return finished_at, run_id

    def _encode_cursor(self, event: AdminAuditEvent) -> str:
        if self._cursor_secret is None:
            raise AdminAuditCursorInvalid("audit cursor secret is unavailable")
        payload = f"{event.occurred_at.isoformat()}|{event.id}".encode("utf-8")
        signature = hmac.new(self._cursor_secret, payload, hashlib.sha256).digest()
        return base64.urlsafe_b64encode(payload + b"." + signature).decode("ascii")

    def _decode_cursor(self, cursor: str) -> tuple[datetime, uuid.UUID]:
        if self._cursor_secret is None:
            raise AdminAuditCursorInvalid("audit cursor secret is unavailable")
        try:
            decoded = base64.urlsafe_b64decode(cursor.encode("ascii"))
            payload, signature = decoded.rsplit(b".", 1)
            expected = hmac.new(self._cursor_secret, payload, hashlib.sha256).digest()
            occurred_raw, event_raw = payload.decode("utf-8").split("|", 1)
            occurred_at = datetime.fromisoformat(occurred_raw)
            event_id = uuid.UUID(event_raw)
        except (ValueError, UnicodeDecodeError, TypeError):
            raise AdminAuditCursorInvalid("invalid audit cursor") from None
        if occurred_at.tzinfo is None or not hmac.compare_digest(signature, expected):
            raise AdminAuditCursorInvalid("invalid audit cursor")
        return occurred_at, event_id
