"""Gym membership plans, member subscriptions (renew/freeze), payments + invoices/receipts."""
import html
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from app.core.audit import audit
from app.core.deps import TenantContext, require
from app.core.errors import bad_request
from app.core.sequences import next_seq
from app.models import (
    Branch, Member, MemberSubscription, MembershipPlan, Payment, PaymentMethod, SubscriptionStatus,
)
from app.modules.members import sub_out
from app.modules.notify import queue

router = APIRouter(tags=["memberships & payments"])
TWO = Decimal("0.01")


# ---------------- Gym's membership plans ----------------
class PlanIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    duration_days: int = Field(ge=1, le=1830)
    price: Decimal = Field(ge=0)
    all_branch_access: bool = False
    max_freeze_days: int = Field(0, ge=0, le=365)
    description: str = ""


class PlanPatch(BaseModel):
    name: str | None = None
    duration_days: int | None = Field(None, ge=1, le=1830)
    price: Decimal | None = Field(None, ge=0)
    all_branch_access: bool | None = None
    max_freeze_days: int | None = Field(None, ge=0, le=365)
    description: str | None = None
    is_active: bool | None = None


def plan_out(p: MembershipPlan) -> dict:
    return {"id": p.id, "name": p.name, "duration_days": p.duration_days, "price": p.price,
            "all_branch_access": p.all_branch_access, "max_freeze_days": p.max_freeze_days,
            "description": p.description, "is_active": p.is_active}


@router.get("/membership-plans")
def list_plans(include_inactive: bool = False, ctx: TenantContext = Depends(require("plans.read", "memberships"))):
    stmt = select(MembershipPlan).where(MembershipPlan.org_id == ctx.org_id)
    if not include_inactive:
        stmt = stmt.where(MembershipPlan.is_active.is_(True))
    return [plan_out(p) for p in ctx.db.scalars(stmt.order_by(MembershipPlan.duration_days))]


@router.post("/membership-plans", status_code=201)
def create_plan(body: PlanIn, ctx: TenantContext = Depends(require("plans.write", "memberships"))):
    p = MembershipPlan(org_id=ctx.org_id, **body.model_dump())
    ctx.db.add(p)
    ctx.db.commit()
    return plan_out(p)


