"use client";
import { useEffect, useState } from "react";
import { CalendarCheck, Dumbbell, LogOut, QrCode } from "lucide-react";
import { OtpLogin } from "@/components/otp-login";
import { Badge, Card, Spinner, useLoad } from "@/components/ui";
import { api, auth, fmtDate, inr } from "@/lib/api";

type Gym = { member_id: number; member_code: string; gym: string; home_branch: { name: string; area: string; code: string };
  subscription: { plan_name: string; end_date: string; days_left: number; amount_due: number; status: string } | null;
  payments: { invoice_no: string; amount: number; paid_at: string }[]; recent_visits: string[] };

export default function MemberHome() {
  const [authed, setAuthed] = useState<boolean | null>(null);
  useEffect(() => setAuthed(!!auth.token), []);
  const gyms = useLoad<Gym[]>(() => (authed ? api("/me/gyms", { org: false }) : Promise.resolve([])), [authed]);

  if (authed === null) return <Spinner />;
  return (
    <div className="mx-auto min-h-screen max-w-md p-4">
      <header className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-2 font-bold"><span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500 text-white"><Dumbbell className="h-5 w-5" /></span>My gym</div>
        {authed && <button aria-label="Log out" onClick={() => { auth.clear(); setAuthed(false); }}><LogOut className="h-5 w-5 text-slate-500" /></button>}
      </header>
      {!authed ? (
        <Card title="Log in"><OtpLogin onDone={() => setAuthed(true)} /></Card>
      ) : gyms.loading ? <Spinner /> : !gyms.data?.length ? (
        <Card><p className="text-sm text-slate-600">No gym membership is linked to this number yet. Ask your gym to register your mobile number.</p></Card>
      ) : gyms.data.map((g) => {
        const s = g.subscription;
        const visitsThisMonth = g.recent_visits.filter((v) => new Date(v).getMonth() === new Date().getMonth()).length;
        return (
          <div key={g.member_id} className="mb-6 space-y-4">
            <div className="rounded-2xl bg-ink p-5 text-white shadow-lg">
              <div className="text-sm opacity-70">{g.home_branch.name} • {g.home_branch.area}</div>
              <div className="text-xl font-bold">{g.gym}</div>
              <div className="mt-4 flex items-end justify-between">
                <div>
                  <div className="text-xs opacity-70">Member ID</div><div className="font-mono">{g.member_code}</div>
                </div>
                {s ? <Badge tone={s.days_left < 0 ? "red" : s.days_left <= 7 ? "amber" : "green"}>{s.status === "frozen" ? "Frozen" : s.days_left < 0 ? "Expired" : `${s.days_left} days left`}</Badge> : <Badge>No plan</Badge>}
              </div>
              {s && <div className="mt-3 text-sm opacity-90">{s.plan_name} • valid till {fmtDate(s.end_date)}</div>}
              {s && s.amount_due > 0 && <div className="mt-2 text-sm text-amber-300">Pending: {inr(s.amount_due)}</div>}
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Card className="p-4"><CalendarCheck className="h-5 w-5 text-brand-500" /><div className="mt-2 text-2xl font-bold">{visitsThisMonth}</div><div className="text-xs text-slate-500">visits this month</div></Card>
              <a href={`/c/${g.home_branch.code}`} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"><QrCode className="h-5 w-5 text-brand-500" /><div className="mt-2 font-semibold">Check in</div><div className="text-xs text-slate-500">or scan the poster QR</div></a>
            </div>
            <Card title="Payments">
              {g.payments.length ? <ul className="space-y-2 text-sm">{g.payments.map((p) => (
                <li key={p.invoice_no} className="flex justify-between"><span>{fmtDate(p.paid_at)} <span className="text-xs text-slate-400">{p.invoice_no}</span></span><b>{inr(p.amount)}</b></li>
              ))}</ul> : <p className="text-sm text-slate-500">No payments yet.</p>}
            </Card>
          </div>
        );
      })}
    </div>
  );
}
