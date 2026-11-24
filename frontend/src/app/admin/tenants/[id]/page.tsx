"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { LogIn } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Badge, Button, Card, ErrorBox, Field, Input, Select, Spinner, Table, Td, cx, statusTone, useLoad, useSubmit } from "@/components/ui";
import { api, auth, fmtDate, inr } from "@/lib/api";

type F = { key: string; name: string; category: string; is_globally_enabled: boolean };

export default function TenantDetail() {
  const { id } = useParams<{ id: string }>();
  const t = useLoad(() => api(`/platform/tenants/${id}`, { org: false }), [id]);
  const features = useLoad(() => api("/platform/features", { org: false }));
  const plans = useLoad(() => api("/platform/plans", { org: false }));
  const act = useSubmit();
  const [periods, setPeriods] = useState("1");
  const [credits, setCredits] = useState({ credits: "500", amount: "299" });

  if (t.loading && !t.data) return <Spinner />;
  if (t.error) return <ErrorBox error={t.error} />;
  const x = t.data;
  const enabled = new Set<string>(x.features_enabled);
  const inPlan = new Set<string>(x.plan_features);
  const override = Object.fromEntries(x.overrides.map((o: { feature: string; enabled: boolean }) => [o.feature, o.enabled]));
  const patch = (body: object) => act.run(async () => { await api(`/platform/tenants/${id}`, { org: false, method: "PATCH", body }); t.reload(); });
  const toggle = (key: string, on: boolean) => act.run(async () => {
    const back = on === inPlan.has(key);  // matches plan default => remove override
    await api(`/platform/tenants/${id}/features/${key}`, { org: false, method: back ? "DELETE" : "PUT", body: back ? undefined : { enabled: on } });
    t.reload();
  });
  const support = () => { auth.setOrg(x.id); window.location.href = "/app"; };

  return (
    <>
      <PageHeader title={x.name} subtitle={`${x.email ?? ""} • ${x.phone ?? ""} • since ${fmtDate(x.created_at)}`}
        action={<Button variant="secondary" onClick={support}><LogIn className="h-4 w-4" />Open as support</Button>} />
      <div className="mb-4"><ErrorBox error={act.error} /></div>
      <div className="grid gap-6 lg:grid-cols-3">
        <Card title="Subscription">
          <div className="space-y-4 text-sm">
            <Field label="Plan">
              <Select value={x.plan} onChange={(e) => patch({ plan_code: e.target.value })}>
                {plans.data?.map((p: { code: string; name: string; price_monthly: number }) => <option key={p.code} value={p.code}>{p.name} — {inr(p.price_monthly)}/mo</option>)}
              </Select>
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Billing"><Select value={x.billing_cycle} onChange={(e) => patch({ billing_cycle: e.target.value })}><option value="monthly">Monthly</option><option value="yearly">Yearly</option></Select></Field>
              <Field label="Status"><Select value={x.status} onChange={(e) => patch({ status: e.target.value })}>{["trial", "active", "past_due", "suspended", "cancelled"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
            </div>
            <div className="flex justify-between"><span className="text-slate-500">Trial ends</span>{fmtDate(x.trial_ends_at)}</div>
            <div className="flex justify-between"><span className="text-slate-500">Paid until</span>{fmtDate(x.subscription_ends_at)}</div>
            <div className="flex items-end gap-2 border-t border-slate-100 pt-4">
              <Field label={x.billing_cycle === "yearly" ? "Years paid" : "Months paid"}><Input type="number" min={1} value={periods} onChange={(e) => setPeriods(e.target.value)} /></Field>
              <Button loading={act.busy} onClick={() => act.run(async () => { await api(`/platform/tenants/${id}/payments`, { org: false, body: { periods: Number(periods) } }); t.reload(); })}>Record payment</Button>
            </div>
          </div>
        </Card>
        <Card title="Usage & limits">
          <ul className="space-y-2 text-sm">
            {Object.entries(x.limits as Record<string, number>).map(([k, v]) => (
              <li key={k} className="flex justify-between"><span className="capitalize text-slate-500">{k.replaceAll("_", " ").replace("max ", "")}</span>
                <span>{k in x.usage ? `${x.usage[k]} / ` : ""}{v < 0 ? "∞" : v}</span></li>
            ))}
            <li className="flex justify-between border-t border-slate-100 pt-2"><span className="text-slate-500">Message credits</span><b>{x.message_credits}</b></li>
          </ul>
          <div className="mt-4 flex items-end gap-2">
            <Field label="Credits"><Input type="number" value={credits.credits} onChange={(e) => setCredits({ ...credits, credits: e.target.value })} /></Field>
            <Field label="₹ received"><Input type="number" value={credits.amount} onChange={(e) => setCredits({ ...credits, amount: e.target.value })} /></Field>
            <Button variant="secondary" onClick={() => act.run(async () => { await api(`/platform/tenants/${id}/credits`, { org: false, body: { credits: Number(credits.credits), amount: Number(credits.amount) } }); t.reload(); })}>Add</Button>
          </div>
          <div className="mt-4 flex gap-2">
            <Button size="sm" variant="ghost" onClick={() => {
              const v = prompt("Member limit override (-1 = unlimited, blank = plan default)");
              if (v !== null) patch({ limit_overrides: v === "" ? {} : { ...x.limit_overrides, max_members: Number(v) } });
            }}>Override member limit</Button>
          </div>
        </Card>
        <Card title="Invoices (Manima)">
          {x.invoices.length ? (
            <ul className="space-y-2 text-sm">{x.invoices.map((i: { id: number; kind: string; amount: number; paid_at: string; period_end: string | null; credits: number }) => (
              <li key={i.id} className="flex justify-between"><span>{fmtDate(i.paid_at)} • {i.kind === "credits" ? `${i.credits} credits` : `to ${fmtDate(i.period_end)}`}</span><b>{inr(i.amount)}</b></li>
            ))}</ul>
          ) : <p className="text-sm text-slate-500">No payments yet.</p>}
        </Card>
        <Card title="Features for this gym" className="lg:col-span-3">
          <p className="mb-4 text-sm text-slate-500">Switch any feature on or off for this client. Changes that differ from the plan are marked <Badge tone="orange">override</Badge>.</p>
          <Table head={["Feature", "Category", "In plan", "Enabled"]}>
            {features.data?.map((f: F) => {
              const on = enabled.has(f.key);
              return (
                <tr key={f.key}>
                  <Td>{f.name} {f.key in override && <Badge tone="orange">override</Badge>} {!f.is_globally_enabled && <Badge tone="red">globally off</Badge>}</Td>
                  <Td className="capitalize text-slate-500">{f.category}</Td>
                  <Td>{inPlan.has(f.key) ? "Yes" : "—"}</Td>
                  <Td>
                    <button role="switch" aria-checked={on} aria-label={`Toggle ${f.name}`} disabled={act.busy} onClick={() => toggle(f.key, !on)}
                      className={cx("relative h-6 w-11 rounded-full transition", on ? "bg-emerald-500" : "bg-slate-300")}>
                      <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition", on ? "left-5" : "left-0.5")} />
                    </button>
                  </Td>
                </tr>
              );
            })}
          </Table>
        </Card>
      </div>
      <p className="mt-6 text-xs text-slate-400">Status: <Badge tone={statusTone(x.status)}>{x.status}</Badge> • All admin actions are recorded in the audit log.</p>
    </>
  );
}
