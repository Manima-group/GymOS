"""Branches (with QR posters) and staff management."""
import io

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from PIL import Image, ImageDraw, ImageFont
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app.core.audit import audit
from app.core.config import get_settings
from app.core.deps import TenantContext, require
from app.core.entitlements import check_limit
from app.core.errors import bad_request, forbidden
from app.core.security import hash_password, new_secret, rotating_qr_token
from app.core.utils import normalize_phone
from app.models import Branch, OrgType, OrgUser, StaffRole, User
from app.modules.onboarding import create_branch

router = APIRouter(tags=["branches & staff"])


class BranchIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    area: str = Field(min_length=2, max_length=120)
    address: str = ""
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geofence_meters: int = Field(150, ge=30, le=2000)


class BranchPatch(BaseModel):
    name: str | None = None
    area: str | None = None
    address: str | None = None
    phone: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    geofence_meters: int | None = Field(None, ge=30, le=2000)
    is_active: bool | None = None


def branch_out(b: Branch) -> dict:
    return {"id": b.id, "name": b.name, "area": b.area, "code": b.code, "address": b.address, "phone": b.phone,
            "latitude": b.latitude, "longitude": b.longitude, "geofence_meters": b.geofence_meters,
            "is_active": b.is_active, "checkin_url": f"{get_settings().public_base_url}/c/{b.code}"}


@router.get("/branches")
def list_branches(ctx: TenantContext = Depends(require("branches.read"))):
    rows = ctx.db.scalars(select(Branch).where(Branch.org_id == ctx.org_id, ctx.branch_filter(Branch.id))
                          .order_by(Branch.id))
    return [branch_out(b) for b in rows]


@router.post("/branches", status_code=201)
def add_branch(body: BranchIn, ctx: TenantContext = Depends(require("branches.write"))):
    check_limit(ctx.db, ctx.org, "max_branches")
    b = create_branch(ctx.db, ctx.org, body.name, body.area, body.address, body.phone)
    b.latitude, b.longitude, b.geofence_meters = body.latitude, body.longitude, body.geofence_meters
    if ctx.org.type == OrgType.single:
        ctx.org.type = OrgType.multi  # second branch => multi-branch owner
    audit(ctx.db, "branch.create", user_id=ctx.user.id, org_id=ctx.org_id, entity="branch", entity_id=b.id)
    ctx.db.commit()
    return branch_out(b)


@router.patch("/branches/{branch_id}")
def edit_branch(branch_id: int, body: BranchPatch, ctx: TenantContext = Depends(require("branches.write"))):
    b = ctx.owned(Branch, branch_id)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(b, k, v)
    ctx.db.commit()
    return branch_out(b)


@router.post("/branches/{branch_id}/rotate-qr-secret")
def rotate_secret(branch_id: int, ctx: TenantContext = Depends(require("branches.write"))):
    b = ctx.owned(Branch, branch_id)
    b.qr_secret = new_secret()
    audit(ctx.db, "branch.rotate_secret", user_id=ctx.user.id, org_id=ctx.org_id, entity="branch", entity_id=b.id)
    ctx.db.commit()
    return {"ok": True}


def _font(size: int):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _qr_img(data: str, box: int) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=box, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    return qr.make_image(fill_color="black", back_color="white").convert("RGB")


