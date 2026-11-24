"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CalendarCheck, Pause, Play, Plus, Receipt, Wallet } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, Select, Spinner, Table, Td, statusTone, useLoad, useSubmit } from "@/components/ui";
import { SubBadge, type Sub } from "@/components/members";
import { api, fmtDate, fmtTime, inr, openAuthed } from "@/lib/api";
import { useSession } from "@/lib/session";

const METHODS = ["cash", "upi", "card", "bank"];

export default function MemberDetail() {
  const { id } = useParams<{ id: string }>();
  const { has } = useSession();
  const m = useLoad(() => api(`/members/${id}`), [id]);
  const [subOpen, setSubOpen] = useState(false);
  const [payFor, setPayFor] = useState<Sub | null>(null);
  const act = useSubmit();

  if (m.loading && !m.data) return <Spinner />;
  if (m.error) return <ErrorBox error={m.error} />;
  const x = m.data;
  const cur: Sub | null = x.subscription;

  const action = (path: string) => act.run(async () => { await api(path, { method: "POST" }); m.reload(); });

  return (
    <>
      <PageHeader title={x.full_name} subtitle={`${x.member_code} • ${x.phone}${x.email ? " • " + x.email : ""}`}
        action={<div className="flex gap-2">
          <Button variant="secondary" onClick={() => act.run(async () => { await api("/attendance/checkin", { body: { member_id: x.id } }); m.reload(); })}>
            <CalendarCheck className="h-4 w-4" />Check in
          </Button>
          <Button onClick={() => setSubOpen(true)}><Plus className="h-4 w-4" />{cur ? "Renew" : "Add membership"}</Button>
        </div>} />
      <div className="mb-4"><ErrorBox error={act.error} /></div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Current membership" className="lg:col-span-2">
          {cur ? (
            <div className="space-y-4">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-lg font-semibold">{cur.plan_name}</span><SubBadge s={cur} />
              </div>
              <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
                <div><div className="text-slate-500">Start</div>{fmtDate(cur.start_date)}</div>
                <div><div className="text-slate-500">Ends</div>{fmtDate(cur.end_date)}</div>
                <div><div className="text-slate-500">Paid</div>{inr(cur.amount_paid)}</div>
                <div><div className="text-slate-500">Due</div><span className={cur.amount_due > 0 ? "font-semibold text-red-600" : ""}>{inr(cur.amount_due)}</span></div>
              </div>
              <div className="flex flex-wrap gap-2">
                {cur.amount_due > 0 && <Button size="sm" onClick={() => setPayFor(cur)}><Wallet className="h-4 w-4" />Collect {inr(cur.amount_due)}</Button>}
                {has("membership_freeze") && cur.status === "active" && <Button size="sm" variant="secondary" onClick={() => action(`/subscriptions/${cur.id}/freeze`)}><Pause className="h-4 w-4" />Freeze</Button>}
                {cur.status === "frozen" && <Button size="sm" variant="secondary" onClick={() => action(`/subscriptions/${cur.id}/unfreeze`)}><Play className="h-4 w-4" />Unfreeze</Button>}
              </div>
            </div>
          ) : <Empty>No active membership. Add one to allow check-ins.</Empty>}
        </Card>
        <Card title="Profile">
          <dl className="space-y-2 text-sm">
            {[["Joined", fmtDate(x.joined_on)], ["Gender", x.gender ?? "—"], ["Birthday", fmtDate(x.dob)],
              ["Emergency", x.emergency_contact ?? "—"], ["App login", x.has_app_login ? "Yes" : "Not yet"],
              ["All branches", x.all_branch_access ? "Yes" : "Home branch only"]].map(([k, v]) => (
              <div key={k} className="flex justify-between gap-4"><dt className="text-slate-500">{k}</dt><dd className="text-right">{v}</dd></div>
            ))}
          </dl>
        </Card>
        <Card title="Membership history" className="lg:col-span-2">
          {x.subscriptions.length ? (
            <Table head={["Plan", "Period", "Price", "Due", "Status", ""]}>
              {x.subscriptions.map((s: Sub) => (
                <tr key={s.id}>
                  <Td>{s.plan_name}</Td><Td>{fmtDate(s.start_date)} – {fmtDate(s.end_date)}</Td>
                  <Td>{inr(s.price - s.discount)}</Td><Td>{inr(s.amount_due)}</Td>
                  <Td><Badge tone={statusTone(s.status)}>{s.status}</Badge></Td>
                  <Td>{s.amount_due > 0 && s.status !== "cancelled" && <Button size="sm" variant="ghost" onClick={() => setPayFor(s)}>Collect</Button>}</Td>
                </tr>
              ))}
            </Table>
          ) : <Empty>No history yet.</Empty>}
        </Card>
        <Card title="Recent visits">
          {x.attendance.length ? (
            <ul className="space-y-2 text-sm">
              {x.attendance.slice(0, 10).map((a: { check_in_at: string; method: string }) => (
                <li key={a.check_in_at} className="flex justify-between"><span>{fmtDate(a.check_in_at)}</span><span className="text-slate-500">{fmtTime(a.check_in_at)}</span></li>
              ))}
            </ul>
          ) : <p className="text-sm text-slate-500">No visits yet.</p>}
        </Card>
        <Card title="Payments" className="lg:col-span-3">
          {x.payments.length ? (
            <Table head={["Invoice", "Date", "Method", "Amount", ""]}>
              {x.payments.map((p: { id: number; invoice_no: string; paid_at: string; method: string; amount: number }) => (
                <tr key={p.id}>
                  <Td>{p.invoice_no}</Td><Td>{fmtDate(p.paid_at)}</Td><Td className="uppercase">{p.method}</Td><Td>{inr(p.amount)}</Td>
                  <Td>{has("invoices") && <Button size="sm" variant="ghost" onClick={() => openAuthed(`/payments/${p.id}/receipt`)}><Receipt className="h-4 w-4" />Receipt</Button>}</Td>
                </tr>
              ))}
            </Table>
          ) : <Empty>No payments yet.</Empty>}
        </Card>
      </div>
      <SubscribeModal open={subOpen} memberId={x.id} onClose={() => setSubOpen(false)} onDone={() => { setSubOpen(false); m.reload(); }} />
      <PayModal sub={payFor} onClose={() => setPayFor(null)} onDone={() => { setPayFor(null); m.reload(); }} />
    </>
  );
}

