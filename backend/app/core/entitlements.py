"""Feature + limit resolution: plan defaults -> tenant overrides -> global kill switch."""
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Branch, Feature, Member, Organization, OrgStatus, OrgUser

LIMIT_MODELS = {"max_branches": Branch, "max_members": Member, "max_staff": OrgUser}


def enabled_features(db: Session, org: Organization) -> set[str]:
    keys = {pf.feature_key for pf in org.plan.features}
    for ov in org.feature_overrides:
        (keys.add if ov.enabled else keys.discard)(ov.feature_key)
    disabled = set(db.scalars(select(Feature.key).where(Feature.is_globally_enabled.is_(False))))
    return keys - disabled


def effective_limits(org: Organization) -> dict:
    return {**(org.plan.limits or {}), **(org.limit_overrides or {})}


def usage(db: Session, org_id: int) -> dict[str, int]:
    return {
        key: db.scalar(select(func.count()).select_from(m).where(m.org_id == org_id)) or 0
        for key, m in LIMIT_MODELS.items()
    }


def check_limit(db: Session, org: Organization, key: str) -> None:
    from app.core.errors import LimitReached

    limit = effective_limits(org).get(key, -1)
    if limit is None or limit < 0:
        return
    model = LIMIT_MODELS[key]
    count = db.scalar(select(func.count()).select_from(model).where(model.org_id == org.id)) or 0
    if count >= limit:
        raise LimitReached(key, limit)


def org_is_operational(org: Organization) -> bool:
    return org.status in (OrgStatus.trial, OrgStatus.active, OrgStatus.past_due)
