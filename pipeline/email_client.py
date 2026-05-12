"""
Stage 7 — Email Client
Sends the QA bug report + screenshots via SMTP, SendGrid, or Resend.
Provider is selected by EMAIL_PROVIDER env var.
"""
import base64
import smtplib
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import Config
from .logger import get_logger

logger = get_logger(__name__)


class EmailClient:
    def send_report(
        self,
        jira_key: str,
        overall_status: str,
        bug_report: str,
        screenshots: list,
        workspace_dir: str,
    ) -> None:
        subject = f"QA Report – {jira_key} – {overall_status}"
        workspace = Path(workspace_dir)
        provider = Config.EMAIL_PROVIDER.lower()

        logger.info(f"Sending report via {provider} to {Config.EMAIL_TO}")
        if provider == "sendgrid":
            self._send_sendgrid(subject, bug_report, screenshots, workspace)
        elif provider == "resend":
            self._send_resend(subject, bug_report, screenshots, workspace)
        else:
            self._send_smtp(subject, bug_report, screenshots, workspace)

        logger.info("Email sent successfully")

    # ------------------------------------------------------------------
    # SMTP
    # ------------------------------------------------------------------

    def _send_smtp(self, subject: str, body: str, screenshots: list, workspace: Path) -> None:
        msg = MIMEMultipart()
        msg["From"] = Config.EMAIL_FROM
        msg["To"] = Config.EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain", "utf-8"))

        for name in screenshots:
            path = workspace / name
            if not path.exists():
                continue
            with open(path, "rb") as f:
                part = MIMEBase("image", "png")
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{name}"')
                msg.attach(part)

        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.login(Config.SMTP_USER, Config.SMTP_PASS)
            server.sendmail(Config.EMAIL_FROM, Config.EMAIL_TO, msg.as_string())

    # ------------------------------------------------------------------
    # SendGrid
    # ------------------------------------------------------------------

    def _send_sendgrid(self, subject: str, body: str, screenshots: list, workspace: Path) -> None:
        try:
            import sendgrid  # type: ignore
            from sendgrid.helpers.mail import (  # type: ignore
                Attachment, Disposition, FileContent, FileName, FileType, Mail,
            )
        except ImportError:
            raise RuntimeError("sendgrid package not installed. Run: pip install sendgrid")

        sg = sendgrid.SendGridAPIClient(api_key=Config.SENDGRID_API_KEY)
        message = Mail(
            from_email=Config.EMAIL_FROM,
            to_emails=Config.EMAIL_TO,
            subject=subject,
            plain_text_content=body,
        )

        for name in screenshots:
            path = workspace / name
            if not path.exists():
                continue
            data = base64.b64encode(path.read_bytes()).decode()
            att = Attachment(
                FileContent(data),
                FileName(name),
                FileType("image/png"),
                Disposition("attachment"),
            )
            message.attachment = att  # type: ignore[assignment]

        sg.send(message)

    # ------------------------------------------------------------------
    # Resend
    # ------------------------------------------------------------------

    def _send_resend(self, subject: str, body: str, screenshots: list, workspace: Path) -> None:
        try:
            import resend  # type: ignore
        except ImportError:
            raise RuntimeError("resend package not installed. Run: pip install resend")

        resend.api_key = Config.RESEND_API_KEY  # type: ignore[attr-defined]

        attachments = []
        for name in screenshots:
            path = workspace / name
            if not path.exists():
                continue
            data = base64.b64encode(path.read_bytes()).decode()
            attachments.append({"filename": name, "content": data})

        params: dict = {
            "from": Config.EMAIL_FROM,
            "to": [Config.EMAIL_TO],
            "subject": subject,
            "text": body,
        }
        if attachments:
            params["attachments"] = attachments

        resend.Emails.send(params)  # type: ignore[attr-defined]
