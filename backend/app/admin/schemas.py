"""Public admin API contracts, separate from SQLAlchemy audit state."""

import uuid
from decimal import Decimal
from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class AdminProbeResponse(BaseModel):
    """Minimal backend-only proof that database RBAC granted access."""

    status: Literal["ADMIN_ACCESS_GRANTED"] = "ADMIN_ACCESS_GRANTED"


class AdminUserQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    search: str = Field(default="", max_length=320)
    role: Literal["user", "admin"] | None = None
    status: Literal["active", "inactive", "unverified"] | None = None
    page: int = Field(default=1, ge=1, le=100_000)
    page_size: int = Field(default=20, ge=1, le=100)

    @field_validator("search")
    @classmethod
    def normalize_search(cls, value: str) -> str:
        return value.strip().lower()


class AdminUserResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    email: str
    email_verified_at: datetime | None
    is_active: bool
    role: Literal["user", "admin"]
    created_at: datetime
    updated_at: datetime


class AdminUserPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[AdminUserResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class AdminRoleResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["user", "admin"]
    label: str
    description: str
    account_count: int = Field(ge=0)
    permissions: list[str]


class AdminRoleListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[AdminRoleResponse]


class AdminRoleChangeCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["user", "admin"]
    reason: str = Field(min_length=1, max_length=500)
    confirm: Literal[True]

    @field_validator("reason")
    @classmethod
    def normalize_role_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized


class AdminRoleChangeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    audit_id: uuid.UUID
    target_user_id: uuid.UUID
    before_role: Literal["user", "admin"]
    after_role: Literal["user", "admin"]
    occurred_at: datetime


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


class RuntimeConfigCommand(BaseModel):
    """Allowlisted, non-secret input for a future provider policy version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: Literal["deepseek"]
    model_alias: Literal["deepseek-v4-flash"]
    enabled: bool
    single_call_cap_usd: Decimal = Field(ge=0, le=1000, max_digits=12, decimal_places=6)
    period_cap_usd: Decimal = Field(ge=0, le=100000, max_digits=12, decimal_places=6)
    input_usd_per_m: Decimal = Field(ge=0, le=1000, max_digits=12, decimal_places=6)
    output_usd_per_m: Decimal = Field(ge=0, le=1000, max_digits=12, decimal_places=6)
    reason: str = Field(min_length=1, max_length=500)
    confirm: Literal[True]

    @field_validator("reason")
    @classmethod
    def normalize_runtime_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must not be blank")
        return normalized


class RuntimeConfigResponse(BaseModel):
    """Safe immutable configuration projection; no resolver secret can reach HTTP."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    version: int = Field(gt=0)
    provider: Literal["deepseek"]
    model_alias: Literal["deepseek-v4-flash"]
    enabled: bool
    single_call_cap_usd: Decimal
    period_cap_usd: Decimal
    input_usd_per_m: Decimal
    output_usd_per_m: Decimal
    created_at: datetime


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
    energy_kcal_per_100g: Decimal = Field(
        ge=0, le=10000, max_digits=14, decimal_places=6
    )
    protein_g_per_100g: Decimal = Field(ge=0, le=1000, max_digits=14, decimal_places=6)
    fat_g_per_100g: Decimal = Field(ge=0, le=1000, max_digits=14, decimal_places=6)
    carbohydrate_g_per_100g: Decimal = Field(
        ge=0, le=1000, max_digits=14, decimal_places=6
    )
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
        if any(not alias for alias in normalized) or len(
            set(alias.casefold() for alias in normalized)
        ) != len(normalized):
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
    energy_kcal_per_100g: Decimal | None = Field(
        default=None, ge=0, le=10000, max_digits=14, decimal_places=6
    )
    protein_g_per_100g: Decimal | None = Field(
        default=None, ge=0, le=1000, max_digits=14, decimal_places=6
    )
    fat_g_per_100g: Decimal | None = Field(
        default=None, ge=0, le=1000, max_digits=14, decimal_places=6
    )
    carbohydrate_g_per_100g: Decimal | None = Field(
        default=None, ge=0, le=1000, max_digits=14, decimal_places=6
    )
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
        return (
            _CatalogDraftFields.normalize_aliases(aliases)
            if aliases is not None
            else None
        )

    @field_validator("source_url")
    @classmethod
    def require_patch_https_source(cls, value: HttpUrl | None) -> HttpUrl | None:
        return (
            _CatalogDraftFields.require_https_source(value)
            if value is not None
            else None
        )

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


class CatalogListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    search: str = Field(default="", max_length=200)
    source: str = Field(default="", max_length=120)
    authorization_status: Literal["authorized", "pending", "revoked"] | None = None
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=20, ge=1, le=100)


