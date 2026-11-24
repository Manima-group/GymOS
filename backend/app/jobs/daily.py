"""Scheduled jobs. Run with cron (e.g. hourly) — no Redis/Celery needed for the MVP:

    python -m app.jobs.daily            # all jobs
    python -m app.jobs.daily dispatch   # only send queued notifications

All reminders use dedupe keys, so running the job many times a day is safe (idempotent).
"""
import logging
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import extract, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import SessionLocal
from app.core.entitlements import enabled_features, org_is_operational
from app.models import (
    Attendance, Member, MemberSubscription, Organization, OrgStatus, OrgUser, Payment, StaffRole, SubscriptionStatus,
)
from app.modules.notify import dispatch_queued, queue

log = logging.getLogger("gymos.jobs")
RENEWAL_DAYS = (7, 3, 1)
INACTIVE_DAYS = 10


def member_channels(feats: set[str]) -> list[str]:
    chans = [c for c, f in (("whatsapp", "reminders_whatsapp"), ("sms", "reminders_sms")) if f in feats]
    return chans[:1] or (["email"] if "reminders_email" in feats else [])


def _send_member(db, org, m: Member, feats, template, payload, key):
    for ch in member_channels(feats):
        to = m.email if ch == "email" else m.phone
        if to:
            queue(db, org_id=org.id, member_id=m.id, channel=ch, recipient=to, template=template,
                  payload={"name": m.full_name.split()[0], "gym": org.name, **payload}, dedupe_key=f"{key}:{ch}")


def expire_subscriptions(db: Session, today: date) -> int:
    rows = list(db.scalars(select(MemberSubscription).where(
        MemberSubscription.status == SubscriptionStatus.active, MemberSubscription.end_date < today)))
    for s in rows:
        s.status = SubscriptionStatus.expired
    return len(rows)


def member_reminders(db: Session, org: Organization, today: date) -> None:
    feats = enabled_features(db, org)
    if not member_channels(feats):
        return
    live = [SubscriptionStatus.active, SubscriptionStatus.frozen]
    # renewal due
    for days in RENEWAL_DAYS:
        target = today + timedelta(days=days)
        for s, m in db.execute(select(MemberSubscription, Member).join(Member).where(
                MemberSubscription.org_id == org.id, MemberSubscription.status.in_(live),
                MemberSubscription.end_date == target)):
            renewed = db.scalar(select(MemberSubscription.id).where(
                MemberSubscription.member_id == m.id, MemberSubscription.start_date > s.end_date,
                MemberSubscription.status.in_(live)))
            if not renewed:
                _send_member(db, org, m, feats, "renewal_due", {"plan": s.plan.name, "end_date": f"{s.end_date:%d %b}"},
                             f"renew:{s.id}:{days}")
    # just expired (yesterday)
    for s, m in db.execute(select(MemberSubscription, Member).join(Member).where(
            MemberSubscription.org_id == org.id, MemberSubscription.end_date == today - timedelta(days=1))):
        _send_member(db, org, m, feats, "membership_expired", {"end_date": f"{s.end_date:%d %b}"}, f"expired:{s.id}")
    # dues pending (weekly, Mondays)
    if today.weekday() == 0:
        for s, m in db.execute(select(MemberSubscription, Member).join(Member).where(
                MemberSubscription.org_id == org.id, MemberSubscription.status.in_(live),
                MemberSubscription.price - MemberSubscription.discount - MemberSubscription.amount_paid > 0)):
            _send_member(db, org, m, feats, "dues_pending", {"amount": str(s.amount_due)}, f"dues:{s.id}:{today}")
    # birthdays
    for m in db.scalars(select(Member).where(Member.org_id == org.id, extract("month", Member.dob) == today.month,
                                             extract("day", Member.dob) == today.day)):
        _send_member(db, org, m, feats, "birthday", {}, f"bday:{m.id}:{today.year}")
    # inactive members with a live membership
    cutoff = datetime.combine(today - timedelta(days=INACTIVE_DAYS), datetime.min.time())
    last_visit = select(Attendance.member_id, func.max(Attendance.check_in_at).label("last")).where(
        Attendance.org_id == org.id, Attendance.member_id.is_not(None)).group_by(Attendance.member_id).subquery()
    for m, last in db.execute(select(Member, last_visit.c.last).join(last_visit, last_visit.c.member_id == Member.id)
                              .where(last_visit.c.last < cutoff)
                              .where(Member.id.in_(select(MemberSubscription.member_id).where(
                                  MemberSubscription.org_id == org.id, MemberSubscription.status == SubscriptionStatus.active,
                                  MemberSubscription.end_date >= today)))):
        days = (today - last.date()).days
        _send_member(db, org, m, feats, "inactive", {"days": days}, f"inactive:{m.id}:{last.date()}")