function SubscribeModal({ open, memberId, onClose, onDone }: { open: boolean; memberId: number; onClose: () => void; onDone: () => void }) {
  const plans = useLoad(() => (open ? api("/membership-plans") : Promise.resolve([])), [open]);
  const [planId, setPlanId] = useState("");
  const [discount, setDiscount] = useState("0");
  const [paid, setPaid] = useState("");
  const [method, setMethod] = useState("cash");
  const [start, setStart] = useState("");
  const { busy, error, run } = useSubmit();
  const plan = plans.data?.find((p: { id: number }) => String(p.id) === planId);
  const total = plan ? Number(plan.price) - Number(discount || 0) : 0;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await api(`/members/${memberId}/subscriptions`, { body: {
        plan_id: Number(planId), discount: Number(discount || 0), start_date: start || undefined,
        payment: Number(paid) > 0 ? { amount: Number(paid), method } : undefined,
      } });
      onDone();
    });
  };
  return (
    <Modal open={open} onClose={onClose} title="Add / renew membership">
      {plans.data && !plans.data.length ? <Empty>Create a membership plan first (Membership plans menu).</Empty> : (
        <form onSubmit={submit} className="space-y-4">
          <Field label="Plan">
            <Select value={planId} onChange={(e) => { setPlanId(e.target.value); setPaid(""); }} required>
              <option value="">Select a plan</option>
              {plans.data?.map((p: { id: number; name: string; price: number; duration_days: number }) => (
                <option key={p.id} value={p.id}>{p.name} — {inr(p.price)} / {p.duration_days} days</option>
              ))}
            </Select>
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="Discount (₹)"><Input type="number" min={0} value={discount} onChange={(e) => setDiscount(e.target.value)} /></Field>
            <Field label="Start date" hint="Blank = today / after current ends"><Input type="date" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
            <Field label={`Amount paid now (of ${inr(total)})`}><Input type="number" min={0} max={total} value={paid} placeholder={String(total)} onChange={(e) => setPaid(e.target.value)} /></Field>
            <Field label="Method"><Select value={method} onChange={(e) => setMethod(e.target.value)}>{METHODS.map((x) => <option key={x} value={x}>{x.toUpperCase()}</option>)}</Select></Field>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="secondary" onClick={() => setPaid(String(total))} disabled={!plan}>Paid in full</Button>
          </div>
          <ErrorBox error={error} />
          <Button className="w-full" loading={busy}>Save</Button>
        </form>
      )}
    </Modal>
  );
}

function PayModal({ sub, onClose, onDone }: { sub: Sub | null; onClose: () => void; onDone: () => void }) {
  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState("cash");
  const [reference, setRef] = useState("");
  const { busy, error, run } = useSubmit();
  return (
    <Modal open={!!sub} onClose={onClose} title={`Collect payment${sub ? ` — due ${inr(sub.amount_due)}` : ""}`}>
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(async () => {
        await api(`/subscriptions/${sub!.id}/payments`, { body: { amount: Number(amount || sub!.amount_due), method, reference: reference || undefined } });
        setAmount(""); setRef(""); onDone();
      }); }}>
        <Field label="Amount (₹)"><Input type="number" min={1} max={sub?.amount_due} value={amount} placeholder={String(sub?.amount_due ?? "")} onChange={(e) => setAmount(e.target.value)} /></Field>
        <Field label="Method"><Select value={method} onChange={(e) => setMethod(e.target.value)}>{METHODS.map((x) => <option key={x} value={x}>{x.toUpperCase()}</option>)}</Select></Field>
        {method !== "cash" && <Field label="Reference / UTR (optional)"><Input value={reference} onChange={(e) => setRef(e.target.value)} /></Field>}
        <ErrorBox error={error} />
        <Button className="w-full" loading={busy}>Record payment</Button>
      </form>
    </Modal>
  );
}
