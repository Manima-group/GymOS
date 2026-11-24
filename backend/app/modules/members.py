from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, or_, select

from app.core.audit import audit
from app.core.deps import TenantContext, require
from app.core.entitlements import check_limit
from app.core.sequences import next_seq
from app.core.utils import normalize_phone
from app.models import (
    Attendance, Branch, Lead, Member, MemberStatus, MemberSubscription, Payment, SubscriptionStatus,
)

router = APIRouter(tags=["members"])


class MemberIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=15)
    email: EmailStr | None = None
    gender: str | None = Field(None, pattern="^(male|female|other)$")
    dob: date | None = None
    home_branch_id: int | None = None
    emergency_contact: str | None = None
    notes: str = ""
    all_branch_access: bool = False
    lead_id: int | None = None  # converting an enquiry


class MemberPatch(BaseModel):
    full_name: str | None = None
    email: EmailStr | None = None
    gender: str | None = Field(None, pattern="^(male|female|other)$")
    dob: date | None = None
    home_branch_id: int | None = None
    emergency_contact: str | None = None
    notes: str | None = None
    all_branch_access: bool | None = None
    status: MemberStatus | None = None


def current_subscription(ctx_db, member_id: int) -> MemberSubscription | None:
    today = date.today()
    return ctx_db.scalar(
        select(MemberSubscription).where(
            MemberSubscription.member_id == member_id,
            MemberSubscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.frozen]),
            MemberSubscription.start_date <= today,
        ).order_by(MemberSubscription.end_date.desc()).limit(1)
    )


def sub_out(s: MemberSubscription | None) -> dict | None:
    if not s:
        return None
    return {"id": s.id, "plan_id": s.plan_id, "plan_name": s.plan.name, "start_date": s.start_date,
            "end_date": s.end_date, "status": s.status.value, "price": s.price, "discount": s.discount,
            "amount_paid": s.amount_paid, "amount_due": s.amount_due,
            "days_left": (s.end_date - date.today()).days, "branch_id": s.branch_id}


def member_out(m: Member, sub: MemberSubscription | None = None) -> dict:
    return {"id": m.id, "member_code": m.member_code, "full_name": m.full_name, "phone": m.phone, "email": m.email,
            "gender": m.gender, "dob": m.dob, "joined_on": m.joined_on, "home_branch_id": m.home_branch_id,
            "status": m.status.value, "all_branch_access": m.all_branch_access, "notes": m.notes,
            "emergency_contact": m.emergency_contact, "has_app_login": m.user_id is not None,
            "subscription": sub_out(sub)}


@router.get("/members")
def list_members(
    q: str | None = None, branch_id: int | None = None,
    membership: str | None = Query(None, pattern="^(active|expiring|expired|none)$"),
    page: int = Query(1, ge=1), size: int = Query(25, ge=1, le=100),
    ctx: TenantContext = Depends(require("members.read", "members")),
):
    stmt = select(Member).where(Member.org_id == ctx.org_id, ctx.branch_filter(Member.home_branch_id))
    if branch_id:
        stmt = stmt.where(Member.home_branch_id == branch_id)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Member.full_name).like(like), Member.phone.like(like),
                              func.lower(Member.member_code).like(like)))
    if membership:
        today = date.today()
        live = select(MemberSubscription.member_id).where(
            MemberSubscription.org_id == ctx.org_id,
            MemberSubscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.frozen]),
            MemberSubscription.end_date >= today)
        if membership == "active":
            stmt = stmt.where(Member.id.in_(live))
        elif membership == "expiring":
            stmt = stmt.where(Member.id.in_(live.where(MemberSubscription.end_date <= today + timedelta(days=7))))
        elif membership == "expired":
            ever = select(MemberSubscription.member_id).where(MemberSubscription.org_id == ctx.org_id)
            stmt = stmt.where(Member.id.in_(ever), Member.id.not_in(live))
        else:
            stmt = stmt.where(Member.id.not_in(select(MemberSubscription.member_id).where(
                MemberSubscription.org_id == ctx.org_id)))
    total = ctx.db.scalar(select(func.count()).select_from(stmt.subquery()))
    members = list(ctx.db.scalars(stmt.order_by(Member.id.desc()).offset((page - 1) * size).limit(size)))
    # one query for current subscriptions of this page (avoid N+1)
    subs: dict[int, MemberSubscription] = {}
    if members:
        for s in ctx.db.scalars(select(MemberSubscription).where(
                MemberSubscription.member_id.in_([m.id for m in members]),
                MemberSubscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.frozen]),
                MemberSubscription.start_date <= date.today()).order_by(MemberSubscription.end_date)):
            subs[s.member_id] = s
    return {"total": total, "page": page, "size": size, "items": [member_out(m, subs.get(m.id)) for m in members]}


