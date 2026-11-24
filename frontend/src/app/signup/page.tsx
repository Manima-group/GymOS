"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Building, Building2 } from "lucide-react";
import { api, auth } from "@/lib/api";
import { Button, Card, ErrorBox, Field, Input, Select, cx, useSubmit } from "@/components/ui";

export default function Signup() {
  const router = useRouter();
  const [f, setF] = useState({ gym_name: "", owner_name: "", email: "", phone: "", password: "", area: "", address: "",
    org_type: "single", plan_code: "basic" });
  const { busy, error, run } = useSubmit();
  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("plan");
    if (p) setF((s) => ({ ...s, plan_code: p }));
  }, []);
  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => setF({ ...f, [k]: e.target.value });

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      const r = await api("/public/signup", { body: f, org: false });
      auth.set(await api("/auth/login", { body: { login: f.email, password: f.password }, org: false }));
      auth.setOrg(r.org_id);
      router.push("/app?welcome=1");
    });
  };

  return (
    <div className="mx-auto max-w-xl p-4 py-10">
      <h1 className="text-2xl font-bold">Start your 14-day free trial</h1>
      <p className="mt-1 text-sm text-slate-500">Set up takes 2 minutes. Already registered? <Link className="text-brand-600" href="/login">Log in</Link></p>
      <form onSubmit={submit} className="mt-6 space-y-5">
        <Card title="Your business">
          <div className="mb-4 grid grid-cols-2 gap-3">
            {[["single", "Single gym", Building], ["multi", "Multiple branches", Building2]].map(([v, label, Icon]) => {
              const I = Icon as typeof Building;
              return (
                <button type="button" key={v as string} onClick={() => setF({ ...f, org_type: v as string, plan_code: v === "multi" && f.plan_code === "basic" ? "plus" : f.plan_code })}
                  className={cx("flex flex-col items-center gap-2 rounded-xl border p-4 text-sm font-medium",
                    f.org_type === v ? "border-brand-500 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600")}>
                  <I className="h-6 w-6" />{label as string}
                </button>
              );
            })}
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Gym name"><Input value={f.gym_name} onChange={set("gym_name")} required placeholder="PowerFit Gym" /></Field>
            <Field label="Area" hint="Shown on your QR poster"><Input value={f.area} onChange={set("area")} required placeholder="Kukatpally" /></Field>
            <div className="sm:col-span-2"><Field label="Address"><Input value={f.address} onChange={set("address")} /></Field></div>
            <Field label="Plan">
              <Select value={f.plan_code} onChange={set("plan_code")}>
                <option value="basic" disabled={f.org_type === "multi"}>Basic — ₹999/mo</option>
                <option value="plus">Plus — ₹2,499/mo</option>
                <option value="premium">Premium — ₹4,999/mo</option>
              </Select>
            </Field>
          </div>
        </Card>
        <Card title="Owner account">
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Your name"><Input value={f.owner_name} onChange={set("owner_name")} required /></Field>
            <Field label="Mobile"><Input value={f.phone} onChange={set("phone")} required inputMode="tel" placeholder="98xxxxxxxx" /></Field>
            <Field label="Email"><Input type="email" value={f.email} onChange={set("email")} required /></Field>
            <Field label="Password" hint="At least 8 characters"><Input type="password" value={f.password} onChange={set("password")} required minLength={8} /></Field>
          </div>
        </Card>
        <ErrorBox error={error} />
        <Button className="w-full" loading={busy}>Create my gym</Button>
      </form>
    </div>
  );
}
