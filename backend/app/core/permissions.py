from app.models.identity import StaffRole

ALL = "*"

ROLE_PERMISSIONS: dict[StaffRole, set[str]] = {
    StaffRole.owner: {ALL},
    StaffRole.manager: {
        "branches.read", "members.read", "members.write", "plans.read", "plans.write",
        "subscriptions.write", "attendance.read", "attendance.write", "payments.read", "payments.write",
        "staff.read", "reports.read", "leads.read", "leads.write",
    },
    StaffRole.front_desk: {
        "branches.read", "members.read", "members.write", "plans.read", "subscriptions.write",
        "attendance.read", "attendance.write", "payments.write", "leads.read", "leads.write",
    },
    StaffRole.trainer: {"branches.read", "members.read", "attendance.read", "attendance.write"},
    StaffRole.accountant: {"branches.read", "members.read", "payments.read", "payments.write", "reports.read"},
}


def has_permission(role: StaffRole, perm: str) -> bool:
    perms = ROLE_PERMISSIONS.get(role, set())
    return ALL in perms or perm in perms
