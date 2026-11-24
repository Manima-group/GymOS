"""Owner dashboard, leads CRM, org settings, notifications log."""
from datetime import date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.audit import audit
from app.core.deps import TenantContext, get_tenant, require
from app.core.entitlements import effective_limits, usage
from app.core.errors import forbidden
from app.core.utils import normalize_phone
from app.models import (
    Attendance, Branch, Lead, Member, MemberSubscription, Notification, Payment, SubscriptionStatus,
)

router = APIRouter(tags=["dashboard & crm"])

LIVE = [SubscriptionStatus.active, SubscriptionStatus.frozen]


@router.get("/dashboard")
def dashboard(branch_id: int | None = None, ctx: TenantContext = Depends(require("reports.read"))):
    if branch_id:
        ctx.owned(Branch, branch_id)
    elif ctx.branch_id is None and ctx.org.type.value == "multi" and "multi_branch_dashboard" not in ctx.features:
        raise forbidden("Consolidated dashboard needs the Plus plan. Pick a branch.")
    scope = branch_id or ctx.branch_id
    db, today = ctx.db, date.today()
    day_start = datetime.combine(today, datetime.min.time())
    month_start = datetime.combine(today.replace(day=1), datetime.min.time())

    def b(col):
        return True if scope is None else col == scope

    sub_base = [MemberSubscription.org_id == ctx.org_id, b(MemberSubscription.branch_id),
                MemberSubscription.status.in_(LIVE)]
    active = db.scalar(select(func.count(func.distinct(MemberSubscription.member_id))).where(
        *sub_base, MemberSubscription.start_date <= today, MemberSubscription.end_date >= today)) or 0
    expiring = db.scalar(select(func.count(func.distinct(MemberSubscription.member_id))).where(
        *sub_base, MemberSubscription.end_date.between(today, today + timedelta(days=7)))) or 0
    dues = db.scalar(select(func.coalesce(func.sum(
        MemberSubscription.price - MemberSubscription.discount - MemberSubscription.amount_paid), 0)).where(*sub_base)) or 0
    checkins = db.scalar(select(func.count()).select_from(Attendance).where(
        Attendance.org_id == ctx.org_id, b(Attendance.branch_id), Attendance.member_id.is_not(None),
        Attendance.check_in_at >= day_start)) or 0
    pay = [Payment.org_id == ctx.org_id, b(Payment.branch_id)]
    rev_today = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(*pay, Payment.paid_at >= day_start))
    rev_month = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(*pay, Payment.paid_at >= month_start))
    total_members = db.scalar(select(func.count()).select_from(Member).where(
        Member.org_id == ctx.org_id, b(Member.home_branch_id))) or 0
    new_month = db.scalar(select(func.count()).select_from(Member).where(
        Member.org_id == ctx.org_id, b(Member.home_branch_id), Member.created_at >= month_start)) or 0
    hours = db.execute(select(func.extract("hour", Attendance.check_in_at).label("h"), func.count())
                       .where(Attendance.org_id == ctx.org_id, b(Attendance.branch_id),
                              Attendance.check_in_at >= day_start - timedelta(days=30))
                       .group_by("h").order_by("h")).all()
    trend = db.execute(select(func.date(Payment.paid_at).label("d"), func.sum(Payment.amount))
                       .where(*pay, Payment.paid_at >= day_start - timedelta(days=29))
                       .group_by("d").order_by("d")).all()
    open_leads = db.scalar(select(func.count()).select_from(Lead).where(
        Lead.org_id == ctx.org_id, b(Lead.branch_id), Lead.status.in_(["new", "contacted", "trial"]))) or 0
    return {
        "scope_branch_id": scope, "members_total": total_members, "members_active": active,
        "new_members_this_month": new_month, "expiring_7d": expiring, "dues_pending": Decimal(dues),
        "checkins_today": checkins, "revenue_today": rev_today, "revenue_month": rev_month,
        "open_leads": open_leads if "crm" in ctx.features else None,
        "peak_hours_30d": [{"hour": int(h), "count": c} for h, c in hours],
        "revenue_30d": [{"date": d, "amount": a} for d, a in trend],
        "plan": {"code": ctx.org.plan.code, "status": ctx.org.status.value, "trial_ends_at": ctx.org.trial_ends_at,
                 "subscription_ends_at": ctx.org.subscription_ends_at, "limits": effective_limits(ctx.org),
                 "usage": usage(db, ctx.org_id), "message_credits": ctx.org.message_credits},
    }


