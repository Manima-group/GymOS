"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, Search } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, Select, Spinner, Table, Td, statusTone, useLoad, useSubmit } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";

type T = { id: number; name: string; type: string; status: string; plan: string; phone: string; usage: Record<string, number>; trial_ends_at: string | null; subscription_ends_at: string | null };

export default function Tenants() {
  const router = useRouter();
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const list = useLoad(() => api("/platform/tenants", { org: false, params: { q, status } }), [q, status]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ gym_name: "", owner_name: "", email: "", phone: "", password: "", area: "", plan_code: "basic", org_type: "single", activate: false });
  const { busy, error, run } = useSubmit();

  return (
    <>
      <PageHeader title="Gyms" subtitle={list.data ? `${list.data.total} tenants` : undefined}
        action={<Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Onboard gym</Button>} />
      <Card>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1"><Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input aria-label="Search" className="pl-9" placeholder="Search name, email, phone" value={q} onChange={(e) => setQ(e.target.value)} /></div>
          <Select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)} className="sm:w-44">
            <option value="">All statuses</option>{["trial", "active", "past_due", "suspended", "cancelled"].map((s) => <option key={s}>{s}</option>)}
          </Select>
        </div>
        {list.loading && !list.data ? <Spinner /> : list.data?.items.length ? (
          <Table head={["Gym", "Plan", "Status", "Branches", "Members", "Renews / trial ends"]}>
            {list.data.items.map((t: T) => (
              <tr key={t.id} className="cursor-pointer hover:bg-slate-50" onClick={() => router.push(`/admin/tenants/${t.id}`)}>
                <Td><div className="font-medium">{t.name}</div><div className="text-xs text-slate-500">{t.phone} • {t.type}</div></Td>
                <Td><Badge tone="orange">{t.plan}</Badge></Td>
                <Td><Badge tone={statusTone(t.status)}>{t.status}</Badge></Td>
                <Td>{t.usage.max_branches}</Td><Td>{t.usage.max_members}</Td>
                <Td>{fmtDate(t.status === "trial" ? t.trial_ends_at : t.subscription_ends_at)}</Td>
              </tr>
            ))}
          </Table>
        ) : <Empty>No gyms yet.</Empty>}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Onboard a gym">
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
          const t = await api("/platform/tenants", { org: false, body: f }); router.push(`/admin/tenants/${t.id}`);
        }); }}>
          <Field label="Gym name"><Input value={f.gym_name} onChange={(e) => setF({ ...f, gym_name: e.target.value })} required /></Field>
          <Field label="Area"><Input value={f.area} onChange={(e) => setF({ ...f, area: e.target.value })} required /></Field>
          <Field label="Owner name"><Input value={f.owner_name} onChange={(e) => setF({ ...f, owner_name: e.target.value })} required /></Field>
          <Field label="Owner mobile"><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required /></Field>
          <Field label="Owner email"><Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required /></Field>
          <Field label="Temporary password"><Input type="password" minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required /></Field>
          <Field label="Type"><Select value={f.org_type} onChange={(e) => setF({ ...f, org_type: e.target.value })}><option value="single">Single gym</option><option value="multi">Multi-branch</option></Select></Field>
          <Field label="Plan"><Select value={f.plan_code} onChange={(e) => setF({ ...f, plan_code: e.target.value })}>{["basic", "plus", "premium"].map((p) => <option key={p}>{p}</option>)}</Select></Field>
          <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" checked={f.activate} onChange={(e) => setF({ ...f, activate: e.target.checked })} />Paid already — skip the free trial</label>
          <div className="space-y-3 sm:col-span-2"><ErrorBox error={error} /><Button className="w-full" loading={busy}>Create gym</Button></div>
        </form>
      </Modal>
    </>
  );
}
