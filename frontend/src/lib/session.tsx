"use client";
import { useRouter } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, api, auth } from "./api";

export type StaffOrg = {
  org_id: number; name: string; type: "single" | "multi"; status: string; plan: string;
  role: "owner" | "manager" | "front_desk" | "trainer" | "accountant"; branch_id: number | null; features: string[];
  impersonating?: boolean;
};
export type Me = {
  id: number; full_name: string; email: string | null; phone: string | null; is_platform_admin: boolean;
  staff_of: StaffOrg[]; member_of: { member_id: number; org_id: number; org_name: string }[];
};

type Ctx = { me: Me | null; org: StaffOrg | null; has: (f: string) => boolean; switchOrg: (id: number) => void; logout: () => void; reload: () => Promise<void> };
const SessionCtx = createContext<Ctx | null>(null);

export function SessionProvider({ children, require: need }: { children: ReactNode; require: "staff" | "admin" | "any" }) {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [org, setOrg] = useState<StaffOrg | null>(null);
  const [blocked, setBlocked] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!auth.token) { router.replace("/login"); return; }
    try {
      const m = await api<Me>("/auth/me", { org: false });
      if (need === "admin" && !m.is_platform_admin) { router.replace("/app"); return; }
      if (need === "staff" && !m.staff_of.length && !auth.orgId) {
        router.replace(m.is_platform_admin ? "/admin" : "/me"); return;
      }
      if (need === "staff") {
        const saved = Number(auth.orgId);
        const id = m.staff_of.find((o) => o.org_id === saved)?.org_id ?? (m.is_platform_admin && saved ? saved : m.staff_of[0]?.org_id);
        auth.setOrg(id);
        try {
          setOrg(await api<StaffOrg>("/context"));
        } catch (e) {
          if (e instanceof ApiError && e.status === 402) setBlocked(e.message); else throw e;
        }
      }
      setMe(m);
    } catch {
      auth.clear();
      router.replace("/login");
    }
  }, [need, router]);

  useEffect(() => { reload(); }, [reload]);

  const value: Ctx = {
    me, org, reload,
    has: (f) => !!org?.features.includes(f),
    switchOrg: (id) => { auth.setOrg(id); },
    logout: () => { auth.clear(); router.replace("/login"); },
  };
  if (blocked) return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 p-6 text-center">
      <h1 className="text-xl font-semibold">Your Gym-OS access is paused</h1>
      <p className="max-w-md text-slate-600">{blocked} Contact Manima at business@manima.co.in to renew — your data is safe.</p>
      <button className="text-sm text-brand-600" onClick={value.logout}>Log out</button>
    </div>
  );
  if (!me) return <div className="flex h-screen items-center justify-center text-slate-400">Loading…</div>;
  return <SessionCtx.Provider value={value}>{children}</SessionCtx.Provider>;
}

export function useSession() {
  const c = useContext(SessionCtx);
  if (!c) throw new Error("useSession outside SessionProvider");
  return c;
}

export const ROLE_LABEL: Record<string, string> = {
  owner: "Owner", manager: "Branch manager", front_desk: "Front desk", trainer: "Trainer", accountant: "Accountant",
};
