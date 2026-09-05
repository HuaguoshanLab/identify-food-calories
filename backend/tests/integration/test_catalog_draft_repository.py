"""PostgreSQL contracts for draft persistence and append-only audit evidence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.admin.models import AdminAuditEvent, CatalogDraft
from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogListQuery


def test_catalog_draft_and_audit_flush_together_without_commit(db_session) -> None:
    repository = SqlAlchemyAdminRepository(db_session)
    draft = CatalogDraft(
        id=uuid.uuid4(), canonical_name="Oats", aliases=["rolled oats"],
        energy_kcal_per_100g=Decimal("389"), protein_g_per_100g=Decimal("16.9"),
        fat_g_per_100g=Decimal("6.9"), carbohydrate_g_per_100g=Decimal("66.3"),
        source_name="USDA", source_url="https://fdc.nal.usda.gov/", authorization_status="authorized",
        revision=1, created_at=datetime.now(UTC), updated_at=datetime.now(UTC),
    )
    repository.add_catalog_draft(draft)
    repository.add_audit_event(AdminAuditEvent(
        id=uuid.uuid4(), actor_identifier="admin-id", occurred_at=datetime.now(UTC),
        action="catalog_draft.create", object_type="catalog_draft", object_id=str(draft.id),
        reason="verified source import", before_diff={"revision": 0}, after_diff={"revision": 1},
        related_version=None, command_key="catalog-create-00000001",
    ))
    assert db_session.scalar(select(CatalogDraft).where(CatalogDraft.id == draft.id)) == draft
    assert repository.get_catalog_draft(draft.id) == draft


def test_catalog_list_filters_literal_search_and_stable_pagination(db_session) -> None:
    repository = SqlAlchemyAdminRepository(db_session)
    now = datetime.now(UTC)
    marker = str(uuid.uuid4())
    ids = []
    for name, alias, source, status in [('燕麦100%', 'rolled oats', 'USDA', 'authorized'), ('米饭', '白米', 'CN', 'pending'), ('燕麦片', 'oats', 'CN', 'revoked')]:
        draft = CatalogDraft(id=uuid.uuid4(), canonical_name=name, aliases=[alias],
            energy_kcal_per_100g=Decimal('100'), protein_g_per_100g=Decimal('1'), fat_g_per_100g=Decimal('2'),
            carbohydrate_g_per_100g=Decimal('3'), source_name=f'{marker} {source}', source_url='https://example.test/',
            authorization_status=status, revision=1, created_at=now, updated_at=now)
        repository.add_catalog_draft(draft)
        ids.append(draft.id)
    items, total = repository.list_catalog_drafts(query=CatalogListQuery(search='OATS', source=f'{marker} usda', authorization_status='authorized'), limit=20, offset=0)
    assert total == 1 and items[0].canonical_name == '燕麦100%'
    items, total = repository.list_catalog_drafts(query=CatalogListQuery(search='白米', source=marker), limit=20, offset=0)
    assert total == 1 and items[0].canonical_name == '米饭'
    items, total = repository.list_catalog_drafts(query=CatalogListQuery(search='%', source=marker), limit=20, offset=0)
    assert total == 1 and items[0].canonical_name == '燕麦100%'
    first, total = repository.list_catalog_drafts(query=CatalogListQuery(source=marker), limit=2, offset=0)
    second, _ = repository.list_catalog_drafts(query=CatalogListQuery(source=marker), limit=2, offset=2)
    assert total == 3
    assert [draft.id for draft in first + second] == sorted(ids, reverse=True)


def test_csv_import_database_failure_rolls_back_entire_batch(db_session) -> None:
    import pytest
    from app.admin.service import AdminService
    from app.admin.schemas import CatalogCsvImportCommand
    from tests.admin.test_catalog_csv import csv_content
    from tests.admin.test_catalog_draft_service import _admin

    actor = _admin()
    db_session.add(actor)
    db_session.commit()

    class FailingRepository(SqlAlchemyAdminRepository):
        writes = 0

        def add_catalog_draft(self, draft):
            self.writes += 1
            if self.writes == 2:
                raise RuntimeError('second row storage failed')
            return super().add_catalog_draft(draft)

    marker = str(uuid.uuid4())
    service = AdminService(repository=FailingRepository(db_session), commit=db_session.commit, rollback=db_session.rollback)
    with pytest.raises(RuntimeError):
        service.import_catalog_csv(actor_user_id=actor.id, command_key=f'csv-{marker}', command=CatalogCsvImportCommand(
            csv_text=csv_content(f'{marker}-one', f'{marker}-two'), reason='rollback integration', confirm=True))
    assert db_session.scalar(select(CatalogDraft).where(CatalogDraft.canonical_name.like(f'{marker}%'))) is None
    assert db_session.scalar(select(AdminAuditEvent).where(AdminAuditEvent.reason == 'rollback integration')) is None
