"use client";
import { Building2, Gauge, Layers, ScrollText, ToggleRight } from "lucide-react";
import { Shell, type NavItem } from "@/components/shell";
import { SessionProvider } from "@/lib/session";

const NAV: NavItem[] = [
  { href: "/admin", label: "Overview", icon: Gauge },
  { href: "/admin/tenants", label: "Gyms (tenants)", icon: Building2 },
  { href: "/admin/plans", label: "Plans & pricing", icon: Layers },
  { href: "/admin/features", label: "Feature switches", icon: ToggleRight },
  { href: "/admin/audit", label: "Audit log", icon: ScrollText },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return <SessionProvider require="admin"><Shell nav={NAV} title="Manima Super Admin">{children}</Shell></SessionProvider>;
}
