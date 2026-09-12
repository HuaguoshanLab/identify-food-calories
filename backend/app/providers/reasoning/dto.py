"""Runtime-validated reasoning-provider contracts, never API, ORM, or graph state."""

from __future__ import annotations

from decimal import Decimal
from enum import StrEnum
from datetime import date
import re
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


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
    prompt_version: SafeIdentifier = "reasoning-parse.v2"
    schema_version: SafeIdentifier = "reasoning-provider.v1"


class ParsedMealItemDTO(ProviderDTO):
    """A model observation only; deterministic tools own nutrition values."""

    item_id: SafeIdentifier
    food_name: SafeText
    quantity_text: SafeText | None = None
    grams: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("2000"))
    preparation: SafeText | None = None
    catalog_query: SafeText | None = None

    @model_validator(mode="after")
    def reject_or_discard_internal_item_references(self) -> "ParsedMealItemDTO":
        """Keep provider bookkeeping IDs out of the user-visible retrieval contract.

        ``item_id`` only identifies an item within one graph invocation.  It is never a
        food description and must not become a catalog lookup key.  A polluted
        ``food_name`` is not recoverable without guessing, so reject it.  A polluted
        optional query can safely fall back to the validated food name instead.
        """

        if _is_internal_item_reference(self.food_name, self.item_id):
            raise ValueError("food_name must not be an internal item identifier")
        if self.catalog_query is not None and _is_internal_item_reference(
            self.catalog_query, self.item_id
        ):
            self.catalog_query = None
        return self


def _is_internal_item_reference(value: str, item_id: str) -> bool:
    normalized = value.strip().casefold()
    return normalized == item_id.strip().casefold() or bool(
        re.fullmatch(r"(?:item|food)[_-]?\d+", normalized)
    )


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
    prompt_version: SafeIdentifier = "reasoning-parse.v2"
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


WeeklyReviewCategory = Literal[
    "meal_balance", "meal_regularity", "food_variety", "portion_awareness"
]


class WeeklyReviewTotalsDTO(ProviderDTO):
    """Numeric facts are inputs only; generated output can never carry them forward."""

    energy_kcal: int = Field(ge=0)
    protein_g: int = Field(ge=0)
    fat_g: int = Field(ge=0)
    carbohydrate_g: int = Field(ge=0)


class WeeklyReviewFactsDTO(ProviderDTO):
    """The complete de-identified whitelist allowed to cross into a reasoning provider."""

    facts_version: SafeIdentifier
    week_start: date
    week_end_exclusive: date
    week_kind: Literal["completed", "current_to_date"]
    coverage_days: int = Field(ge=0, le=7)
    meal_count: int = Field(ge=0)
    totals: WeeklyReviewTotalsDTO
    allowed_patterns: list[WeeklyReviewCategory] = Field(default_factory=list, max_length=4)
    coverage_sufficient: bool

    @field_validator("allowed_patterns")
    @classmethod
    def reject_duplicate_patterns(cls, values: list[WeeklyReviewCategory]) -> list[WeeklyReviewCategory]:
        if len(values) != len(set(values)):
            raise ValueError("weekly review patterns must be unique")
        return values


class WeeklyReviewRequest(ProviderDTO):
    """Transient facts-only request; ledgers retain its digest, never this body."""

    facts: WeeklyReviewFactsDTO
    prompt_version: SafeIdentifier = "weekly-review-prompt.v1"
    schema_version: SafeIdentifier = "weekly-review-schema.v1"
    retry_reason: Literal["schema_or_safety_invalid"] | None = None


class WeeklyReviewSuggestionDTO(ProviderDTO):
    category: WeeklyReviewCategory
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=220)]


class WeeklyReviewOutputDTO(ProviderDTO):
    """Structured shape only; graph-owned semantics revalidate every result."""

    suggestions: list[WeeklyReviewSuggestionDTO] = Field(min_length=1, max_length=3)
    disclaimer: Literal["仅基于已记录数据，供一般饮食参考，不构成医疗建议。"]


class WeeklyReviewResult(ProviderDTO):
    value: WeeklyReviewOutputDTO
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
