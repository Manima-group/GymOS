"""Manima Super Admin: tenants, plans, feature toggles, SaaS billing, MRR."""
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.db import get_db, utcnow
from app.core.deps import require_platform_admin
from app.core.entitlements import effective_limits, enabled_features, usage
from app.core.errors import bad_request, not_found
from app.models import (
    AuditLog, Feature, Member, Organization, OrgFeatureOverride, OrgStatus, Plan, PlanFeature, SaasInvoice, User,
)
from app.modules.onboarding import SignupIn, create_organization

router = APIRouter(prefix="/platform", tags=["platform"], dependencies=[Depends(require_platform_admin)])


def _monthly_value(org: Organization) -> Decimal:
    p = org.plan
    return (p.price_yearly / 12) if org.billing_cycle == "yearly" else p.price_monthly


def _org_summary(db: Session, org: Organization) -> dict:
    return {
        "id": org.id, "name": org.name, "slug": org.slug, "type": org.type.value, "status": org.status.value,
        "plan": org.plan.code, "billing_cycle": org.billing_cycle, "trial_ends_at": org.trial_ends_at,
        "subscription_ends_at": org.subscription_ends_at, "email": org.email, "phone": org.phone,
        "message_credits": org.message_credits, "usage": usage(db, org.id), "limits": effective_limits(org),
        "created_at": org.created_at,
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    orgs = list(db.scalars(select(Organization)))
    paying = [o for o in orgs if o.status in (OrgStatus.active, OrgStatus.past_due)]
    month_start = date.today().replace(day=1)
    collected = db.scalar(select(func.coalesce(func.sum(SaasInvoice.amount), 0)).where(
        SaasInvoice.status == "paid", SaasInvoice.paid_at >= month_start)) or 0
    soon = date.today() + timedelta(days=7)
    return {
        "tenants_total": len(orgs),
        "by_status": {s.value: sum(o.status == s for o in orgs) for s in OrgStatus},
        "by_plan": {code: sum(o.plan.code == code for o in orgs) for code in {o.plan.code for o in orgs}},
        "mrr": round(sum((_monthly_value(o) for o in paying), Decimal(0)), 2),
        "arr": round(sum((_monthly_value(o) for o in paying), Decimal(0)) * 12, 2),
        "collected_this_month": collected,
        "trials_ending_7d": [{"id": o.id, "name": o.name, "trial_ends_at": o.trial_ends_at} for o in orgs
                             if o.status == OrgStatus.trial and o.trial_ends_at and o.trial_ends_at <= soon],
        "renewals_due_7d": [{"id": o.id, "name": o.name, "subscription_ends_at": o.subscription_ends_at}
                            for o in paying if o.subscription_ends_at and o.subscription_ends_at <= soon],
        "members_total": db.scalar(select(func.count()).select_from(Member)) or 0,
    }


# ---------------- Tenants ----------------
class TenantCreateIn(SignupIn):
    activate: bool = False  # True = skip trial (paid upfront)


class TenantPatchIn(BaseModel):
    plan_code: str | None = None
    status: OrgStatus | None = None
    billing_cycle: str | None = Field(default=None, pattern="^(monthly|yearly)$")
    subscription_ends_at: date | None = None
    trial_ends_at: date | None = None
    limit_overrides: dict[str, int] | None = None
    name: str | None = None


class FeatureToggleIn(BaseModel):
    enabled: bool
    note: str = ""


class SaasPaymentIn(BaseModel):
    periods: int = Field(1, ge=1, le=36, description="months or years depending on billing_cycle")
    amount: Decimal | None = None  # default = plan price * periods
    method: str = "manual"
    reference: str | None = None


class CreditsIn(BaseModel):
    credits: int = Field(gt=0)
    amount: Decimal = Field(ge=0)
    reference: str | None = None


def _org(db: Session, org_id: int) -> Organization:
    org = db.get(Organization, org_id)
    if not org:
        raise not_found("Organization")
    return org


@router.get("/tenants")
def list_tenants(q: str | None = None, status: OrgStatus | None = None, page: int = Query(1, ge=1),
                 size: int = Query(25, le=100), db: Session = Depends(get_db)):
    stmt = select(Organization)
    if q:
        like = f"%{q.lower()}%"
        stmt = stmt.where(or_(func.lower(Organization.name).like(like), Organization.phone.like(like),
                              func.lower(Organization.email).like(like)))
    if status:
        stmt = stmt.where(Organization.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Organization.id.desc()).offset((page - 1) * size).limit(size))
    return {"total": total, "items": [_org_summary(db, o) for o in rows]}


