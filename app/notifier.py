import smtplib
import ssl
from email.message import EmailMessage
import logging

def send_email(subject, body, to_email, smtp_cfg):
    """
    Send email notification.
    smtp_cfg should include:
      - host
      - port
      - username
      - password
      - use_tls (bool)
    """
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = smtp_cfg.get("username")
        msg["To"] = to_email
        msg.set_content(body)

        context = ssl.create_default_context()

        if smtp_cfg.get("use_tls", True):
            with smtplib.SMTP(smtp_cfg["host"], smtp_cfg["port"]) as server:
                server.starttls(context=context)
                server.login(smtp_cfg["username"], smtp_cfg["password"])
                server.send_message(msg)
        else:
            with smtplib.SMTP_SSL(smtp_cfg["host"], smtp_cfg["port"], context=context) as server:
                server.login(smtp_cfg["username"], smtp_cfg["password"])
                server.send_message(msg)

        logging.info(f"Email sent to {to_email} with subject '{subject}'")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")
