"use client";
import { PageHeader } from "@/components/shell";
import { Badge, Card, Spinner, Table, Td, cx, useLoad } from "@/components/ui";
import { api } from "@/lib/api";

type F = { key: string; name: string; category: string; is_globally_enabled: boolean };

export default function GlobalFeatures() {
  const list = useLoad(() => api("/platform/features", { org: false }));
  const flip = (f: F) => api(`/platform/features/${f.key}`, { org: false, method: "PATCH", body: { enabled: !f.is_globally_enabled } }).then(list.reload);
  return (
    <>
      <PageHeader title="Feature switches" subtitle="Global kill switch — turning a feature off here disables it for every gym, whatever their plan" />
      <Card>
        {!list.data ? <Spinner /> : (
          <Table head={["Feature", "Key", "Category", "Status"]}>
            {list.data.map((f: F) => (
              <tr key={f.key}>
                <Td className="font-medium">{f.name}</Td><Td className="font-mono text-xs text-slate-500">{f.key}</Td>
                <Td><Badge>{f.category}</Badge></Td>
                <Td>
                  <button role="switch" aria-checked={f.is_globally_enabled} aria-label={`Toggle ${f.name}`} onClick={() => flip(f)}
                    className={cx("relative h-6 w-11 rounded-full transition", f.is_globally_enabled ? "bg-emerald-500" : "bg-slate-300")}>
                    <span className={cx("absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition", f.is_globally_enabled ? "left-5" : "left-0.5")} />
                  </button>
                </Td>
              </tr>
            ))}
          </Table>
        )}
      </Card>
    </>
  );
}
