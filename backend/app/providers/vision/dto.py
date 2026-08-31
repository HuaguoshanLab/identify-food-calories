"""Strict visual observations; model output is never a nutrition source of truth."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.images.schemas import ValidatedImageReference


SafeIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
SafeText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=512)]


class VisionProviderDTO(BaseModel):
    """Unknown provider fields cannot silently enter the graph's observation boundary."""

    model_config = ConfigDict(extra="forbid")


class VisionUsageDTO(VisionProviderDTO):
    image_tokens: int = Field(ge=0)
    prompt_tokens: int = Field(ge=0)
    completion_tokens: int = Field(ge=0)
    total_tokens: int | None = Field(default=None, ge=0)
    cost_usd: Decimal = Field(ge=Decimal("0"))

    def model_post_init(self, __context: object) -> None:
        expected = self.image_tokens + self.prompt_tokens + self.completion_tokens
        if self.total_tokens is None:
            self.total_tokens = expected
        elif self.total_tokens != expected:
            raise ValueError("total_tokens must equal image, prompt and completion tokens")


class VisionCallMetadataDTO(VisionProviderDTO):
    call_id: SafeIdentifier = Field(default_factory=lambda: uuid4().hex)
    model_alias: SafeIdentifier
    provider_request_id: SafeIdentifier | None = None
    usage: VisionUsageDTO
    latency_ms: int = Field(ge=0)
    prompt_version: SafeIdentifier = "vision-meal.v1"
    schema_version: SafeIdentifier = "vision-provider.v1"


class VisionMealRequest(VisionProviderDTO):
    """A provider receives only this normalized temporary handle, never an upload body."""

    image: ValidatedImageReference
    prompt_version: SafeIdentifier = "vision-meal.v1"
    schema_version: SafeIdentifier = "vision-provider.v1"
    model_alias: SafeIdentifier
    pixel_budget: int = Field(gt=0, le=20_000_000)


class VisionMealItemDTO(VisionProviderDTO):
    item_id: SafeIdentifier
    food_name: SafeText
    preparation: SafeText | None = None
    portion_clue: SafeText | None = None
    estimated_grams: Decimal | None = Field(default=None, gt=Decimal("0"), le=Decimal("2000"))
    confidence: Decimal = Field(ge=Decimal("0"), le=Decimal("1"))


class VisionMealResult(VisionProviderDTO):
    items: list[VisionMealItemDTO] = Field(min_length=1, max_length=20)
    metadata: VisionCallMetadataDTO