class CatalogListItem(CatalogDraftResponse):
    updated_at: datetime


class CatalogListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[CatalogListItem]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class CatalogCsvInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    csv_text: str = Field(min_length=1, max_length=1_048_576)


class CatalogCsvImportCommand(CatalogCsvInput):
    reason: str = Field(min_length=1, max_length=500)
    confirm: Literal[True]

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        return CatalogDraftCreateCommand.normalize_reason(value)


class CatalogCsvError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    row: int
    field: str
    message: str


class CatalogCsvPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total_rows: int
    valid_rows: int
    rows: list[CatalogDraftCreateCommand]
    errors: list[CatalogCsvError]


class CatalogCsvImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    imported_count: int
    draft_ids: list[uuid.UUID]


class RecipeCandidateCsvRow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    catalog_food_name: str = Field(min_length=1, max_length=200)
    meal_slot: Literal["breakfast", "lunch", "dinner", "snack"]
    portion_grams: Decimal = Field(gt=0, le=2000, max_digits=14, decimal_places=6)
    portion_description: str = Field(min_length=1, max_length=120)
    method_tags: tuple[str, ...] = Field(min_length=1, max_length=20)
    flavour_tags: tuple[str, ...] = Field(min_length=1, max_length=20)
    status: Literal["pending", "disabled"] = "pending"

    @field_validator("catalog_food_name", "portion_description")
    @classmethod
    def clean_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("method_tags", "flavour_tags")
    @classmethod
    def clean_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        tags = tuple(tag.strip() for tag in value)
        if any(not tag for tag in tags):
            raise ValueError("tags cannot be blank")
        return tags


class RecipeCandidateCsvError(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    row: int
    field: str
    message: str


class RecipeCandidateCsvPreview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    total_rows: int
    valid_rows: int
    rows: list[RecipeCandidateCsvRow]
    errors: list[RecipeCandidateCsvError]


class RecipeCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: uuid.UUID
    catalog_food_name: str
    meal_slot: Literal["breakfast", "lunch", "dinner", "snack"]
    portion_grams: Decimal
    portion_description: str
    method_tags: tuple[str, ...]
    flavour_tags: tuple[str, ...]
    status: Literal["pending", "enabled", "disabled"]
    revision: int = Field(ge=1)


class RecipeCandidateListQuery(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)
    search: str = Field(default="", max_length=200)
    meal_slot: Literal["breakfast", "lunch", "dinner", "snack"] | None = None
    status: Literal["pending", "enabled", "disabled"] | None = None
    page: int = Field(default=1, ge=1, le=100000)
    page_size: int = Field(default=20, ge=1, le=100)


class RecipeCandidateListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: list[RecipeCandidateResponse]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)


class RecipeCandidateImportCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    csv_text: str = Field(min_length=1, max_length=1_048_576)
    reason: str = Field(min_length=1, max_length=500)
    confirm: Literal[True]

    @field_validator("reason")
    @classmethod
    def clean_reason(cls, value: str) -> str:
        return CatalogDraftCreateCommand.normalize_reason(value)


class RecipeCandidateImportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    imported_count: int
    candidate_ids: list[uuid.UUID]


class RecipeCandidateBulkCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    ids: list[uuid.UUID] = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=500)
    confirm: Literal[True]

    @field_validator("ids")
    @classmethod
    def unique_ids(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("ids must be unique")
        return value


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
        Literal[
            "catalog_identity",
            "nutrition_per_100g",
            "source_evidence",
            "authorization_status",
        ]
    ] = Field(min_length=1)


