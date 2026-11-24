"use client";
import { Loader2, X } from "lucide-react";
import { useEffect, useState, type ButtonHTMLAttributes, type InputHTMLAttributes, type ReactNode, type SelectHTMLAttributes } from "react";
import { ApiError } from "@/lib/api";

export const cx = (...c: (string | false | null | undefined)[]) => c.filter(Boolean).join(" ");

type BtnProps = ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; loading?: boolean; size?: "sm" | "md" };
export function Button({ variant = "primary", loading, size = "md", className, children, disabled, ...p }: BtnProps) {
  const v = {
    primary: "bg-brand-500 text-white hover:bg-brand-600 shadow-sm",
    secondary: "bg-white text-slate-800 border border-slate-200 hover:bg-slate-50",
    ghost: "text-slate-600 hover:bg-slate-100",
    danger: "bg-red-600 text-white hover:bg-red-700",
  }[variant];
  return (
    <button
      {...p}
      disabled={disabled || loading}
      className={cx("inline-flex items-center justify-center gap-2 rounded-lg font-medium transition disabled:opacity-50 focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500",
        size === "sm" ? "px-3 py-1.5 text-sm" : "px-4 py-2.5 text-sm", v, className)}
    >
      {loading && <Loader2 className="h-4 w-4 animate-spin" />}
      {children}
    </button>
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="text-sm font-medium text-slate-700">{label}</span>
      {children}
      {hint && <span className="block text-xs text-slate-500">{hint}</span>}
    </label>
  );
}

const inputCls = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 text-sm placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-100";
export const Input = (p: InputHTMLAttributes<HTMLInputElement>) => <input {...p} className={cx(inputCls, p.className)} />;
export const Select = (p: SelectHTMLAttributes<HTMLSelectElement>) => <select {...p} className={cx(inputCls, p.className)} />;

export function Card({ title, action, children, className }: { title?: ReactNode; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={cx("rounded-2xl border border-slate-200 bg-white p-5 shadow-sm", className)}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="font-semibold text-slate-900">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint, icon }: { label: string; value: ReactNode; hint?: string; icon?: ReactNode }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-center justify-between text-sm text-slate-500">{label}{icon}</div>
      <div className="mt-2 text-2xl font-bold text-slate-900">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}

const badgeTone = {
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  red: "bg-red-50 text-red-700 ring-red-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  slate: "bg-slate-100 text-slate-700 ring-slate-200",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  orange: "bg-brand-50 text-brand-700 ring-brand-100",
};
export function Badge({ tone = "slate", children }: { tone?: keyof typeof badgeTone; children: ReactNode }) {
  return <span className={cx("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset", badgeTone[tone])}>{children}</span>;
}

export function statusTone(s?: string): keyof typeof badgeTone {
  return ({ active: "green", trial: "blue", past_due: "amber", frozen: "blue", expired: "red", suspended: "red",
    cancelled: "slate", new: "orange", contacted: "blue", converted: "green", lost: "slate" } as const)[s ?? ""] ?? "slate";
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-slate-900/40 p-0 sm:items-center sm:p-4" onClick={onClose}>
      <div role="dialog" aria-modal="true" aria-label={title} className="max-h-[90vh] w-full overflow-y-auto rounded-t-2xl bg-white p-5 shadow-xl sm:max-w-lg sm:rounded-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold">{title}</h3>
          <button aria-label="Close" onClick={onClose} className="rounded p-1 text-slate-500 hover:bg-slate-100"><X className="h-5 w-5" /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500">{children}</div>;
}

export function Spinner() {
  return <div className="flex justify-center p-10"><Loader2 className="h-6 w-6 animate-spin text-slate-400" /></div>;
}

export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  const e = error as ApiError;
  const upgrade = e.code === "feature_not_in_plan" || e.code === "limit_reached";
  return (
    <div className={cx("rounded-lg p-3 text-sm", upgrade ? "bg-brand-50 text-brand-700" : "bg-red-50 text-red-700")}>
      {e.message}
      {upgrade && <span className="block text-xs mt-1">Contact Manima to upgrade: business@manima.co.in</span>}
    </div>
  );
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="-mx-5 overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr className="border-b border-slate-200 text-left text-xs uppercase tracking-wide text-slate-500">
          {head.map((h) => <th key={h} className="px-5 py-2 font-medium">{h}</th>)}
        </tr></thead>
        <tbody className="divide-y divide-slate-100">{children}</tbody>
      </table>
    </div>
  );
}

export const Td = ({ children, className }: { children?: ReactNode; className?: string }) =>
  <td className={cx("px-5 py-3 align-middle", className)}>{children}</td>;

/** Small data-loading hook: returns [data, error, loading, reload]. */
export function useLoad<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [state, set] = useState<{ data?: T; error?: unknown; loading: boolean }>({ loading: true });
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let alive = true;
    set((s) => ({ ...s, loading: true }));
    fn().then((data) => alive && set({ data, loading: false })).catch((error) => alive && set({ error, loading: false }));
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, tick]);
  return { ...state, reload: () => setTick((t) => t + 1) };
}

/** Form submit helper with loading + error state. */
export function useSubmit() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const run = async (fn: () => Promise<unknown>) => {
    setBusy(true); setError(null);
    try { await fn(); return true; } catch (e) { setError(e); return false; } finally { setBusy(false); }
  };
  return { busy, error, run, setError };
}