@router.get("/reports/expiring")
def expiring(days: int = Query(7, ge=0, le=60), ctx: TenantContext = Depends(require("members.read"))):
    today = date.today()
    rows = ctx.db.execute(select(MemberSubscription, Member).join(Member, Member.id == MemberSubscription.member_id)
                          .where(MemberSubscription.org_id == ctx.org_id, ctx.branch_filter(MemberSubscription.branch_id),
                                 MemberSubscription.status.in_(LIVE),
                                 MemberSubscription.end_date.between(today, today + timedelta(days=days)))
                          .order_by(MemberSubscription.end_date)).all()
    return [{"member_id": m.id, "name": m.full_name, "phone": m.phone, "plan": s.plan.name, "end_date": s.end_date,
             "amount_due": s.amount_due} for s, m in rows]


# ---------------- Settings ----------------
class SettingsPatch(BaseModel):
    name: str | None = Field(None, min_length=2, max_length=160)
    email: str | None = None
    phone: str | None = None
    gstin: str | None = Field(None, max_length=20)
    tax_percent: Decimal | None = Field(None, ge=0, le=28)
    branding: dict | None = None


@router.get("/context")
def context(ctx: TenantContext = Depends(get_tenant)):
    """Current tenant context for the UI (also used by Manima support access, which is audited)."""
    if ctx.impersonating:
        audit(ctx.db, "support.access", user_id=ctx.user.id, org_id=ctx.org_id)
        ctx.db.commit()
    o = ctx.org
    return {"org_id": o.id, "name": o.name, "type": o.type.value, "status": o.status.value, "plan": o.plan.code,
            "role": ctx.role.value, "branch_id": ctx.branch_id, "features": sorted(ctx.features),
            "impersonating": ctx.impersonating}


@router.get("/settings")
def get_settings_(ctx: TenantContext = Depends(require("branches.read"))):
    o = ctx.org
    return {"name": o.name, "email": o.email, "phone": o.phone, "gstin": o.gstin, "tax_percent": o.tax_percent,
            "branding": o.branding or {}, "type": o.type.value}


@router.patch("/settings")
def update_settings(body: SettingsPatch, ctx: TenantContext = Depends(require("settings.write"))):
    data = body.model_dump(exclude_unset=True)
    if "branding" in data and "white_label" not in ctx.features:
        raise forbidden("White-label branding needs the Premium plan")
    for k, v in data.items():
        setattr(ctx.org, k, v)
    ctx.db.commit()
    return {"ok": True}


@router.get("/notifications")
def notifications(limit: int = Query(100, le=500), ctx: TenantContext = Depends(require("reports.read"))):
    rows = ctx.db.scalars(select(Notification).where(Notification.org_id == ctx.org_id)
                          .order_by(Notification.id.desc()).limit(limit))
    return [{"id": n.id, "channel": n.channel, "template": n.template, "recipient": n.recipient,
             "status": n.status, "error": n.error, "created_at": n.created_at, "sent_at": n.sent_at} for n in rows]


# ---------------- Leads (CRM) ----------------
class LeadIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=15)
    branch_id: int | None = None
    interest: str = ""
    source: str = Field("walk_in", pattern="^(qr|walk_in|referral|ads|other)$")
    follow_up_on: date | None = None
    notes: str = ""


class LeadPatch(BaseModel):
    status: str | None = Field(None, pattern="^(new|contacted|trial|converted|lost)$")
    follow_up_on: date | None = None
    notes: str | None = None


def lead_out(lead: Lead) -> dict:
    return {"id": lead.id, "branch_id": lead.branch_id, "full_name": lead.full_name, "phone": lead.phone,
            "interest": lead.interest, "source": lead.source, "status": lead.status,
            "follow_up_on": lead.follow_up_on, "notes": lead.notes, "created_at": lead.created_at}


@router.get("/leads")
def list_leads(status: str | None = None, ctx: TenantContext = Depends(require("leads.read", "crm"))):
    stmt = select(Lead).where(Lead.org_id == ctx.org_id, ctx.branch_filter(Lead.branch_id))
    if status:
        stmt = stmt.where(Lead.status == status)
    return [lead_out(x) for x in ctx.db.scalars(stmt.order_by(Lead.id.desc()).limit(500))]


@router.post("/leads", status_code=201)
def create_lead(body: LeadIn, ctx: TenantContext = Depends(require("leads.write", "crm"))):
    branch_id = body.branch_id or ctx.branch_id or ctx.db.scalar(
        select(Branch.id).where(Branch.org_id == ctx.org_id).order_by(Branch.id).limit(1))
    ctx.owned(Branch, branch_id)
    lead = Lead(org_id=ctx.org_id, branch_id=branch_id, full_name=body.full_name, phone=normalize_phone(body.phone),
                interest=body.interest, source=body.source, follow_up_on=body.follow_up_on or date.today(),
                notes=body.notes)
    ctx.db.add(lead)
    ctx.db.commit()
    return lead_out(lead)


@router.patch("/leads/{lead_id}")
def update_lead(lead_id: int, body: LeadPatch, ctx: TenantContext = Depends(require("leads.write", "crm"))):
    lead = ctx.owned(Lead, lead_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(lead, k, v)
    ctx.db.commit()
    return lead_out(lead)
