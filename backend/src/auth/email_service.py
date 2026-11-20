import smtplib
from email.message import EmailMessage

from ..core.config import get_settings


def send_reset_email(to_email: str, reset_url: str) -> None:
    settings = get_settings()

    message = EmailMessage()
    message["Subject"] = "Đặt mật khẩu FinMind"
    message["From"] = settings.smtp_from
    message["To"] = to_email
    message.set_content(
        "Bạn vừa yêu cầu đặt hoặc đặt lại mật khẩu FinMind.\n\n"
        f"Mở liên kết này để đặt mật khẩu mới:\n{reset_url}\n\n"
        "Nếu bạn không yêu cầu, hãy bỏ qua email này."
    )

    with smtplib.SMTP(
        settings.smtp_host,
        settings.smtp_port,
        timeout=20,
    ) as smtp:
        smtp.starttls()
        smtp.login(
            settings.smtp_username,
            settings.smtp_password.get_secret_value(),
        )
        smtp.send_message(message)