@router.post("/tenants", status_code=201)
def create_tenant(body: TenantCreateIn, admin: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    org, owner = create_organization(db, body, status_=OrgStatus.active if body.activate else OrgStatus.trial)
    if body.activate:
        org.subscription_ends_at = date.today() + relativedelta(months=1)
    audit(db, "tenant.create", user_id=admin.id, org_id=org.id, entity="organization", entity_id=org.id)
    db.commit()
    return _org_summary(db, org)


@router.get("/tenants/{org_id}")
def tenant_detail(org_id: int, db: Session = Depends(get_db)):
    org = _org(db, org_id)
    invoices = db.scalars(select(SaasInvoice).where(SaasInvoice.org_id == org.id).order_by(SaasInvoice.id.desc()))
    return {
        **_org_summary(db, org),
        "features_enabled": sorted(enabled_features(db, org)),
        "plan_features": sorted(f.feature_key for f in org.plan.features),
        "overrides": [{"feature": o.feature_key, "enabled": o.enabled, "note": o.note} for o in org.feature_overrides],
        "invoices": [{"id": i.id, "kind": i.kind, "amount": i.amount, "period_start": i.period_start,
                      "period_end": i.period_end, "credits": i.credits, "status": i.status, "paid_at": i.paid_at}
                     for i in invoices],
    }


@router.patch("/tenants/{org_id}")
def update_tenant(org_id: int, body: TenantPatchIn, admin: User = Depends(require_platform_admin),
                  db: Session = Depends(get_db)):
    org = _org(db, org_id)
    changes = body.model_dump(exclude_unset=True)
    if "plan_code" in changes:
        plan = db.scalar(select(Plan).where(Plan.code == body.plan_code))
        if not plan:
            raise bad_request("Unknown plan")
        org.plan_id = plan.id
        db.flush()
        db.refresh(org)
    for k in ("status", "billing_cycle", "subscription_ends_at", "trial_ends_at", "limit_overrides", "name"):
        if k in changes:
            setattr(org, k, changes[k])
    audit(db, "tenant.update", user_id=admin.id, org_id=org.id, entity="organization", entity_id=org.id,
          changes={k: str(v) for k, v in changes.items()})
    db.commit()
    return _org_summary(db, org)


@router.put("/tenants/{org_id}/features/{key}")
def toggle_feature(org_id: int, key: str, body: FeatureToggleIn, admin: User = Depends(require_platform_admin),
                   db: Session = Depends(get_db)):
    org = _org(db, org_id)
    if not db.get(Feature, key):
        raise not_found("Feature")
    ov = db.get(OrgFeatureOverride, (org.id, key))
    if ov:
        ov.enabled, ov.note = body.enabled, body.note
    else:
        db.add(OrgFeatureOverride(org_id=org.id, feature_key=key, enabled=body.enabled, note=body.note))
    audit(db, "tenant.feature_override", user_id=admin.id, org_id=org.id, entity="feature", entity_id=key,
          enabled=body.enabled)
    db.commit()
    db.refresh(org)
    return {"features_enabled": sorted(enabled_features(db, org))}


@router.delete("/tenants/{org_id}/features/{key}")
def reset_feature(org_id: int, key: str, admin: User = Depends(require_platform_admin), db: Session = Depends(get_db)):
    org = _org(db, org_id)
    ov = db.get(OrgFeatureOverride, (org.id, key))
    if ov:
        db.delete(ov)
        audit(db, "tenant.feature_reset", user_id=admin.id, org_id=org.id, entity="feature", entity_id=key)
        db.commit()
        db.refresh(org)
    return {"features_enabled": sorted(enabled_features(db, org))}


@router.post("/tenants/{org_id}/payments", status_code=201)
def record_saas_payment(org_id: int, body: SaasPaymentIn, admin: User = Depends(require_platform_admin),
                        db: Session = Depends(get_db)):
    """Gym paid Manima: extend subscription, reactivate, top up monthly credits."""
    org = _org(db, org_id)
    yearly = org.billing_cycle == "yearly"
    unit = org.plan.price_yearly if yearly else org.plan.price_monthly
    start = max(org.subscription_ends_at or date.today(), date.today())
    end = start + (relativedelta(years=body.periods) if yearly else relativedelta(months=body.periods))
    inv = SaasInvoice(org_id=org.id, plan_id=org.plan_id, amount=body.amount if body.amount is not None else unit * body.periods,
                      period_start=start, period_end=end, status="paid", method=body.method,
                      reference=body.reference, paid_at=utcnow())
    db.add(inv)
    org.subscription_ends_at, org.status = end, OrgStatus.active
    months = body.periods * (12 if yearly else 1)
    org.message_credits += org.plan.limits.get("monthly_message_credits", 0) * months
    audit(db, "saas.payment", user_id=admin.id, org_id=org.id, entity="saas_invoice", amount=str(inv.amount))
    db.commit()
    return {"invoice_id": inv.id, "subscription_ends_at": end, "status": org.status.value,
            "message_credits": org.message_credits}


@router.post("/tenants/{org_id}/credits", status_code=201)
def add_credits(org_id: int, body: CreditsIn, admin: User = Depends(require_platform_admin),
                db: Session = Depends(get_db)):
    org = _org(db, org_id)
    org.message_credits += body.credits
    db.add(SaasInvoice(org_id=org.id, plan_id=org.plan_id, kind="credits", amount=body.amount,
                       credits=body.credits, status="paid", reference=body.reference, paid_at=utcnow()))
    audit(db, "saas.credits", user_id=admin.id, org_id=org.id, credits=body.credits)
    db.commit()
    return {"message_credits": org.message_credits}


# ---------------- Plans & features ----------------
class PlanIn(BaseModel):
    code: str = Field(pattern="^[a-z0-9_]{2,32}$")
    name: str
    price_monthly: Decimal = Field(ge=0)
    price_yearly: Decimal = Field(ge=0)
    limits: dict[str, int] = {}
    features: list[str] = []
    sort_order: int = 0
    is_active: bool = True


class PlanPatchIn(BaseModel):
    name: str | None = None
    price_monthly: Decimal | None = None
    price_yearly: Decimal | None = None
    limits: dict[str, int] | None = None
    features: list[str] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


def _plan_out(p: Plan) -> dict:
    return {"id": p.id, "code": p.code, "name": p.name, "price_monthly": p.price_monthly,
            "price_yearly": p.price_yearly, "limits": p.limits, "is_active": p.is_active,
            "sort_order": p.sort_order, "features": sorted(f.feature_key for f in p.features)}


def _set_plan_features(db: Session, plan: Plan, keys: list[str]) -> None:
    valid = set(db.scalars(select(Feature.key)))
    unknown = set(keys) - valid
    if unknown:
        raise bad_request(f"Unknown features: {sorted(unknown)}")
    plan.features = [PlanFeature(feature_key=k) for k in sorted(set(keys))]


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    return [_plan_out(p) for p in db.scalars(select(Plan).order_by(Plan.sort_order))]


@router.post("/plans", status_code=201)
def create_plan(body: PlanIn, db: Session = Depends(get_db)):
    if db.scalar(select(Plan.id).where(Plan.code == body.code)):
        raise bad_request("Plan code exists")
    plan = Plan(**body.model_dump(exclude={"features"}))
    db.add(plan)
    _set_plan_features(db, plan, body.features)
    db.commit()
    return _plan_out(plan)


@router.patch("/plans/{plan_id}")
def update_plan(plan_id: int, body: PlanPatchIn, db: Session = Depends(get_db)):
    plan = db.get(Plan, plan_id)
    if not plan:
        raise not_found("Plan")
    data = body.model_dump(exclude_unset=True)
    if "features" in data:
        _set_plan_features(db, plan, data.pop("features"))
    for k, v in data.items():
        setattr(plan, k, v)
    db.commit()
    return _plan_out(plan)


@router.get("/features")
def list_features(db: Session = Depends(get_db)):
    return [{"key": f.key, "name": f.name, "category": f.category, "is_globally_enabled": f.is_globally_enabled}
            for f in db.scalars(select(Feature).order_by(Feature.category, Feature.key))]


@router.patch("/features/{key}")
def kill_switch(key: str, body: FeatureToggleIn, admin: User = Depends(require_platform_admin),
                db: Session = Depends(get_db)):
    f = db.get(Feature, key)
    if not f:
        raise not_found("Feature")
    f.is_globally_enabled = body.enabled
    audit(db, "feature.global_toggle", user_id=admin.id, entity="feature", entity_id=key, enabled=body.enabled)
    db.commit()
    return {"key": key, "is_globally_enabled": f.is_globally_enabled}


@router.get("/audit")
def audit_log(org_id: int | None = None, limit: int = Query(100, le=500), db: Session = Depends(get_db)):
    stmt = select(AuditLog).order_by(AuditLog.id.desc()).limit(limit)
    if org_id:
        stmt = stmt.where(AuditLog.org_id == org_id)
    return [{"id": a.id, "org_id": a.org_id, "user_id": a.user_id, "action": a.action, "entity": a.entity,
             "entity_id": a.entity_id, "data": a.data, "at": a.created_at} for a in db.scalars(stmt)]
