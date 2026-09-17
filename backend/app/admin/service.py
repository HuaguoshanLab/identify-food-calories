"""Admin authorization and role-elevation policy over a repository port."""

from __future__ import annotations

import uuid
import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
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
from app.nutrition.search_models import (
    CatalogEmbeddingJob,
    CatalogVectorSpaceActivationApproval,
    CatalogSearchRelationEvidence,
    CatalogSearchName,
    CatalogSearchVersion,
    CatalogVectorSpace,
    CatalogVectorSpaceBuild,
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
from app.admin.recipe_classification import classify_recipe, PURPOSE_LABELS, ROLE_LABELS, TAG_LABELS
from app.admin.schemas import (
    RecipeClassificationCommand, RecipeClassificationPreviewCommand, RecipeClassificationPreview, RecipeClassificationEntry,
    AdminAuditEventResponse,
    AdminAuditPageResponse,
    AdminRunDetailResponse,
    AdminRunInvocationResponse,
    AdminRunMetricsResponse,
    AdminRunPageResponse,
    AdminRoleChangeResponse,
    AdminRoleListResponse,
    AdminRoleResponse,
    AdminUserPageResponse,
    AdminUserQuery,
    AdminUserResponse,
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
    CatalogEmbeddingJobResponse,
    CatalogEmbeddingRetryCommand,
    CatalogEmbeddingRetryResponse,
    CatalogSearchIndexBackfillCommand,
    CatalogSearchIndexBackfillResponse,
    CatalogEmbeddingStatusResponse,
    CatalogVectorSpaceBuildCommand,
    CatalogVectorSpaceBuildResponse,
    CatalogVectorSpaceBuildPageResponse,
    CatalogVectorSpaceBuildRetryCommand,
    CatalogVectorSpaceBuildRetryResponse,
    CatalogVectorSpaceBuildStatusResponse,
    CatalogRelationEvidenceCommand,
    CatalogRelationEvidenceResponse,
    CatalogRelationEvidenceRevokeCommand,
    RuntimeConfigCommand,
    RuntimeConfigResponse,
    RecipeCandidateBulkCommand,
    RecipeClassificationResponse,
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


CatalogEmbeddingRetryConflict = CatalogDraftConflict


CatalogVectorSpaceBuildConflict = CatalogDraftConflict


CatalogVectorSpaceActivationConflict = CatalogDraftConflict


CatalogRelationEvidenceConflict = CatalogDraftConflict


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

_PHASE063_RELEASE_SPACE = {
    # The evaluator remains deterministic and uses Fake vectors, but the
    # release it certifies is deliberately the only production retrieval
    # identity.  A completed build for this space proves that every frozen
    # catalog name was actually sent through the configured DashScope adapter;
    # the evaluator proves the policy around those vectors separately.
    "embedding_model": "text-embedding-v4",
    "embedding_dimension": 1024,
    "adapter_version": "dashscope-text-embedding-v4-1024.v1",
    "retrieval_version": "retrieval-06-3-v1",
}


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

    def list_users(self, *, actor_user_id: uuid.UUID, query: AdminUserQuery) -> AdminUserPageResponse:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        rows, total = self._repository.list_users(query=query, limit=query.page_size, offset=(query.page - 1) * query.page_size)
        return AdminUserPageResponse(
            items=[AdminUserResponse(id=row.id, email=row.email, email_verified_at=row.email_verified_at, is_active=row.is_active, role=cast(Literal["user", "admin"], row.role), created_at=row.created_at, updated_at=row.updated_at) for row in rows],
            total=total, page=query.page, page_size=query.page_size,
        )

    def list_roles(self, *, actor_user_id: uuid.UUID) -> AdminRoleListResponse:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        counts = self._repository.count_users_by_role()
        return AdminRoleListResponse(items=[
            AdminRoleResponse(role="admin", label="管理员", description="可访问独立管理后台并执行受审计的管理操作。", account_count=counts.get("admin", 0), permissions=["查看后台数据", "管理营养目录和菜谱", "查看运行与操作审计", "管理管理员角色"]),
            AdminRoleResponse(role="user", label="普通用户", description="只能访问自己的饮食分析、记录、计划和个人资料。", account_count=counts.get("user", 0), permissions=["使用用户端功能", "管理自己的数据"]),
        ])

    def change_user_role(self, *, actor_user_id: uuid.UUID, target_user_id: uuid.UUID, after_role: UserRole, reason: str, command_key: str) -> AdminRoleChangeResponse:
        normalized_reason = reason.strip()
        if not normalized_reason or not command_key.strip():
            raise AdminRoleChangeDenied("a non-empty reason and command key are required")
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_bootstrap_lock()
        actor = self._repository.get_user_for_update(actor_user_id)
        if actor is None or not actor.is_active or actor.role != UserRole.ADMIN.value:
            raise AdminPermissionDenied("database role does not permit this operation")
        action = "role.promote" if after_role is UserRole.ADMIN else "role.demote"
        existing = self._repository.get_audit_event_by_command_key(command_key)
        if existing is not None:
            if existing.actor_identifier != str(actor.id) or existing.action != action or existing.object_id != str(target_user_id) or existing.reason != normalized_reason or existing.after_diff != {"role": after_role.value}:
                raise AdminRoleChangeDenied("role command conflict")
            return AdminRoleChangeResponse(audit_id=existing.id, target_user_id=target_user_id, before_role=cast(Literal["user", "admin"], existing.before_diff["role"]), after_role=after_role.value, occurred_at=existing.occurred_at)
        if actor_user_id == target_user_id:
            raise AdminRoleChangeDenied("an actor cannot change its own role")
        target = self._repository.get_user_for_update(target_user_id)
        if target is None:
            raise KeyError(target_user_id)
        if target.role == after_role.value:
            raise AdminRoleChangeDenied("target already has requested role")
        if after_role is UserRole.ADMIN and (not target.is_active or target.email_verified_at is None):
            raise AdminRoleChangeDenied("target must be an active verified user")
        if after_role is UserRole.USER and self._repository.count_active_admins() <= 1:
            raise AdminRoleChangeDenied("the last active administrator cannot be demoted")
        before_role = target.role
        occurred_at = self._now()
        target.role = after_role.value
        target.updated_at = occurred_at
        self._repository.add_audit(AdminRoleAudit(id=uuid.uuid4(), actor_identifier=str(actor.id), target_user_id=target.id, before_role=before_role, after_role=after_role.value, occurred_at=occurred_at, reason=normalized_reason))
        event = self._repository.add_audit_event(AdminAuditEvent(id=uuid.uuid4(), actor_identifier=str(actor.id), occurred_at=occurred_at, action=action, object_type="user", object_id=str(target.id), reason=normalized_reason, before_diff={"role": before_role}, after_diff={"role": after_role.value}, related_version=None, command_key=command_key.strip()))
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        return AdminRoleChangeResponse(audit_id=event.id, target_user_id=target.id, before_role=cast(Literal["user", "admin"], before_role), after_role=after_role.value, occurred_at=occurred_at)

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
        actor: str | None = None,
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
            actor_identifier=self._audit_actor_identifier(actor),
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
            for row_number, row in enumerate(preview.rows, start=2):
                foods = self._repository.resolve_qualified_food_by_name(
                    row.catalog_food_name
                )
                if len(foods) != 1:
                    raise RecipeCandidateCsvInvalid(
                        f"第 {row_number} 行“{row.catalog_food_name}”在当前合格目录中"
                        "不存在或营养值不一致，无法自动创建或猜测关联。"
                    )
                food = foods[0]
                candidate = ManagedRecipeCandidate(
                    id=uuid.uuid4(),
                    food_catalog_item_id=(
                        food.id if food.source_kind == "food_catalog_item" else None
                    ),
                    catalog_publication_id=(
                        food.id if food.source_kind == "catalog_publication" else None
                    ),
                    catalog_food_name=food.canonical_name,
                    nutrition_catalog_version=food.nutrition_catalog_version,
                    meal_slot=row.meal_slot,
                    classification=row.classification.model_dump(mode="json") if row.classification else None,
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
                            "nutrition_item_id": str(food.id),
                            "nutrition_catalog_version": food.nutrition_catalog_version,
                            "meal_slot": candidate.meal_slot,
                            "classification": candidate.classification,
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

    def preview_recipe_classification(self, *, actor_user_id, command: RecipeClassificationPreviewCommand):
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        entries = []
        skipped = 0
        for identity in sorted(command.ids):
            row = self._repository.get_recipe_candidate(identity)
            if row is None or row.deleted_at is not None:
                raise KeyError("recipe candidate not found")
            if row.classification is not None and not (command.review_unknown and row.classification.get("role") == "unknown" and classify_recipe(row.catalog_food_name).role != "unknown"):
                skipped += 1
                continue
            entries.append(RecipeClassificationEntry(id=row.id, revision=row.revision,
                catalog_food_name=row.catalog_food_name, classification=classify_recipe(row.catalog_food_name)))
        return RecipeClassificationPreview(entries=entries, skipped_count=skipped)

    def backfill_recipe_classification(self, *, actor_user_id, command: RecipeClassificationCommand, command_key: str, review: bool = False):
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        operation = "recipe-classification-review" if review else "recipe-classification"
        batch_key = operation + ":" + hashlib.sha256(f"{actor.id}:{command_key}".encode()).hexdigest()
        request_hash = self._request_hash(operation, command.model_dump())
        self._repository.acquire_recipe_candidate_lock(batch_key)
        replay = self._repository.get_audit_event_by_command_key(batch_key)
        if replay is not None:
            if replay.after_diff.get("request_hash") != request_hash:
                raise RecipeCandidateConflict("command changed")
            return RecipeClassificationResponse(changed_count=len(replay.after_diff["candidate_ids"]))
        try:
            pairs = [(entry, self._repository.get_recipe_candidate(entry.id, for_update=True))
                     for entry in sorted(command.entries, key=lambda entry: entry.id)]
            # Validate the entire preview before mutating any member of the batch.
            for entry, row in pairs:
                if row is None or row.deleted_at is not None:
                    raise KeyError("recipe candidate not found")
                if row.revision != entry.revision or (not review and row.classification is not None and not (command.review_unknown and row.classification.get("role") == "unknown")) or row.catalog_food_name != entry.catalog_food_name:
                    raise RecipeCandidateConflict("classification preview is stale")
                if review and entry.classification.basis != "admin_review":
                    raise RecipeCandidateConflict("manual review requires review evidence")
                if not review and entry.classification != classify_recipe(row.catalog_food_name):
                    raise RecipeCandidateConflict("classification preview changed")
            now = self._now()
            for entry, row in pairs:
                before = {"classification": row.classification, "revision": row.revision}
                if row.classification is not None:
                    before.update(classification_purpose=PURPOSE_LABELS[row.classification["purpose"]],
                                  classification_role=ROLE_LABELS[row.classification["role"]],
                                  classification_tags="、".join(TAG_LABELS[tag] for tag in row.classification["ingredient_tags"]) or "待确认")
                row.classification = entry.classification.model_dump(mode="json")
                row.revision += 1
                row.updated_at = now
                self._repository.add_audit_event(AdminAuditEvent(id=uuid.uuid4(), actor_identifier=str(actor.id), occurred_at=now,
                    action="recipe_candidate.classified", object_type="managed_recipe_candidate", object_id=str(row.id), reason=command.reason,
                    before_diff=before, after_diff={"classification": row.classification, "revision": row.revision, "classification_purpose": PURPOSE_LABELS[entry.classification.purpose], "classification_role": ROLE_LABELS[entry.classification.role], "classification_tags": "、".join(TAG_LABELS[tag] for tag in entry.classification.ingredient_tags) or "待确认"},
                    related_version="recipe-classification.v1", command_key=f"{batch_key}:{row.id}"))
            ids = [str(entry.id) for entry, _ in pairs]
            self._repository.add_audit_event(AdminAuditEvent(id=uuid.uuid4(), actor_identifier=str(actor.id), occurred_at=now,
                action="recipe_candidate.classified_batch", object_type="managed_recipe_candidate_batch", object_id=command_key, reason=command.reason,
                before_diff={}, after_diff={"candidate_ids": ids, "request_hash": request_hash}, related_version="recipe-classification.v1", command_key=batch_key))
            self._commit()
        except Exception:
            self._rollback()
            raise
        return RecipeClassificationResponse(changed_count=len(ids))

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
        self._enqueue_catalog_embedding_jobs(publication)
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

    def get_catalog_embedding_status(
        self, *, actor_user_id: uuid.UUID, publication_id: uuid.UUID
    ) -> CatalogEmbeddingStatusResponse:
        """Project publication work without leaking controlled names or provider data."""

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        if self._repository.get_catalog_publication(publication_id) is None:
            raise KeyError("catalog publication not found")
        return self._catalog_embedding_status(publication_id)

    def backfill_catalog_search_index(self, *, actor_user_id: uuid.UUID, command: CatalogSearchIndexBackfillCommand, command_key: str) -> CatalogSearchIndexBackfillResponse:
        """Repair derived names from immutable active publication snapshots only."""
        key = command_key.strip()
        if not key:
            raise CatalogVectorSpaceBuildConflict("an idempotency key is required")
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        audit_key = f"catalog-search-index-backfill:{key}"
        self._repository.acquire_catalog_search_index_backfill_lock()
        replay = self._repository.get_audit_event_by_command_key(audit_key)
        if replay is not None:
            if replay.action != "catalog.search_index.backfill" or replay.actor_identifier != str(actor.id) or replay.reason != command.reason:
                raise CatalogVectorSpaceBuildConflict("idempotency key was reused for a different search-index backfill")
            after = replay.after_diff
            return CatalogSearchIndexBackfillResponse(audit_id=replay.id, publication_count=int(after["publication_count"]), name_count=int(after["name_count"]), embedding_job_count=int(after["embedding_job_count"]))
        now = self._now()
        spaces = self._repository.list_active_catalog_vector_spaces()
        publications = names = jobs_count = 0
        for publication in self._repository.list_current_qualified_catalog_publications():
            version = self._repository.get_catalog_search_version(publication_id=publication.id, content_hash=publication.content_hash)
            if version is None:
                version = self._repository.add_catalog_search_version(CatalogSearchVersion(id=uuid.uuid4(), publication_id=publication.id, content_hash=publication.content_hash, created_at=now))
            desired: dict[str, tuple[str, Literal["canonical", "controlled_alias"]]] = {}
            for display_name, kind in [(str(publication.snapshot["canonical_name"]), "canonical"), *((str(alias), "controlled_alias") for alias in publication.snapshot["aliases"])]:
                normalized = " ".join(display_name.casefold().split())
                if normalized:
                    desired.setdefault(normalized, (display_name, cast(Literal["canonical", "controlled_alias"], kind)))
            existing = {row.normalized_name for row in self._repository.list_catalog_search_names_for_publication(publication.id)}
            created = self._repository.add_catalog_search_names([CatalogSearchName(id=uuid.uuid4(), publication_id=publication.id, search_version_id=version.id, display_name=display, normalized_name=normalized, name_kind=kind, created_at=now) for normalized, (display, kind) in sorted(desired.items()) if normalized not in existing])
            if created:
                publications += 1
                names += len(created)
            new_jobs = [CatalogEmbeddingJob(id=uuid.uuid4(), publication_id=publication.id, name_id=name.id, vector_space_id=space.id, status="pending", attempt_count=0, max_attempts=5, not_before=now, lease_owner=None, leased_at=None, lease_expires_at=None, last_error_code=None, created_at=now, updated_at=now) for name in created for space in spaces]
            self._repository.add_catalog_embedding_jobs(new_jobs)
            jobs_count += len(new_jobs)
        audit = self._repository.add_audit_event(AdminAuditEvent(id=uuid.uuid4(), actor_identifier=str(actor.id), occurred_at=now, action="catalog.search_index.backfill", object_type="catalog_search_index", object_id="current-qualified-publications", reason=command.reason, before_diff={}, after_diff={"publication_count": publications, "name_count": names, "embedding_job_count": jobs_count}, related_version="catalog-search-index.v1", command_key=audit_key))
        self._commit_catalog_mutation()
        return CatalogSearchIndexBackfillResponse(audit_id=audit.id, publication_count=publications, name_count=names, embedding_job_count=jobs_count)

    def create_catalog_vector_space_build(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: CatalogVectorSpaceBuildCommand,
        command_key: str,
    ) -> CatalogVectorSpaceBuildResponse:
        """Freeze current eligible names before workers are allowed to spend provider cost.

        The build is deliberately separate from activation and completion evidence:
        this command can only snapshot and enqueue deterministic database work.
        """

        normalized_key = command_key.strip()
        if not normalized_key:
            raise CatalogVectorSpaceBuildConflict("an idempotency key is required")
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_catalog_vector_space_build_lock()
        existing = self._repository.get_catalog_vector_space_build_by_command_key(normalized_key)
        if existing is not None:
            response = self._vector_space_build_response(existing)
            space = self._repository.get_catalog_vector_space(
                embedding_model=command.embedding_model,
                embedding_dimension=command.embedding_dimension,
                adapter_version=command.adapter_version,
                retrieval_version=command.retrieval_version,
            )
            if (
                space is None or existing.vector_space_id != space.id
                or existing.requested_by != str(actor.id) or existing.reason != command.reason
                or existing.retrieval_version != command.retrieval_version
            ):
                raise CatalogVectorSpaceBuildConflict("idempotency key was reused for a different vector-space build")
            return response

        names = self._repository.list_current_eligible_catalog_search_names()
        if not names:
            raise CatalogVectorSpaceBuildConflict(
                "no eligible catalog search names are available; backfill the search index before creating a build"
            )
        space = self._repository.get_catalog_vector_space(
            embedding_model=command.embedding_model,
            embedding_dimension=command.embedding_dimension,
            adapter_version=command.adapter_version,
            retrieval_version=command.retrieval_version,
        )
        now = self._now()
        if space is None:
            space = self._repository.add_catalog_vector_space(CatalogVectorSpace(
                id=uuid.uuid4(), embedding_model=command.embedding_model,
                embedding_dimension=command.embedding_dimension,
                adapter_version=command.adapter_version, retrieval_version=command.retrieval_version, created_at=now,
            ))
        manifest = [
            {"publication_id": str(name.publication_id), "name_id": str(name.id),
             "search_version_id": str(name.search_version_id), "name_kind": name.name_kind}
            for name in names
        ]
        snapshot_hash = hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        build = self._repository.add_catalog_vector_space_build(CatalogVectorSpaceBuild(
            id=uuid.uuid4(), vector_space_id=space.id, requested_by=str(actor.id),
            reason=command.reason, command_key=normalized_key, retrieval_version=command.retrieval_version, snapshot_manifest=manifest,
            snapshot_hash=snapshot_hash, expected_name_count=len(names), requested_at=now,
        ))
        # A vector space is intentionally reusable for its exact model/adapter/
        # retrieval identity.  A later build may extend the immutable snapshot,
        # but it must reuse existing per-name work rather than violate the
        # business-key uniqueness or enqueue a second provider charge.
        existing_job_keys = {
            (job.publication_id, job.name_id)
            for job in self._repository.list_catalog_embedding_jobs_for_vector_space(
                space.id, name_ids=[name.id for name in names]
            )
        }
        self._repository.add_catalog_embedding_jobs([
            CatalogEmbeddingJob(
                id=uuid.uuid4(), publication_id=name.publication_id, name_id=name.id,
                vector_space_id=space.id, status="pending", attempt_count=0,
                max_attempts=5, not_before=now, lease_owner=None, leased_at=None,
                lease_expires_at=None, last_error_code=None, created_at=now, updated_at=now,
            ) for name in names
            if (name.publication_id, name.id) not in existing_job_keys
        ])
        # Reusing a completed vector-space job must still yield independent
        # completion evidence for this *new* immutable manifest.  This is local
        # PostgreSQL reconciliation only: no Provider call and no pointer change.
        self._repository.reconcile_catalog_vector_space_build_completion(build=build, now=now)
        self._repository.add_audit_event(AdminAuditEvent(
            id=uuid.uuid4(), actor_identifier=str(actor.id), occurred_at=now,
            action="catalog.vector_space_build.create", object_type="catalog_vector_space_build",
            object_id=str(build.id), reason=command.reason, before_diff={},
            after_diff={"vector_space_id": str(space.id), "expected_name_count": len(names),
                        "snapshot_hash": snapshot_hash, "retrieval_version": command.retrieval_version},
            related_version=command.retrieval_version, command_key=f"vector-space-build-audit:{normalized_key}",
        ))
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        return self._vector_space_build_response(build)

    def _vector_space_build_response(self, build: CatalogVectorSpaceBuild) -> CatalogVectorSpaceBuildResponse:
        name_ids = [uuid.UUID(item["name_id"]) for item in build.snapshot_manifest]
        jobs = self._repository.list_catalog_embedding_jobs_for_vector_space(build.vector_space_id, name_ids=name_ids)
        counts = self._embedding_job_counts(jobs)
        status: Literal["empty", "pending", "processing", "partial_failure", "ready"]
        if build.expected_name_count == 0:
            status = "empty"
        elif counts["failed_count"]:
            status = "partial_failure"
        elif counts["completed_count"] == build.expected_name_count:
            status = "ready"
        elif counts["processing_count"]:
            status = "processing"
        else:
            status = "pending"
        actual = self._repository.get_catalog_vector_space_by_id(build.vector_space_id)
        if actual is None:  # pragma: no cover - FK integrity protects this in PostgreSQL
            raise CatalogVectorSpaceBuildConflict("vector space is missing")
        return CatalogVectorSpaceBuildResponse(
            id=build.id, vector_space_id=build.vector_space_id,
            embedding_model=actual.embedding_model, embedding_dimension=actual.embedding_dimension,
            adapter_version=actual.adapter_version, retrieval_version=build.retrieval_version,
            snapshot_hash=build.snapshot_hash, expected_name_count=build.expected_name_count,
            pending_count=counts["pending_count"],
            failed_count=counts["failed_count"], completed_count=counts["completed_count"], status=status,
        )

    def list_catalog_vector_space_builds(self, *, actor_user_id: uuid.UUID) -> CatalogVectorSpaceBuildPageResponse:
        """Return operational counts only; manifests and provider data stay server-side."""

        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        active_ids = {space.id for space in self._repository.list_active_catalog_vector_spaces()}
        return CatalogVectorSpaceBuildPageResponse(items=[
            self._vector_space_build_status(build, is_active=build.vector_space_id in active_ids)
            for build in self._repository.list_catalog_vector_space_builds()
        ])

    def get_catalog_vector_space_build_status(
        self, *, actor_user_id: uuid.UUID, build_id: uuid.UUID
    ) -> CatalogVectorSpaceBuildStatusResponse:
        self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        build = self._repository.get_catalog_vector_space_build_for_activation(build_id)
        if build is None:
            raise KeyError("vector-space build not found")
        active_ids = {space.id for space in self._repository.list_active_catalog_vector_spaces()}
        return self._vector_space_build_status(build, is_active=build.vector_space_id in active_ids)

    def _vector_space_build_status(
        self, build: CatalogVectorSpaceBuild, *, is_active: bool
    ) -> CatalogVectorSpaceBuildStatusResponse:
        response = self._vector_space_build_response(build)
        activation_ready = False
        if response.status == "ready":
            try:
                space = self._repository.get_catalog_vector_space_by_id(build.vector_space_id)
                if space is not None and all(getattr(space, field) == value for field, value in _PHASE063_RELEASE_SPACE.items()):
                    self._load_phase063_release(None)
                    self._validate_activation_build(build=build, vector_space_id=build.vector_space_id)
                    activation_ready = True
            except CatalogVectorSpaceActivationConflict:
                # Do not reveal evaluator internals through a read endpoint.
                activation_ready = False
        return CatalogVectorSpaceBuildStatusResponse(
            **response.model_dump(), requested_at=build.requested_at,
            is_active=is_active, activation_ready=activation_ready,
        )

    def retry_catalog_vector_space_build(
        self, *, actor_user_id: uuid.UUID, build_id: uuid.UUID,
        command: CatalogVectorSpaceBuildRetryCommand, command_key: str,
    ) -> CatalogVectorSpaceBuildRetryResponse:
        """Retry only failed, budget-remaining jobs in one frozen build snapshot."""

        key = command_key.strip()
        if not key:
            raise CatalogVectorSpaceBuildConflict("an idempotency key is required")
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_catalog_vector_space_build_lock()
        build = self._repository.get_catalog_vector_space_build_for_activation(build_id)
        if build is None:
            raise KeyError("vector-space build not found")
        audit_key = f"vector-space-build-retry:{key}"
        existing = self._repository.get_audit_event_by_command_key(audit_key)
        if existing is not None:
            if (existing.action != "catalog.vector_space_build.retry" or existing.object_id != str(build.id)
                    or existing.actor_identifier != str(actor.id) or existing.reason != command.reason):
                raise CatalogVectorSpaceBuildConflict("idempotency key was reused for a different vector-space retry")
            status = self._vector_space_build_status(build, is_active=False)
            return CatalogVectorSpaceBuildRetryResponse(**status.model_dump(), reset_count=int(existing.after_diff["reset_count"]))
        name_ids = [uuid.UUID(item["name_id"]) for item in build.snapshot_manifest]
        jobs = self._repository.list_catalog_embedding_jobs_for_vector_space(build.vector_space_id, name_ids=name_ids)
        before = self._embedding_job_counts(jobs)
        now = self._now()
        retryable = [job for job in jobs if job.status == "failed" and job.attempt_count < job.max_attempts]
        for job in retryable:
            job.status, job.not_before = "pending", now
            job.lease_owner = job.leased_at = job.lease_expires_at = None
            job.last_error_code, job.updated_at = None, now
        after = self._embedding_job_counts(jobs)
        self._repository.add_audit_event(AdminAuditEvent(
            id=uuid.uuid4(), actor_identifier=str(actor.id), occurred_at=now,
            action="catalog.vector_space_build.retry", object_type="catalog_vector_space_build",
            object_id=str(build.id), reason=command.reason, before_diff=before,
            after_diff={**after, "reset_count": len(retryable)}, related_version=build.retrieval_version,
            command_key=audit_key,
        ))
        self._commit_catalog_mutation()
        status = self._vector_space_build_status(build, is_active=False)
        return CatalogVectorSpaceBuildRetryResponse(**status.model_dump(), reset_count=len(retryable))

    def activate_vector_space(
        self,
        *,
        actor_user_id: uuid.UUID,
        vector_space_id: uuid.UUID,
        build_id: uuid.UUID,
        reason: str,
        command_key: str,
        release_path: Path | None = None,
    ) -> CatalogVectorSpaceActivationApproval:
        """Atomically advance the search pointer only from independently stored proof.

        The CLI supplies identifiers and a file path, never a trusted PASS claim.
        Every mutable fact is re-read under the activation transaction; the frozen
        report, manifest, worker completion and live rows must agree before the
        pointer can move.
        """

        normalized_reason, normalized_key = reason.strip(), command_key.strip()
        if not normalized_reason or len(normalized_reason) > 500:
            raise CatalogVectorSpaceActivationConflict("a bounded approval reason is required")
        if not normalized_key or len(normalized_key) > 160:
            raise CatalogVectorSpaceActivationConflict("a bounded idempotency key is required")
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_catalog_vector_space_activation_lock()

        existing = self._repository.get_catalog_vector_space_activation_approval(normalized_key)
        audit_key = f"vector-space-activation-audit:{normalized_key}"
        if existing is not None:
            audit = self._repository.get_audit_event_by_command_key(audit_key)
            if (
                audit is None
                or existing.approver_identifier != str(actor.id)
                or existing.build_id != build_id
                or audit.action != "catalog.vector_space.activate"
                or audit.object_id != str(vector_space_id)
                or audit.reason != normalized_reason
            ):
                raise CatalogVectorSpaceActivationConflict("idempotency key was reused for a different activation")
            return existing

        release = self._load_phase063_release(release_path)
        space = self._repository.get_catalog_vector_space_by_id(vector_space_id)
        if space is None:
            raise CatalogVectorSpaceActivationConflict("target vector space is missing")
        if any(getattr(space, field) != value for field, value in _PHASE063_RELEASE_SPACE.items()):
            raise CatalogVectorSpaceActivationConflict("target vector space does not match frozen release identity")

        build = self._repository.get_catalog_vector_space_build_for_activation(build_id)
        if build is None or build.vector_space_id != vector_space_id:
            raise CatalogVectorSpaceActivationConflict("target build does not belong to target vector space")
        self._validate_activation_build(build=build, vector_space_id=vector_space_id)

        now = self._now()
        approval = CatalogVectorSpaceActivationApproval(
            id=uuid.uuid4(), build_id=build.id,
            release_hash=release["evidence_hash"],
            dataset_hash=release["input_hashes"]["dataset_sha256"],
            code_hash=release["input_hashes"]["evaluator_sha256"],
            retrieval_hash=release["input_hashes"]["search_policy_sha256"],
            embedding_hash=self._activation_embedding_hash(space),
            approver_identifier=str(actor.id), approved_at=now, command_key=normalized_key,
        )
        self._repository.activate_catalog_vector_space(
            approval=approval, vector_space_id=vector_space_id, now=now
        )
        self._repository.add_audit_event(AdminAuditEvent(
            id=uuid.uuid4(), actor_identifier=str(actor.id), occurred_at=now,
            action="catalog.vector_space.activate", object_type="catalog_vector_space",
            object_id=str(vector_space_id), reason=normalized_reason, before_diff={},
            after_diff={
                "build_id": str(build.id), "snapshot_hash": build.snapshot_hash,
                "completion_hash": self._repository.get_catalog_vector_space_build_completion(build.id).completion_hash,
                "release_hash": approval.release_hash,
            },
            related_version=space.retrieval_version, command_key=audit_key,
        ))
        try:
            self._commit()
        except Exception:
            self._rollback()
            raise
        return approval

    @staticmethod
    def _activation_embedding_hash(space: CatalogVectorSpace) -> str:
        payload = {
            "embedding_model": space.embedding_model,
            "embedding_dimension": space.embedding_dimension,
            "adapter_version": space.adapter_version,
            "retrieval_version": space.retrieval_version,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

    @staticmethod
    def _phase063_release_path() -> Path:
        return Path(__file__).resolve().parents[2] / "evals" / "phase_06_3" / "release.json"

    def _load_phase063_release(self, path: Path | None) -> dict[str, object]:
        """Validate committed activation evidence through the evaluator's strict contract.

        ``verify_release`` owns the release schema/evaluator versions and the
        source-hash binding.  Duplicating those checks here made the admin path
        drift from the evaluator after a contract version upgrade.
        """

        from evals.phase_06_3.evaluate import EvaluationContractError, verify_release

        try:
            release = verify_release(path or self._phase063_release_path())
            return release
        except (EvaluationContractError, KeyError, TypeError) as error:
            raise CatalogVectorSpaceActivationConflict("release evidence is not activation-valid") from error

    def _validate_activation_build(self, *, build: CatalogVectorSpaceBuild, vector_space_id: uuid.UUID) -> None:
        manifest = build.snapshot_manifest
        if build.expected_name_count == 0 or not manifest:
            raise CatalogVectorSpaceActivationConflict("empty vector-space builds cannot be activated")
        serialized = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(manifest) != build.expected_name_count or hashlib.sha256(serialized).hexdigest() != build.snapshot_hash:
            raise CatalogVectorSpaceActivationConflict("immutable build manifest does not match its hash")
        try:
            manifest_keys = {
                (uuid.UUID(item["publication_id"]), uuid.UUID(item["name_id"]), uuid.UUID(item["search_version_id"]))
                for item in manifest
            }
        except (KeyError, TypeError, ValueError) as error:
            raise CatalogVectorSpaceActivationConflict("immutable build manifest is invalid") from error
        if len(manifest_keys) != build.expected_name_count:
            raise CatalogVectorSpaceActivationConflict("immutable build manifest contains duplicate entries")
        name_ids = [name_id for _, name_id, _ in manifest_keys]
        completion = self._repository.get_catalog_vector_space_build_completion(build.id)
        from app.nutrition.index_worker import completion_hash
        if (
            completion is None
            or completion.completed_name_count != build.expected_name_count
            or completion.completion_hash != completion_hash(snapshot_hash=build.snapshot_hash, manifest=manifest)
        ):
            raise CatalogVectorSpaceActivationConflict("separate build completion evidence is missing or mismatched")
        jobs = self._repository.list_catalog_embedding_jobs_for_vector_space(vector_space_id, name_ids=name_ids)
        if len(jobs) != build.expected_name_count or any(job.status != "completed" for job in jobs):
            raise CatalogVectorSpaceActivationConflict("target build has pending or failed embedding jobs")
        job_keys = set()
        for job in jobs:
            name = self._repository.get_catalog_search_name(job.name_id)
            if name is None:
                raise CatalogVectorSpaceActivationConflict("target build name is missing")
            job_keys.add((job.publication_id, job.name_id, name.search_version_id))
        if job_keys != manifest_keys:
            raise CatalogVectorSpaceActivationConflict("completed jobs do not exactly cover immutable build manifest")
        embeddings = self._repository.list_catalog_search_embeddings_for_vector_space(vector_space_id, name_ids=name_ids)
        if len(embeddings) != build.expected_name_count or any(item.status != "ready" for item in embeddings):
            raise CatalogVectorSpaceActivationConflict("target build does not have one ready embedding per manifest item")
        if {(item.publication_id, item.name_id) for item in embeddings} != {(publication_id, name_id) for publication_id, name_id, _ in manifest_keys}:
            raise CatalogVectorSpaceActivationConflict("ready embeddings do not exactly cover immutable build manifest")

    def retry_catalog_embedding_jobs(
        self,
        *,
        actor_user_id: uuid.UUID,
        publication_id: uuid.UUID,
        command: CatalogEmbeddingRetryCommand,
    ) -> CatalogEmbeddingRetryResponse:
        """Reset only finite-budget failed jobs in one locked, replay-safe batch."""

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        self._repository.acquire_catalog_embedding_retry_lock(publication_id)
        publication = self._repository.get_catalog_publication(publication_id)
        if publication is None:
            raise KeyError("catalog publication not found")

        request_hash = self._embedding_retry_request_hash(
            actor_id=actor.id,
            publication_id=publication_id,
            command=command,
        )
        audit_key = self._embedding_retry_audit_key(
            publication_id=publication_id, idempotency_key=command.idempotency_key
        )
        existing = self._repository.get_audit_event_by_command_key(audit_key)
        if existing is not None:
            if (
                existing.action != "catalog.embedding_retry"
                or existing.object_type != "catalog_publication"
                or existing.object_id != str(publication_id)
                or existing.actor_identifier != str(actor.id)
                or existing.reason != command.reason
                or existing.related_version != request_hash
            ):
                raise CatalogEmbeddingRetryConflict(
                    "idempotency key was reused for a different embedding retry command"
                )
            return self._catalog_embedding_retry_response(
                publication_id, reset_count=int(existing.after_diff["reset_count"])
            )

        jobs = self._repository.list_catalog_embedding_jobs(
            publication_id, for_update=True
        )
        before = self._embedding_job_counts(jobs)
        now = self._now()
        retryable = [
            job
            for job in jobs
            if job.status == "failed" and job.attempt_count < job.max_attempts
        ]
        for job in retryable:
            job.status = "pending"
            job.not_before = now
            job.lease_owner = None
            job.leased_at = None
            job.lease_expires_at = None
            job.last_error_code = None
            job.updated_at = now
        after = self._embedding_job_counts(jobs)
        reset_count = len(retryable)
        self._repository.add_audit_event(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_identifier=str(actor.id),
                occurred_at=now,
                action="catalog.embedding_retry",
                object_type="catalog_publication",
                object_id=str(publication_id),
                reason=command.reason,
                before_diff=before,
                after_diff={**after, "reset_count": reset_count},
                related_version=request_hash,
                command_key=audit_key,
            )
        )
        self._commit_catalog_mutation()
        return self._catalog_embedding_retry_response(
            publication_id, reset_count=reset_count
        )

    def create_catalog_relation_evidence(
        self,
        *,
        actor_user_id: uuid.UUID,
        command: CatalogRelationEvidenceCommand,
        command_key: str,
    ) -> CatalogRelationEvidenceResponse:
        """Append a controlled, version-bound relation without changing eligibility."""

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        normalized_key = command_key.strip()
        existing = self._repository.get_catalog_relation_evidence_by_command_key(
            normalized_key
        )
        if existing is not None:
            if not self._relation_command_matches(existing, actor.id, command):
                raise CatalogRelationEvidenceConflict(
                    "idempotency key was reused for a different relation command"
                )
            return self._relation_evidence_response(existing)

        source = self._repository.get_catalog_search_name_for_publication(
            name_id=command.source_name_id,
            publication_id=command.source_publication_id,
        )
        target = self._repository.get_catalog_search_name_for_publication(
            name_id=command.target_name_id,
            publication_id=command.target_publication_id,
        )
        if source is None or target is None:
            raise KeyError("relation names must belong to their current publications")
        if source.id == target.id:
            raise CatalogRelationEvidenceConflict("relation endpoints must differ")

        evidence = self._repository.add_catalog_relation_evidence(
            CatalogSearchRelationEvidence(
                id=uuid.uuid4(),
                source_name_id=source.id,
                target_name_id=target.id,
                relation=command.relation,
                status="active",
                actor_identifier=str(actor.id),
                reason=command.reason,
                command_key=normalized_key,
                occurred_at=self._now(),
            )
        )
        self._record_relation_audit(
            actor_identifier=str(actor.id),
            evidence=evidence,
            action="catalog.relation_evidence.create",
            before={"status": None},
            after={"status": "active", "relation": evidence.relation},
        )
        self._commit_catalog_mutation()
        return self._relation_evidence_response(evidence)

    def revoke_catalog_relation_evidence(
        self,
        *,
        actor_user_id: uuid.UUID,
        evidence_id: uuid.UUID,
        command: CatalogRelationEvidenceRevokeCommand,
        command_key: str,
    ) -> CatalogRelationEvidenceResponse:
        """Append a revocation record; historical relationship evidence remains intact."""

        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        normalized_key = command_key.strip()
        previous = self._repository.get_catalog_relation_evidence(evidence_id)
        if previous is None:
            raise KeyError("catalog relation evidence not found")
        existing = self._repository.get_catalog_relation_evidence_by_command_key(
            normalized_key
        )
        if existing is not None:
            if (
                existing.status != "revoked"
                or existing.actor_identifier != str(actor.id)
                or existing.reason != command.reason
                or existing.source_name_id != previous.source_name_id
                or existing.target_name_id != previous.target_name_id
                or existing.relation != previous.relation
            ):
                raise CatalogRelationEvidenceConflict(
                    "idempotency key was reused for a different relation revocation"
                )
            return self._relation_evidence_response(existing)
        evidence = self._repository.add_catalog_relation_evidence(
            CatalogSearchRelationEvidence(
                id=uuid.uuid4(),
                source_name_id=previous.source_name_id,
                target_name_id=previous.target_name_id,
                relation=previous.relation,
                status="revoked",
                actor_identifier=str(actor.id),
                reason=command.reason,
                command_key=normalized_key,
                occurred_at=self._now(),
            )
        )
        self._record_relation_audit(
            actor_identifier=str(actor.id),
            evidence=evidence,
            action="catalog.relation_evidence.revoke",
            before={"status": previous.status, "evidence_id": str(previous.id)},
            after={"status": "revoked", "evidence_id": str(evidence.id)},
        )
        self._commit_catalog_mutation()
        return self._relation_evidence_response(evidence)

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
        return RecipeCandidateResponse(
            id=candidate.id,
            catalog_food_name=candidate.catalog_food_name,
            meal_slot=cast(
                Literal["breakfast", "lunch", "dinner", "snack"], candidate.meal_slot
            ),
            classification=candidate.classification,
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

    def _enqueue_catalog_embedding_jobs(self, publication: CatalogPublication) -> None:
        """Create derived name work in the same publication transaction, never via I/O."""

        search_version = self._repository.add_catalog_search_version(
            CatalogSearchVersion(
                id=uuid.uuid4(),
                publication_id=publication.id,
                content_hash=publication.content_hash,
                created_at=self._now(),
            )
        )
        candidates = [
            (str(publication.snapshot["canonical_name"]), "canonical"),
            *(
                (str(alias), "controlled_alias")
                for alias in publication.snapshot["aliases"]
            ),
        ]
        unique_names: dict[str, tuple[str, Literal["canonical", "controlled_alias"]]] = {}
        for display_name, name_kind in candidates:
            normalized_name = " ".join(display_name.casefold().split())
            if normalized_name:
                unique_names.setdefault(
                    normalized_name,
                    (display_name, cast(Literal["canonical", "controlled_alias"], name_kind)),
                )
        names = self._repository.add_catalog_search_names(
            [
                CatalogSearchName(
                    id=uuid.uuid4(),
                    publication_id=publication.id,
                    search_version_id=search_version.id,
                    display_name=display_name,
                    normalized_name=normalized_name,
                    name_kind=name_kind,
                    created_at=self._now(),
                )
                for normalized_name, (display_name, name_kind) in sorted(
                    unique_names.items()
                )
            ]
        )
        spaces = self._repository.list_active_catalog_vector_spaces()
        now = self._now()
        self._repository.add_catalog_embedding_jobs(
            [
                CatalogEmbeddingJob(
                    id=uuid.uuid4(),
                    publication_id=publication.id,
                    name_id=name.id,
                    vector_space_id=space.id,
                    status="pending",
                    attempt_count=0,
                    max_attempts=5,
                    not_before=now,
                    lease_owner=None,
                    leased_at=None,
                    lease_expires_at=None,
                    last_error_code=None,
                    created_at=now,
                    updated_at=now,
                )
                for name in names
                for space in spaces
            ]
        )

    def _catalog_embedding_status(
        self, publication_id: uuid.UUID
    ) -> CatalogEmbeddingStatusResponse:
        jobs = self._repository.list_catalog_embedding_jobs(publication_id)
        counts = self._embedding_job_counts(jobs)
        return CatalogEmbeddingStatusResponse(
            publication_id=publication_id,
            status=self._embedding_aggregate_status(jobs),
            pending_count=counts["pending_count"],
            processing_count=counts["processing_count"],
            failed_count=counts["failed_count"],
            completed_count=counts["completed_count"],
            jobs=[self._embedding_job_response(job) for job in jobs],
        )

    def _relation_evidence_response(
        self, evidence: CatalogSearchRelationEvidence
    ) -> CatalogRelationEvidenceResponse:
        source = self._repository.get_catalog_search_name(evidence.source_name_id)
        target = self._repository.get_catalog_search_name(evidence.target_name_id)
        if source is None or target is None:
            # FK RESTRICT makes this unreachable for correctly migrated production data.
            raise CatalogRelationEvidenceConflict("relation evidence endpoints are missing")
        return CatalogRelationEvidenceResponse(
            id=evidence.id,
            source_publication_id=source.publication_id,
            target_publication_id=target.publication_id,
            relation=cast(
                Literal[
                    "name_variant",
                    "regional_preparation_variant",
                    "same_category_food",
                ],
                evidence.relation,
            ),
            status=cast(Literal["active", "revoked"], evidence.status),
        )

    @staticmethod
    def _relation_command_matches(
        evidence: CatalogSearchRelationEvidence,
        actor_id: uuid.UUID,
        command: CatalogRelationEvidenceCommand,
    ) -> bool:
        return (
            evidence.status == "active"
            and evidence.actor_identifier == str(actor_id)
            and evidence.source_name_id == command.source_name_id
            and evidence.target_name_id == command.target_name_id
            and evidence.relation == command.relation
            and evidence.reason == command.reason
        )

    def _record_relation_audit(
        self,
        *,
        actor_identifier: str,
        evidence: CatalogSearchRelationEvidence,
        action: str,
        before: dict[str, object],
        after: dict[str, object],
    ) -> None:
        self._repository.add_audit_event(
            AdminAuditEvent(
                id=uuid.uuid4(),
                actor_identifier=actor_identifier,
                occurred_at=evidence.occurred_at,
                action=action,
                object_type="catalog_relation_evidence",
                object_id=str(evidence.id),
                reason=evidence.reason,
                before_diff=before,
                after_diff=after,
                related_version=str(evidence.id),
                command_key=f"relation-audit-{evidence.command_key}",
            )
        )

    def _catalog_embedding_retry_response(
        self, publication_id: uuid.UUID, *, reset_count: int
    ) -> CatalogEmbeddingRetryResponse:
        status = self._catalog_embedding_status(publication_id)
        return CatalogEmbeddingRetryResponse(
            **status.model_dump(), reset_count=reset_count
        )

    @staticmethod
    def _embedding_job_response(job: CatalogEmbeddingJob) -> CatalogEmbeddingJobResponse:
        return CatalogEmbeddingJobResponse(
            id=job.id,
            vector_space_id=job.vector_space_id,
            status=cast(Literal["pending", "leased", "completed", "failed"], job.status),
            attempt_count=job.attempt_count,
            max_attempts=job.max_attempts,
            last_error_code=job.last_error_code,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )

    @staticmethod
    def _embedding_job_counts(jobs: list[CatalogEmbeddingJob]) -> dict[str, int]:
        return {
            "pending_count": sum(job.status == "pending" for job in jobs),
            "processing_count": sum(job.status == "leased" for job in jobs),
            "failed_count": sum(job.status == "failed" for job in jobs),
            "completed_count": sum(job.status == "completed" for job in jobs),
        }

    @staticmethod
    def _embedding_aggregate_status(
        jobs: list[CatalogEmbeddingJob],
    ) -> Literal["pending", "processing", "partial_failure", "failed", "ready"]:
        if not jobs or all(job.status == "completed" for job in jobs):
            return "ready"
        has_completed = any(job.status == "completed" for job in jobs)
        has_failed = any(job.status == "failed" for job in jobs)
        if has_failed and (has_completed or any(job.status == "pending" for job in jobs)):
            return "partial_failure"
        if any(job.status == "leased" for job in jobs):
            return "processing"
        if any(job.status == "pending" for job in jobs):
            return "pending"
        return "failed"

    @staticmethod
    def _embedding_retry_audit_key(
        *, publication_id: uuid.UUID, idempotency_key: str
    ) -> str:
        material = f"catalog-embedding-retry:{publication_id}:{idempotency_key}"
        return f"embedding-retry-{hashlib.sha256(material.encode('utf-8')).hexdigest()}"

    @staticmethod
    def _embedding_retry_request_hash(
        *, actor_id: uuid.UUID,
        publication_id: uuid.UUID,
        command: CatalogEmbeddingRetryCommand,
    ) -> str:
        material = json.dumps(
            {
                "actor_id": str(actor_id),
                "publication_id": str(publication_id),
                "reason": command.reason,
                "idempotency_key": command.idempotency_key,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

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

    def _audit_actor_identifier(self, actor: str | None) -> str | None:
        """Accept an administrator email while keeping old opaque-ID filters valid."""

        if actor is None or actor.startswith("system:"):
            return actor
        user = self._repository.get_user_by_email(actor.casefold())
        return str(user.id) if user is not None else actor

    def _audit_actor_label(self, actor_identifier: str) -> str:
        """Resolve the label at the admin-only projection boundary, never in the client."""

        if actor_identifier == "system:bootstrap":
            return "系统初始化"
        try:
            actor_id = uuid.UUID(actor_identifier)
        except ValueError:
            return "管理员"
        user = self._repository.get_user_by_id(actor_id)
        return user.email if user is not None else "已删除的管理员"

    def _audit_response(self, event: AdminAuditEvent) -> AdminAuditEventResponse:
        return AdminAuditEventResponse(
            id=event.id,
            actor_identifier=event.actor_identifier,
            actor_label=self._audit_actor_label(event.actor_identifier),
            occurred_at=event.occurred_at,
            action=event.action,
            object_type=event.object_type,
            object_id=event.object_id,
            reason=event.reason,
            # Full classification remains in authoritative audit storage; the
            # public audit contract exposes its three bounded display fields.
            before={key: value for key, value in event.before_diff.items() if key != "classification"},
            after={key: value for key, value in event.after_diff.items() if key != "classification"},
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
            failure_stage=run.failure_stage,
            failure_class=run.failure_class,
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
