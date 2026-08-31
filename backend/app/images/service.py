"""Decode and normalize one upload before any Provider can observe it."""

from __future__ import annotations

import hashlib
import io
import secrets
import warnings
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import cast

from PIL import Image, UnidentifiedImageError

from app.images.repository import PrivateTemporaryImageRepository
from app.images.schemas import CanonicalImageMime, ImageValidationError, ValidatedImageReference


_FORMAT_TO_MIME: dict[str, CanonicalImageMime] = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
_MIME_TO_FORMAT = {mime: image_format for image_format, mime in _FORMAT_TO_MIME.items()}
_MIME_TO_EXTENSION = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


class ImageSafetyService:
    """Normalize untrusted uploads and ensure every exit has a deletion path."""

    def __init__(
        self,
        *,
        repository: PrivateTemporaryImageRepository,
        max_bytes: int,
        max_pixels: int,
        ttl_seconds: int,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if min(max_bytes, max_pixels, ttl_seconds) <= 0:
            raise ValueError("image safety limits must be positive")
        self._repository = repository
        self._max_bytes = max_bytes
        self._max_pixels = max_pixels
        self._ttl = timedelta(seconds=ttl_seconds)
        self._now = now or (lambda: datetime.now(UTC))

    def validate_and_store(self, *, content: bytes, declared_mime: str | None) -> ValidatedImageReference:
        """Return only a metadata reference after bounded decode and metadata stripping."""

        if not content:
            raise ImageValidationError("IMAGE_EMPTY", "请选择一张有效图片后重试。")
        if len(content) > self._max_bytes:
            raise ImageValidationError("IMAGE_TOO_LARGE", "图片文件超过允许大小，请压缩后重试。")
        if declared_mime not in _MIME_TO_FORMAT:
            raise ImageValidationError("IMAGE_TYPE_UNSUPPORTED", "仅支持 JPEG、PNG 或 WebP 图片。")

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(io.BytesIO(content)) as source:
                    actual_format = source.format
                    mime = _FORMAT_TO_MIME.get(actual_format or "")
                    if mime is None or mime != declared_mime:
                        raise ImageValidationError("IMAGE_TYPE_MISMATCH", "图片格式与文件声明不一致。")
                    width, height = source.size
                    if width <= 0 or height <= 0 or width * height > self._max_pixels:
                        raise ImageValidationError("IMAGE_PIXELS_EXCEEDED", "图片尺寸超过允许范围，请缩小后重试。")
                    source.load()
                    normalized = self._normalize(source, mime)
        except ImageValidationError:
            raise
        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            raise ImageValidationError("IMAGE_PIXELS_EXCEEDED", "图片尺寸超过允许范围，请缩小后重试。") from None
        except (UnidentifiedImageError, OSError, ValueError):
            raise ImageValidationError("IMAGE_DECODE_INVALID", "图片无法安全解析，请重新选择图片。") from None

        digest = hashlib.sha256(normalized).hexdigest()
        created_at = self._now()
        canonical_mime = cast(CanonicalImageMime, declared_mime)
        extension = _MIME_TO_EXTENSION[canonical_mime]
        reference = ValidatedImageReference(
            digest_sha256=digest,
            mime_type=canonical_mime,
            width=width,
            height=height,
            byte_size=len(normalized),
            locator=f"{secrets.token_hex(16)}.{extension}",
            created_at=created_at,
            expires_at=created_at + self._ttl,
        )
        self._repository.write(locator=reference.locator, content=normalized)
        return reference

    def delete(self, reference: ValidatedImageReference) -> None:
        self._repository.delete(reference)

    def cleanup_expired(self, references: tuple[ValidatedImageReference, ...]) -> tuple[str, ...]:
        """Delete expired handles; callers keep authoritative metadata outside this repository."""

        now = self._now()
        deleted: list[str] = []
        for reference in references:
            if reference.expires_at <= now:
                self.delete(reference)
                deleted.append(reference.locator)
        return tuple(deleted)

    @staticmethod
    def _normalize(source: Image.Image, mime: CanonicalImageMime) -> bytes:
        """Re-encode pixel data to intentionally drop EXIF and format-specific metadata."""

        if mime == "image/jpeg":
            normalized = source.convert("RGB")
        elif mime == "image/png":
            normalized = source.convert("RGBA") if "A" in source.getbands() else source.convert("RGB")
        else:
            normalized = source.convert("RGBA") if "A" in source.getbands() else source.convert("RGB")
        output = io.BytesIO()
        normalized.save(output, format=_MIME_TO_FORMAT[mime])
        return output.getvalue()
