"""Platform-level (Manima) models: plans, features, tenants, SaaS billing, audit."""
import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, TimestampMixin, utcnow


class OrgType(str, enum.Enum):
    single = "single"
    multi = "multi"


class OrgStatus(str, enum.Enum):
    trial = "trial"
    active = "active"
    past_due = "past_due"  # in grace period
    suspended = "suspended"
    cancelled = "cancelled"


class Feature(Base):
    __tablename__ = "features"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(40), default="core")
    description: Mapped[str] = mapped_column(Text, default="")
    is_globally_enabled: Mapped[bool] = mapped_column(Boolean, default=True)  # kill switch


class Plan(Base, TimestampMixin):
    __tablename__ = "plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    price_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    price_yearly: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    # e.g. {"max_branches": 1, "max_members": 300, "max_staff": 5, "monthly_message_credits": 0}
    limits: Mapped[dict] = mapped_column(JSON, default=dict)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    features: Mapped[list["PlanFeature"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class PlanFeature(Base):
    __tablename__ = "plan_features"
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), primary_key=True)
    feature_key: Mapped[str] = mapped_column(ForeignKey("features.key", ondelete="CASCADE"), primary_key=True)


class Organization(Base, TimestampMixin):
    """A tenant. A single gym is an organization with exactly one branch."""
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    type: Mapped[OrgType] = mapped_column(Enum(OrgType, name="org_type"), default=OrgType.single)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    billing_cycle: Mapped[str] = mapped_column(String(10), default="monthly")  # monthly | yearly
    status: Mapped[OrgStatus] = mapped_column(Enum(OrgStatus, name="org_status"), default=OrgStatus.trial)
    trial_ends_at: Mapped[date | None] = mapped_column(Date)
    subscription_ends_at: Mapped[date | None] = mapped_column(Date)
    email: Mapped[str | None] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(20))
    gstin: Mapped[str | None] = mapped_column(String(20))
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)
    limit_overrides: Mapped[dict] = mapped_column(JSON, default=dict)
    branding: Mapped[dict] = mapped_column(JSON, default=dict)  # logo_url, primary_color (white-label)
    message_credits: Mapped[int] = mapped_column(Integer, default=0)
    invoice_seq: Mapped[int] = mapped_column(Integer, default=0)
    member_seq: Mapped[int] = mapped_column(Integer, default=0)

    plan: Mapped[Plan] = relationship(lazy="joined")
    feature_overrides: Mapped[list["OrgFeatureOverride"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class OrgFeatureOverride(Base):
    __tablename__ = "org_feature_overrides"
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), primary_key=True)
    feature_key: Mapped[str] = mapped_column(ForeignKey("features.key", ondelete="CASCADE"), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean)
    note: Mapped[str] = mapped_column(String(200), default="")


class SaasInvoice(Base, TimestampMixin):
    """Manima -> gym subscription invoices (the recurring revenue)."""
    __tablename__ = "saas_invoices"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    plan_id: Mapped[int] = mapped_column(ForeignKey("plans.id"))
    kind: Mapped[str] = mapped_column(String(20), default="subscription")  # subscription | credits
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    period_start: Mapped[date | None] = mapped_column(Date)
    period_end: Mapped[date | None] = mapped_column(Date)
    credits: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default="paid")  # due | paid | void
    method: Mapped[str] = mapped_column(String(20), default="manual")
    reference: Mapped[str | None] = mapped_column(String(120))
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    org_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    action: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(60), default="")
    entity_id: Mapped[str] = mapped_column(String(60), default="")
    data: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


__all__ = [
    "OrgType", "OrgStatus", "Feature", "Plan", "PlanFeature", "Organization",
    "OrgFeatureOverride", "SaasInvoice", "AuditLog",
]