@router.post("/members", status_code=201)
def create_member(body: MemberIn, ctx: TenantContext = Depends(require("members.write", "members"))):
    branch_id = body.home_branch_id or ctx.branch_id
    if branch_id is None:
        branch_id = ctx.db.scalar(select(Branch.id).where(Branch.org_id == ctx.org_id).order_by(Branch.id).limit(1))
    ctx.owned(Branch, branch_id)
    check_limit(ctx.db, ctx.org, "max_members")
    phone = normalize_phone(body.phone)
    if ctx.db.scalar(select(Member.id).where(Member.org_id == ctx.org_id, Member.phone == phone)):
        raise HTTPException(status.HTTP_409_CONFLICT, "A member with this phone already exists")
    seq = next_seq(ctx.db, ctx.org_id, "member_seq")
    m = Member(org_id=ctx.org_id, home_branch_id=branch_id, member_code=f"M{seq:05d}",
               full_name=body.full_name, phone=phone, email=body.email, gender=body.gender, dob=body.dob,
               emergency_contact=body.emergency_contact, notes=body.notes, all_branch_access=body.all_branch_access)
    ctx.db.add(m)
    if body.lead_id:
        lead = ctx.owned(Lead, body.lead_id)
        lead.status = "converted"
    ctx.db.flush()
    audit(ctx.db, "member.create", user_id=ctx.user.id, org_id=ctx.org_id, entity="member", entity_id=m.id)
    ctx.db.commit()
    return member_out(m)


@router.get("/members/{member_id}")
def get_member(member_id: int, ctx: TenantContext = Depends(require("members.read", "members"))):
    m = ctx.owned(Member, member_id)
    db = ctx.db
    subs = db.scalars(select(MemberSubscription).where(MemberSubscription.member_id == m.id)
                      .order_by(MemberSubscription.start_date.desc()))
    pays = db.scalars(select(Payment).where(Payment.member_id == m.id).order_by(Payment.paid_at.desc()).limit(50))
    att = db.scalars(select(Attendance).where(Attendance.member_id == m.id)
                     .order_by(Attendance.check_in_at.desc()).limit(30))
    return {
        **member_out(m, current_subscription(db, m.id)),
        "subscriptions": [sub_out(s) for s in subs],
        "payments": [{"id": p.id, "invoice_no": p.invoice_no, "amount": p.amount, "method": p.method.value,
                      "paid_at": p.paid_at} for p in pays],
        "attendance": [{"check_in_at": a.check_in_at, "branch_id": a.branch_id, "method": a.method} for a in att],
    }


@router.patch("/members/{member_id}")
def update_member(member_id: int, body: MemberPatch, ctx: TenantContext = Depends(require("members.write", "members"))):
    m = ctx.owned(Member, member_id)
    data = body.model_dump(exclude_unset=True)
    if data.get("home_branch_id"):
        ctx.owned(Branch, data["home_branch_id"])
    for k, v in data.items():
        setattr(m, k, v)
    ctx.db.commit()
    return member_out(m, current_subscription(ctx.db, m.id))
