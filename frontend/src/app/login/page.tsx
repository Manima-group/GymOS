"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Dumbbell } from "lucide-react";
import { api, auth } from "@/lib/api";
import { Button, ErrorBox, Field, Input, useSubmit } from "@/components/ui";
import type { Me } from "@/lib/session";

export default function Login() {
  const router = useRouter();
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const { busy, error, run } = useSubmit();

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      auth.clear();
      auth.set(await api("/auth/login", { body: { login, password }, org: false }));
      const me = await api<Me>("/auth/me", { org: false });
      if (me.staff_of.length) { auth.setOrg(me.staff_of[0].org_id); router.push("/app"); }
      else if (me.is_platform_admin) router.push("/admin");
      else router.push("/me");
    });
  };

  return (
    <div className="flex min-h-screen items-center justify-center p-4">
      <form onSubmit={submit} className="w-full max-w-sm space-y-4 rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
        <div className="flex items-center gap-2 text-lg font-bold">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500 text-white"><Dumbbell className="h-5 w-5" /></span>Gym-OS
        </div>
        <h1 className="text-xl font-semibold">Log in to your gym</h1>
        <Field label="Email or phone"><Input value={login} onChange={(e) => setLogin(e.target.value)} required autoComplete="username" /></Field>
        <Field label="Password"><Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" /></Field>
        <ErrorBox error={error} />
        <Button className="w-full" loading={busy}>Log in</Button>
        <p className="text-center text-sm text-slate-500">
          Gym member? <Link href="/me" className="text-brand-600">Log in with OTP</Link> • New gym? <Link href="/signup" className="text-brand-600">Start trial</Link>
        </p>
      </form>
    </div>
  );
}