class CatalogLifecycleFieldDiff(BaseModel):
    """Safe before/current values for a high-risk review or publication command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: CatalogDraftDiffField
    before: str | None
    after: str | None
    change: Literal["added", "modified", "removed", "unchanged"]


class CatalogLifecycleImpact(BaseModel):
    """Bounded consequence text derived by the server, never by browser input."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    affected_catalog_items: int = Field(ge=0, le=1)
    description: str = Field(min_length=1, max_length=500)


class CatalogLifecyclePublicationResponse(BaseModel):
    """Minimal active immutable-version state needed for an explicit command."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    draft_revision: int = Field(gt=0)
    eligibility: Literal["eligible", "disqualified"]
    related_version: str = Field(min_length=1, max_length=120)


class CatalogLifecyclePreviewResponse(BaseModel):
    """Read-only server projection for review/publish/disqualification confirmation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    draft: CatalogDraftResponse
    publication: CatalogLifecyclePublicationResponse | None
    field_diffs: list[CatalogLifecycleFieldDiff] = Field(min_length=1, max_length=9)
    impact: CatalogLifecycleImpact


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


class AdminRunQuery(BaseModel):
    """Bounded filters for terminal Agent ledger evidence only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    limit: int = Field(default=50, ge=1, le=100)
    cursor: str | None = Field(default=None, min_length=16, max_length=500)
    occurred_after: datetime | None = None
    occurred_before: datetime | None = None
    status: Literal["completed", "failed", "limit_reached"] | None = None
    graph_version: str | None = Field(default=None, min_length=1, max_length=80)
    model: str | None = Field(default=None, min_length=3, max_length=201)
    failure_node: str | None = Field(default=None, min_length=1, max_length=80)
    failure_code: str | None = Field(default=None, min_length=1, max_length=80)

    @model_validator(mode="after")
    def validate_terminal_window_and_model(self) -> "AdminRunQuery":
        if (
            self.occurred_after is not None
            and self.occurred_before is not None
            and self.occurred_after > self.occurred_before
        ):
            raise ValueError("occurred_after must not be after occurred_before")
        if self.model is not None and self.model.count(":") != 1:
            raise ValueError("model must use provider:model_version")
        return self


class AdminRunMetricsResponse(BaseModel):
    """Shared server-side terminal-run metrics; browsers do not recalculate them."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    terminal_count: int = Field(ge=0)
    failure_ratio: Decimal = Field(ge=0, le=1)
    p50_elapsed_ms: int | None = Field(default=None, ge=0)
    p95_elapsed_ms: int | None = Field(default=None, ge=0)
    total_cost_usd: Decimal = Field(ge=0)
    from_: datetime = Field(serialization_alias="from", validation_alias="from")
    to: datetime


class AdminRunDetailResponse(BaseModel):
    """Whitelist projection: no email, raw request/image, body, State, or secrets."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: uuid.UUID
    status: Literal["completed", "failed", "limit_reached"]
    graph_version: str
    model_provider: str | None
    model_version: str | None
    graph_steps: int = Field(ge=0)
    model_calls: int = Field(ge=0)
    tool_calls: int = Field(ge=0)
    elapsed_ms: int = Field(ge=0)
    estimated_cost_usd: Decimal = Field(ge=0)
    failure_code: str | None
    finished_at: datetime
    invocations: list["AdminRunInvocationResponse"] = Field(default_factory=list)


class AdminRunInvocationResponse(BaseModel):
    """Allowlisted tool/node outcome; provider inputs and bodies never cross this boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    node_name: str
    status: Literal["prepared", "completed", "failed", "outcome_unknown"]
    attempt: int = Field(ge=0)
    cost_usd: Decimal = Field(ge=0)
    failure_code: str | None
    safe_result_digest: str | None


class AdminRunPageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    items: list[AdminRunDetailResponse]
    next_cursor: str | None
