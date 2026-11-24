"use client";
import Link from "next/link";
import { useState } from "react";
import { MessageCircle } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Card, Empty, Select, Spinner, Table, Td, useLoad } from "@/components/ui";
import { api, fmtDate, inr } from "@/lib/api";

type R = { member_id: number; name: string; phone: string; plan: string; end_date: string; amount_due: number };

export default function Expiring() {
  const [days, setDays] = useState(7);
  const list = useLoad(() => api("/reports/expiring", { params: { days } }), [days]);
  return (
    <>
      <PageHeader title="Expiring memberships" subtitle="Call or WhatsApp them before they lapse — renewals are your easiest revenue"
        action={<Select aria-label="Window" value={days} onChange={(e) => setDays(Number(e.target.value))} className="w-40">
          {[3, 7, 15, 30].map((d) => <option key={d} value={d}>Next {d} days</option>)}
        </Select>} />
      <Card>
        {list.loading && !list.data ? <Spinner /> : list.data?.length ? (
          <Table head={["Member", "Plan", "Ends", "Due", ""]}>
            {list.data.map((r: R) => (
              <tr key={r.member_id}>
                <Td><Link href={`/app/members/${r.member_id}`} className="font-medium text-brand-600">{r.name}</Link><div className="text-xs text-slate-500">{r.phone}</div></Td>
                <Td>{r.plan}</Td><Td>{fmtDate(r.end_date)}</Td><Td>{r.amount_due > 0 ? inr(r.amount_due) : "—"}</Td>
                <Td>
                  <a className="inline-flex items-center gap-1 text-sm text-emerald-700" target="_blank" rel="noreferrer"
                    href={`https://wa.me/91${r.phone}?text=${encodeURIComponent(`Hi ${r.name.split(" ")[0]}, your ${r.plan} membership ends on ${fmtDate(r.end_date)}. Renew today to keep your streak going!`)}`}>
                    <MessageCircle className="h-4 w-4" />WhatsApp
                  </a>
                </Td>
              </tr>
            ))}
          </Table>
        ) : <Empty>Nobody is expiring in this window. 🎉</Empty>}
      </Card>
    </>
  );
}
