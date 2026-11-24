"use client";
import { useState } from "react";
import { Plus } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, Select, Spinner, Table, Td, useLoad, useSubmit } from "@/components/ui";
import { api } from "@/lib/api";
import { ROLE_LABEL, useSession } from "@/lib/session";

type S = { id: number; full_name: string; phone: string; email: string | null; role: string; branch_id: number | null; is_active: boolean };

export default function Staff() {
  const { org } = useSession();
  const list = useLoad(() => api("/staff"));
  const branches = useLoad(() => api("/branches"));
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ full_name: "", phone: "", email: "", password: "", role: "front_desk", branch_id: "" });
  const { busy, error, run } = useSubmit();
  const isOwner = org?.role === "owner";
  const bname = (id: number | null) => (id ? branches.data?.find((b: { id: number }) => b.id === id)?.name : "All branches");

  return (
    <>
      <PageHeader title="Staff" subtitle="Each role sees only what it needs"
        action={isOwner && <Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Add staff</Button>} />
      <Card>
        {list.loading && !list.data ? <Spinner /> : list.data?.length ? (
          <Table head={["Name", "Login", "Role", "Branch", ""]}>
            {list.data.map((s: S) => (
              <tr key={s.id}>
                <Td className="font-medium">{s.full_name}</Td><Td>{s.email ?? s.phone}</Td>
                <Td><Badge tone={s.role === "owner" ? "orange" : "slate"}>{ROLE_LABEL[s.role]}</Badge></Td>
                <Td>{bname(s.branch_id)}</Td>
                <Td>{isOwner && s.role !== "owner" && (
                  <Button size="sm" variant="ghost" onClick={() => api(`/staff/${s.id}`, { method: "PATCH", body: { is_active: !s.is_active } }).then(list.reload)}>
                    {s.is_active ? "Disable" : "Enable"}
                  </Button>)}</Td>
              </tr>
            ))}
          </Table>
        ) : <Empty>No staff yet.</Empty>}
      </Card>
      <Modal open={open} onClose={() => setOpen(false)} title="Add staff member">
        <form className="grid gap-4 sm:grid-cols-2" onSubmit={(e) => { e.preventDefault(); run(async () => {
          await api("/staff", { body: { ...f, email: f.email || undefined, branch_id: f.branch_id ? Number(f.branch_id) : null } });
          setOpen(false); list.reload();
        }); }}>
          <Field label="Name"><Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></Field>
          <Field label="Mobile (login)"><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required /></Field>
          <Field label="Email (optional)"><Input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Field>
          <Field label="Temporary password"><Input type="password" minLength={8} value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} required /></Field>
          <Field label="Role">
            <Select value={f.role} onChange={(e) => setF({ ...f, role: e.target.value })}>
              {["manager", "front_desk", "trainer", "accountant"].map((r) => <option key={r} value={r}>{ROLE_LABEL[r]}</option>)}
            </Select>
          </Field>
          <Field label="Branch">
            <Select value={f.branch_id} onChange={(e) => setF({ ...f, branch_id: e.target.value })}>
              <option value="">All branches</option>
              {branches.data?.map((b: { id: number; name: string }) => <option key={b.id} value={b.id}>{b.name}</option>)}
            </Select>
          </Field>
          <div className="space-y-3 sm:col-span-2"><ErrorBox error={error} /><Button className="w-full" loading={busy}>Add</Button></div>
        </form>
      </Modal>
    </>
  );
}
