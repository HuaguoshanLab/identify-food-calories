"""SMTP adapter; Mailpit is merely the local implementation of this port."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.core.config import ConfigurationError, Settings


class SMTPMailProvider:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        from_email: str,
        username: str | None = None,
        password: str | None = None,
        use_starttls: bool = False,
        timeout_seconds: float = 10.0,
    ) -> None:
        self._host = host
        self._port = port
        self._from_email = from_email
        self._username = username
        self._password = password
        self._use_starttls = use_starttls
        self._timeout_seconds = timeout_seconds

    def send_verification_code(
        self, *, recipient: str, code: str, expires_in_minutes: int
    ) -> None:
        message = EmailMessage()
        message["From"] = self._from_email
        message["To"] = recipient
        message["Subject"] = "饮食健康 Agent 邮箱验证码"
        message.set_content(
            f"你的邮箱验证码是：{code}\n\n"
            f"验证码 {expires_in_minutes} 分钟内有效。若非本人操作，请忽略此邮件。"
        )

        with smtplib.SMTP(
            self._host, self._port, timeout=self._timeout_seconds
        ) as smtp:
            if self._use_starttls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password or "")
            smtp.send_message(message)


def create_smtp_mail_provider(settings: Settings) -> SMTPMailProvider:
    """Build an adapter only from validated settings; production never falls back locally."""

    if not settings.smtp_from_email:
        raise ConfigurationError("SMTP_FROM_EMAIL is required for the mail provider")
    password = (
        settings.smtp_password.get_secret_value()
        if settings.smtp_password is not None
        else None
    )
    return SMTPMailProvider(
        host=settings.smtp_host,
        port=settings.smtp_port,
        from_email=settings.smtp_from_email,
        username=settings.smtp_username,
        password=password,
        use_starttls=settings.app_env == "production",
    )
