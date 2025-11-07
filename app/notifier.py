"""Notification functionality for RMV-Watcher"""

import os
import logging
import smtplib
import ssl
from typing import Dict, Any, List, Optional
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_validator import validate_email as validate_email_address, EmailNotValidError

logger = logging.getLogger(__name__)

# Email configuration from environment
EMAIL_HOST = os.getenv('EMAIL_HOST', 'smtp.gmail.com')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USER = os.getenv('EMAIL_USER', '')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD', '')
EMAIL_FROM = os.getenv('EMAIL_FROM', EMAIL_USER)
EMAIL_RECIPIENTS = os.getenv('EMAIL_RECIPIENTS', '').split(',')


def _get_smtp_connection():
    """Create and return an authenticated SMTP connection with TLS"""
    try:
        # Create SSL context
        context = ssl.create_default_context()

        # Connect to SMTP server with TLS
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls(context=context)

        # Authenticate
        if EMAIL_USER and EMAIL_PASSWORD:
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            logger.info(f"Successfully authenticated with SMTP server: {EMAIL_HOST}")

        return server
    except Exception as e:
        logger.error(f"Failed to connect to SMTP server: {e}")
        raise


def send_alert_email(grouped_slots: Dict[str, Dict[str, List[datetime]]], link: str, expires_at: Optional[datetime] = None):
    """
    Send alert email with appointment slots grouped by location and date.

    Args:
        grouped_slots: Dict[location, Dict[date_str, List[time]]]
                      e.g., {"Frankfurt": {"2025-11-08": [datetime(...), datetime(...)]}}
        link: Appointment booking link
        expires_at: Optional expiration time for the link
    """
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.warning("Email credentials not configured, skipping alert email")
        return

    if not grouped_slots:
        logger.info("No slots to send, skipping alert email")
        return

    # Get recipients
    recipients = [r.strip() for r in EMAIL_RECIPIENTS if r.strip()]
    if not recipients:
        logger.warning("No email recipients configured")
        return

    # Format the email body
    body = _format_alert_email_body(grouped_slots, link, expires_at)

    # Create email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f'🎯 RMV Appointment Slots Available - {len(grouped_slots)} Location(s)'
    msg['From'] = EMAIL_FROM
    msg['To'] = ', '.join(recipients)

    # Create plain text and HTML versions
    text_part = MIMEText(body, 'plain')
    html_part = MIMEText(_format_alert_email_html(grouped_slots, link, expires_at), 'html')

    msg.attach(text_part)
    msg.attach(html_part)

    # Send email
    try:
        server = _get_smtp_connection()
        server.send_message(msg)
        server.quit()
        logger.info(f"Alert email sent successfully to {len(recipients)} recipient(s)")
    except Exception as e:
        logger.error(f"Failed to send alert email: {e}")
        raise


