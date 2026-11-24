"""Idempotent seed: features, default plans, and the first Manima super admin.

    python -m app.seed --admin-email you@manima.co.in --admin-password '...'
"""
import argparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.catalog import DEFAULT_PLANS, FEATURES
from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models import Feature, Plan, PlanFeature, User


def seed_catalog(db: Session) -> None:
    for key, (name, cat) in FEATURES.items():
        f = db.get(Feature, key)
        if not f:
            db.add(Feature(key=key, name=name, category=cat))
    db.flush()
    for spec in DEFAULT_PLANS:
        plan = db.scalar(select(Plan).where(Plan.code == spec["code"]))
        if plan:
            continue  # never overwrite prices/features edited by the admin
        plan = Plan(code=spec["code"], name=spec["name"], price_monthly=spec["price_monthly"],
                    price_yearly=spec["price_yearly"], limits=spec["limits"], sort_order=spec["sort_order"])
        plan.features = [PlanFeature(feature_key=k) for k in spec["features"]]
        db.add(plan)
    db.commit()


def seed_admin(db: Session, email: str, password: str, name: str = "Manima Admin") -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user:
        user = User(full_name=name, email=email.lower(), password_hash=hash_password(password), is_platform_admin=True)
        db.add(user)
        db.commit()
    return user


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--admin-email")
    ap.add_argument("--admin-password")
    a = ap.parse_args()
    with SessionLocal() as s:
        seed_catalog(s)
        if a.admin_email and a.admin_password:
            seed_admin(s, a.admin_email, a.admin_password)
    print("seeded")
