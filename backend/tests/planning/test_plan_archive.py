"""Daily archive invariants with a fake repository and an injected clock."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.planning.archive_schemas import PlanArchiveWrite, PlanReport
from app.planning.archive_service import (
    PlanArchiveConflict,
    PlanArchiveService,
    PlanUnavailable,
)

NOW = datetime(2026, 9, 6, 16, 5, tzinfo=UTC)
OWNER = uuid.uuid4()


def report(name="早餐"):
    return PlanReport.model_validate(
        {
            "stage": "complete",
            "target": {
                key: {"lower": "0", "upper": "2000"}
                for key in ("energy_kcal", "protein_g", "fat_g", "carbohydrate_g")
            },
            "meals": [
                {
                    "slot": slot,
                    "display_name": name if slot == "breakfast" else slot,
                    "portion_description": "一份",
                    "portion_grams": "200",
                    "method_tags": [],
                    "flavour_tags": [],
                    "matched_preference_summaries": [],
                    "matched_exclusion_summaries": [],
                    "nutrients": {
                        "energy_kcal": "400.25",
                        "protein_g": "20",
                        "fat_g": "10",
                        "carbohydrate_g": "50",
                    },
                }
                for slot in ("breakfast", "lunch", "dinner")
            ],
            "disclaimer": "普通饮食参考，不替代医疗建议。",
        }
    )


def command(**updates):
    return PlanArchiveWrite(
        user_id=OWNER,
        run_id=updates.pop("run_id", uuid.uuid4()),
        thread_id=updates.pop("thread_id", uuid.uuid4()),
        started_at=updates.pop("started_at", NOW - timedelta(minutes=10)),
        report=updates.pop("report", report()),
        recipe_ids=(uuid.uuid4(), uuid.uuid4(), uuid.uuid4()),
        target_version="target.v1",
        formula_version="formula.v1",
        graph_version="graph.v1",
        tool_version="tools.v1",
        **updates,
    )


class FakeArchive:
    def __init__(self):
        self.plans = []
        self.versions = []
        self.zone = "Asia/Shanghai"
        self.can_resume = True

    def lock_owner(self, user_id):
        pass

    def time_zone(self, user_id):
        return self.zone

    def by_id(self, user_id, plan_id):
        return next(
            (p for p in self.plans if p.id == plan_id and p.user_id == user_id), None
        )

    def latest_deletion(self, user_id, day):
        return max(
            (
                p.deleted_at
                for p in self.plans
                if p.user_id == user_id
                and p.plan_date == day
                and p.deleted_at is not None
            ),
            default=None,
        )

    def by_date(self, user_id, day):
        return next(
            (
                p
                for p in self.plans
                if p.plan_date == day and p.user_id == user_id and p.deleted_at is None
            ),
            None,
        )

    def by_thread(self, user_id, thread_id):
        version = next(
            (
                v
                for v in self.versions
                if v.user_id == user_id and v.source_thread_id == thread_id
            ),
            None,
        )
        return self.by_id(user_id, version.plan_id) if version else None

    def by_run(self, user_id, run_id):
        return next(
            (
                v
                for v in self.versions
                if v.user_id == user_id and v.source_run_id == run_id
            ),
            None,
        )

    def version(self, user_id, plan_id, number):
        return next(
            (
                v
                for v in self.versions
                if v.user_id == user_id and v.plan_id == plan_id and v.version == number
            ),
            None,
        )

    def history(self, user_id, before, limit):
        return sorted(
            (
                p
                for p in self.plans
                if p.user_id == user_id
                and p.deleted_at is None
                and (before is None or p.plan_date < before)
            ),
            key=lambda p: p.plan_date,
            reverse=True,
        )[:limit]

    def add_plan(self, plan):
        self.plans.append(plan)

    def add_version(self, version):
        self.versions.append(version)

    def flush(self):
        pass

    def erase_snapshots(self, user_id, plan_id):
        for v in self.versions:
            if v.user_id == user_id and v.plan_id == plan_id:
                v.report = v.totals = v.provenance = None

    def resumable(self, user_id, thread_id):
        return self.can_resume

    def recipe_versions(self, ids):
        return []


def test_date_pins_start_before_midnight_and_never_reclassifies_adjustments():
    repo = FakeArchive()
    service = PlanArchiveService(repository=repo, now=lambda: NOW)
    first = command()
    service.record_completion(first)
    plan = repo.plans[0]
    assert str(plan.plan_date) == "2026-09-06"
    assert service.today(OWNER).plan is None
    service.record_completion(command(thread_id=first.thread_id, started_at=NOW))
    assert len(repo.plans) == 1 and plan.current_version == 2
    assert service.detail(OWNER, plan.id).totals.energy_kcal == 1200.75
    assert service.detail(OWNER, plan.id).adjustment_thread_id is None


def test_replay_is_idempotent_and_regeneration_preserves_prior_snapshot():
    repo = FakeArchive()
    service = PlanArchiveService(repository=repo, now=lambda: NOW)
    first = command(started_at=NOW)
    service.record_completion(first)
    service.record_completion(first)
    assert len(repo.versions) == 1
    service.record_completion(command(started_at=NOW, report=report("新早餐")))
    plan = repo.plans[0]
    assert service.detail(OWNER, plan.id, 1).report.meals[0].display_name == "早餐"
    assert service.detail(OWNER, plan.id).report.meals[0].display_name == "新早餐"
    with pytest.raises(PlanArchiveConflict):
        service.record_completion(command(thread_id=first.thread_id, started_at=NOW))
    assert plan.current_version == 2


def test_delete_erases_payloads_and_stale_completion_cannot_resurrect():
    repo = FakeArchive()
    service = PlanArchiveService(repository=repo, now=lambda: NOW)
    first = command(started_at=NOW)
    service.record_completion(first)
    plan = repo.plans[0]
    service.delete(OWNER, plan.id)
    assert all(
        v.report is None and v.totals is None and v.provenance is None
        for v in repo.versions
    )
    assert service.history(OWNER, None, 20).items == ()
    with pytest.raises(PlanArchiveConflict):
        service.record_completion(first)
    with pytest.raises(PlanUnavailable):
        service.detail(OWNER, plan.id)


def test_owner_isolation_expired_runtime_and_timezone_precondition():
    repo = FakeArchive()
    service = PlanArchiveService(repository=repo, now=lambda: NOW)
    service.record_completion(command(started_at=NOW))
    plan = repo.plans[0]
    with pytest.raises(PlanUnavailable):
        service.detail(uuid.uuid4(), plan.id)
    with pytest.raises(PlanUnavailable):
        service.delete(uuid.uuid4(), plan.id)
    repo.can_resume = False
    assert service.detail(OWNER, plan.id).adjustment_thread_id is None
    assert service.detail(OWNER, plan.id).report.meals
    repo.zone = None
    assert service.today(OWNER).time_zone is None
    with pytest.raises(PlanArchiveConflict):
        service.record_completion(command())


def test_history_keyset_and_version_bounds():
    repo = FakeArchive()
    service = PlanArchiveService(repository=repo, now=lambda: NOW)
    for days in range(3):
        service.record_completion(command(started_at=NOW - timedelta(days=days)))
    page = service.history(OWNER, None, 2)
    assert len(page.items) == 2 and page.next_before == page.items[-1].plan_date
    assert len(service.history(OWNER, page.next_before, 2).items) == 1
    with pytest.raises(PlanUnavailable):
        service.detail(OWNER, page.items[0].id, 100)


def test_inflight_regeneration_cannot_recreate_a_day_deleted_after_it_started():
    repo = FakeArchive()
    service = PlanArchiveService(repository=repo, now=lambda: NOW)
    service.record_completion(command(started_at=NOW))
    service.delete(OWNER, repo.plans[0].id)
    with pytest.raises(PlanArchiveConflict):
        service.record_completion(command(started_at=NOW))
    service.record_completion(command(started_at=NOW + timedelta(seconds=1)))
    assert len(service.history(OWNER, None, 20).items) == 1
