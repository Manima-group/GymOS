"use client";
import Link from "next/link";
import { Building2, IndianRupee, TrendingUp, Users } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Badge, Card, ErrorBox, Spinner, Stat, statusTone, useLoad } from "@/components/ui";
import { api, fmtDate, inr } from "@/lib/api";

export default function AdminHome() {
  const d = useLoad(() => api("/platform/dashboard", { org: false }));
  if (d.loading && !d.data) return <Spinner />;
  if (d.error) return <ErrorBox error={d.error} />;
  const x = d.data;
  return (
    <>
      <PageHeader title="Gym-OS business overview" subtitle="Recurring revenue across all gyms" />
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="MRR" value={inr(x.mrr)} hint={`ARR ${inr(x.arr)}`} icon={<TrendingUp className="h-4 w-4" />} />
        <Stat label="Collected this month" value={inr(x.collected_this_month)} icon={<IndianRupee className="h-4 w-4" />} />
        <Stat label="Gyms" value={x.tenants_total} hint={`${x.by_status.active} paying • ${x.by_status.trial} on trial`} icon={<Building2 className="h-4 w-4" />} />
        <Stat label="Members managed" value={x.members_total.toLocaleString("en-IN")} icon={<Users className="h-4 w-4" />} />
      </div>
      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card title="By status">
          <ul className="space-y-2 text-sm">{Object.entries(x.by_status).map(([k, v]) => (
            <li key={k} className="flex justify-between"><Badge tone={statusTone(k)}>{k}</Badge><b>{v as number}</b></li>))}</ul>
        </Card>
        <Card title="Trials ending in 7 days — convert them">
          {x.trials_ending_7d.length ? <ul className="space-y-2 text-sm">{x.trials_ending_7d.map((t: { id: number; name: string; trial_ends_at: string }) => (
            <li key={t.id} className="flex justify-between"><Link className="text-brand-600" href={`/admin/tenants/${t.id}`}>{t.name}</Link>{fmtDate(t.trial_ends_at)}</li>))}</ul>
            : <p className="text-sm text-slate-500">None.</p>}
        </Card>
        <Card title="Renewals due in 7 days">
          {x.renewals_due_7d.length ? <ul className="space-y-2 text-sm">{x.renewals_due_7d.map((t: { id: number; name: string; subscription_ends_at: string }) => (
            <li key={t.id} className="flex justify-between"><Link className="text-brand-600" href={`/admin/tenants/${t.id}`}>{t.name}</Link>{fmtDate(t.subscription_ends_at)}</li>))}</ul>
            : <p className="text-sm text-slate-500">None.</p>}
        </Card>
      </div>
    </>
  );
}
