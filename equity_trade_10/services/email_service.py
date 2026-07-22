import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    sender_email = os.environ.get("SMTP_EMAIL")
    sender_password = os.environ.get("SMTP_PASSWORD")

    print("SMTP_EMAIL =", sender_email)
    print("SMTP_PASSWORD set =", bool(sender_password))
    print("Trying to send email to =", to_email)

    if not sender_email or not sender_password:
        print("SMTP_EMAIL / SMTP_PASSWORD not set. Skipping email send.")
        return False

    try:
        msg = MIMEMultipart()
        msg["From"] = sender_email
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.attach(MIMEText(html_body, "html"))

        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, to_email, msg.as_string())
        server.quit()

        print("Email sent successfully")
        return True

    except Exception as exc:
        print("Email send failed:", exc)
        return False


def send_welcome_email(to_email: str, username: str) -> bool:
    subject = "Welcome to Equity Trade Screener"
    html_body = f"""
    <html>
      <body>
        <h2>Account Created Successfully</h2>
        <p>Hello <b>{username}</b>,</p>
        <p>Your account has been created successfully on Equity Trade Screener.</p>
        <p>You can now log in and start using your dashboard, watchlists, charts, and alerts.</p>
      </body>
    </html>
    """
    return _send_email(to_email, subject, html_body)


def send_password_reset_email(to_email: str, username: str, reset_link: str) -> bool:
    subject = "Reset your Equity Trade Screener password"
    html_body = f"""
    <html>
      <body>
        <h2>Password Reset Request</h2>
        <p>Hello <b>{username}</b>,</p>
        <p>We received a request to reset your password.</p>
        <p>Click the link below to set a new password:</p>
        <p><a href="{reset_link}">{reset_link}</a></p>
        <p>If you did not request this, you can ignore this email.</p>
      </body>
    </html>
    """
    return _send_email(to_email, subject, html_body)


def send_alert_email(to_email: str, message: str) -> bool:
    return _send_email(
        to_email,
        "Stock alert triggered",
        f"<html><body><h2>Stock Alert</h2><p>{message}</p></body></html>",
    )
