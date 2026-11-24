"use client";
import { useState } from "react";
import { CheckCircle2, LogOut, Search } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Badge, Button, Card, Empty, ErrorBox, Input, Spinner, Table, Td, useLoad, useSubmit } from "@/components/ui";
import { api, fmtTime } from "@/lib/api";
import { useSession } from "@/lib/session";

type Row = { id: number; member_name: string | null; member_code: string | null; staff_name: string | null; check_in_at: string; check_out_at: string | null; method: string };

export default function Attendance() {
  const { has, org } = useSession();
  const today = new Date().toISOString().slice(0, 10);
  const [day, setDay] = useState(today);
  const list = useLoad(() => api("/attendance", { params: { day } }), [day]);
  const [q, setQ] = useState("");
  const found = useLoad(() => (q.length >= 2 ? api("/members", { params: { q, size: 6 } }) : Promise.resolve(null)), [q]);
  const [ok, setOk] = useState<string | null>(null);
  const { error, run } = useSubmit();

  const checkin = (id: number, force = false) => run(async () => {
    const r = await api("/attendance/checkin", { body: { member_id: id, force } });
    setOk(`${r.member.name} checked in${r.duplicate ? " (already in)" : ""}${r.subscription ? ` • ${r.subscription.days_left} days left` : ""}`);
    setQ(""); list.reload();
  });
  const canForce = org && ["owner", "manager", "front_desk"].includes(org.role);

  return (
    <>
      <PageHeader title="Check-ins" subtitle="Members scan the branch QR — or check them in here"
        action={has("staff_attendance") && <Button variant="secondary" onClick={() => api("/attendance/staff/checkin", { method: "POST" }).then(list.reload)}>My staff check-in/out</Button>} />
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Quick check-in">
          <div className="relative">
            <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input aria-label="Find member" autoFocus placeholder="Name, phone or ID" className="pl-9" value={q} onChange={(e) => { setQ(e.target.value); setOk(null); }} />
          </div>
          <ul className="mt-3 divide-y divide-slate-100">
            {found.data?.items.map((m: { id: number; full_name: string; member_code: string; subscription: { days_left: number } | null }) => (
              <li key={m.id} className="flex items-center justify-between py-2">
                <div><div className="text-sm font-medium">{m.full_name}</div><div className="text-xs text-slate-500">{m.member_code}</div></div>
                <Button size="sm" onClick={() => checkin(m.id)}>Check in</Button>
              </li>
            ))}
          </ul>
          {ok && <div className="mt-3 flex items-center gap-2 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-700"><CheckCircle2 className="h-4 w-4" />{ok}</div>}
          <div className="mt-3"><ErrorBox error={error} /></div>
          {!!error && canForce && (error as { code?: string }).code === "membership_expired" && (
            <p className="mt-2 text-xs text-slate-500">Membership expired. Renew it from the member&apos;s page before letting them in.</p>
          )}
        </Card>
        <Card title={`Visits (${list.data?.length ?? 0})`} className="lg:col-span-2"
          action={<Input type="date" value={day} max={today} onChange={(e) => setDay(e.target.value)} className="w-40" aria-label="Day" />}>
          {list.loading && !list.data ? <Spinner /> : list.data?.length ? (
            <Table head={["Who", "In", "Out", "Via"]}>
              {list.data.map((a: Row) => (
                <tr key={a.id}>
                  <Td><div className="font-medium">{a.member_name ?? a.staff_name}</div><div className="text-xs text-slate-500">{a.member_code ?? "Staff"}</div></Td>
                  <Td>{fmtTime(a.check_in_at)}</Td>
                  <Td>{a.check_out_at ? fmtTime(a.check_out_at) : (
                    <Button size="sm" variant="ghost" onClick={() => api(`/attendance/${a.id}/checkout`, { method: "POST" }).then(list.reload)}><LogOut className="h-3.5 w-3.5" />Out</Button>)}</Td>
                  <Td><Badge tone={a.method.startsWith("qr") ? "green" : "slate"}>{a.method.replace("_", " ")}</Badge></Td>
                </tr>
              ))}
            </Table>
          ) : <Empty>No check-ins on this day.</Empty>}
        </Card>
      </div>
    </>
  );
}
