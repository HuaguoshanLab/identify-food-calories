"""Minimal, runtime-validated values that may cross the image safety boundary."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


CanonicalImageMime = Literal["image/jpeg", "image/png", "image/webp"]
OpaqueLocator = Annotated[
    str,
    StringConstraints(pattern=r"^[a-f0-9]{32}\.(?:jpg|png|webp)$"),
]


class ImageBoundaryModel(BaseModel):
    """Reject fields that could accidentally add raw upload data to the boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class ValidatedImageReference(ImageBoundaryModel):
    """Safe handle for a normalized, short-lived file; never embeds image content."""

    digest_sha256: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")]
    mime_type: CanonicalImageMime
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    byte_size: int = Field(gt=0)
    locator: OpaqueLocator
    created_at: datetime
    expires_at: datetime


class ImageValidationError(ValueError):
    """Stable user-safe failure without preserving a parser or filesystem detail."""

    def __init__(self, code: str, safe_message: str) -> None:
        super().__init__(safe_message)
        self.code = code
        self.safe_message = safe_message
