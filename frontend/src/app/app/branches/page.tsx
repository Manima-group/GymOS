"use client";
import { useEffect, useState } from "react";
import { Download, MapPin, MonitorSmartphone, Plus } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Button, Card, ErrorBox, Field, Input, Modal, Spinner, useLoad, useSubmit } from "@/components/ui";
import { api, openAuthed } from "@/lib/api";
import { useSession } from "@/lib/session";

type B = { id: number; name: string; area: string; code: string; address: string; checkin_url: string };

export default function Branches() {
  const { org, has, reload } = useSession();
  const list = useLoad(() => api("/branches"));
  const [open, setOpen] = useState(false);
  const [live, setLive] = useState<B | null>(null);
  const [f, setF] = useState({ name: "", area: "", address: "" });
  const { busy, error, run } = useSubmit();
  const isOwner = org?.role === "owner";

  return (
    <>
      <PageHeader title="Branches & QR codes" subtitle="Print the poster and stick it at the entrance"
        action={isOwner && <Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Add branch</Button>} />
      {list.loading && !list.data ? <Spinner /> : (
        <div className="grid gap-4 sm:grid-cols-2">
          {list.data?.map((b: B) => (
            <Card key={b.id}>
              <div className="font-semibold">{b.name}</div>
              <div className="mt-1 flex items-center gap-1 text-sm text-slate-500"><MapPin className="h-3.5 w-3.5" />{b.area}</div>
              <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                Branch code <b className="font-mono text-slate-900">{b.code}</b><br /><span className="break-all">{b.checkin_url}</span>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {has("attendance_qr") && <Button size="sm" onClick={() => openAuthed(`/branches/${b.id}/qr-poster.png`, `${b.code}-qr-poster.png`)}><Download className="h-4 w-4" />QR poster</Button>}
                {has("qr_rotating") && <Button size="sm" variant="secondary" onClick={() => setLive(b)}><MonitorSmartphone className="h-4 w-4" />Live QR screen</Button>}
              </div>
            </Card>
          ))}
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Add branch">
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); run(async () => {
          await api("/branches", { body: f }); setOpen(false); setF({ name: "", area: "", address: "" }); list.reload(); reload();
        }); }}>
          <Field label="Branch name"><Input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} required /></Field>
          <Field label="Area tag" hint="Shown on the QR poster, e.g. Madhapur"><Input value={f.area} onChange={(e) => setF({ ...f, area: e.target.value })} required /></Field>
          <Field label="Address"><Input value={f.address} onChange={(e) => setF({ ...f, address: e.target.value })} /></Field>
          <ErrorBox error={error} />
          <Button className="w-full" loading={busy}>Create branch</Button>
        </form>
      </Modal>
      {live && <LiveQr branch={live} onClose={() => setLive(null)} />}
    </>
  );
}

function LiveQr({ branch, onClose }: { branch: B; onClose: () => void }) {
  const [payload, setPayload] = useState<string>("");
  useEffect(() => {
    let t: ReturnType<typeof setTimeout>;
    const tick = async () => {
      const r = await api(`/branches/${branch.id}/live-qr`);
      setPayload(r.payload);
      t = setTimeout(tick, Math.max(5, r.refresh_seconds - 5) * 1000);
    };
    tick();
    return () => clearTimeout(t);
  }, [branch.id]);
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-ink p-6 text-white" onClick={onClose}>
      <div className="text-3xl font-bold">{branch.name}</div>
      <div className="mb-6 text-slate-300">{branch.area} • Scan to check in</div>
      {payload ? <QrSvg text={payload} /> : <Spinner />}
      <div className="mt-6 text-sm text-slate-400">Code refreshes automatically. Tap anywhere to close.</div>
    </div>
  );
}

function QrSvg({ text }: { text: string }) {
  const [svg, setSvg] = useState("");
  useEffect(() => { import("qrcode").then((q) => q.toString(text, { type: "svg", margin: 1, width: 360 }).then(setSvg)); }, [text]);
  return <div className="rounded-2xl bg-white p-4" style={{ width: 392 }} dangerouslySetInnerHTML={{ __html: svg }} />;
}
