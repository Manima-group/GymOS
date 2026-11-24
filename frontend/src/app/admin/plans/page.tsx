"use client";
import { useState } from "react";
import { PageHeader } from "@/components/shell";
import { Button, Card, ErrorBox, Field, Input, Spinner, useLoad, useSubmit } from "@/components/ui";
import { api } from "@/lib/api";

type P = { id: number; code: string; name: string; price_monthly: number; price_yearly: number; limits: Record<string, number>; features: string[] };
type F = { key: string; name: string; category: string };

export default function AdminPlans() {
  const plans = useLoad(() => api("/platform/plans", { org: false }));
  const feats = useLoad(() => api("/platform/features", { org: false }));
  if (!plans.data || !feats.data) return <Spinner />;
  return (
    <>
      <PageHeader title="Plans & pricing" subtitle="Changes apply instantly to every gym on the plan" />
      <div className="grid gap-6 lg:grid-cols-3">
        {plans.data.map((p: P) => <PlanCard key={p.id} plan={p} features={feats.data} onSaved={plans.reload} />)}
      </div>
    </>
  );
}

function PlanCard({ plan, features, onSaved }: { plan: P; features: F[]; onSaved: () => void }) {
  const [p, setP] = useState(plan);
  const { busy, error, run } = useSubmit();
  const toggle = (k: string) => setP({ ...p, features: p.features.includes(k) ? p.features.filter((x) => x !== k) : [...p.features, k] });
  return (
    <Card title={`${p.name} (${p.code})`}>
      <div className="grid grid-cols-2 gap-3">
        <Field label="₹ / month"><Input type="number" value={p.price_monthly} onChange={(e) => setP({ ...p, price_monthly: Number(e.target.value) })} /></Field>
        <Field label="₹ / year"><Input type="number" value={p.price_yearly} onChange={(e) => setP({ ...p, price_yearly: Number(e.target.value) })} /></Field>
        {Object.entries(p.limits).map(([k, v]) => (
          <Field key={k} label={k.replaceAll("_", " ")} hint="-1 = unlimited">
            <Input type="number" value={v} onChange={(e) => setP({ ...p, limits: { ...p.limits, [k]: Number(e.target.value) } })} />
          </Field>
        ))}
      </div>
      <div className="mt-4 space-y-1.5">
        {features.map((f) => (
          <label key={f.key} className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={p.features.includes(f.key)} onChange={() => toggle(f.key)} />{f.name}
          </label>
        ))}
      </div>
      <div className="mt-4 space-y-2">
        <ErrorBox error={error} />
        <Button className="w-full" loading={busy} onClick={() => run(async () => {
          await api(`/platform/plans/${p.id}`, { org: false, method: "PATCH", body: { price_monthly: p.price_monthly, price_yearly: p.price_yearly, limits: p.limits, features: p.features } });
          onSaved();
        })}>Save {p.name}</Button>
      </div>
    </Card>
  );
}
