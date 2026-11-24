"""Single source of truth for feature keys and default plans. Seeded into DB; editable by Super Admin."""

FEATURES: dict[str, tuple[str, str]] = {
    # key: (name, category)
    "members": ("Member management", "core"),
    "memberships": ("Membership plans & renewals", "core"),
    "attendance_qr": ("QR check-in", "core"),
    "payments": ("Payment recording", "core"),
    "invoices": ("GST invoices & receipts", "core"),
    "reminders_email": ("Email reminders", "engagement"),
    "reminders_sms": ("SMS reminders", "engagement"),
    "reminders_whatsapp": ("WhatsApp reminders", "engagement"),
    "membership_freeze": ("Membership freeze/pause", "core"),
    "member_app": ("Member app (PWA)", "engagement"),
    "online_payments": ("Online payments (Razorpay/UPI) (coming soon)", "payments"),
    "crm": ("Leads & enquiry CRM", "growth"),
    "trainers": ("Trainers & PT packages (coming soon)", "growth"),
    "classes": ("Class scheduling (coming soon)", "growth"),
    "staff_attendance": ("Staff attendance", "growth"),
    "multi_branch_dashboard": ("Consolidated multi-branch dashboard", "growth"),
    "reports_advanced": ("Advanced reports (coming soon)", "growth"),
    "data_export": ("CSV/Excel export", "growth"),
    "workouts": ("Workout & diet plans (coming soon)", "premium"),
    "expenses": ("Expenses & P&L (coming soon)", "premium"),
    "pos": ("POS / inventory (coming soon)", "premium"),
    "qr_rotating": ("Rotating anti-cheat QR", "premium"),
    "geofence": ("Geofenced check-in", "premium"),
    "white_label": ("White-label branding", "premium"),
    "ai": ("AI features (coming soon)", "ai"),
}

_BASIC = ["members", "memberships", "attendance_qr", "payments", "invoices", "reminders_email", "member_app"]
_PLUS = _BASIC + [
    "reminders_sms", "membership_freeze", "online_payments", "crm", "trainers", "classes",
    "staff_attendance", "multi_branch_dashboard", "reports_advanced", "data_export",
]
_PREMIUM = _PLUS + ["reminders_whatsapp", "workouts", "expenses", "pos", "qr_rotating", "geofence", "white_label"]

DEFAULT_PLANS = [
    {
        "code": "basic", "name": "Basic", "price_monthly": 999, "price_yearly": 9990, "sort_order": 1,
        "limits": {"max_branches": 1, "max_members": 300, "max_staff": 3, "monthly_message_credits": 0},
        "features": _BASIC,
    },
    {
        "code": "plus", "name": "Plus", "price_monthly": 2499, "price_yearly": 24990, "sort_order": 2,
        "limits": {"max_branches": 3, "max_members": 1500, "max_staff": 15, "monthly_message_credits": 300},
        "features": _PLUS,
    },
    {
        "code": "premium", "name": "Premium", "price_monthly": 4999, "price_yearly": 49990, "sort_order": 3,
        "limits": {"max_branches": -1, "max_members": -1, "max_staff": -1, "monthly_message_credits": 1000},
        "features": _PREMIUM,
    },
]

# Message credit cost per channel (Manima resells credits => recurring income)
CHANNEL_CREDIT_COST = {"email": 0, "in_app": 0, "sms": 1, "whatsapp": 1}
CREDIT_PACKS = {"500": 299, "2000": 999, "5000": 2199}  # credits: price INR
