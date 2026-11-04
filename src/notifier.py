"""
notifier.py
-----------
Notification service for the SpaceBasic booking agent.

Supports:
  - Desktop OS notifications (via plyer)
  - Email notifications (via smtplib + SMTP settings in .env)
  - Console / log output (always active)
"""

import logging
import os
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger("spacebasic.notifier")

LEVEL_ICONS = {
    "success": "✅",
    "error":   "❌",
    "warning": "⚠️",
    "info":    "ℹ️",
}


class Notifier:
    """Sends notifications through configured channels."""

    def __init__(self, config: dict):
        notif_cfg = config.get("notifications", {})
        self.desktop_enabled = notif_cfg.get("desktop_notifications", True)
        self.email_enabled = notif_cfg.get("email_notifications", False)
        self.agent_name = config.get("agent", {}).get("name", "SpaceBasic Agent")

        # Email settings from environment
        self.smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = int(os.environ.get("SMTP_PORT", "587"))
        self.smtp_user = os.environ.get("SMTP_USERNAME", "")
        self.smtp_pass = os.environ.get("SMTP_PASSWORD", "")
        self.notify_email = os.environ.get("NOTIFY_EMAIL", "")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def send(self, message: str, level: str = "info", is_summary: bool = False) -> None:
        """
        Send a notification through all enabled channels.

        Args:
            message:    Human-readable notification text.
            level:      "success" | "error" | "warning" | "info"
            is_summary: True for daily summary messages (longer text OK).
        """
        icon = LEVEL_ICONS.get(level, "")
        log_msg = f"{icon} {message}".strip()

        # Always log
        if level == "error":
            logger.error(log_msg)
        elif level == "warning":
            logger.warning(log_msg)
        else:
            logger.info(log_msg)

        # Desktop notification
        if self.desktop_enabled:
            self._send_desktop(message, level)

        # Email notification (errors + summaries only, to avoid spam)
        if self.email_enabled and (level in ("error", "warning") or is_summary):
            self._send_email(message, level)

    # ------------------------------------------------------------------
    # Desktop notifications (plyer)
    # ------------------------------------------------------------------

    def _send_desktop(self, message: str, level: str) -> None:
        try:
            from plyer import notification as plyer_notif
            # Truncate to 256 chars for OS notification
            short_msg = message[:250] + "…" if len(message) > 250 else message
            plyer_notif.notify(
                title=self.agent_name,
                message=short_msg,
                app_name=self.agent_name,
                timeout=8,
            )
        except ImportError:
            pass  # plyer not installed — silent fallback
        except Exception as e:
            logger.debug("Desktop notification failed: %s", e)

    # ------------------------------------------------------------------
    # Email notifications (smtplib)
    # ------------------------------------------------------------------

    def _send_email(self, message: str, level: str) -> None:
        if not self.smtp_user or not self.notify_email:
            logger.debug("Email not configured — skipping email notification")
            return

        subject = f"[{self.agent_name}] {level.upper()}: {message[:60]}"
        body = (
            f"SpaceBasic Booking Agent Notification\n"
            f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Level: {level.upper()}\n\n"
            f"{message}"
        )

        msg = MIMEMultipart()
        msg["From"] = self.smtp_user
        msg["To"] = self.notify_email
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=10) as server:
                server.ehlo()
                server.starttls()
                server.login(self.smtp_user, self.smtp_pass)
                server.sendmail(self.smtp_user, self.notify_email, msg.as_string())
            logger.debug("Email sent to %s", self.notify_email)
        except Exception as e:
            logger.warning("Email notification failed: %s", e)

