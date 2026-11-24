"use client";
import { useState } from "react";
import { Badge, Button, ErrorBox, Field, Input, Modal, Select, useLoad, useSubmit } from "@/components/ui";
import { api } from "@/lib/api";
import { useSession } from "@/lib/session";

export type Sub = { id: number; status: string; start_date: string; end_date: string; days_left: number; plan_name: string; amount_due: number; amount_paid: number; price: number; discount: number };

export function SubBadge({ s }: { s: Sub | null }) {
  if (!s) return <Badge>No plan</Badge>;
  if (s.status === "frozen") return <Badge tone="blue">Frozen</Badge>;
  if (s.days_left < 0) return <Badge tone="red">Expired</Badge>;
  if (s.days_left <= 7) return <Badge tone="amber">{s.days_left}d left</Badge>;
  return <Badge tone="green">Active</Badge>;
}

export function AddMember({ open, onClose, onDone, leadId, preset }: { open: boolean; onClose: () => void; onDone: (id: number) => void; leadId?: number; preset?: { full_name: string; phone: string } }) {
  const { org } = useSession();
  const branches = useLoad(() => (open ? api("/branches") : Promise.resolve([])), [open]);
  const [f, setF] = useState({ full_name: preset?.full_name ?? "", phone: preset?.phone ?? "", email: "", gender: "", dob: "", home_branch_id: "", emergency_contact: "" });
  const { busy, error, run } = useSubmit();
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const body = Object.fromEntries(Object.entries({ ...f, lead_id: leadId }).filter(([, v]) => v !== "" && v !== undefined));
      const m = await api("/members", { body });
      onDone(m.id);
    });
  };
  return (
    <Modal open={open} onClose={onClose} title="Add member">
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2">
        <Field label="Full name"><Input value={f.full_name} onChange={set("full_name")} required /></Field>
        <Field label="Mobile"><Input value={f.phone} onChange={set("phone")} required inputMode="tel" /></Field>
        <Field label="Email (optional)"><Input type="email" value={f.email} onChange={set("email")} /></Field>
        <Field label="Gender"><Select value={f.gender} onChange={set("gender")}><option value="">—</option><option value="male">Male</option><option value="female">Female</option><option value="other">Other</option></Select></Field>
        <Field label="Date of birth" hint="For birthday wishes"><Input type="date" value={f.dob} onChange={set("dob")} /></Field>
        <Field label="Emergency contact"><Input value={f.emergency_contact} onChange={set("emergency_contact")} /></Field>
        {org?.type === "multi" && !org.branch_id && (
          <div className="sm:col-span-2"><Field label="Home branch">
            <Select value={f.home_branch_id} onChange={set("home_branch_id")} required>
              <option value="">Select branch</option>
              {branches.data?.map((b: { id: number; name: string; area: string }) => <option key={b.id} value={b.id}>{b.name} • {b.area}</option>)}
            </Select>
          </Field></div>
        )}
        <div className="sm:col-span-2 space-y-3"><ErrorBox error={error} /><Button className="w-full" loading={busy}>Save member</Button></div>
      </form>
    </Modal>
  );
}
