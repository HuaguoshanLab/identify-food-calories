"""Persistence capabilities consumed by admin authorization services."""

from __future__ import annotations

import uuid
from typing import Protocol

from app.admin.models import AdminRoleAudit
from app.auth.models import User


class AdminRepository(Protocol):
    def get_user_by_id(self, user_id: uuid.UUID) -> User | None: ...

    def get_user_by_email(self, normalized_email: str) -> User | None: ...

    def get_user_for_update(self, user_id: uuid.UUID) -> User | None: ...

    def has_active_admin(self) -> bool: ...

    def add_audit(self, audit: AdminRoleAudit) -> AdminRoleAudit: ...
