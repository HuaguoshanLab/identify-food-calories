"""Public admin API contracts, separate from SQLAlchemy audit state."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator


class AdminProbeResponse(BaseModel):
    """Minimal backend-only proof that database RBAC granted access."""

    status: Literal["ADMIN_ACCESS_GRANTED"] = "ADMIN_ACCESS_GRANTED"


class AdminAuditEventResponse(BaseModel):
    """Allowlisted audit projection; it cannot grow into a raw event payload."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    actor_identifier: str
    occurred_at: datetime
    action: str
    object_type: str
    object_id: str
    reason: str
    before: dict[str, object]
    after: dict[str, object]
    related_version: str | None
    command_key: str


class AdminAuditPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[AdminAuditEventResponse]
    next_cursor: str | None


class AdminAuditQuery(BaseModel):
    """Bounded, read-only filters accepted by the audit timeline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=16, max_length=500)
    action: str | None = Field(default=None, max_length=80)
    object_type: str | None = Field(default=None, max_length=80)
    object_id: str | None = Field(default=None, max_length=160)
    actor: str | None = Field(default=None, max_length=320)
    reason: str | None = Field(default=None, max_length=500)
    occurred_after: datetime | None = None
    occurred_before: datetime | None = None

    @field_validator("action", "object_type", "object_id", "actor", "reason")
    @classmethod
    def normalize_optional_filter(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("filter must not be blank")
        return normalized


class _CatalogDraftFields(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_name: str = Field(min_length=1, max_length=200)
    aliases: list[str] = Field(min_length=1, max_length=50)
    energy_kcal_per_100g: Decimal = Field(ge=0, le=10000, max_digits=14, decimal_places=6)
    protein_g_per_100g: Decimal = Field(ge=0, le=1000, max_digits=14, decimal_places=6)
    fat_g_per_100g: Decimal = Field(ge=0, le=1000, max_digits=14, decimal_places=6)
    carbohydrate_g_per_100g: Decimal = Field(ge=0, le=1000, max_digits=14, decimal_places=6)
    source_name: str = Field(min_length=1, max_length=120)
    source_url: HttpUrl = Field(max_length=500)
    authorization_status: Literal["authorized", "pending", "revoked"]

    @field_validator("canonical_name", "source_name")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("aliases")
    @classmethod
    def normalize_aliases(cls, aliases: list[str]) -> list[str]:
        normalized = [alias.strip() for alias in aliases]
        if any(not alias for alias in normalized) or len(set(alias.casefold() for alias in normalized)) != len(normalized):
            raise ValueError("aliases must be non-empty and unique")
        return normalized

    @field_validator("source_url")
    @classmethod
    def require_https_source(cls, value: HttpUrl) -> HttpUrl:
        if value.scheme != "https":
            raise ValueError("source_url must use https")
        return value


class CatalogDraftCreateCommand(_CatalogDraftFields):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized


class CatalogDraftPatchCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_name: str | None = Field(default=None, min_length=1, max_length=200)
    aliases: list[str] | None = Field(default=None, min_length=1, max_length=50)
    energy_kcal_per_100g: Decimal | None = Field(default=None, ge=0, le=10000, max_digits=14, decimal_places=6)
    protein_g_per_100g: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=14, decimal_places=6)
    fat_g_per_100g: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=14, decimal_places=6)
    carbohydrate_g_per_100g: Decimal | None = Field(default=None, ge=0, le=1000, max_digits=14, decimal_places=6)
    source_name: str | None = Field(default=None, min_length=1, max_length=120)
    source_url: HttpUrl | None = Field(default=None, max_length=500)
    authorization_status: Literal["authorized", "pending", "revoked"] | None = None
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("canonical_name", "source_name", "reason")
    @classmethod
    def normalize_patch_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized

    @field_validator("aliases")
    @classmethod
    def normalize_patch_aliases(cls, aliases: list[str] | None) -> list[str] | None:
        return _CatalogDraftFields.normalize_aliases(aliases) if aliases is not None else None

    @field_validator("source_url")
    @classmethod
    def require_patch_https_source(cls, value: HttpUrl | None) -> HttpUrl | None:
        return _CatalogDraftFields.require_https_source(value) if value is not None else None

    @model_validator(mode="after")
    def require_field_change(self) -> "CatalogDraftPatchCommand":
        if not self.model_dump(exclude={"reason"}, exclude_none=True):
            raise ValueError("a draft field is required")
        return self


class CatalogDraftResponse(BaseModel):
    """Small UI-safe draft projection. Audit evidence has its own endpoint."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    canonical_name: str
    aliases: list[str]
    energy_kcal_per_100g: Decimal
    protein_g_per_100g: Decimal
    fat_g_per_100g: Decimal
    carbohydrate_g_per_100g: Decimal
    source_name: str
    source_url: str
    authorization_status: Literal["authorized", "pending", "revoked"]
    revision: int


class CatalogDraftPreviewCommand(_CatalogDraftFields):
    """A full candidate evaluated against the database's current draft state.

    The browser supplies no diff, revision, or impact claim: those are derived by
    the service after the same current-role check used by catalog mutations.
    """

    draft_id: uuid.UUID | None = None


CatalogDraftDiffField = Literal[
    "canonical_name",
    "aliases",
    "energy_kcal_per_100g",
    "protein_g_per_100g",
    "fat_g_per_100g",
    "carbohydrate_g_per_100g",
    "source_name",
    "source_url",
    "authorization_status",
]


class CatalogDraftFieldDiff(BaseModel):
    """An allowlisted, readable scalar difference produced by the server."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: CatalogDraftDiffField
    before: str | None
    after: str


class CatalogDraftPreviewResponse(BaseModel):
    """Safe server-computed preview for a create or edit command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft_id: uuid.UUID | None
    base_revision: int
    field_diffs: list[CatalogDraftFieldDiff] = Field(min_length=1)
    impact_categories: list[
        Literal["catalog_identity", "nutrition_per_100g", "source_evidence", "authorization_status"]
    ] = Field(min_length=1)


class CatalogLifecycleCommand(BaseModel):
    """High-risk lifecycle commands must be explicitly confirmed and explainable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reason: str = Field(min_length=1, max_length=500)
    confirm: Literal[True]

    @field_validator("reason")
    @classmethod
    def normalize_lifecycle_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized


class CatalogPublicationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    draft_id: uuid.UUID
    draft_revision: int
    content_hash: str
    eligibility: Literal["eligible", "disqualified"]
