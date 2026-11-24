"""Request dependencies: authentication, tenant context, RBAC, and feature gating (all server-side)."""
from dataclasses import dataclass, field

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.entitlements import enabled_features, org_is_operational
from app.core.errors import forbidden, not_found
from app.core.permissions import has_permission
from app.core.security import decode_token
from app.models import Organization, OrgUser, StaffRole, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    if not creds:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    try:
        payload = decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User inactive")
    return user


def require_platform_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_platform_admin:
        raise forbidden("Platform admin only")
    return user


@dataclass
class TenantContext:
    db: Session
    user: User
    org: Organization
    role: StaffRole
    branch_id: int | None  # None = all branches
    features: set[str] = field(default_factory=set)
    impersonating: bool = False

    @property
    def org_id(self) -> int:
        return self.org.id

    def can_access_branch(self, branch_id: int) -> bool:
        return self.branch_id is None or self.branch_id == branch_id

    def ensure_branch(self, branch_id: int) -> None:
        if not self.can_access_branch(branch_id):
            raise forbidden("No access to this branch")

    def owned(self, model, obj_id: int, what: str | None = None):
        """Fetch a tenant-owned row, 404 if it belongs to another tenant/branch."""
        obj = self.db.get(model, obj_id)
        if not obj or obj.org_id != self.org_id:
            raise not_found(what or model.__name__)
        if model.__tablename__ == "branches":
            bid = obj.id
        else:
            bid = getattr(obj, "branch_id", None) or getattr(obj, "home_branch_id", None)
        if bid is not None and not self.can_access_branch(bid):
            raise not_found(what or model.__name__)
        return obj

    def branch_filter(self, column):
        """SQL condition limiting a branch column to the caller's scope."""
        return True if self.branch_id is None else column == self.branch_id


def get_tenant(
    x_org_id: int = Header(..., alias="X-Org-Id"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TenantContext:
    org = db.get(Organization, x_org_id)
    if not org:
        raise not_found("Organization")
    ou = db.scalar(
        select(OrgUser).where(OrgUser.org_id == org.id, OrgUser.user_id == user.id, OrgUser.is_active.is_(True))
    )
    if ou:
        role, branch_id, imp = ou.role, ou.branch_id, False
    elif user.is_platform_admin:  # Manima support access, owner-equivalent, audited by callers
        role, branch_id, imp = StaffRole.owner, None, True
    else:
        raise forbidden("Not a member of this organization")
    if not org_is_operational(org) and not user.is_platform_admin:
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            {"code": "org_suspended", "message": "Subscription inactive. Please renew."})
    return TenantContext(db, user, org, role, branch_id, enabled_features(db, org), imp)


def require(perm: str, feature: str | None = None):
    """Dependency factory: RBAC permission + optional plan feature."""

    def dep(ctx: TenantContext = Depends(get_tenant)) -> TenantContext:
        if feature and feature not in ctx.features:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                {"code": "feature_not_in_plan", "feature": feature,
                 "message": "This feature is not available on your plan. Upgrade to unlock it."},
            )
        if not has_permission(ctx.role, perm):
            raise forbidden(f"Missing permission: {perm}")
        return ctx

    return dep
