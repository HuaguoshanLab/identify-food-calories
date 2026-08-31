"""Security boundary tests for temporary image normalization."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from app.core.config import Settings
from app.images.repository import PrivateTemporaryImageRepository
from app.images.schemas import ImageValidationError
from app.images.service import ImageSafetyService


def _image_bytes(*, image_format: str = "JPEG", exif: bytes | None = None) -> bytes:
    image = Image.new("RGB", (12, 8), color="red")
    output = BytesIO()
    image.save(output, format=image_format, exif=exif or b"")
    return output.getvalue()


def _service(directory: Path, now: datetime | None = None) -> ImageSafetyService:
    return ImageSafetyService(
        repository=PrivateTemporaryImageRepository(directory),
        max_bytes=1024 * 1024,
        max_pixels=1000,
        ttl_seconds=60,
        now=(lambda: now) if now else None,
    )


def test_normalizes_metadata_into_private_file_and_returns_minimal_reference(tmp_path: Path) -> None:
    service = _service(tmp_path / "private")
    original = _image_bytes(exif=b"Exif\x00\x00GPS-data")

    reference = service.validate_and_store(content=original, declared_mime="image/jpeg")

    stored = (tmp_path / "private" / reference.locator).read_bytes()
    with Image.open(BytesIO(stored)) as result:
        assert result.getexif() == {}
        assert result.size == (12, 8)
    assert reference.mime_type == "image/jpeg"
    assert reference.byte_size == len(stored)
    assert "GPS" not in repr(reference)
    assert "original" not in reference.model_dump_json()
    assert (tmp_path / "private").stat().st_mode & 0o077 == 0


@pytest.mark.parametrize(
    ("content", "declared_mime", "code"),
    [
        (b"not-an-image", "image/jpeg", "IMAGE_DECODE_INVALID"),
        (_image_bytes(), "image/png", "IMAGE_TYPE_MISMATCH"),
        (_image_bytes(), "text/plain", "IMAGE_TYPE_UNSUPPORTED"),
        (b"x" * (1024 * 1024 + 1), "image/jpeg", "IMAGE_TOO_LARGE"),
    ],
)
def test_rejects_invalid_or_mismatched_uploads_without_writing_files(
    tmp_path: Path, content: bytes, declared_mime: str, code: str
) -> None:
    repository = PrivateTemporaryImageRepository(tmp_path / "private")
    service = ImageSafetyService(repository=repository, max_bytes=1024 * 1024, max_pixels=1000, ttl_seconds=60)

    with pytest.raises(ImageValidationError) as error:
        service.validate_and_store(content=content, declared_mime=declared_mime)

    assert error.value.code == code
    assert repository.list_locators() == ()


def test_rejects_pixel_bomb_and_deletes_expired_reference(tmp_path: Path) -> None:
    image = Image.new("RGB", (40, 40), color="red")
    output = BytesIO()
    image.save(output, format="PNG")
    service = _service(tmp_path / "private")

    with pytest.raises(ImageValidationError, match="尺寸"):
        service.validate_and_store(content=output.getvalue(), declared_mime="image/png")

    created = datetime(2026, 1, 1, tzinfo=UTC)
    expiring_service = _service(tmp_path / "expiring", created)
    reference = expiring_service.validate_and_store(content=_image_bytes(), declared_mime="image/jpeg")
    assert (tmp_path / "expiring" / reference.locator).exists()
    cleanup = _service(tmp_path / "expiring", created + timedelta(seconds=61))

    assert cleanup.cleanup_expired((reference,)) == (reference.locator,)
    assert not (tmp_path / "expiring" / reference.locator).exists()


def test_production_requires_explicit_safe_image_configuration() -> None:
    production = {
        "app_env": "production",
        "database_url": "postgresql+psycopg://db.example/food_agent",
        "secret_key": "x" * 32,
        "cookie_secure": True,
        "cors_origins": ["https://app.example"],
        "smtp_host": "smtp.example",
        "smtp_from_email": "noreply@example.com",
        "smtp_username": "mailer",
        "smtp_password": "password",
        "reasoning_provider_mode": "deepseek",
        "deepseek_api_key": "test-key",
        "deepseek_model": "deepseek-v4-flash",
        "deepseek_price_snapshot_version": "price-v1",
        "deepseek_input_usd_per_m": "1",
        "deepseek_output_usd_per_m": "1",
        "retention_checkpoint_event_days": 7,
        "retention_audit_days": 30,
        "retention_deletion_sla_hours": 24,
        "retention_poll_interval_seconds": 300,
    }
    with pytest.raises(ValidationError, match="IMAGE_MAX_BYTES"):
        Settings(_env_file=None, **production)

    configured = {
        **production,
        "image_max_bytes": 100,
        "image_max_pixels": 100,
        "image_ttl_seconds": 60,
        "image_temporary_directory": "/",
    }
    with pytest.raises(ValidationError, match="IMAGE_TEMPORARY_DIRECTORY"):
        Settings(_env_file=None, **configured)
