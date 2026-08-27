"""Outbound mail capability used by application services."""

from __future__ import annotations

from typing import Protocol


class MailProvider(Protocol):
    def send_verification_code(
        self, *, recipient: str, code: str, expires_in_minutes: int
    ) -> None: ...