@router.patch("/membership-plans/{plan_id}")
def update_plan(plan_id: int, body: PlanPatch, ctx: TenantContext = Depends(require("plans.write", "memberships"))):
    p = ctx.owned(MembershipPlan, plan_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    ctx.db.commit()
    return plan_out(p)


# ---------------- Payments core ----------------
class PaymentIn(BaseModel):
    amount: Decimal = Field(gt=0)
    method: PaymentMethod = PaymentMethod.cash
    reference: str | None = Field(None, max_length=120)
    notes: str = ""


def _notify_channel(features: set[str]) -> str:
    for ch, feat in (("whatsapp", "reminders_whatsapp"), ("sms", "reminders_sms")):
        if feat in features:
            return ch
    return "email"


def record_payment(ctx: TenantContext, member: Member, sub: MemberSubscription | None, body: PaymentIn) -> Payment:
    if sub is not None and body.amount > sub.amount_due:
        raise bad_request(f"Amount exceeds due ({sub.amount_due})")
    org = ctx.org
    seq = next_seq(ctx.db, ctx.org_id, "invoice_seq")
    invoice_no = f"{org.slug[:6].upper()}-{date.today():%y%m}-{seq:05d}"
    rate = Decimal(org.tax_percent or 0)
    tax = (body.amount * rate / (100 + rate)).quantize(TWO, ROUND_HALF_UP) if rate else Decimal(0)
    p = Payment(org_id=ctx.org_id, branch_id=sub.branch_id if sub else member.home_branch_id, member_id=member.id,
                subscription_id=sub.id if sub else None, invoice_no=invoice_no, amount=body.amount, tax_amount=tax,
                method=body.method, reference=body.reference, notes=body.notes, recorded_by=ctx.user.id)
    ctx.db.add(p)
    if sub is not None:
        sub.amount_paid += body.amount
    ctx.db.flush()
    channel = _notify_channel(ctx.features)
    recipient = member.email if channel == "email" else member.phone
    if recipient:
        queue(ctx.db, org_id=ctx.org_id, member_id=member.id, channel=channel, recipient=recipient,
              template="payment_receipt", payload={"amount": str(body.amount), "invoice_no": invoice_no, "gym": org.name},
              dedupe_key=f"receipt:{p.id}")
    audit(ctx.db, "payment.create", user_id=ctx.user.id, org_id=ctx.org_id, entity="payment", entity_id=p.id,
          amount=str(body.amount))
    return p


def payment_out(p: Payment) -> dict:
    return {"id": p.id, "invoice_no": p.invoice_no, "member_id": p.member_id, "subscription_id": p.subscription_id,
            "branch_id": p.branch_id, "amount": p.amount, "tax_amount": p.tax_amount, "method": p.method.value,
            "reference": p.reference, "paid_at": p.paid_at}


# ---------------- Subscriptions ----------------
class SubscribeIn(BaseModel):
    plan_id: int
    start_date: date | None = None
    discount: Decimal = Field(Decimal(0), ge=0)
    payment: PaymentIn | None = None


@router.post("/members/{member_id}/subscriptions", status_code=201)
def subscribe(member_id: int, body: SubscribeIn,
              ctx: TenantContext = Depends(require("subscriptions.write", "memberships"))):
    """New membership or renewal. Renewals start the day after the current one ends."""
    member = ctx.owned(Member, member_id)
    plan = ctx.owned(MembershipPlan, body.plan_id)
    if not plan.is_active:
        raise bad_request("Plan is inactive")
    if body.discount > plan.price:
        raise bad_request("Discount exceeds price")
    latest_end = ctx.db.scalar(select(func.max(MemberSubscription.end_date)).where(
        MemberSubscription.member_id == member.id,
        MemberSubscription.status.in_([SubscriptionStatus.active, SubscriptionStatus.frozen])))
    start = body.start_date or (latest_end + timedelta(days=1) if latest_end and latest_end >= date.today()
                                else date.today())
    sub = MemberSubscription(org_id=ctx.org_id, branch_id=member.home_branch_id, member_id=member.id, plan_id=plan.id,
                             start_date=start, end_date=start + timedelta(days=plan.duration_days - 1),
                             price=plan.price, discount=body.discount, amount_paid=Decimal(0))
    ctx.db.add(sub)
    ctx.db.flush()
    ctx.db.refresh(sub)
    payment = record_payment(ctx, member, sub, body.payment) if body.payment else None
    if plan.all_branch_access and not member.all_branch_access:
        member.all_branch_access = True
    ctx.db.commit()
    return {"subscription": sub_out(sub), "payment": payment_out(payment) if payment else None}


@router.post("/subscriptions/{sub_id}/payments", status_code=201)
def pay_subscription(sub_id: int, body: PaymentIn, ctx: TenantContext = Depends(require("payments.write", "payments"))):
    sub = ctx.owned(MemberSubscription, sub_id)
    member = ctx.db.get(Member, sub.member_id)
    p = record_payment(ctx, member, sub, body)
    ctx.db.commit()
    return payment_out(p)


@router.post("/subscriptions/{sub_id}/freeze")
def freeze(sub_id: int, ctx: TenantContext = Depends(require("subscriptions.write", "membership_freeze"))):
    sub = ctx.owned(MemberSubscription, sub_id)
    if sub.status != SubscriptionStatus.active:
        raise bad_request("Only active memberships can be frozen")
    if sub.freeze_days_used >= sub.plan.max_freeze_days:
        raise bad_request("No freeze days left on this plan")
    sub.status, sub.frozen_from = SubscriptionStatus.frozen, date.today()
    ctx.db.commit()
    return sub_out(sub)


@router.post("/subscriptions/{sub_id}/unfreeze")
def unfreeze(sub_id: int, ctx: TenantContext = Depends(require("subscriptions.write", "membership_freeze"))):
    sub = ctx.owned(MemberSubscription, sub_id)
    if sub.status != SubscriptionStatus.frozen or not sub.frozen_from:
        raise bad_request("Membership is not frozen")
    days = min((date.today() - sub.frozen_from).days, sub.plan.max_freeze_days - sub.freeze_days_used)
    sub.end_date += timedelta(days=max(days, 0))
    sub.freeze_days_used += max(days, 0)
    sub.status, sub.frozen_from = SubscriptionStatus.active, None
    ctx.db.commit()
    return sub_out(sub)


@router.post("/subscriptions/{sub_id}/cancel")
def cancel(sub_id: int, ctx: TenantContext = Depends(require("subscriptions.write", "memberships"))):
    sub = ctx.owned(MemberSubscription, sub_id)
    sub.status = SubscriptionStatus.cancelled
    audit(ctx.db, "subscription.cancel", user_id=ctx.user.id, org_id=ctx.org_id, entity="subscription", entity_id=sub.id)
    ctx.db.commit()
    return sub_out(sub)


# ---------------- Payment listing & receipts ----------------
@router.get("/payments")
def list_payments(
    date_from: date | None = None, date_to: date | None = None, branch_id: int | None = None,
    method: PaymentMethod | None = None, member_id: int | None = None,
    page: int = Query(1, ge=1), size: int = Query(50, ge=1, le=200),
    ctx: TenantContext = Depends(require("payments.read", "payments")),
):
    conds = [Payment.org_id == ctx.org_id, ctx.branch_filter(Payment.branch_id)]
    if date_from:
        conds.append(Payment.paid_at >= datetime.combine(date_from, datetime.min.time()))
    if date_to:
        conds.append(Payment.paid_at < datetime.combine(date_to + timedelta(days=1), datetime.min.time()))
    if branch_id:
        conds.append(Payment.branch_id == branch_id)
    if method:
        conds.append(Payment.method == method)
    if member_id:
        conds.append(Payment.member_id == member_id)
    total, count = ctx.db.execute(select(func.coalesce(func.sum(Payment.amount), 0), func.count()).where(*conds)).one()
    rows = ctx.db.scalars(select(Payment).where(*conds).order_by(Payment.paid_at.desc())
                          .offset((page - 1) * size).limit(size))
    return {"total_amount": total, "count": count, "items": [payment_out(p) for p in rows]}


@router.get("/payments/{payment_id}/receipt", response_class=HTMLResponse)
def receipt(payment_id: int, ctx: TenantContext = Depends(require("payments.read", "invoices"))):
    """Printable receipt (browser 'Save as PDF' — no PDF dependency needed)."""
    p = ctx.owned(Payment, payment_id)
    m, b, org = ctx.db.get(Member, p.member_id), ctx.db.get(Branch, p.branch_id), ctx.org
    sub = ctx.db.get(MemberSubscription, p.subscription_id) if p.subscription_id else None
    e = html.escape
    rows = f"<tr><td>{e(sub.plan.name)} ({sub.start_date:%d %b %Y} – {sub.end_date:%d %b %Y})</td>" \
           f"<td>₹{p.amount}</td></tr>" if sub else f"<tr><td>{e(p.notes or 'Payment')}</td><td>₹{p.amount}</td></tr>"
    gst = f"<p>GSTIN: {e(org.gstin)}</p>" if org.gstin else ""
    tax = f"<p>Includes GST ₹{p.tax_amount}</p>" if p.tax_amount else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>{e(p.invoice_no)}</title>
<style>body{{font-family:system-ui,sans-serif;max-width:640px;margin:32px auto;color:#0f172a}}
table{{width:100%;border-collapse:collapse}}td{{padding:8px;border-bottom:1px solid #e2e8f0}}
td:last-child{{text-align:right}}.muted{{color:#64748b}}@media print{{button{{display:none}}}}</style></head><body>
<h2>{e(org.name)}</h2><p class="muted">{e(b.name)} • {e(b.area)}<br>{e(b.address)}</p>{gst}
<h3>Receipt {e(p.invoice_no)}</h3><p>Date: {p.paid_at:%d %b %Y}<br>Member: {e(m.full_name)} ({e(m.member_code)})
<br>Phone: {e(m.phone)}</p><table>{rows}<tr><td><b>Total paid ({e(p.method.value.upper())})</b></td>
<td><b>₹{p.amount}</b></td></tr></table>{tax}
<p class="muted">Powered by Gym-OS</p><button onclick="window.print()">Print / Save PDF</button></body></html>"""
