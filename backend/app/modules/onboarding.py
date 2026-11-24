"""Public endpoints: plan catalogue, gym self-signup (free trial), branch QR landing, enquiry form."""
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db
from app.core.entitlements import enabled_features, org_is_operational
from app.core.errors import bad_request, not_found
from app.core.security import hash_password, new_secret
from app.core.utils import normalize_phone, short_code, slugify
from app.models import Branch, Lead, Organization, OrgStatus, OrgType, OrgUser, Plan, StaffRole, User

router = APIRouter(prefix="/public", tags=["public"])


class SignupIn(BaseModel):
    gym_name: str = Field(min_length=2, max_length=160)
    owner_name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    phone: str = Field(min_length=10, max_length=15)
    password: str = Field(min_length=8, max_length=128)
    org_type: OrgType = OrgType.single
    plan_code: str = "basic"
    branch_name: str | None = None
    area: str = Field(min_length=2, max_length=120)
    address: str = ""


class EnquiryIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=10, max_length=15)
    interest: str = Field(default="", max_length=200)


def unique_branch_code(db: Session) -> str:
    while True:
        code = short_code(6)
        if not db.scalar(select(Branch.id).where(Branch.code == code)):
            return code


def create_branch(db: Session, org: Organization, name: str, area: str, address: str = "",
                  phone: str | None = None) -> Branch:
    b = Branch(org_id=org.id, name=name, area=area, address=address, phone=phone,
               code=unique_branch_code(db), qr_secret=new_secret())
    db.add(b)
    db.flush()
    return b


def create_organization(db: Session, body: SignupIn, *, status_: OrgStatus = OrgStatus.trial) -> tuple[Organization, User]:
    plan = db.scalar(select(Plan).where(Plan.code == body.plan_code, Plan.is_active.is_(True)))
    if not plan:
        raise bad_request("Unknown plan")
    email, phone = body.email.lower(), normalize_phone(body.phone)
    if db.scalar(select(User.id).where((User.email == email) | (User.phone == phone))):
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email or phone already exists")

    slug, i = slugify(body.gym_name), 1
    base = slug
    while db.scalar(select(Organization.id).where(Organization.slug == slug)):
        i += 1
        slug = f"{base}-{i}"
    org = Organization(
        name=body.gym_name, slug=slug, type=body.org_type, plan_id=plan.id, status=status_,
        email=email, phone=phone, trial_ends_at=date.today() + timedelta(days=get_settings().trial_days),
        message_credits=plan.limits.get("monthly_message_credits", 0),
    )
    db.add(org)
    db.flush()
    owner = User(full_name=body.owner_name, email=email, phone=phone, password_hash=hash_password(body.password))
    db.add(owner)
    db.flush()
    db.add(OrgUser(org_id=org.id, user_id=owner.id, role=StaffRole.owner))
    create_branch(db, org, body.branch_name or body.gym_name, body.area, body.address, phone)
    db.flush()
    return org, owner


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    plans = db.scalars(select(Plan).where(Plan.is_active.is_(True)).order_by(Plan.sort_order))
    return [{"code": p.code, "name": p.name, "price_monthly": p.price_monthly, "price_yearly": p.price_yearly,
             "limits": p.limits, "features": sorted(f.feature_key for f in p.features)} for p in plans]


@router.post("/signup", status_code=201)
def signup(body: SignupIn, db: Session = Depends(get_db)):
    org, owner = create_organization(db, body)
    db.commit()
    return {"org_id": org.id, "slug": org.slug, "trial_ends_at": org.trial_ends_at, "owner_user_id": owner.id}


def _active_branch(db: Session, code: str) -> tuple[Branch, Organization]:
    b = db.scalar(select(Branch).where(Branch.code == code.upper(), Branch.is_active.is_(True)))
    if not b:
        raise not_found("Branch")
    org = db.get(Organization, b.org_id)
    if not org_is_operational(org):
        raise not_found("Branch")
    return b, org


@router.get("/branches/{code}")
def branch_landing(code: str, db: Session = Depends(get_db)):
    """What a phone shows after scanning the poster QR."""
    b, org = _active_branch(db, code)
    feats = enabled_features(db, org)
    return {
        "branch_code": b.code, "branch_name": b.name, "area": b.area, "address": b.address,
        "gym_name": org.name, "branding": org.branding if "white_label" in feats else {},
        "rotating_qr": "qr_rotating" in feats, "enquiry_enabled": "crm" in feats,
        "geofence": "geofence" in feats and b.latitude is not None and b.longitude is not None,
    }


@router.post("/branches/{code}/enquiry", status_code=201)
def enquiry(code: str, body: EnquiryIn, db: Session = Depends(get_db)):
    b, org = _active_branch(db, code)
    if "crm" not in enabled_features(db, org):
        raise not_found("Enquiry form")
    db.add(Lead(org_id=org.id, branch_id=b.id, full_name=body.full_name, phone=normalize_phone(body.phone),
                interest=body.interest, source="qr", follow_up_on=date.today()))
    db.commit()
    return {"ok": True, "message": f"Thanks! {org.name} will contact you shortly."}
