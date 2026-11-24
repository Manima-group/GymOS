"use client";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { CheckCircle2, MapPin, XCircle } from "lucide-react";
import { OtpLogin } from "@/components/otp-login";
import { Button, Spinner, useLoad } from "@/components/ui";
import { ApiError, api, auth, fmtDate } from "@/lib/api";

type Landing = { branch_code: string; branch_name: string; area: string; gym_name: string; branding: { primary_color?: string; logo_url?: string };
  rotating_qr: boolean; enquiry_enabled: boolean; geofence: boolean };

function getPosition(): Promise<GeolocationPosition> {
  return new Promise((ok, err) => navigator.geolocation.getCurrentPosition(ok, err, { enableHighAccuracy: true, timeout: 10000 }));
}

function CheckIn() {
  const { code } = useParams<{ code: string }>();
  const token = useSearchParams().get("t");
  const landing = useLoad<Landing>(() => api(`/public/branches/${code}`, { org: false }), [code]);
  const [loggedIn, setLoggedIn] = useState(false);
  const [state, setState] = useState<{ ok?: any; err?: string; busy?: boolean }>({});
  useEffect(() => setLoggedIn(!!auth.token), []);

  const checkin = async () => {
    setState({ busy: true });
    try {
      const body: Record<string, unknown> = { branch_code: code, token: token ?? undefined };
      if (landing.data?.geofence) {
        const p = await getPosition();
        body.latitude = p.coords.latitude; body.longitude = p.coords.longitude;
      }
      setState({ ok: await api("/me/checkin", { body, org: false }) });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { auth.clear(); setLoggedIn(false); setState({}); return; }
      setState({ err: e instanceof Error ? e.message : "Location permission is needed to check in" });
    }
  };

  if (landing.loading) return <Spinner />;
  if (landing.error || !landing.data) return <p className="p-10 text-center text-slate-500">This QR code is not active.</p>;
  const g = landing.data;
  const color = g.branding.primary_color ?? "#0f172a";

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="px-6 pb-16 pt-10 text-center text-white" style={{ background: color }}>
        {g.branding.logo_url && <img src={g.branding.logo_url} alt="" className="mx-auto mb-3 h-14" />}
        <h1 className="text-2xl font-bold">{g.gym_name}</h1>
        <p className="mt-1 flex items-center justify-center gap-1 text-sm opacity-80"><MapPin className="h-4 w-4" />{g.branch_name} • {g.area}</p>
      </div>
      <div className="mx-auto -mt-10 max-w-sm px-4">
        <div className="rounded-2xl bg-white p-6 shadow-lg">
          {!loggedIn ? (
            <>
              <h2 className="mb-4 text-lg font-semibold">Member check-in</h2>
              <OtpLogin onDone={() => { setLoggedIn(true); checkin(); }} />
            </>
          ) : state.ok ? (
            <div className="text-center">
              <CheckCircle2 className="mx-auto h-16 w-16 text-emerald-500" />
              <h2 className="mt-3 text-xl font-bold">{state.ok.duplicate ? "Already checked in" : "You're in!"}</h2>
              <p className="mt-1 text-slate-600">Have a great workout, {state.ok.member.name.split(" ")[0]} 💪</p>
              {state.ok.subscription && (
                <p className="mt-4 rounded-lg bg-slate-50 p-3 text-sm">
                  {state.ok.subscription.plan_name} valid till <b>{fmtDate(state.ok.subscription.end_date)}</b>
                  {state.ok.subscription.days_left <= 7 && <span className="block text-amber-700">Only {state.ok.subscription.days_left} days left — renew at the desk.</span>}
                  {state.ok.subscription.amount_due > 0 && <span className="block text-red-600">Pending dues: ₹{state.ok.subscription.amount_due}</span>}
                </p>
              )}
              <Link href="/me" className="mt-4 block text-sm text-brand-600">View my membership</Link>
            </div>
          ) : state.err ? (
            <div className="text-center">
              <XCircle className="mx-auto h-16 w-16 text-red-500" />
              <p className="mt-3 font-medium">{state.err}</p>
              <Button className="mt-4 w-full" variant="secondary" onClick={checkin}>Try again</Button>
            </div>
          ) : (
            <Button className="w-full py-4 text-base" loading={state.busy} onClick={checkin}>Check in now</Button>
          )}
        </div>
        {g.enquiry_enabled && !state.ok && (
          <p className="mt-6 text-center text-sm text-slate-600">Not a member yet? <Link className="font-medium text-brand-600" href={`/c/${code}/join`}>Enquire / book a free trial</Link></p>
        )}
        <p className="mt-8 text-center text-xs text-slate-400">Powered by Gym-OS</p>
      </div>
    </div>
  );
}

export default function Page() {
  return <Suspense fallback={<Spinner />}><CheckIn /></Suspense>;
}
