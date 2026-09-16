"""Role changes are explicit, authorized, atomic and replayable."""
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.admin.schemas import RecipeCandidateRoleCommand
from app.admin.service import AdminPermissionDenied, AdminService, RecipeCandidateConflict
from app.planning.models import ManagedRecipeCandidate
from tests.admin.test_admin_rbac_audit_service import FakeAdminRepository, _user


class Repository(FakeAdminRepository):
    def __init__(self, user, rows):
        super().__init__(user)
        self.rows = {row.id: row for row in rows}

    def acquire_recipe_candidate_lock(self, key):
        pass

    def get_recipe_candidate(self, identity, *, for_update=False):
        return self.rows.get(identity)

    def get_audit_event_by_command_key(self, key):
        return next((event for event in self.events if event.command_key == key), None)


def test_role_changes_are_audited_idempotent_and_check_current_admin():
    actor = _user(role="admin")
    row = ManagedRecipeCandidate(id=uuid4(), meal_role="standalone", revision=4)
    repo = Repository(actor, [row])
    service = AdminService(repository=repo)
    command = RecipeCandidateRoleCommand(ids=[row.id], meal_role="vegetable", reason="  已核对菜品  ", confirm=True)
    args = dict(actor_user_id=actor.id, command=command, command_key="x" * 160)
    assert service.change_recipe_candidate_role(**args).changed_count == 1
    assert row.meal_role == "vegetable" and row.revision == 5
    assert repo.events[0].before_diff == {"meal_role": "standalone", "revision": 4}
    assert repo.events[0].after_diff == {"meal_role": "vegetable", "revision": 5}
    assert repo.events[0].reason == "已核对菜品"
    assert all(len(event.command_key) <= 160 for event in repo.events)
    assert service.change_recipe_candidate_role(**args).changed_count == 1
    assert len(repo.events) == 2 and row.revision == 5
    with pytest.raises(RecipeCandidateConflict):
        service.change_recipe_candidate_role(**(args | {"command": command.model_copy(update={"meal_role": "staple"})}))
    assert service.change_recipe_candidate_role(**(args | {"command_key": "new-key"})).changed_count == 0
    actor.role = "user"
    with pytest.raises(AdminPermissionDenied):
        service.change_recipe_candidate_role(**args)


@pytest.mark.parametrize("deleted", [False, True])
def test_missing_or_deleted_member_aborts_before_changing_other_rows(deleted):
    actor = _user(role="admin")
    valid = ManagedRecipeCandidate(id=uuid4(), meal_role="standalone", revision=1)
    other = ManagedRecipeCandidate(id=uuid4(), meal_role="standalone", revision=1, deleted_at=datetime.now(UTC))
    repo = Repository(actor, [valid, other] if deleted else [valid])
    rollbacks = []
    service = AdminService(repository=repo, rollback=lambda: rollbacks.append(True))
    with pytest.raises(KeyError):
        service.change_recipe_candidate_role(actor_user_id=actor.id, command_key="missing-member", command=RecipeCandidateRoleCommand(ids=[valid.id, other.id], meal_role="drink", reason="核对", confirm=True))
    assert valid.meal_role == "standalone" and valid.revision == 1
    assert not repo.events and rollbacks == [True]


@pytest.mark.parametrize("changes", [{"meal_role": "unknown"}, {"reason": "  "}, {"confirm": False}])
def test_role_command_rejects_unknown_roles_blank_reasons_and_missing_confirmation(changes):
    with pytest.raises(ValidationError):
        RecipeCandidateRoleCommand.model_validate(dict(ids=[uuid4()], meal_role="drink", reason="已核对", confirm=True) | changes)