@router.get("/branches/{branch_id}/qr-poster.png", response_class=Response)
def qr_poster(branch_id: int, ctx: TenantContext = Depends(require("branches.read", "attendance_qr"))):
    """Printable A5-ish poster: gym name, branch + area tag, check-in QR (+ enquiry QR if CRM enabled)."""
    b = ctx.owned(Branch, branch_id)
    base = get_settings().public_base_url
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    color = (ctx.org.branding or {}).get("primary_color", "#0F172A") if "white_label" in ctx.features else "#0F172A"
    d.rectangle([0, 0, W, 260], fill=color)
    d.text((W // 2, 110), ctx.org.name, font=_font(78), fill="white", anchor="mm")
    d.text((W // 2, 200), f"{b.name}  •  {b.area}", font=_font(44), fill="white", anchor="mm")
    qr = _qr_img(f"{base}/c/{b.code}", 22).resize((820, 820))
    img.paste(qr, ((W - 820) // 2, 330))
    d.text((W // 2, 1200), "SCAN TO CHECK IN", font=_font(64), fill="#0F172A", anchor="mm")
    d.text((W // 2, 1275), f"Branch code: {b.code}", font=_font(36), fill="#475569", anchor="mm")
    if "crm" in ctx.features:
        small = _qr_img(f"{base}/c/{b.code}/join", 8).resize((280, 280))
        img.paste(small, (120, 1360))
        d.text((460, 1460), "New here? Scan to enquire", font=_font(40), fill="#0F172A")
        d.text((460, 1520), "or book a free trial", font=_font(34), fill="#475569")
    d.text((W // 2, H - 50), "Powered by Gym-OS • Manima AI Tech Solutions", font=_font(26), fill="#94A3B8", anchor="mm")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return Response(buf.getvalue(), media_type="image/png",
                    headers={"Content-Disposition": f'inline; filename="{b.code}-qr.png"'})


@router.get("/branches/{branch_id}/live-qr")
def live_qr(branch_id: int, ctx: TenantContext = Depends(require("attendance.read", "qr_rotating"))):
    """For the reception tablet: a QR payload that changes every N seconds (anti-cheat)."""
    b = ctx.owned(Branch, branch_id)
    token = rotating_qr_token(b.qr_secret)
    return {"payload": f"{get_settings().public_base_url}/c/{b.code}?t={token}", "token": token,
            "refresh_seconds": get_settings().rotating_qr_window_seconds}


# ---------------- Staff ----------------
class StaffIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    email: EmailStr | None = None
    phone: str = Field(min_length=10, max_length=15)
    password: str = Field(min_length=8, max_length=128)
    role: StaffRole
    branch_id: int | None = None


class StaffPatch(BaseModel):
    role: StaffRole | None = None
    branch_id: int | None = None
    is_active: bool | None = None


def staff_out(ou: OrgUser) -> dict:
    u = ou.user
    return {"id": ou.id, "user_id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone,
            "role": ou.role.value, "branch_id": ou.branch_id, "is_active": ou.is_active}


@router.get("/staff")
def list_staff(ctx: TenantContext = Depends(require("staff.read"))):
    rows = ctx.db.scalars(select(OrgUser).where(OrgUser.org_id == ctx.org_id, ctx.branch_filter(OrgUser.branch_id))
                          .order_by(OrgUser.id))
    return [staff_out(ou) for ou in rows]


@router.post("/staff", status_code=201)
def add_staff(body: StaffIn, ctx: TenantContext = Depends(require("staff.write"))):
    if body.role == StaffRole.owner:
        raise forbidden("Owners are assigned by Manima support")
    if body.branch_id is not None:
        ctx.owned(Branch, body.branch_id)
    elif body.role != StaffRole.manager and ctx.org.type == OrgType.multi:
        raise bad_request("Assign a branch to this staff member")
    check_limit(ctx.db, ctx.org, "max_staff")
    phone = normalize_phone(body.phone)
    email = body.email.lower() if body.email else None
    user = ctx.db.scalar(select(User).where(User.phone == phone))
    if user is None:
        if email and ctx.db.scalar(select(User.id).where(User.email == email)):
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already used by another account")
        user = User(full_name=body.full_name, phone=phone, email=email, password_hash=hash_password(body.password))
        ctx.db.add(user)
        ctx.db.flush()
    elif ctx.db.scalar(select(OrgUser.id).where(OrgUser.org_id == ctx.org_id, OrgUser.user_id == user.id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Already a staff member")
    ou = OrgUser(org_id=ctx.org_id, user_id=user.id, role=body.role, branch_id=body.branch_id)
    ctx.db.add(ou)
    audit(ctx.db, "staff.create", user_id=ctx.user.id, org_id=ctx.org_id, entity="org_user", entity_id=user.id,
          role=body.role.value)
    ctx.db.commit()
    return staff_out(ou)


@router.patch("/staff/{staff_id}")
def edit_staff(staff_id: int, body: StaffPatch, ctx: TenantContext = Depends(require("staff.write"))):
    ou = ctx.db.get(OrgUser, staff_id)
    if not ou or ou.org_id != ctx.org_id:
        raise HTTPException(404, "Staff not found")
    if ou.role == StaffRole.owner or body.role == StaffRole.owner:
        raise forbidden("Owner role can't be changed here")
    data = body.model_dump(exclude_unset=True)
    if data.get("branch_id") is not None:
        ctx.owned(Branch, data["branch_id"])
    for k, v in data.items():
        setattr(ou, k, v)
    audit(ctx.db, "staff.update", user_id=ctx.user.id, org_id=ctx.org_id, entity="org_user", entity_id=ou.id,
          changes={k: str(v) for k, v in data.items()})
    ctx.db.commit()
    return staff_out(ou)
