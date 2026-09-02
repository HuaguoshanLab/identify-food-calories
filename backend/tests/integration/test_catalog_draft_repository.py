"""PostgreSQL contracts for draft persistence and append-only audit evidence."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select

from app.admin.models import AdminAuditEvent, CatalogDraft
from app.admin.repository import SqlAlchemyAdminRepository


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
