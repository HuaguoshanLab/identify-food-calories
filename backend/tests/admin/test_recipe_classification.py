from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.admin.recipe_classification import classify_recipe
from app.admin.schemas import (
    RecipeClassificationCommand,
    RecipeClassificationPreviewCommand,
    RecipeClassification,
)
from app.admin.service import (
    AdminService,
    RecipeCandidateConflict,
    AdminPermissionDenied,
)
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





@pytest.mark.parametrize(
    "name,role,tags,absent",
    [
        ("烤鱿鱼", "protein", {"shellfish"}, {"fish"}),
        ("奶茶粥", "unknown", set(), set()),
        ("鸡肉炒饭", "mixed_main", {"poultry"}, set()),
        ("白米饭", "staple", {"rice"}, set()),
        ("红烧鸡枞", "vegetable", {"mushroom"}, {"poultry"}),
        ("鱼香肉丝", "protein", set(), {"fish"}),
        ("菠萝包", "side", set(), {"fruit"}),
        ("奶豆腐", "dairy", {"dairy"}, {"soy"}),
        ("银鱼炒蛋", "protein", {"fish", "egg"}, set()),
        ("番茄炒蛋", "protein", {"fruit_veg", "egg"}, set()),
        ("瓦罐汤", "soup", set(), set()),
        ("一品锅", "unknown", set(), set()),
        ("奶茶", "drink", set(), set()),
        ("酸奶", "dairy", {"dairy"}, set()),
    ],
)
def test_evidence_based_classification(name, role, tags, absent):
    result = classify_recipe(name)
    assert result.role == role
    assert tags <= set(result.ingredient_tags)
    assert not absent & set(result.ingredient_tags)


def setup():
    actor = _user(role="admin")
    rows = [
        ManagedRecipeCandidate(
            id=uuid4(), catalog_food_name=name, revision=1, meal_slots=["lunch"]
        )
        for name in ["白米饭", "一品锅"]
    ]
    repo = Repository(actor, rows)
    service = AdminService(repository=repo)
    preview = service.preview_recipe_classification(
        actor_user_id=actor.id,
        command=RecipeClassificationPreviewCommand(ids=[r.id for r in rows]),
    )
    command = RecipeClassificationCommand(
        entries=preview.entries, reason="根据已知名称补齐", confirm=True
    )
    return actor, rows, repo, service, command


def test_backfill_audit_retry_and_legacy_eligibility_unchanged():
    actor, rows, repo, service, command = setup()
    args = dict(
        actor_user_id=actor.id, command=command, command_key="backfill-classification-1"
    )
    assert service.backfill_recipe_classification(**args).changed_count == 2
    assert all(row.revision == 2 for row in rows)
    assert (
        len(repo.events) == 3 and repo.events[0].before_diff["classification"] is None
    )
    assert service.backfill_recipe_classification(**args).changed_count == 2
    assert len(repo.events) == 3
    assert (
        service.preview_recipe_classification(
            actor_user_id=actor.id,
            command=RecipeClassificationPreviewCommand(ids=[r.id for r in rows]),
        ).skipped_count
        == 2
    )
    with pytest.raises(RecipeCandidateConflict):
        service.backfill_recipe_classification(
            **(args | {"command": command.model_copy(update={"reason": "different"})})
        )
    actor.role = "user"
    with pytest.raises(AdminPermissionDenied):
        service.backfill_recipe_classification(**args)


@pytest.mark.parametrize("failure", ["revision", "deleted", "classification", "tamper"])
def test_entire_batch_is_checked_before_changes(failure):
    actor, rows, repo, service, command = setup()
    if failure == "revision":
        rows[1].revision += 1
    if failure == "deleted":
        repo.rows.pop(rows[1].id)
    if failure == "classification":
        rows[1].classification = classify_recipe("一品锅").model_dump(
            mode="json"
        )
    if failure == "tamper":
        command = command.model_copy(
            update={
                "entries": [
                    command.entries[0].model_copy(
                        update={"classification": classify_recipe("鸡")}
                    ),
                    command.entries[1],
                ]
            }
        )
    with pytest.raises((RecipeCandidateConflict, KeyError)):
        service.backfill_recipe_classification(
            actor_user_id=actor.id, command=command, command_key="failure"
        )
    assert rows[0].classification is None and rows[0].revision == 1
    assert not repo.events


def test_unknown_tags_and_duplicate_ids_rejected():
    with pytest.raises(ValidationError):
        RecipeClassification(
            purpose="component", role="protein", ingredient_tags=["magic"], evidence="x"
        )
    identity = uuid4()
    with pytest.raises(ValidationError):
        RecipeClassificationPreviewCommand(ids=[identity, identity])


def test_manual_review_updates_existing_classification_and_retry_is_idempotent():
    actor, rows, repo, service, command = setup()
    service.backfill_recipe_classification(actor_user_id=actor.id, command=command, command_key="initial")
    entries = [entry.model_copy(update={"revision": 2, "classification": entry.classification.model_copy(update={"basis": "admin_review", "evidence": "管理员根据菜品资料确认"})}) for entry in command.entries]
    reviewed = command.model_copy(update={"entries": entries})
    args = dict(actor_user_id=actor.id, command=reviewed, command_key="review", review=True)
    assert service.backfill_recipe_classification(**args).changed_count == 2
    assert service.backfill_recipe_classification(**args).changed_count == 2
    assert len(repo.events) == 6
    assert all(row.revision == 3 for row in rows)
    with pytest.raises(RecipeCandidateConflict):
        service.backfill_recipe_classification(**(args | {"command_key": "stale-review"}))
    actor.role = "user"
    with pytest.raises(AdminPermissionDenied):
        service.backfill_recipe_classification(**args)


def test_unknown_recheck_cannot_overwrite_known_role():
    actor, rows, repo, service, command = setup()
    rows[0].classification = classify_recipe(rows[0].catalog_food_name).model_dump(mode="json")
    with pytest.raises(RecipeCandidateConflict):
        service.backfill_recipe_classification(actor_user_id=actor.id, command=command.model_copy(update={"review_unknown": True}), command_key="recheck")
    assert len(repo.events) == 0


def test_review_meal_slots_records_audit_and_replays_without_second_change():
    actor, rows, repo, service, command = setup()
    entry = command.entries[0].model_copy(update={'meal_slots': ('lunch', 'dinner'), 'classification': command.entries[0].classification.model_copy(update={'basis': 'admin_review'})})
    cmd = RecipeClassificationCommand(entries=[entry], reason='主食午晚共用', confirm=True)
    args = dict(actor_user_id=actor.id, command=cmd, command_key='multi-slot-review', review=True)
    assert service.backfill_recipe_classification(**args).changed_count == 1
    row = repo.rows[entry.id]
    assert row.meal_slots == ['lunch', 'dinner'] and row.revision == 2
    assert service.backfill_recipe_classification(**args).changed_count == 1
    assert row.revision == 2
    event = next(e for e in repo.events if e.object_id == str(row.id))
    assert event.before_diff['meal_slots'] == ['lunch']
    assert event.after_diff['meal_slots'] == ['lunch', 'dinner']