def owner_summary(db: Session, org: Organization, today: date) -> None:
    start = datetime.combine(today, datetime.min.time())
    checkins = db.scalar(select(func.count()).select_from(Attendance).where(
        Attendance.org_id == org.id, Attendance.member_id.is_not(None), Attendance.check_in_at >= start)) or 0
    revenue = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.org_id == org.id, Payment.paid_at >= start)) or 0
    expiring = db.scalar(select(func.count()).select_from(MemberSubscription).where(
        MemberSubscription.org_id == org.id, MemberSubscription.status == SubscriptionStatus.active,
        MemberSubscription.end_date.between(today, today + timedelta(days=7)))) or 0
    for ou in db.scalars(select(OrgUser).where(OrgUser.org_id == org.id, OrgUser.role == StaffRole.owner)):
        if ou.user.email:
            queue(db, org_id=org.id, channel="email", recipient=ou.user.email, template="owner_daily_summary",
                  payload={"gym": org.name, "checkins": checkins, "revenue": str(revenue), "expiring": expiring},
                  dedupe_key=f"owner_summary:{org.id}:{today}")


def saas_lifecycle(db: Session, org: Organization, today: date) -> None:
    """Manima's recurring revenue engine: trial end, renewal reminders, grace period, suspension."""
    grace = get_settings().grace_days
    owner_email = org.email
    p = org.plan
    amount = p.price_yearly if org.billing_cycle == "yearly" else p.price_monthly
    if org.status == OrgStatus.trial and org.trial_ends_at:
        if org.trial_ends_at < today:
            org.status = OrgStatus.suspended
        elif (org.trial_ends_at - today).days in (3, 1) and owner_email:
            queue(db, org_id=None, channel="email", recipient=owner_email, template="saas_renewal_due",
                  payload={"plan": p.name, "gym": org.name, "date": f"{org.trial_ends_at:%d %b}", "amount": str(amount)},
                  dedupe_key=f"saas_trial:{org.id}:{org.trial_ends_at}:{(org.trial_ends_at - today).days}")
    elif org.status in (OrgStatus.active, OrgStatus.past_due) and org.subscription_ends_at:
        end = org.subscription_ends_at
        if end < today - timedelta(days=grace):
            org.status = OrgStatus.suspended
            if owner_email:
                queue(db, org_id=None, channel="email", recipient=owner_email, template="saas_suspended",
                      payload={"gym": org.name}, dedupe_key=f"saas_susp:{org.id}:{end}")
        elif end < today:
            org.status = OrgStatus.past_due
        elif (end - today).days in (7, 3, 1) and owner_email:
            queue(db, org_id=None, channel="email", recipient=owner_email, template="saas_renewal_due",
                  payload={"plan": p.name, "gym": org.name, "date": f"{end:%d %b}", "amount": str(amount)},
                  dedupe_key=f"saas_renew:{org.id}:{end}:{(end - today).days}")


def run_all(db: Session, today: date | None = None, send_summary: bool | None = None) -> dict:
    today = today or date.today()
    if send_summary is None:  # owners get the summary once, in the evening (IST)
        send_summary = datetime.now(ZoneInfo("Asia/Kolkata")).hour >= 21
    expired = expire_subscriptions(db, today)
    orgs = list(db.scalars(select(Organization)))
    for org in orgs:
        saas_lifecycle(db, org, today)
        if org_is_operational(org):
            member_reminders(db, org, today)
            if send_summary:
                owner_summary(db, org, today)
    db.commit()
    sent = dispatch_queued(db)
    return {"expired_subscriptions": expired, "orgs": len(orgs), **sent}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    with SessionLocal() as session:
        if len(sys.argv) > 1 and sys.argv[1] == "dispatch":
            print(dispatch_queued(session))
        else:
            print(run_all(session))
