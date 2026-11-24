"""QR check-in (member self-service), manual check-in by staff, staff attendance, member self-service views."""
import math
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.deps import TenantContext, get_current_user, require
from app.core.entitlements import enabled_features, org_is_operational
from app.core.errors import bad_request, forbidden, not_found
from app.core.permissions import has_permission
from app.core.security import verify_rotating_qr_token
from app.models import (
    Attendance, Branch, Member, MemberSubscription, Organization, Payment, SubscriptionStatus, User,
)
from app.modules.members import current_subscription, sub_out

router = APIRouter(tags=["attendance"])
DUPLICATE_WINDOW = timedelta(hours=2)


class QrCheckinIn(BaseModel):
    branch_code: str = Field(min_length=4, max_length=16)
    token: str | None = None  # rotating QR token
    latitude: float | None = None
    longitude: float | None = None


class ManualCheckinIn(BaseModel):
    member_id: int
    branch_id: int | None = None
    force: bool = False  # manager override for expired memberships


def _distance_m(lat1, lon1, lat2, lon2) -> float:
    r = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _validate_membership(db: Session, member: Member, branch: Branch) -> MemberSubscription:
    if member.home_branch_id != branch.id and not member.all_branch_access:
        raise forbidden("Your membership is not valid at this branch")
    sub = current_subscription(db, member.id)
    if not sub or sub.end_date < date.today():
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            {"code": "membership_expired", "message": "Membership expired. Please renew at the desk."})
    if sub.status == SubscriptionStatus.frozen:
        raise bad_request("Membership is frozen. Ask the desk to unfreeze it.")
    return sub


def _do_checkin(db: Session, org_id: int, branch: Branch, member: Member, method: str) -> tuple[Attendance, bool]:
    recent = db.scalar(select(Attendance).where(
        Attendance.member_id == member.id, Attendance.check_in_at > utcnow() - DUPLICATE_WINDOW)
        .order_by(Attendance.id.desc()).limit(1))
    if recent:
        return recent, False
    a = Attendance(org_id=org_id, branch_id=branch.id, member_id=member.id, method=method)
    db.add(a)
    db.flush()
    return a, True


def _result(member: Member, sub: MemberSubscription | None, a: Attendance, new: bool, branch: Branch) -> dict:
    return {"checked_in": True, "duplicate": not new, "attendance_id": a.id, "at": a.check_in_at,
            "member": {"id": member.id, "name": member.full_name, "code": member.member_code},
            "branch": {"id": branch.id, "name": branch.name, "area": branch.area},
            "subscription": sub_out(sub)}


