"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Plus, Search } from "lucide-react";
import { Locked, PageHeader } from "@/components/shell";
import { Badge, Button, Card, Empty, ErrorBox, Input, Spinner, Table, Td, cx, useLoad } from "@/components/ui";
import { AddMember, SubBadge, type Sub } from "@/components/members";
import { api, fmtDate } from "@/lib/api";
import { useSession } from "@/lib/session";

type Member = { id: number; member_code: string; full_name: string; phone: string; subscription: Sub | null; home_branch_id: number };

const FILTERS = [["", "All"], ["active", "Active"], ["expiring", "Expiring soon"], ["expired", "Expired"], ["none", "No plan"]];

export default function Members() {
  const { has } = useSession();
  const router = useRouter();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState("");
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const list = useLoad(() => api("/members", { params: { q, membership: filter, page } }), [q, filter, page]);
  if (!has("members")) return <Locked feature="members" />;

  return (
    <>
      <PageHeader title="Members" subtitle={list.data ? `${list.data.total} members` : undefined}
        action={<Button onClick={() => setOpen(true)}><Plus className="h-4 w-4" />Add member</Button>} />
      <Card>
        <div className="mb-4 flex flex-col gap-3 sm:flex-row">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
            <Input aria-label="Search" placeholder="Search name, phone or member ID" className="pl-9" value={q}
              onChange={(e) => { setQ(e.target.value); setPage(1); }} />
          </div>
          <div className="flex gap-1 overflow-x-auto">
            {FILTERS.map(([v, l]) => (
              <button key={v} onClick={() => { setFilter(v); setPage(1); }}
                className={cx("whitespace-nowrap rounded-lg px-3 py-2 text-sm", filter === v ? "bg-ink text-white" : "text-slate-600 hover:bg-slate-100")}>{l}</button>
            ))}
          </div>
        </div>
        <ErrorBox error={list.error} />
        {list.loading && !list.data ? <Spinner /> : list.data?.items.length ? (
          <>
            <Table head={["Member", "Phone", "Plan", "Ends", "Status"]}>
              {list.data.items.map((m: Member) => (
                <tr key={m.id} className="cursor-pointer hover:bg-slate-50" onClick={() => router.push(`/app/members/${m.id}`)}>
                  <Td><div className="font-medium">{m.full_name}</div><div className="text-xs text-slate-500">{m.member_code}</div></Td>
                  <Td>{m.phone}</Td>
                  <Td>{m.subscription?.plan_name ?? "—"}</Td>
                  <Td>{fmtDate(m.subscription?.end_date)}</Td>
                  <Td><SubBadge s={m.subscription} /> {m.subscription && m.subscription.amount_due > 0 && <Badge tone="red">Due</Badge>}</Td>
                </tr>
              ))}
            </Table>
            {list.data.total > list.data.size && (
              <div className="mt-4 flex justify-end gap-2">
                <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</Button>
                <Button variant="secondary" size="sm" disabled={page * list.data.size >= list.data.total} onClick={() => setPage(page + 1)}>Next</Button>
              </div>
            )}
          </>
        ) : <Empty>No members found. Add your first member to get started.</Empty>}
      </Card>
      <AddMember open={open} onClose={() => setOpen(false)} onDone={(id) => router.push(`/app/members/${id}?new=1`)} />
    </>
  );
}
