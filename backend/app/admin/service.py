"""Admin authorization and role-elevation policy over a repository port."""

from __future__ import annotations

import uuid
import base64
import hashlib
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Literal, cast

from app.admin.models import AdminAuditEvent, AdminRoleAudit, CatalogDraft, CatalogDraftChangeSet, CatalogDraftRevision
from app.admin.ports import AdminRepository
from app.admin.schemas import (
    AdminAuditEventResponse,
    AdminAuditPageResponse,
    CatalogDraftCreateCommand,
    CatalogDraftDiffField,
    CatalogDraftFieldDiff,
    CatalogDraftPatchCommand,
    CatalogDraftPreviewCommand,
    CatalogDraftPreviewResponse,
    CatalogDraftResponse,
)
from app.auth.models import User, UserRole


class AdminPermissionDenied(PermissionError):
    """Authenticated users without the current database role cannot continue."""


class AdminRoleChangeDenied(ValueError):
    """A role mutation did not meet the explicit CLI-only safety policy."""


class AdminAuditCursorInvalid(ValueError):
    """A client-supplied cursor failed its integrity or shape validation."""


class CatalogDraftConflict(ValueError):
    """A stale revision or incompatible idempotency replay cannot overwrite a draft."""


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

    def require_role(self, *, user_id: uuid.UUID, required_role: UserRole) -> User:
        """Read the active role from PostgreSQL; JWT claims are never authorization truth."""

        user = self._repository.get_user_by_id(user_id)
        if user is None or not user.is_active or user.role != required_role.value:
            raise AdminPermissionDenied("database role does not permit this operation")
        return user

    def bootstrap_first_admin(
        self, *, target_user_id: uuid.UUID, reason: str
    ) -> AdminRoleAudit:
        """Promote only when the system has no active admin, recording the system actor."""

        # A transaction-scoped PostgreSQL advisory lock closes the check-then-promote
        # race: concurrent bootstrap processes cannot both observe an empty admin set.
        self._repository.acquire_bootstrap_lock()
        if self._repository.has_active_admin():
            raise AdminRoleChangeDenied("bootstrap is only available before an active admin exists")
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
            items=[self._audit_response(event) for event in visible], next_cursor=next_cursor
        )

    def create_catalog_draft(
        self, *, actor_user_id: uuid.UUID, command: CatalogDraftCreateCommand, command_key: str
    ) -> CatalogDraftResponse:
        """Create a mutable draft and its evidence in one service-owned transaction."""

        payload = self._catalog_payload(command)
        replay = self._catalog_replay(command_key, self._request_hash("create", payload))
        if replay is not None:
            return self._catalog_response(replay)
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        now = self._now()
        draft = CatalogDraft(id=uuid.uuid4(), **payload, revision=1, created_at=now, updated_at=now)
        self._repository.add_catalog_draft(draft)
        self._record_catalog_mutation(
            actor_identifier=str(actor.id), draft=draft, command_key=command_key, operation="create",
            reason=command.reason, revision_before=0, before={field: None for field in payload} | {"revision": 0},
            after=self._audit_catalog_payload(draft), request_hash=self._request_hash("create", payload),
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

        patch = self._catalog_payload(command, partial=True)
        replay = self._catalog_replay(command_key, self._request_hash("patch", {"draft_id": str(draft_id), "expected_revision": expected_revision, **patch}))
        if replay is not None:
            return self._catalog_response(replay)
        actor = self.require_role(user_id=actor_user_id, required_role=UserRole.ADMIN)
        draft = self._repository.get_catalog_draft(draft_id)
        if draft is None:
            raise KeyError("catalog draft not found")
        if expected_revision != draft.revision:
            raise CatalogDraftConflict("catalog draft revision does not match If-Match")
        before_all = self._audit_catalog_payload(draft)
        before = {name: before_all[name] for name in patch if before_all[name] != self._audit_scalar(patch[name])}
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
            actor_identifier=str(actor.id), draft=draft, command_key=command_key, operation="patch",
            reason=command.reason, revision_before=revision_before, before=before, after=after,
            request_hash=self._request_hash("patch", {"draft_id": str(draft_id), "expected_revision": expected_revision, **patch}),
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
            action=f"catalog_draft.{operation}", object_type="catalog_draft", object_id=str(draft.id),
            reason=reason, command_key=command_key,
        )["command_key"]
        change_set = self._repository.add_catalog_draft_change_set(CatalogDraftChangeSet(
            id=uuid.uuid4(), draft_id=draft.id, actor_identifier=actor_identifier, occurred_at=now,
            reason=reason.strip(), command_key=normalized_command_key, request_hash=request_hash,
            revision_before=revision_before, revision_after=draft.revision, before_diff=self._safe_diff(before), after_diff=self._safe_diff(after),
        ))
        self._repository.add_catalog_draft_revision(CatalogDraftRevision(
            id=uuid.uuid4(), draft_id=draft.id, change_set_id=change_set.id, revision=draft.revision,
            snapshot=self._audit_catalog_payload(draft), created_at=now,
        ))
        self._repository.add_audit_event(AdminAuditEvent(
            id=uuid.uuid4(), actor_identifier=actor_identifier, occurred_at=now, action=f"catalog_draft.{operation}",
            object_type="catalog_draft", object_id=str(draft.id), reason=reason.strip(), before_diff=self._safe_diff(before),
            after_diff=self._safe_diff(after), related_version=None, command_key=f"audit-{normalized_command_key}",
        ))

    def _catalog_replay(self, command_key: str, request_hash: str) -> CatalogDraft | None:
        existing = self._repository.get_catalog_draft_command(command_key.strip())
        if existing is None:
            return None
        if existing.request_hash != request_hash:
            raise CatalogDraftConflict("Idempotency-Key was reused for a different command")
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
        command: CatalogDraftCreateCommand | CatalogDraftPatchCommand | CatalogDraftPreviewCommand,
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
            "canonical_name": draft.canonical_name, "aliases": cls._audit_scalar(draft.aliases),
            "energy_kcal_per_100g": cls._audit_scalar(draft.energy_kcal_per_100g),
            "protein_g_per_100g": cls._audit_scalar(draft.protein_g_per_100g),
            "fat_g_per_100g": cls._audit_scalar(draft.fat_g_per_100g),
            "carbohydrate_g_per_100g": cls._audit_scalar(draft.carbohydrate_g_per_100g),
            "source_name": draft.source_name, "source_url": draft.source_url,
            "authorization_status": draft.authorization_status, "revision": draft.revision,
        }

    @staticmethod
    def _catalog_preview_impacts(
        diffs: list[CatalogDraftFieldDiff],
    ) -> list[Literal["catalog_identity", "nutrition_per_100g", "source_evidence", "authorization_status"]]:
        """Classify only known catalog fields; no raw request payload reaches the UI."""

        changed = {diff.field for diff in diffs}
        impacts: list[Literal["catalog_identity", "nutrition_per_100g", "source_evidence", "authorization_status"]] = []
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
    def _request_hash(operation: str, payload: dict[str, object]) -> str:
        normalized = json.dumps({"operation": operation, "payload": payload}, sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def _catalog_response(draft: CatalogDraft) -> CatalogDraftResponse:
        return CatalogDraftResponse(
            id=draft.id, canonical_name=draft.canonical_name, aliases=list(draft.aliases),
            energy_kcal_per_100g=draft.energy_kcal_per_100g, protein_g_per_100g=draft.protein_g_per_100g,
            fat_g_per_100g=draft.fat_g_per_100g, carbohydrate_g_per_100g=draft.carbohydrate_g_per_100g,
            source_name=draft.source_name, source_url=draft.source_url,
            authorization_status=cast(Literal["authorized", "pending", "revoked"], draft.authorization_status), revision=draft.revision,
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
                id=uuid.uuid4(), actor_identifier=actor_identifier, occurred_at=self._now(),
                action="role.promote", object_type="user", object_id=str(target.id),
                reason=normalized_reason, before_diff={"role": previous_role},
                after_diff={"role": UserRole.ADMIN.value}, related_version=None,
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
            raise AdminRoleChangeDenied("action, object, reason and idempotency key must be non-empty")
        return normalized

    @staticmethod
    def _safe_diff(value: dict[str, object]) -> dict[str, object]:
        """Require a shallow, scalar field diff rather than an opaque payload blob."""

        if not value or any(not isinstance(key, str) or not key.strip() for key in value):
            raise AdminRoleChangeDenied("audit diff must contain named fields")
        prohibited = {"email", "password", "secret", "token", "image", "base64", "provider", "state", "prompt"}
        if any(any(term in key.casefold() for term in prohibited) for key in value):
            raise AdminRoleChangeDenied("audit diff contains a prohibited sensitive field")
        if any(isinstance(item, (dict, list, tuple, set, bytes)) for item in value.values()):
            raise AdminRoleChangeDenied("audit diff values must be scalar")
        return dict(value)

    @staticmethod
    def _audit_response(event: AdminAuditEvent) -> AdminAuditEventResponse:
        return AdminAuditEventResponse(
            id=event.id, actor_identifier=event.actor_identifier, occurred_at=event.occurred_at,
            action=event.action, object_type=event.object_type, object_id=event.object_id,
            reason=event.reason, before=event.before_diff, after=event.after_diff,
            related_version=event.related_version, command_key=event.command_key,
        )

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
