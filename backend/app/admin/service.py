"""Admin authorization and role-elevation policy over a repository port."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.admin.models import AdminRoleAudit
from app.admin.ports import AdminRepository
from app.auth.models import User, UserRole


class AdminPermissionDenied(PermissionError):
    """Authenticated users without the current database role cannot continue."""


class AdminRoleChangeDenied(ValueError):
    """A role mutation did not meet the explicit CLI-only safety policy."""


class AdminService:
    """Keeps RBAC truth and audit mutations inside one application transaction."""

    def __init__(
        self,
        *,
        repository: AdminRepository,
        now: Callable[[], datetime] | None = None,
        commit: Callable[[], None] | None = None,
        rollback: Callable[[], None] | None = None,
    ) -> None:
        self._repository = repository
        self._now = now or (lambda: datetime.now(UTC))
        self._commit = commit or (lambda: None)
        self._rollback = rollback or (lambda: None)

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
        try:
            self._commit()
        except Exception:
            # The role mutation and audit row share one session transaction: neither
            # may escape if persistence rejects either write.
            self._rollback()
            raise
        return audit
