"use client";
import { useState } from "react";
import { api, auth } from "@/lib/api";
import { Button, ErrorBox, Field, Input, useSubmit } from "./ui";

/** Phone + OTP login for gym members. */
export function OtpLogin({ onDone }: { onDone: () => void }) {
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [devOtp, setDevOtp] = useState<string | null>(null);
  const { busy, error, run } = useSubmit();

  return (
    <form className="space-y-4" onSubmit={(e) => {
      e.preventDefault();
      run(async () => {
        if (!sent) {
          const r = await api("/auth/otp/request", { body: { phone }, org: false });
          setSent(true); setDevOtp(r.dev_otp ?? null);
        } else {
          auth.clear();
          auth.set(await api("/auth/otp/verify", { body: { phone, code }, org: false }));
          onDone();
        }
      });
    }}>
      <Field label="Mobile number registered at your gym">
        <Input inputMode="tel" autoComplete="tel" value={phone} onChange={(e) => setPhone(e.target.value)} required disabled={sent} placeholder="98xxxxxxxx" />
      </Field>
      {sent && (
        <Field label="Enter the 6-digit OTP" hint={devOtp ? `Dev mode OTP: ${devOtp}` : "Sent by SMS"}>
          <Input inputMode="numeric" autoComplete="one-time-code" maxLength={6} value={code} onChange={(e) => setCode(e.target.value)} required autoFocus />
        </Field>
      )}
      <ErrorBox error={error} />
      <Button className="w-full" loading={busy}>{sent ? "Verify & continue" : "Send OTP"}</Button>
      {sent && <button type="button" className="w-full text-sm text-slate-500" onClick={() => { setSent(false); setCode(""); }}>Change number</button>}
    </form>
  );
}
