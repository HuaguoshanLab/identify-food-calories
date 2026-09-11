"""Strict, privacy-bounded contracts for catalog/query embeddings."""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

EmbeddingTextType = Literal["query", "document"]
SafeIdentifier = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
NormalizedFoodName = Annotated[str, StringConstraints(min_length=1, max_length=200)]
FiniteFloat = Annotated[float, Field(allow_inf_nan=False)]
EMBEDDING_DIMENSION = 1024
MAX_CATALOG_BATCH_SIZE = 10


class EmbeddingProviderDTO(BaseModel):
    """Reject unrecognised fields so contextual data cannot cross this boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class EmbeddingUsageDTO(EmbeddingProviderDTO):
    input_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    cost_cny: Decimal = Field(ge=Decimal("0"))

    @model_validator(mode="after")
    def total_covers_input(self) -> EmbeddingUsageDTO:
        if self.total_tokens < self.input_tokens:
            raise ValueError("total_tokens must not be less than input_tokens")
        return self


class EmbeddingCallMetadataDTO(EmbeddingProviderDTO):
    call_id: SafeIdentifier = Field(default_factory=lambda: uuid4().hex)
    model_alias: SafeIdentifier
    embedding_version: SafeIdentifier
    provider_request_id: SafeIdentifier | None = None
    usage: EmbeddingUsageDTO
    latency_ms: int = Field(ge=0)
    schema_version: SafeIdentifier = "embedding-provider.v1"


class EmbeddingRequest(EmbeddingProviderDTO):
    """Only normalized food names are admissible; no meal or identity context exists here."""

    names: tuple[NormalizedFoodName, ...] = Field(min_length=1, max_length=MAX_CATALOG_BATCH_SIZE)
    text_type: EmbeddingTextType
    model_alias: SafeIdentifier
    embedding_version: SafeIdentifier = "embedding.v1"
    schema_version: SafeIdentifier = "embedding-provider.v1"
    request_key: SafeIdentifier = Field(default_factory=lambda: uuid4().hex)

    @field_validator("names")
    @classmethod
    def names_are_normalized_and_distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        for value in values:
            if value != " ".join(value.split()):
                raise ValueError("embedding names must already be normalized")
        if len(values) != len(set(values)):
            raise ValueError("embedding names must be unique within one request")
        return values

    @model_validator(mode="after")
    def enforces_query_or_catalog_cardinality(self) -> EmbeddingRequest:
        if self.text_type == "query" and len(self.names) != 1:
            raise ValueError("query embeddings require exactly one normalized food name")
        return self


class EmbeddingVectorDTO(EmbeddingProviderDTO):
    values: tuple[FiniteFloat, ...] = Field(min_length=EMBEDDING_DIMENSION, max_length=EMBEDDING_DIMENSION)


class EmbeddingResult(EmbeddingProviderDTO):
    """Validated provider output; input_count is scalar accounting, never input text."""

    input_count: int = Field(ge=1, le=MAX_CATALOG_BATCH_SIZE)
    vectors: tuple[EmbeddingVectorDTO, ...] = Field(min_length=1, max_length=MAX_CATALOG_BATCH_SIZE)
    metadata: EmbeddingCallMetadataDTO

    @model_validator(mode="after")
    def requires_one_vector_for_each_input(self) -> EmbeddingResult:
        if len(self.vectors) != self.input_count:
            raise ValueError("embedding result count must equal input_count")
        return self
