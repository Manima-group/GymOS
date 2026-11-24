import Link from "next/link";
import { Bell, Building2, Check, CreditCard, Dumbbell, QrCode, Sparkles, Users } from "lucide-react";
import { API_URL } from "@/lib/api";

type Plan = { code: string; name: string; price_monthly: number; price_yearly: number; limits: Record<string, number>; features: string[] };

async function getPlans(): Promise<Plan[]> {
  try {
    const r = await fetch(`${API_URL}/public/plans`, { next: { revalidate: 300 } });
    return r.ok ? r.json() : [];
  } catch {
    return [];
  }
}

const HIGHLIGHTS: Record<string, string[]> = {
  basic: ["1 branch, up to 300 members", "QR check-in poster", "Members, plans & renewals", "Payments + GST receipts", "Email reminders", "Member app"],
  plus: ["Up to 3 branches, 1,500 members", "Everything in Basic", "SMS reminders + 300 credits/mo", "Leads & enquiry CRM", "Membership freeze", "Multi-branch dashboard, staff roles", "Coming soon: online payments, trainers & classes"],
  premium: ["Unlimited branches & members", "Everything in Plus", "WhatsApp reminders + 1,000 credits/mo", "Anti-cheat rotating QR + geofence", "White-label branding", "Coming soon: workouts, expenses, POS, AI"],
};

const lim = (n: number) => (n < 0 ? "Unlimited" : n.toLocaleString("en-IN"));

export default async function Home() {
  const plans = await getPlans();
  return (
    <div className="bg-white">
      <header className="mx-auto flex max-w-6xl items-center justify-between p-5">
        <div className="flex items-center gap-2 text-lg font-bold">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-500 text-white"><Dumbbell className="h-5 w-5" /></span>Gym-OS
        </div>
        <nav className="flex items-center gap-3 text-sm">
          <a href="#pricing" className="hidden text-slate-600 hover:text-slate-900 sm:inline">Pricing</a>
          <Link href="/login" className="text-slate-600 hover:text-slate-900">Log in</Link>
          <Link href="/signup" className="rounded-lg bg-brand-500 px-4 py-2 font-medium text-white hover:bg-brand-600">Start free trial</Link>
        </nav>
      </header>

      <section className="mx-auto max-w-6xl px-5 pb-16 pt-10 text-center sm:pt-20">
        <span className="rounded-full bg-brand-50 px-3 py-1 text-xs font-medium text-brand-700">14-day free trial • No card needed</span>
        <h1 className="mx-auto mt-5 max-w-3xl text-4xl font-extrabold tracking-tight text-slate-900 sm:text-6xl">
          Run your gym from one simple screen
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-lg text-slate-600">
          Members, QR check-in, payments and automatic renewal reminders. Built for single gyms and multi-branch owners in India.
        </p>
        <div className="mt-8 flex justify-center gap-3">
          <Link href="/signup" className="rounded-lg bg-brand-500 px-6 py-3 font-semibold text-white hover:bg-brand-600">Start free trial</Link>
          <a href="#pricing" className="rounded-lg border border-slate-200 px-6 py-3 font-semibold text-slate-800 hover:bg-slate-50">See pricing</a>
        </div>
      </section>

      <section className="bg-slate-50 py-16">
        <div className="mx-auto grid max-w-6xl gap-5 px-5 sm:grid-cols-2 lg:grid-cols-3">
          {[
            [QrCode, "QR check-in per branch", "Print a poster with your gym name and area. Members scan and they're in — expired memberships are blocked automatically."],
            [CreditCard, "Payments & receipts", "Cash, UPI or card. Partial payments, dues tracking and GST receipts in one tap."],
            [Bell, "Automatic reminders", "Renewal, dues, birthday and 'we miss you' messages by email, SMS or WhatsApp."],
            [Building2, "Multi-branch control", "One owner login across branches, with branch managers seeing only their branch."],
            [Users, "Leads to members", "Walk-ins scan the enquiry QR. Follow up, give a trial, convert."],
            [Sparkles, "AI coming soon", "Churn prediction, AI WhatsApp assistant and workout plans — built in, switched on when you're ready."],
          ].map(([Icon, t, d]) => {
            const I = Icon as typeof QrCode;
            return (
              <div key={t as string} className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200">
                <I className="h-6 w-6 text-brand-500" />
                <h3 className="mt-3 font-semibold">{t as string}</h3>
                <p className="mt-1 text-sm text-slate-600">{d as string}</p>
              </div>
            );
          })}
        </div>
      </section>

      <section id="pricing" className="mx-auto max-w-6xl px-5 py-20">
        <h2 className="text-center text-3xl font-bold">Simple, affordable pricing</h2>
        <p className="mt-2 text-center text-slate-600">Pay yearly and get 2 months free.</p>
        <div className="mt-10 grid gap-6 md:grid-cols-3">
          {plans.map((p) => (
            <div key={p.code} className={`rounded-2xl p-6 ring-1 ${p.code === "plus" ? "bg-ink text-white ring-ink" : "bg-white ring-slate-200"}`}>
              {p.code === "plus" && <span className="rounded-full bg-brand-500 px-2 py-0.5 text-xs font-medium">Most popular</span>}
              <h3 className="mt-2 text-xl font-bold">{p.name}</h3>
              <div className="mt-3"><span className="text-4xl font-extrabold">₹{Number(p.price_monthly).toLocaleString("en-IN")}</span><span className="opacity-70">/month</span></div>
              <div className="text-sm opacity-70">or ₹{Number(p.price_yearly).toLocaleString("en-IN")}/year</div>
              <ul className="mt-6 space-y-2 text-sm">
                {(HIGHLIGHTS[p.code] ?? [`${lim(p.limits.max_branches)} branches`, `${lim(p.limits.max_members)} members`]).map((h) => (
                  <li key={h} className="flex gap-2"><Check className="h-4 w-4 shrink-0 text-brand-500" />{h}</li>
                ))}
              </ul>
              <Link href={`/signup?plan=${p.code}`} className={`mt-6 block rounded-lg py-2.5 text-center font-semibold ${p.code === "plus" ? "bg-brand-500 text-white hover:bg-brand-600" : "bg-slate-900 text-white hover:bg-slate-800"}`}>
                Start free trial
              </Link>
            </div>
          ))}
        </div>
        <p className="mt-6 text-center text-sm text-slate-500">Extra SMS/WhatsApp credits: 500 for ₹299 • 2,000 for ₹999 • 5,000 for ₹2,199</p>
      </section>

      <footer className="border-t border-slate-200 py-8 text-center text-sm text-slate-500">
        Gym-OS is a product of Manima AI Tech Solutions • business@manima.co.in
      </footer>
    </div>
  );
}
