"use client";
import { useEffect, useState } from "react";
import { PageHeader } from "@/components/shell";
import { Badge, Button, Card, ErrorBox, Field, Input, Table, Td, useLoad, useSubmit } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";
import { useSession } from "@/lib/session";

export default function Settings() {
  const { org, has, reload } = useSession();
  const dash = useLoad(() => api("/dashboard").catch(() => null));
  const notes = useLoad(() => api("/notifications", { params: { limit: 30 } }).catch(() => []));
  const [f, setF] = useState({ name: org?.name ?? "", gstin: "", tax_percent: "0", primary_color: "#0F172A", logo_url: "" });
  const [saved, setSaved] = useState(false);
  const { busy, error, run } = useSubmit();
  const current = useLoad(() => api("/settings"));
  useEffect(() => {
    const c = current.data;
    if (c) setF({ name: c.name, gstin: c.gstin ?? "", tax_percent: String(c.tax_percent ?? 0),
      primary_color: c.branding?.primary_color ?? "#0F172A", logo_url: c.branding?.logo_url ?? "" });
  }, [current.data]);

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await api("/settings", { method: "PATCH", body: {
        name: f.name, gstin: f.gstin || null, tax_percent: Number(f.tax_percent),
        ...(has("white_label") ? { branding: { primary_color: f.primary_color, logo_url: f.logo_url } } : {}),
      } });
      setSaved(true); reload();
    });
  };
  const plan = dash.data?.plan;

  return (
    <>
      <PageHeader title="Settings" />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card title="Gym details">
          <form onSubmit={save} className="space-y-4">
            <Field label="Gym name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="GSTIN (optional)"><Input value={f.gstin} onChange={(e) => setF({ ...f, gstin: e.target.value })} /></Field>
              <Field label="GST % (inclusive)"><Input type="number" min={0} max={28} value={f.tax_percent} onChange={(e) => setF({ ...f, tax_percent: e.target.value })} /></Field>
            </div>
            {has("white_label") && (
              <div className="grid grid-cols-2 gap-4">
                <Field label="Brand colour"><Input type="color" value={f.primary_color} onChange={(e) => setF({ ...f, primary_color: e.target.value })} /></Field>
                <Field label="Logo URL"><Input value={f.logo_url} onChange={(e) => setF({ ...f, logo_url: e.target.value })} /></Field>
              </div>
            )}
            <ErrorBox error={error} />
            {saved && <p className="text-sm text-emerald-700">Saved.</p>}
            <Button loading={busy}>Save</Button>
          </form>
        </Card>
        <Card title="Your Gym-OS subscription">
          {plan && (
            <dl className="space-y-2 text-sm">
              <div className="flex justify-between"><dt className="text-slate-500">Plan</dt><dd><Badge tone="orange">{plan.code}</Badge></dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Status</dt><dd>{plan.status}</dd></div>
              {plan.trial_ends_at && plan.status === "trial" && <div className="flex justify-between"><dt className="text-slate-500">Trial ends</dt><dd>{fmtDate(plan.trial_ends_at)}</dd></div>}
              {plan.subscription_ends_at && <div className="flex justify-between"><dt className="text-slate-500">Renews on</dt><dd>{fmtDate(plan.subscription_ends_at)}</dd></div>}
              <div className="flex justify-between"><dt className="text-slate-500">Message credits</dt><dd>{plan.message_credits}</dd></div>
            </dl>
          )}
          <p className="mt-4 text-sm text-slate-500">To upgrade, renew or buy SMS/WhatsApp credits, contact Manima: business@manima.co.in</p>
        </Card>
        <Card title="Recent messages sent" className="lg:col-span-2">
          <Table head={["When", "Channel", "Type", "To", "Status"]}>
            {(notes.data ?? []).map((n: { id: number; created_at: string; channel: string; template: string; recipient: string; status: string }) => (
              <tr key={n.id}><Td>{fmtDate(n.created_at)}</Td><Td>{n.channel}</Td><Td>{n.template.replaceAll("_", " ")}</Td><Td>{n.recipient}</Td>
                <Td><Badge tone={n.status === "sent" ? "green" : n.status === "queued" ? "blue" : "red"}>{n.status}</Badge></Td></tr>
            ))}
          </Table>
        </Card>
      </div>
    </>
  );
}
