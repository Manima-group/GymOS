"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ComponentType, type ReactNode } from "react";
import { Dumbbell, Lock, LogOut, Menu, X } from "lucide-react";
import { cx } from "./ui";
import { useSession } from "@/lib/session";

export type NavItem = { href: string; label: string; icon: ComponentType<{ className?: string }>; feature?: string; roles?: string[] };

export function Shell({ nav, title, children, extra }: { nav: NavItem[]; title: string; children: ReactNode; extra?: ReactNode }) {
  const path = usePathname();
  const { me, org, has, logout } = useSession();
  const [open, setOpen] = useState(false);
  const visible = nav.filter((n) => !n.roles || (org && n.roles.includes(org.role)));

  const sidebar = (
    <nav className="flex h-full flex-col gap-1 p-4">
      <Link href="/" className="mb-6 flex items-center gap-2 px-2 text-lg font-bold text-white">
        <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500"><Dumbbell className="h-5 w-5" /></span>
        Gym-OS
      </Link>
      <div className="mb-3 px-2 text-xs uppercase tracking-wider text-slate-400">{title}</div>
      {visible.map((n) => {
        const locked = n.feature && !has(n.feature);
        const active = n.href === path || (n.href !== "/app" && n.href !== "/admin" && path.startsWith(n.href));
        return (
          <Link key={n.href} href={n.href} onClick={() => setOpen(false)}
            className={cx("flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
              active ? "bg-white/10 text-white" : "text-slate-300 hover:bg-white/5 hover:text-white")}>
            <n.icon className="h-4 w-4" />
            <span className="flex-1">{n.label}</span>
            {locked && <Lock className="h-3.5 w-3.5 text-slate-500" aria-label="Upgrade to unlock" />}
          </Link>
        );
      })}
      <div className="mt-auto space-y-3 border-t border-white/10 pt-4">
        {extra}
        <div className="px-2 text-sm">
          <div className="font-medium text-white">{me?.full_name}</div>
          <div className="text-xs text-slate-400">{me?.email ?? me?.phone}</div>
        </div>
        <button onClick={logout} className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-sm text-slate-300 hover:bg-white/5">
          <LogOut className="h-4 w-4" /> Log out
        </button>
        <div className="px-2 text-[11px] text-slate-500">Powered by Manima AI Tech Solutions</div>
      </div>
    </nav>
  );

  return (
    <div className="min-h-screen lg:pl-64">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 bg-ink lg:block">{sidebar}</aside>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/50" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-64 bg-ink">{sidebar}</aside>
        </div>
      )}
      <header className="sticky top-0 z-20 flex items-center gap-3 border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur lg:hidden">
        <button aria-label="Menu" onClick={() => setOpen(!open)}>{open ? <X /> : <Menu />}</button>
        <span className="font-semibold">{org?.name ?? "Gym-OS"}</span>
      </header>
      <main className="mx-auto max-w-6xl p-4 sm:p-6 lg:p-8">{children}</main>
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: string; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function Locked({ feature }: { feature: string }) {
  return (
    <div className="rounded-2xl border border-brand-100 bg-brand-50 p-8 text-center">
      <Lock className="mx-auto h-8 w-8 text-brand-600" />
      <h2 className="mt-3 font-semibold text-slate-900">This feature isn&apos;t on your plan yet</h2>
      <p className="mt-1 text-sm text-slate-600">Upgrade to unlock <b>{feature.replaceAll("_", " ")}</b>. Contact Manima at business@manima.co.in.</p>
    </div>
  );
}
