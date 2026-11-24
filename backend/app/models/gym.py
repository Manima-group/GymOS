"""Tenant-owned gym models. Every table carries org_id; branch-level tables also carry branch_id."""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, utcnow


class Branch(Base, TimestampMixin):
    __tablename__ = "branches"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    area: Mapped[str] = mapped_column(String(120))  # area tag shown on QR, e.g. "Kukatpally"
    code: Mapped[str] = mapped_column(String(16), unique=True, index=True)  # public QR code
    address: Mapped[str] = mapped_column(Text, default="")
    phone: Mapped[str | None] = mapped_column(String(20))
    latitude: Mapped[float | None] = mapped_column()
    longitude: Mapped[float | None] = mapped_column()
    geofence_meters: Mapped[int] = mapped_column(Integer, default=150)
    qr_secret: Mapped[str] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class MemberStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    lead = "lead"


class Member(Base, TimestampMixin):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("org_id", "phone", name="uq_member_org_phone"),
        UniqueConstraint("org_id", "member_code", name="uq_member_org_code"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    home_branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    member_code: Mapped[str] = mapped_column(String(20))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    email: Mapped[str | None] = mapped_column(String(160))
    gender: Mapped[str | None] = mapped_column(String(10))
    dob: Mapped[date | None] = mapped_column(Date)
    joined_on: Mapped[date] = mapped_column(Date, default=date.today)
    emergency_contact: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    all_branch_access: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[MemberStatus] = mapped_column(Enum(MemberStatus, name="member_status"), default=MemberStatus.active)


class MembershipPlan(Base, TimestampMixin):
    """A gym's own plan sold to members (e.g. 'Quarterly - ₹4,500')."""
    __tablename__ = "membership_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    duration_days: Mapped[int] = mapped_column(Integer)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    all_branch_access: Mapped[bool] = mapped_column(Boolean, default=False)
    max_freeze_days: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class SubscriptionStatus(str, enum.Enum):
    active = "active"
    frozen = "frozen"
    expired = "expired"
    cancelled = "cancelled"


class MemberSubscription(Base, TimestampMixin):
    __tablename__ = "member_subscriptions"
    __table_args__ = (Index("ix_sub_org_end", "org_id", "end_date"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("membership_plans.id"))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    discount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    status: Mapped[SubscriptionStatus] = mapped_column(
        Enum(SubscriptionStatus, name="subscription_status"), default=SubscriptionStatus.active
    )
    frozen_from: Mapped[date | None] = mapped_column(Date)
    freeze_days_used: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[MembershipPlan] = relationship(lazy="joined")

    @property
    def amount_due(self) -> Decimal:
        return max(Decimal(0), self.price - self.discount - self.amount_paid)


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    card = "card"
    bank = "bank"
    online = "online"


class Payment(Base, TimestampMixin):
    """Member -> gym payment. Each payment gets an org-sequential invoice number."""
    __tablename__ = "payments"
    __table_args__ = (UniqueConstraint("org_id", "invoice_no", name="uq_payment_invoice"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("member_subscriptions.id", ondelete="SET NULL"))
    invoice_no: Mapped[str] = mapped_column(String(30))
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))  # total collected, tax inclusive
    tax_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    method: Mapped[PaymentMethod] = mapped_column(Enum(PaymentMethod, name="payment_method"))
    reference: Mapped[str | None] = mapped_column(String(120))
    notes: Mapped[str] = mapped_column(Text, default="")
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (Index("ix_att_org_branch_time", "org_id", "branch_id", "check_in_at"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    staff_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    check_in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    check_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    method: Mapped[str] = mapped_column(String(20), default="qr")  # qr | qr_rotating | manual


class Lead(Base, TimestampMixin):
    __tablename__ = "leads"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    branch_id: Mapped[int] = mapped_column(ForeignKey("branches.id"))
    full_name: Mapped[str] = mapped_column(String(120))
    phone: Mapped[str] = mapped_column(String(20))
    interest: Mapped[str] = mapped_column(String(200), default="")
    source: Mapped[str] = mapped_column(String(30), default="qr")  # qr | walk_in | referral | ads
    status: Mapped[str] = mapped_column(String(20), default="new")  # new | contacted | trial | converted | lost
    follow_up_on: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")


class Notification(Base, TimestampMixin):
    """Outbox for reminders. A worker sends 'queued' rows; dedupe_key prevents duplicate reminders."""
    __tablename__ = "notifications"
    __table_args__ = (UniqueConstraint("dedupe_key", name="uq_notification_dedupe"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"))
    recipient: Mapped[str] = mapped_column(String(160))  # phone or email
    channel: Mapped[str] = mapped_column(String(20))  # email | sms | whatsapp | in_app
    template: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued|sent|failed|skipped
    error: Mapped[str] = mapped_column(Text, default="")
    dedupe_key: Mapped[str | None] = mapped_column(String(160))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
