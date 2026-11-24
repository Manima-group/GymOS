"""Notification channels + outbox. Providers are pluggable; 'log' just prints (dev / not yet configured).

Real providers to plug in later: SMTP/SES (email), MSG91 (SMS, needs DLT templates),
Meta WhatsApp Cloud API or a BSP like AiSensy/Interakt (needs approved templates).
"""
import logging
import smtplib
from email.message import EmailMessage

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.catalog import CHANNEL_CREDIT_COST
from app.core.config import get_settings
from app.core.db import utcnow
from app.models import Notification, Organization

log = logging.getLogger("gymos.notify")

TEMPLATES = {
    "otp": "Your Gym-OS login OTP is {code}. Valid for 5 minutes.",
    "renewal_due": "Hi {name}, your {plan} membership at {gym} expires on {end_date}. Renew to keep training!",
    "membership_expired": "Hi {name}, your membership at {gym} expired on {end_date}. Renew today to continue.",
    "dues_pending": "Hi {name}, ₹{amount} is pending for your {gym} membership. Please clear it at the desk.",
    "birthday": "Happy birthday {name}! 🎉 Wishing you a strong year ahead from {gym}.",
    "inactive": "Hi {name}, we missed you at {gym}! It's been {days} days. See you soon 💪",
    "payment_receipt": "Payment received: ₹{amount} (Invoice {invoice_no}) at {gym}. Thank you!",
    "owner_daily_summary": "{gym} today: {checkins} check-ins, ₹{revenue} collected, {expiring} memberships expiring in 7 days.",
    "saas_renewal_due": "Your Gym-OS {plan} subscription for {gym} renews on {date}. Amount ₹{amount}.",
    "saas_suspended": "Your Gym-OS subscription for {gym} is suspended due to non-payment. Renew to restore access.",
}


def render(template: str, payload: dict) -> str:
    try:
        return TEMPLATES[template].format(**payload)
    except (KeyError, IndexError):
        return f"[{template}] {payload}"


def _send_email(to: str, text: str, subject: str) -> None:
    s = get_settings()
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = s.smtp_from, to, subject
    msg.set_content(text)
    with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=10) as smtp:
        smtp.starttls()
        if s.smtp_user:
            smtp.login(s.smtp_user, s.smtp_password)
        smtp.send_message(msg)


def send_now(channel: str, recipient: str, template: str, payload: dict) -> None:
    s = get_settings()
    text = render(template, payload)
    provider = {"email": s.email_provider, "sms": s.sms_provider, "whatsapp": s.whatsapp_provider}.get(channel, "log")
    if provider == "log":
        log.info("[%s -> %s] %s", channel, recipient, text)
        return
    if channel == "email" and provider == "smtp":
        _send_email(recipient, text, subject=template.replace("_", " ").title())
        return
    raise NotImplementedError(f"Provider {provider!r} for {channel} not implemented yet")


def queue(db: Session, *, org_id: int | None, channel: str, recipient: str, template: str,
          payload: dict, member_id: int | None = None, dedupe_key: str | None = None) -> bool:
    """Add to outbox. Returns False if a notification with the same dedupe_key already exists."""
    if dedupe_key and db.scalar(select(Notification.id).where(Notification.dedupe_key == dedupe_key)):
        return False
    try:
        with db.begin_nested():
            db.add(Notification(org_id=org_id, member_id=member_id, channel=channel, recipient=recipient,
                                template=template, payload=payload, dedupe_key=dedupe_key))
    except IntegrityError:
        return False
    return True


def dispatch_queued(db: Session, batch: int = 200) -> dict:
    """Send queued notifications, charging message credits for paid channels."""
    stats = {"sent": 0, "failed": 0, "skipped": 0}
    rows = db.scalars(select(Notification).where(Notification.status == "queued")
                      .order_by(Notification.id).limit(batch).with_for_update(skip_locked=True))
    for n in rows:
        cost = CHANNEL_CREDIT_COST.get(n.channel, 0)
        org = db.get(Organization, n.org_id) if (n.org_id and cost) else None
        if org and org.message_credits < cost:
            n.status, n.error = "skipped", "insufficient message credits"
            stats["skipped"] += 1
            continue
        try:
            send_now(n.channel, n.recipient, n.template, n.payload)
            n.status, n.sent_at = "sent", utcnow()
            if org:  # atomic decrement, safe with concurrent workers
                db.execute(update(Organization).where(Organization.id == org.id)
                           .values(message_credits=Organization.message_credits - cost))
                db.refresh(org)
            stats["sent"] += 1
        except Exception as e:  # noqa: BLE001 - provider errors must not stop the batch
            n.status, n.error = "failed", str(e)[:500]
            stats["failed"] += 1
    db.commit()
    return stats
