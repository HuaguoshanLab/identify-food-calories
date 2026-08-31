"""Private temporary-file repository; locators are opaque and never public paths."""

from __future__ import annotations

import os
from pathlib import Path

from app.images.schemas import ValidatedImageReference


class PrivateTemporaryImageRepository:
    """Own a directory that is deliberately unsuitable for static-file serving."""

    def __init__(self, directory: Path) -> None:
        if not directory.is_absolute() or directory == Path("/"):
            raise ValueError("temporary image directory must be a private absolute directory")
        self._directory = directory

    def initialize(self) -> None:
        self._directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self._directory, 0o700)
        mode = self._directory.stat().st_mode & 0o777
        if mode & 0o077:
            raise ValueError("temporary image directory must not be group or world accessible")

    def write(self, *, locator: str, content: bytes) -> Path:
        self.initialize()
        target = self._path(locator)
        if target.exists():
            raise FileExistsError("temporary image locator collision")
        descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return target

    def read_path(self, reference: ValidatedImageReference) -> Path:
        target = self._path(reference.locator)
        if not target.is_file():
            raise FileNotFoundError("temporary image is unavailable")
        return target

    def delete(self, reference: ValidatedImageReference) -> None:
        self._path(reference.locator).unlink(missing_ok=True)

    def list_locators(self) -> tuple[str, ...]:
        if not self._directory.exists():
            return ()
        return tuple(path.name for path in self._directory.iterdir() if path.is_file())

    def _path(self, locator: str) -> Path:
        if "/" in locator or "\\" in locator or Path(locator).name != locator:
            raise ValueError("temporary image locator is invalid")
        return self._directory / locator
