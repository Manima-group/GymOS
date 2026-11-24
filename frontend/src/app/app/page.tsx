"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { AlertTriangle, CalendarCheck, IndianRupee, UserCheck, Users } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Card, ErrorBox, Select, Spinner, Stat, useLoad } from "@/components/ui";
import { api, fmtDate, inr } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function Dashboard() {
  const { org, has } = useSession();
  const router = useRouter();
  const [branch, setBranch] = useState<string>("");
  const branches = useLoad(() => api("/branches"), [org?.org_id]);
  const needsBranch = org?.type === "multi" && !has("multi_branch_dashboard") && !org.branch_id;
  useEffect(() => {
    if (org && !["owner", "manager", "accountant"].includes(org.role)) router.replace("/app/attendance");
    if (needsBranch && branches.data?.length && !branch) setBranch(String(branches.data[0].id));
  }, [org, router, needsBranch, branches.data, branch]);
  const d = useLoad(() => (needsBranch && !branch ? Promise.resolve(null) : api("/dashboard", { params: { branch_id: branch } })),
    [org?.org_id, branch]);

  const x = d.data;
  const maxRev = Math.max(1, ...(x?.revenue_30d ?? []).map((r: { amount: number }) => Number(r.amount)));
  const maxHour = Math.max(1, ...(x?.peak_hours_30d ?? []).map((r: { count: number }) => r.count));

  return (
    <>
      <PageHeader title={`Welcome back`} subtitle={org?.name}
        action={(branches.data?.length ?? 0) > 1 && (
          <Select aria-label="Branch" value={branch} onChange={(e) => setBranch(e.target.value)} className="w-56">
            {!needsBranch && <option value="">All branches</option>}
            {branches.data?.map((b: { id: number; name: string; area: string }) => <option key={b.id} value={b.id}>{b.name} • {b.area}</option>)}
          </Select>
        )} />
      {x?.plan?.status === "trial" && (
        <div className="mb-5 rounded-xl bg-blue-50 p-4 text-sm text-blue-800">
          Free trial ends on <b>{fmtDate(x.plan.trial_ends_at)}</b>. To continue without interruption, contact Manima at business@manima.co.in.
        </div>
      )}
      <ErrorBox error={d.error} />
      {d.loading && !x ? <Spinner /> : x && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="Active members" value={x.members_active} hint={`${x.members_total} total • ${x.new_members_this_month} new this month`} icon={<UserCheck className="h-4 w-4" />} />
            <Stat label="Check-ins today" value={x.checkins_today} icon={<CalendarCheck className="h-4 w-4" />} />
            <Stat label="Collected this month" value={inr(x.revenue_month)} hint={`${inr(x.revenue_today)} today`} icon={<IndianRupee className="h-4 w-4" />} />
            <Stat label="Pending dues" value={inr(x.dues_pending)} icon={<AlertTriangle className="h-4 w-4" />} />
          </div>
          <div className="grid gap-6 lg:grid-cols-3">
            <Card title="Collections — last 30 days" className="lg:col-span-2">
              {x.revenue_30d.length ? (
                <div className="flex h-40 items-end gap-1" role="img" aria-label="Daily collections bar chart">
                  {Array.from({ length: 30 }, (_, i) => {
                    const d = new Date(); d.setDate(d.getDate() - 29 + i);
                    const key = d.toLocaleDateString("en-CA");
                    const amt = Number(x.revenue_30d.find((r: { date: string }) => r.date === key)?.amount ?? 0);
                    return <div key={key} title={`${fmtDate(key)}: ${inr(amt)}`}
                      className={amt ? "flex-1 rounded-t bg-brand-500 hover:bg-brand-600" : "flex-1 rounded-t bg-slate-100"}
                      style={{ height: amt ? `${(amt / maxRev) * 100}%` : 4 }} />;
                  })}
                </div>
              ) : <p className="text-sm text-slate-500">No payments yet.</p>}
            </Card>
            <Card title="Needs attention">
              <ul className="space-y-3 text-sm">
                <li className="flex justify-between"><span>Expiring in 7 days</span><Link href="/app/reports" className="font-semibold text-brand-600">{x.expiring_7d}</Link></li>
                {x.open_leads !== null && <li className="flex justify-between"><span>Open leads</span><Link href="/app/leads" className="font-semibold text-brand-600">{x.open_leads}</Link></li>}
                <li className="flex justify-between"><span>Message credits</span><span className="font-semibold">{x.plan.message_credits}</span></li>
                {Object.entries(x.plan.limits as Record<string, number>).filter(([k]) => k.startsWith("max_")).map(([k, v]) => (
                  <li key={k} className="flex justify-between text-slate-600">
                    <span className="capitalize">{k.replace("max_", "")}</span>
                    <span>{x.plan.usage[k] ?? 0} / {v < 0 ? "∞" : v}</span>
                  </li>
                ))}
              </ul>
            </Card>
          </div>
          <Card title="Busiest hours (last 30 days)">
            {x.peak_hours_30d.length ? (
              <div className="flex h-28 items-end gap-1">
                {Array.from({ length: 24 }, (_, h) => {
                  const c = x.peak_hours_30d.find((p: { hour: number }) => p.hour === h)?.count ?? 0;
                  return (
                    <div key={h} className="flex flex-1 flex-col items-center gap-1">
                      <div title={`${h}:00 — ${c} check-ins`} className="w-full rounded-t bg-slate-800" style={{ height: `${(c / maxHour) * 80}px` }} />
                      <span className="text-[10px] text-slate-400">{h % 3 === 0 ? h : ""}</span>
                    </div>
                  );
                })}
              </div>
            ) : <p className="flex items-center gap-2 text-sm text-slate-500"><Users className="h-4 w-4" />Check-in data will appear here.</p>}
          </Card>
        </div>
      )}
    </>
  );
}
