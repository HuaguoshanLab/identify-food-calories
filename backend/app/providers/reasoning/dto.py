"""Runtime-validated reasoning-provider contracts, never API, ORM, or graph state."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


SafeIdentifier = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=128),
]
SafeText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=512),
]


class ProviderDTO(BaseModel):
    """Make unrecognised provider fields a hard boundary violation."""

    model_config = ConfigDict(extra="forbid")


class ProviderFailureKind(StrEnum):
    """Stable error categories used by the run supervisor, not vendor exceptions."""

    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    OUTCOME_UNKNOWN = "PROVIDER_OUTCOME_UNKNOWN"


class ProviderUsageDTO(ProviderDTO):
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_usd: Decimal = Field(ge=Decimal("0"))

    def model_post_init(self, __context: object) -> None:
        if self.total_tokens is None:
            self.total_tokens = self.prompt_tokens + self.completion_tokens
        elif self.total_tokens != self.prompt_tokens + self.completion_tokens:
            raise ValueError("total_tokens must equal prompt_tokens + completion_tokens")


class ProviderCallMetadataDTO(ProviderDTO):
    call_id: SafeIdentifier = Field(default_factory=lambda: uuid4().hex)
    model_alias: SafeIdentifier
    provider_request_id: SafeIdentifier | None = None
    usage: ProviderUsageDTO
    latency_ms: int = Field(ge=0)
    prompt_version: SafeIdentifier = "reasoning-parse.v1"
    schema_version: SafeIdentifier = "reasoning-provider.v1"


class ParsedMealItemDTO(ProviderDTO):
    """A model observation only; deterministic tools own nutrition values."""

    item_id: SafeIdentifier
    food_name: SafeText
    quantity_text: SafeText | None = None
    grams: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("2000"))
    preparation: SafeText | None = None
    catalog_query: SafeText | None = None


class MissingMealFieldDTO(ProviderDTO):
    item_id: SafeIdentifier
    field: SafeIdentifier
    prompt_key: SafeIdentifier


class ParsedMealDTO(ProviderDTO):
    items: list[ParsedMealItemDTO] = Field(min_length=1, max_length=20)
    missing_fields: list[MissingMealFieldDTO] = Field(default_factory=list, max_length=20)


class ParseMealRequest(ProviderDTO):
    """Transient parse input. Call ledgers must store only its hash, never this body."""

    meal_description: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    prompt_version: SafeIdentifier = "reasoning-parse.v1"
    schema_version: SafeIdentifier = "reasoning-provider.v1"


class ApplyCorrectionRequest(ProviderDTO):
    """Transient correction input; it is intentionally excluded from Fake call traces."""

    correction_text: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    known_item_ids: list[SafeIdentifier] = Field(default_factory=list, max_length=20)
    prompt_version: SafeIdentifier = "reasoning-correction.v1"
    schema_version: SafeIdentifier = "reasoning-provider.v1"


class CorrectionDTO(ProviderDTO):
    items: list[ParsedMealItemDTO] = Field(default_factory=list, max_length=20)
    removed_item_ids: list[SafeIdentifier] = Field(default_factory=list, max_length=20)
    missing_fields: list[MissingMealFieldDTO] = Field(default_factory=list, max_length=20)


class ParseMealResult(ProviderDTO):
    value: ParsedMealDTO
    metadata: ProviderCallMetadataDTO


class ApplyCorrectionResult(ProviderDTO):
    value: CorrectionDTO
    metadata: ProviderCallMetadataDTO


class ProviderCallError(RuntimeError):
    """Safe failure envelope. Vendor body, stack, and chain-of-thought never cross this port."""

    def __init__(
        self,
        *,
        kind: ProviderFailureKind,
        code: SafeIdentifier,
        safe_message: SafeText = "Reasoning provider request could not be completed.",
        metadata: ProviderCallMetadataDTO | None = None,
    ) -> None:
        super().__init__(safe_message)
        self.kind = kind
        self.code = code
        self.safe_message = safe_message
        self.metadata = metadata
