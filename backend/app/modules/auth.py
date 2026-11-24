from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, utcnow
from app.core.entitlements import enabled_features
from app.core.deps import get_current_user
from app.core.utils import normalize_phone
from app.core.security import (
    create_access_token, create_refresh_token, decode_token, generate_otp, hash_otp, verify_password,
)
from app.models import Member, Organization, OtpCode, User
from app.modules.notify import send_now

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    login: str = Field(description="email or phone")
    password: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshIn(BaseModel):
    refresh_token: str


class OtpRequestIn(BaseModel):
    phone: str = Field(min_length=10, max_length=15)


class OtpVerifyIn(OtpRequestIn):
    code: str = Field(min_length=6, max_length=6)


def issue_tokens(db: Session, user: User) -> TokenOut:
    user.last_login_at = utcnow()
    db.commit()
    return TokenOut(access_token=create_access_token(user.id), refresh_token=create_refresh_token(user.id))


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Session = Depends(get_db)):
    ident = body.login.strip().lower()
    q = select(User).where(User.email == ident) if "@" in ident else select(User).where(
        User.phone == normalize_phone(ident))
    user = db.scalar(q)
    if not user or not user.is_active or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return issue_tokens(db, user)


@router.post("/refresh", response_model=TokenOut)
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    return TokenOut(access_token=create_access_token(user.id), refresh_token=create_refresh_token(user.id))


@router.post("/otp/request")
def otp_request(body: OtpRequestIn, db: Session = Depends(get_db)):
    """Member login via phone OTP. Only phones registered as a member or user can receive an OTP."""
    phone = normalize_phone(body.phone)
    known = db.scalar(select(Member.id).where(Member.phone == phone).limit(1)) or db.scalar(
        select(User.id).where(User.phone == phone))
    resp: dict = {"sent": True}
    if not known:
        return resp  # don't reveal whether a phone is registered
    recent = db.scalar(select(OtpCode).where(
        OtpCode.phone == phone, OtpCode.created_at > utcnow() - timedelta(seconds=30)))
    if recent:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Please wait before requesting another OTP")
    code = generate_otp()
    s = get_settings()
    db.add(OtpCode(phone=phone, code_hash=hash_otp(code),
                   expires_at=utcnow() + timedelta(minutes=s.otp_ttl_minutes)))
    db.commit()
    send_now("sms", phone, "otp", {"code": code})
    if s.otp_dev_echo:
        resp["dev_otp"] = code
    return resp


@router.post("/otp/verify", response_model=TokenOut)
def otp_verify(body: OtpVerifyIn, db: Session = Depends(get_db)):
    phone = normalize_phone(body.phone)
    otp = db.scalar(select(OtpCode).where(OtpCode.phone == phone, OtpCode.used.is_(False))
                    .order_by(OtpCode.id.desc()).limit(1))
    if not otp or otp.expires_at < utcnow() or otp.attempts >= 5:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "OTP expired, request a new one")
    if otp.code_hash != hash_otp(body.code):
        otp.attempts += 1
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect OTP")
    otp.used = True
    user = db.scalar(select(User).where(User.phone == phone))
    members = list(db.scalars(select(Member).where(Member.phone == phone)))
    if not user:
        if not members:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Phone not registered")
        user = User(full_name=members[0].full_name, phone=phone)
        db.add(user)
        db.flush()
    for m in members:  # link member profiles across gyms to this login
        if m.user_id is None:
            m.user_id = user.id
    return issue_tokens(db, user)


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    orgs = []
    for ou in user.org_roles:
        if not ou.is_active:
            continue
        org = db.get(Organization, ou.org_id)
        orgs.append({
            "org_id": org.id, "name": org.name, "type": org.type.value, "status": org.status.value,
            "plan": org.plan.code, "role": ou.role.value, "branch_id": ou.branch_id,
            "features": sorted(enabled_features(db, org)),
        })
    memberships = [
        {"member_id": m.id, "org_id": m.org_id, "org_name": db.get(Organization, m.org_id).name,
         "home_branch_id": m.home_branch_id}
        for m in db.scalars(select(Member).where(Member.user_id == user.id))
    ]
    return {
        "id": user.id, "full_name": user.full_name, "email": user.email, "phone": user.phone,
        "is_platform_admin": user.is_platform_admin, "staff_of": orgs, "member_of": memberships,
    }
