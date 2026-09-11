"""PostgreSQL contracts for governed catalog relation evidence."""

from __future__ import annotations

from datetime import UTC, datetime
import uuid

import pytest
from sqlalchemy import select

from app.admin.repository import SqlAlchemyAdminRepository
from app.admin.schemas import CatalogDraftCreateCommand, CatalogLifecycleCommand, CatalogRelationEvidenceCommand, CatalogRelationEvidenceRevokeCommand
from app.admin.service import AdminPermissionDenied, AdminService
from app.auth.models import User, UserRole
from app.nutrition.search_models import CatalogSearchName, CatalogSearchRelationEvidence


def _actor(now: datetime, role: UserRole = UserRole.ADMIN) -> User:
    return User(id=uuid.uuid4(), email=f"relation-{uuid.uuid4().hex}@example.test", password_hash="hash", role=role.value, is_active=True, email_verified_at=now, created_at=now, updated_at=now)


def _publish(service: AdminService, actor_id: uuid.UUID, name: str, alias: str, key: str) -> uuid.UUID:
    draft = service.create_catalog_draft(actor_user_id=actor_id, command=CatalogDraftCreateCommand(canonical_name=name, aliases=[alias], energy_kcal_per_100g="89", protein_g_per_100g="5", fat_g_per_100g="6", carbohydrate_g_per_100g="4", source_name="USDA", source_url="https://fdc.nal.usda.gov/", authorization_status="authorized", reason="relation fixture"), command_key=f"create-{key}-00000001")
    lifecycle = CatalogLifecycleCommand(reason="reviewed", confirm=True)
    service.review_catalog_draft(actor_user_id=actor_id, draft_id=draft.id, expected_revision=1, command=lifecycle, command_key=f"review-{key}-00000001")
    return service.publish_catalog_draft(actor_user_id=actor_id, draft_id=draft.id, expected_revision=1, command=lifecycle, command_key=f"publish-{key}-00000001").id


def test_relation_evidence_is_admin_only_version_bound_append_only_and_audited(db_session) -> None:
    now = datetime.now(UTC)
    admin, user = _actor(now), _actor(now, UserRole.USER)
    db_session.add_all([admin, user])
    db_session.flush()
    service = AdminService(repository=SqlAlchemyAdminRepository(db_session), now=lambda: now, commit=db_session.commit, rollback=db_session.rollback)
    source_publication_id = _publish(service, admin.id, "番茄炒蛋", "西红柿炒鸡蛋", "source")
    target_publication_id = _publish(service, admin.id, "烤鱼", "四川烤鱼", "target")
    source_name = db_session.scalar(select(CatalogSearchName).where(CatalogSearchName.publication_id == source_publication_id, CatalogSearchName.name_kind == "controlled_alias"))
    target_name = db_session.scalar(select(CatalogSearchName).where(CatalogSearchName.publication_id == target_publication_id, CatalogSearchName.name_kind == "canonical"))
    assert source_name is not None and target_name is not None
    command = CatalogRelationEvidenceCommand(source_publication_id=source_publication_id, source_name_id=source_name.id, target_publication_id=target_publication_id, target_name_id=target_name.id, relation="name_variant", reason="verified controlled synonym")
    created = service.create_catalog_relation_evidence(actor_user_id=admin.id, command=command, command_key="relation-create-00000001")
    assert created.status == "active"
    assert service.create_catalog_relation_evidence(actor_user_id=admin.id, command=command, command_key="relation-create-00000001").id == created.id
    updated = service.create_catalog_relation_evidence(actor_user_id=admin.id, command=command.model_copy(update={"relation": "regional_preparation_variant", "reason": "refined evidence"}), command_key="relation-update-00000001")
    revoked = service.revoke_catalog_relation_evidence(actor_user_id=admin.id, evidence_id=updated.id, command=CatalogRelationEvidenceRevokeCommand(reason="superseded"), command_key="relation-revoke-00000001")
    assert revoked.status == "revoked"
    rows = list(db_session.scalars(select(CatalogSearchRelationEvidence)))
    assert {(row.status, row.relation) for row in rows} == {("active", "name_variant"), ("active", "regional_preparation_variant"), ("revoked", "regional_preparation_variant")}
    with pytest.raises(AdminPermissionDenied):
        service.create_catalog_relation_evidence(actor_user_id=user.id, command=command, command_key="relation-user-00000001")
    with pytest.raises(KeyError):
        service.create_catalog_relation_evidence(actor_user_id=admin.id, command=command.model_copy(update={"source_publication_id": uuid.uuid4()}), command_key="relation-stale-00000001")
