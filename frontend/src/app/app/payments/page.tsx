"use client";
import Link from "next/link";
import { useState } from "react";
import { Receipt } from "lucide-react";
import { PageHeader } from "@/components/shell";
import { Button, Card, Empty, ErrorBox, Input, Select, Spinner, Stat, Table, Td, useLoad } from "@/components/ui";
import { api, fmtDate, inr, openAuthed } from "@/lib/api";
import { useSession } from "@/lib/session";

type P = { id: number; invoice_no: string; member_id: number; amount: number; method: string; paid_at: string; reference: string | null };

export default function Payments() {
  const { has } = useSession();
  const now = new Date();
  const [from, setFrom] = useState(new Date(now.getFullYear(), now.getMonth(), 1).toLocaleDateString("en-CA"));
  const [to, setTo] = useState(now.toLocaleDateString("en-CA"));
  const [method, setMethod] = useState("");
  const list = useLoad(() => api("/payments", { params: { date_from: from, date_to: to, method } }), [from, to, method]);

  const exportCsv = () => {
    const rows = [["Invoice", "Date", "Member ID", "Method", "Reference", "Amount"],
      ...list.data.items.map((p: P) => [p.invoice_no, fmtDate(p.paid_at), p.member_id, p.method, p.reference ?? "", p.amount])];
    const blob = new Blob([rows.map((r) => r.join(",")).join("\n")], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob); a.download = `payments-${from}-to-${to}.csv`; a.click();
  };

  return (
    <>
      <PageHeader title="Payments" action={has("data_export") && list.data?.items.length > 0 && <Button variant="secondary" onClick={exportCsv}>Export CSV</Button>} />
      <div className="mb-4 flex flex-wrap gap-3">
        <Input type="date" aria-label="From" value={from} onChange={(e) => setFrom(e.target.value)} className="w-40" />
        <Input type="date" aria-label="To" value={to} onChange={(e) => setTo(e.target.value)} className="w-40" />
        <Select aria-label="Method" value={method} onChange={(e) => setMethod(e.target.value)} className="w-36">
          <option value="">All methods</option>{["cash", "upi", "card", "bank", "online"].map((m) => <option key={m} value={m}>{m.toUpperCase()}</option>)}
        </Select>
      </div>
      <ErrorBox error={list.error} />
      {list.data && (
        <div className="mb-4 grid grid-cols-2 gap-4 sm:max-w-md">
          <Stat label="Collected" value={inr(list.data.total_amount)} />
          <Stat label="Payments" value={list.data.count} />
        </div>
      )}
      <Card>
        {list.loading && !list.data ? <Spinner /> : list.data?.items.length ? (
          <Table head={["Invoice", "Date", "Member", "Method", "Amount", ""]}>
            {list.data.items.map((p: P) => (
              <tr key={p.id}>
                <Td>{p.invoice_no}</Td><Td>{fmtDate(p.paid_at)}</Td>
                <Td><Link className="text-brand-600" href={`/app/members/${p.member_id}`}>View member</Link></Td>
                <Td className="uppercase">{p.method}</Td><Td className="font-medium">{inr(p.amount)}</Td>
                <Td>{has("invoices") && <Button size="sm" variant="ghost" onClick={() => openAuthed(`/payments/${p.id}/receipt`)}><Receipt className="h-4 w-4" /></Button>}</Td>
              </tr>
            ))}
          </Table>
        ) : <Empty>No payments in this period.</Empty>}
      </Card>
    </>
  );
}
