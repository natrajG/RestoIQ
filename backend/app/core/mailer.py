"""Outgoing email: Resend HTTP API if RESEND_API_KEY is set, otherwise SMTP."""
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def _sender() -> str | None:
    return settings.mail_from or settings.feedback_notify_email


def configured() -> bool:
    return bool(_sender() and (settings.resend_api_key or settings.smtp_host))


def send(to: str, subject: str, body: str) -> None:
    if settings.resend_api_key:
        response = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": _sender(), "to": [to], "subject": subject, "text": body},
            timeout=15,
        )
        response.raise_for_status()
        return
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = _sender(), to, subject
    message.set_content(body)
    context = ssl.create_default_context()
    if settings.smtp_port == 465:
        server = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=15, context=context)
    else:
        server = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15)
    with server:
        if settings.smtp_port != 465:
            server.starttls(context=context)
        if settings.smtp_username:
            server.login(settings.smtp_username, settings.smtp_password or "")
        server.send_message(message)


def send_safe(to: str, subject: str, body: str) -> str:
    """For notifications: a mail problem must never break the request that triggered it."""
    if not configured():
        logger.info("Email not configured; skipped %r", subject)
        return "not_configured"
    try:
        send(to, subject, body)
        return "sent"
    except Exception:
        logger.exception("Email %r could not be sent", subject)
        return "failed"
