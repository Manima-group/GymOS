"use client";
import { useState } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, Spinner, useLoad, useSubmit } from "@/components/ui";
import { api, inr } from "@/lib/api";
import { useSession } from "@/lib/session";

type Plan = { id: number; name: string; duration_days: number; price: number; all_branch_access: boolean; max_freeze_days: number; is_active: boolean; description: string };
const PRESETS = [["Monthly", 30], ["Quarterly", 90], ["Half-yearly", 180], ["Yearly", 365]] as const;

export default function Plans() {
  const { has, org } = useSession();
  const list = useLoad(() => api("/membership-plans", { params: { include_inactive: true } }));
  const [edit, setEdit] = useState<Partial<Plan> | null>(null);
  const { busy, error, run } = useSubmit();

  const save = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const body = { name: edit!.name, duration_days: Number(edit!.duration_days), price: Number(edit!.price),
        all_branch_access: !!edit!.all_branch_access, max_freeze_days: Number(edit!.max_freeze_days || 0), description: edit!.description ?? "" };
      if (edit!.id) await api(`/membership-plans/${edit!.id}`, { method: "PATCH", body });
      else await api("/membership-plans", { body });
      setEdit(null); list.reload();
    });
  };
  const toggle = (p: Plan) => api(`/membership-plans/${p.id}`, { method: "PATCH", body: { is_active: !p.is_active } }).then(list.reload);

  return (
    <>
      <PageHeader title="Membership plans" subtitle="What you sell to your members"
        action={<Button onClick={() => setEdit({ duration_days: 30, max_freeze_days: 0 })}><Plus className="h-4 w-4" />New plan</Button>} />
      {list.loading && !list.data ? <Spinner /> : list.data?.length ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {list.data.map((p: Plan) => (
            <Card key={p.id} className={p.is_active ? "" : "opacity-60"}>
              <div className="flex items-start justify-between">
                <div><div className="font-semibold">{p.name}</div><div className="text-sm text-slate-500">{p.duration_days} days</div></div>
                {!p.is_active && <Badge>Hidden</Badge>}
              </div>
              <div className="my-3 text-2xl font-bold">{inr(p.price)}</div>
              <div className="flex flex-wrap gap-1.5 text-xs">
                {p.all_branch_access && <Badge tone="blue">All branches</Badge>}
                {p.max_freeze_days > 0 && <Badge tone="blue">{p.max_freeze_days}d freeze</Badge>}
              </div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="secondary" onClick={() => setEdit(p)}>Edit</Button>
                <Button size="sm" variant="ghost" onClick={() => toggle(p)}>{p.is_active ? "Hide" : "Show"}</Button>
              </div>
            </Card>
          ))}
        </div>
      ) : <Empty>No plans yet. Create Monthly / Quarterly / Yearly plans to start selling memberships.</Empty>}

      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.id ? "Edit plan" : "New plan"}>
        {edit && (
          <form onSubmit={save} className="space-y-4">
            {!edit.id && (
              <div className="flex flex-wrap gap-2">
                {PRESETS.map(([n, d]) => <Button key={n} type="button" size="sm" variant="secondary" onClick={() => setEdit({ ...edit, name: n, duration_days: d })}>{n}</Button>)}
              </div>
            )}
            <Field label="Name"><Input value={edit.name ?? ""} onChange={(e) => setEdit({ ...edit, name: e.target.value })} required /></Field>
            <div className="grid grid-cols-2 gap-4">
              <Field label="Duration (days)"><Input type="number" min={1} value={edit.duration_days ?? ""} onChange={(e) => setEdit({ ...edit, duration_days: Number(e.target.value) })} required /></Field>
              <Field label="Price (₹)"><Input type="number" min={0} value={edit.price ?? ""} onChange={(e) => setEdit({ ...edit, price: Number(e.target.value) })} required /></Field>
              {has("membership_freeze") && <Field label="Max freeze days"><Input type="number" min={0} value={edit.max_freeze_days ?? 0} onChange={(e) => setEdit({ ...edit, max_freeze_days: Number(e.target.value) })} /></Field>}
            </div>
            {org?.type === "multi" && (
              <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={!!edit.all_branch_access} onChange={(e) => setEdit({ ...edit, all_branch_access: e.target.checked })} />Valid at all branches</label>
            )}
            <ErrorBox error={error} />
            <Button className="w-full" loading={busy}>Save plan</Button>
          </form>
        )}
      </Modal>
    </>
  );
}
