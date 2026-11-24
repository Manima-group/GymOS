"use client";
import { PageHeader } from "@/components/shell";
import { Card, Spinner, Table, Td, useLoad } from "@/components/ui";
import { api, fmtDate, fmtTime } from "@/lib/api";

type A = { id: number; org_id: number | null; user_id: number | null; action: string; entity: string; entity_id: string; data: object; at: string };

export default function Audit() {
  const list = useLoad(() => api("/platform/audit", { org: false, params: { limit: 200 } }));
  return (
    <>
      <PageHeader title="Audit log" subtitle="Who changed what, including support access to gyms" />
      <Card>
        {!list.data ? <Spinner /> : (
          <Table head={["When", "Action", "Gym", "User", "Details"]}>
            {list.data.map((a: A) => (
              <tr key={a.id}>
                <Td className="whitespace-nowrap">{fmtDate(a.at)} {fmtTime(a.at)}</Td><Td className="font-mono text-xs">{a.action}</Td>
                <Td>{a.org_id ?? "—"}</Td><Td>{a.user_id ?? "—"}</Td>
                <Td className="max-w-xs truncate font-mono text-xs text-slate-500">{a.entity} {a.entity_id} {JSON.stringify(a.data)}</Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </>
  );
}