def _format_alert_email_body(grouped_slots: Dict[str, Dict[str, List[datetime]]], link: str, expires_at: Optional[datetime]) -> str:
    """Format alert email as plain text"""
    lines = [
        "RMV Appointment Slots Available!",
        "=" * 50,
        ""
    ]

    # Add appointment link
    lines.append(f"📅 Booking Link: {link}")
    if expires_at:
        lines.append(f"⏰ Link Expires: {expires_at.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("Available Slots:")
    lines.append("-" * 50)
    lines.append("")

    # Group by location
    for location, dates in sorted(grouped_slots.items()):
        lines.append(f"📍 {location}")
        lines.append("")

        # Group by date
        for date_str, times in sorted(dates.items()):
            lines.append(f"  📆 {date_str}")

            # Format times
            time_strs = [t.strftime('%H:%M') for t in sorted(times)]
            # Group times in rows of 6
            for i in range(0, len(time_strs), 6):
                time_row = ', '.join(time_strs[i:i+6])
                lines.append(f"     {time_row}")

            lines.append("")

        lines.append("")

    lines.append("=" * 50)
    lines.append("Book your appointment now before slots fill up!")

    return '\n'.join(lines)


def _format_alert_email_html(grouped_slots: Dict[str, Dict[str, List[datetime]]], link: str, expires_at: Optional[datetime]) -> str:
    """Format alert email as HTML"""
    html_parts = [
        '<html><body style="font-family: Arial, sans-serif; color: #333;">',
        '<h2 style="color: #2c5aa0;">🎯 RMV Appointment Slots Available!</h2>',
        f'<p><strong>📅 Booking Link:</strong> <a href="{link}" style="color: #2c5aa0;">{link}</a></p>'
    ]

    if expires_at:
        html_parts.append(f'<p><strong>⏰ Link Expires:</strong> {expires_at.strftime("%Y-%m-%d %H:%M:%S")}</p>')

    html_parts.append('<hr style="border: 1px solid #ddd;">')
    html_parts.append('<h3>Available Slots:</h3>')

    # Group by location
    for location, dates in sorted(grouped_slots.items()):
        html_parts.append(f'<h4 style="color: #2c5aa0;">📍 {location}</h4>')

        # Group by date
        for date_str, times in sorted(dates.items()):
            html_parts.append(f'<p><strong>📆 {date_str}</strong></p>')
            html_parts.append('<div style="margin-left: 20px; margin-bottom: 10px;">')

            # Format times
            time_strs = [t.strftime('%H:%M') for t in sorted(times)]
            time_badges = [f'<span style="background: #e3f2fd; padding: 4px 8px; margin: 2px; border-radius: 4px; display: inline-block;">{t}</span>' for t in time_strs]
            html_parts.append(' '.join(time_badges))

            html_parts.append('</div>')

    html_parts.append('<hr style="border: 1px solid #ddd;">')
    html_parts.append('<p style="font-weight: bold; color: #d32f2f;">Book your appointment now before slots fill up!</p>')
    html_parts.append('</body></html>')

    return ''.join(html_parts)


def send_report_email(html_report: str, subject: str = "RMV Watcher Report"):
    """
    Send an HTML report via email.

    Args:
        html_report: HTML content of the report
        subject: Email subject line
    """
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.warning("Email credentials not configured, skipping report email")
        return

    # Get recipients
    recipients = [r.strip() for r in EMAIL_RECIPIENTS if r.strip()]
    if not recipients:
        logger.warning("No email recipients configured")
        return

    # Create email message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = ', '.join(recipients)

    # Attach HTML report
    html_part = MIMEText(html_report, 'html')
    msg.attach(html_part)

    # Send email
    try:
        server = _get_smtp_connection()
        server.send_message(msg)
        server.quit()
        logger.info(f"Report email sent successfully to {len(recipients)} recipient(s)")
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        raise


def init_notification_service():
    """Initialize notification service"""
    logger.info("Notification service initialized")
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.warning("Email credentials not configured - email notifications will be disabled")


def send_notification(message: str, recipients: List[str]):
    """Send a notification to recipients"""
    send_email("RMV Watcher Notification", message, recipients)


def send_email(subject: str, body: str, recipients: List[str]):
    """Send an email notification"""
    if not EMAIL_USER or not EMAIL_PASSWORD:
        logger.warning("Email credentials not configured, skipping email")
        return

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_FROM
    msg['To'] = ', '.join(recipients)

    try:
        server = _get_smtp_connection()
        server.send_message(msg)
        server.quit()
        logger.info(f"Email sent successfully to {len(recipients)} recipient(s)")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise


def format_notification_message(data: Dict[str, Any]) -> str:
    """Format scrape data into notification message"""
    # Basic formatting
    return f"Data: {data}"


def validate_email(email: str) -> bool:
    """Validate email address"""
    try:
        validate_email_address(email)
        return True
    except EmailNotValidError:
        return False


def send_webhook_notification(webhook_url: str, data: Dict[str, Any]):
    """Send notification via webhook"""
    import requests
    try:
        response = requests.post(webhook_url, json=data, timeout=10)
        response.raise_for_status()
        logger.info(f"Webhook notification sent successfully to {webhook_url}")
    except Exception as e:
        logger.error(f"Failed to send webhook notification: {e}")
        raise


def send_slack_notification(webhook_url: str, message: str):
    """Send notification to Slack"""
    send_webhook_notification(webhook_url, {"text": message})


def should_send_notification(data: Dict[str, Any]) -> bool:
    """Determine if a notification should be sent"""
    # Basic check - send if data exists
    return bool(data)


def get_notification_recipients() -> List[str]:
    """Get list of notification recipients"""
    return [r.strip() for r in EMAIL_RECIPIENTS if r.strip()]
