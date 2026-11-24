"use client";
import { BarChart3, Building2, CalendarCheck, CreditCard, LayoutDashboard, ListChecks, Settings, UserPlus, Users, UsersRound } from "lucide-react";
import { Shell, type NavItem } from "@/components/shell";
import { Badge, Select, statusTone } from "@/components/ui";
import { ROLE_LABEL, SessionProvider, useSession } from "@/lib/session";

const NAV: NavItem[] = [
  { href: "/app", label: "Dashboard", icon: LayoutDashboard, roles: ["owner", "manager", "accountant"] },
  { href: "/app/members", label: "Members", icon: Users, feature: "members" },
  { href: "/app/attendance", label: "Check-ins", icon: CalendarCheck, feature: "attendance_qr" },
  { href: "/app/payments", label: "Payments", icon: CreditCard, feature: "payments", roles: ["owner", "manager", "accountant"] },
  { href: "/app/plans", label: "Membership plans", icon: ListChecks, feature: "memberships", roles: ["owner", "manager"] },
  { href: "/app/leads", label: "Leads", icon: UserPlus, feature: "crm", roles: ["owner", "manager", "front_desk"] },
  { href: "/app/branches", label: "Branches & QR", icon: Building2 },
  { href: "/app/staff", label: "Staff", icon: UsersRound, roles: ["owner", "manager"] },
  { href: "/app/reports", label: "Expiring", icon: BarChart3, roles: ["owner", "manager", "front_desk"] },
  { href: "/app/settings", label: "Settings", icon: Settings, roles: ["owner"] },
];

function OrgSwitcher() {
  const { me, org, switchOrg } = useSession();
  if (!org) return null;
  return (
    <div className="space-y-2 px-2">
      {me && me.staff_of.length > 1 && (
        <Select aria-label="Switch gym" value={org.org_id} onChange={(e) => { switchOrg(Number(e.target.value)); location.href = "/app"; }}
          className="border-white/10 bg-white/5 text-white">
          {me.staff_of.map((o) => <option key={o.org_id} value={o.org_id} className="text-slate-900">{o.name}</option>)}
        </Select>
      )}
      <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-300">
        <span className="font-medium text-white">{org.name}</span>
        <Badge tone="orange">{org.plan}</Badge>
        {org.status !== "active" && <Badge tone={statusTone(org.status)}>{org.status}</Badge>}
      </div>
      <div className="text-xs text-slate-400">{ROLE_LABEL[org.role]}</div>
    </div>
  );
}

function Inner({ children }: { children: React.ReactNode }) {
  return <Shell nav={NAV} title="Gym" extra={<OrgSwitcher />}>{children}</Shell>;
}

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return <SessionProvider require="staff"><Inner>{children}</Inner></SessionProvider>;
}
