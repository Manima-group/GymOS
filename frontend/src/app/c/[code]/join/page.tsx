"use client";
import { useParams } from "next/navigation";
import { useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { Button, ErrorBox, Field, Input, Spinner, useLoad, useSubmit } from "@/components/ui";
import { api } from "@/lib/api";

export default function Join() {
  const { code } = useParams<{ code: string }>();
  const g = useLoad(() => api(`/public/branches/${code}`, { org: false }), [code]);
  const [f, setF] = useState({ full_name: "", phone: "", interest: "" });
  const [done, setDone] = useState<string | null>(null);
  const { busy, error, run } = useSubmit();
  if (g.loading) return <Spinner />;
  if (!g.data?.enquiry_enabled) return <p className="p-10 text-center text-slate-500">Please ask at the front desk.</p>;
  return (
    <div className="mx-auto max-w-sm p-6">
      <h1 className="text-2xl font-bold">{g.data.gym_name}</h1>
      <p className="text-sm text-slate-500">{g.data.branch_name} • {g.data.area}</p>
      {done ? (
        <div className="mt-8 text-center"><CheckCircle2 className="mx-auto h-14 w-14 text-emerald-500" /><p className="mt-3">{done}</p></div>
      ) : (
        <form className="mt-6 space-y-4" onSubmit={(e) => { e.preventDefault(); run(async () => setDone((await api(`/public/branches/${code}/enquiry`, { body: f, org: false })).message)); }}>
          <Field label="Your name"><Input value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required /></Field>
          <Field label="Mobile"><Input inputMode="tel" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} required /></Field>
          <Field label="What are your goals?"><Input value={f.interest} onChange={(e) => setF({ ...f, interest: e.target.value })} placeholder="Weight loss, strength, Zumba…" /></Field>
          <ErrorBox error={error} />
          <Button className="w-full" loading={busy}>Book my free trial</Button>
        </form>
      )}
    </div>
  );
}
