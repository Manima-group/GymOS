"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Phone, Plus } from "lucide-react";
import { Locked, PageHeader } from "@/components/shell";
import { AddMember } from "@/components/members";
import { Badge, Button, Card, Empty, ErrorBox, Field, Input, Modal, Select, Spinner, statusTone, useLoad, useSubmit } from "@/components/ui";
import { api, fmtDate } from "@/lib/api";
import { useSession } from "@/lib/session";

type L = { id: number; full_name: string; phone: string; interest: string; source: string; status: string; follow_up_on: string | null; created_at: string };
const STAGES = ["new", "contacted", "trial", "converted", "lost"];

export default function Leads() {
  const { has } = useSession();
  const router = useRouter();
  const list = useLoad(() => (has("crm") ? api("/leads") : Promise.resolve([])));
  const [open, setOpen] = useState(false);
  const [convert, setConvert] = useState<L | null>(null);
  const [f, setF] = useState({ full_name: "", phone: "", interest: "", source: "walk_in" });
  const { busy, error, run } = useSubmit();
  if (!has("crm")) return <Locked feature="crm" />;

  const move = (l: L, status: string) => api(`/leads/${l.id}`, { method: "PATCH", body: { status } }).then(list.reload);

  return (
    <>
      <PageHeader title="Leads" subtitle="Enquiries from your QR poster and walk-ins"
        action={<Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Add lead</Button>} />
      {list.loading && !list.data ? <Spinner /> : list.data?.length ? (
        <div className="grid gap-4 lg:grid-cols-4">
          {STAGES.slice(0, 4).map((stage) => (
            <div key={stage} className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold capitalize">{stage}<Badge>{list.data.filter((l: L) => l.status === stage).length}</Badge></div>
              {list.data.filter((l: L) => l.status === stage).map((l: L) => (
                <Card key={l.id} className="p-4">
                  <div className="font-medium">{l.full_name}</div>
                  <a href={`tel:${l.phone}`} className="mt-1 flex items-center gap-1 text-sm text-brand-600"><Phone className="h-3.5 w-3.5" />{l.phone}</a>
                  {l.interest && <div className="mt-1 text-xs text-slate-500">{l.interest}</div>}
                  <div className="mt-2 flex items-center gap-2 text-xs text-slate-500"><Badge tone={statusTone(l.source === "qr" ? "new" : "")}>{l.source}</Badge>{fmtDate(l.created_at)}</div>
                  {stage !== "converted" && (
                    <div className="mt-3 flex gap-2">
                      <Select aria-label="Stage" className="py-1.5 text-xs" value={l.status} onChange={(e) => move(l, e.target.value)}>
                        {STAGES.map((s) => <option key={s} value={s}>{s}</option>)}
                      </Select>
                      <Button size="sm" onClick={() => setConvert(l)}>Join</Button>
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ))}
        </div>
      ) : <Empty>No leads yet. Your QR poster includes an enquiry code for walk-ins.</Empty>}
      <Modal open={open} onClose={() => setOpen(false)} title="Add lead">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(async () => { await api("/leads", { body: f }); setOpen(false); list.reload(); }); }}>
          <Field label="Name"><Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></Field>
          <Field label="Mobile"><Input value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required /></Field>
          <Field label="Interested in"><Input value={f.interest} onChange={(e) => setF({ ...f, interest: e.target.value })} placeholder="Weight loss, PT, Zumba…" /></Field>
          <Field label="Source"><Select value={f.source} onChange={(e) => setF({ ...f, source: e.target.value })}>{["walk_in", "referral", "ads", "other"].map((s) => <option key={s}>{s}</option>)}</Select></Field>
          <ErrorBox error={error} /><Button className="w-full" loading={busy}>Save</Button>
        </form>
      </Modal>
      {convert && <AddMember open leadId={convert.id} preset={{ full_name: convert.full_name, phone: convert.phone }}
        onClose={() => setConvert(null)} onDone={(id) => router.push(`/app/members/${id}?new=1`)} />}
    </>
  );
}