@router.post("/me/checkin")
def qr_checkin(body: QrCheckinIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Member scanned the branch QR in the app/PWA."""
    branch = db.scalar(select(Branch).where(Branch.code == body.branch_code.upper(), Branch.is_active.is_(True)))
    if not branch:
        raise not_found("Branch")
    org = db.get(Organization, branch.org_id)
    feats = enabled_features(db, org)
    if not org_is_operational(org) or "attendance_qr" not in feats:
        raise forbidden("QR check-in is not available for this gym")
    member = db.scalar(select(Member).where(Member.org_id == org.id, Member.user_id == user.id))
    if not member:
        raise forbidden("You are not a member of this gym")
    method = "qr"
    if "qr_rotating" in feats:
        if not body.token or not verify_rotating_qr_token(branch.qr_secret, body.token):
            raise bad_request("QR expired. Scan the live QR on the reception screen.")
        method = "qr_rotating"
    if "geofence" in feats and branch.latitude is not None and branch.longitude is not None:
        if body.latitude is None or body.longitude is None:
            raise bad_request("Location is required to check in at this gym")
        if _distance_m(body.latitude, body.longitude, branch.latitude, branch.longitude) > branch.geofence_meters:
            raise forbidden("You must be at the gym to check in")
    sub = _validate_membership(db, member, branch)
    a, new = _do_checkin(db, org.id, branch, member, method)
    db.commit()
    return _result(member, sub, a, new, branch)


@router.post("/attendance/checkin")
def manual_checkin(body: ManualCheckinIn, ctx: TenantContext = Depends(require("attendance.write", "attendance_qr"))):
    member = ctx.owned(Member, body.member_id) if ctx.branch_id is None else ctx.db.get(Member, body.member_id)
    if not member or member.org_id != ctx.org_id:
        raise not_found("Member")
    branch_id = body.branch_id or ctx.branch_id or member.home_branch_id
    branch = ctx.owned(Branch, branch_id)
    try:
        sub = _validate_membership(ctx.db, member, branch)
    except HTTPException:
        if not (body.force and has_permission(ctx.role, "subscriptions.write")):
            raise
        sub = current_subscription(ctx.db, member.id)
    a, new = _do_checkin(ctx.db, ctx.org_id, branch, member, "manual")
    ctx.db.commit()
    return _result(member, sub, a, new, branch)


@router.post("/attendance/{attendance_id}/checkout")
def checkout(attendance_id: int, ctx: TenantContext = Depends(require("attendance.write"))):
    a = ctx.owned(Attendance, attendance_id)
    a.check_out_at = a.check_out_at or utcnow()
    ctx.db.commit()
    return {"id": a.id, "check_out_at": a.check_out_at}


@router.get("/attendance")
def list_attendance(day: date | None = None, branch_id: int | None = None,
                    ctx: TenantContext = Depends(require("attendance.read"))):
    day = day or date.today()
    start = datetime.combine(day, datetime.min.time())
    conds = [Attendance.org_id == ctx.org_id, ctx.branch_filter(Attendance.branch_id),
             Attendance.check_in_at >= start, Attendance.check_in_at < start + timedelta(days=1)]
    if branch_id:
        conds.append(Attendance.branch_id == branch_id)
    rows = ctx.db.execute(
        select(Attendance, Member.full_name, Member.member_code, User.full_name)
        .outerjoin(Member, Member.id == Attendance.member_id)
        .outerjoin(User, User.id == Attendance.staff_user_id)
        .where(*conds).order_by(Attendance.check_in_at.desc())
    ).all()
    return [{"id": a.id, "branch_id": a.branch_id, "member_id": a.member_id, "member_name": mn, "member_code": mc,
             "staff_user_id": a.staff_user_id, "staff_name": sn, "check_in_at": a.check_in_at,
             "check_out_at": a.check_out_at, "method": a.method} for a, mn, mc, sn in rows]


@router.post("/attendance/staff/checkin")
def staff_checkin(ctx: TenantContext = Depends(require("branches.read", "staff_attendance"))):
    branch_id = ctx.branch_id or ctx.db.scalar(
        select(Branch.id).where(Branch.org_id == ctx.org_id).order_by(Branch.id).limit(1))
    today = datetime.combine(date.today(), datetime.min.time())
    existing = ctx.db.scalar(select(Attendance).where(
        Attendance.staff_user_id == ctx.user.id, Attendance.org_id == ctx.org_id, Attendance.check_in_at >= today))
    if existing:
        if not existing.check_out_at:
            existing.check_out_at = utcnow()
            ctx.db.commit()
        return {"id": existing.id, "check_in_at": existing.check_in_at, "check_out_at": existing.check_out_at}
    a = Attendance(org_id=ctx.org_id, branch_id=branch_id, staff_user_id=ctx.user.id, method="manual")
    ctx.db.add(a)
    ctx.db.commit()
    return {"id": a.id, "check_in_at": a.check_in_at, "check_out_at": None}


# ---------------- Member self-service (PWA) ----------------
@router.get("/me/gyms")
def my_gyms(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    out = []
    for m in db.scalars(select(Member).where(Member.user_id == user.id)):
        org = db.get(Organization, m.org_id)
        if "member_app" not in enabled_features(db, org):
            continue
        branch = db.get(Branch, m.home_branch_id)
        sub = current_subscription(db, m.id)
        pays = db.scalars(select(Payment).where(Payment.member_id == m.id).order_by(Payment.paid_at.desc()).limit(10))
        visits = db.scalars(select(Attendance.check_in_at).where(Attendance.member_id == m.id)
                            .order_by(Attendance.check_in_at.desc()).limit(30))
        out.append({
            "member_id": m.id, "member_code": m.member_code, "gym": org.name, "org_id": org.id,
            "home_branch": {"name": branch.name, "area": branch.area, "code": branch.code},
            "subscription": sub_out(sub),
            "payments": [{"invoice_no": p.invoice_no, "amount": p.amount, "paid_at": p.paid_at} for p in pays],
            "recent_visits": list(visits),
        })
    return out
