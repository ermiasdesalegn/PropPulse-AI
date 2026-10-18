"use client";

import { Check, Receipt, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, Empty, ErrorNote, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { clientName, dateOnly, dateTime, money, todayISO } from "@/lib/format";
import { useApi, useIntegrations } from "@/lib/hooks";
import type { Contract, Installment } from "@/lib/types";

function installmentState(i: Installment, today: string): "PAID" | "OVERDUE" | "DUE_SOON" | "PENDING" {
  if (i.status === "PAID") return "PAID";
  if (i.due_date < today) return "OVERDUE";
  const days = (new Date(i.due_date).getTime() - new Date(today).getTime()) / 86400000;
  return days <= 3 ? "DUE_SOON" : "PENDING";
}

export default function LedgerPage() {
  const info = useIntegrations();
  const currency = info?.currency ?? "ETB";
  const contracts = useApi<Contract[]>("api/admin/contracts");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // read the clock only after data arrives (client-side), never during prerender
  const today = contracts.data ? todayISO() : "";

  async function toggle(i: Installment) {
    setBusy(i.id);
    setError(null);
    try {
      await api(`api/admin/installments/${i.id}`, { method: "PATCH", body: { status: i.status === "PAID" ? "PENDING" : "PAID" } });
      await contracts.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  const all = (contracts.data ?? []).flatMap((c) => c.installments);
  const overdue = all.filter((i) => installmentState(i, today) === "OVERDUE");
  const dueSoon = all.filter((i) => installmentState(i, today) === "DUE_SOON");
  const collected = all.filter((i) => i.status === "PAID").reduce((sum, i) => sum + Number(i.amount), 0);
  const outstanding = all.filter((i) => i.status === "PENDING").reduce((sum, i) => sum + Number(i.amount), 0);

  return (
    <>
      <PageHeader
        title="Buyer Ledger"
        subtitle="Post-sale contracts and monthly installment schedules. Due and overdue installments get automatic Telegram + email invoices."
      />
      <section className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Stat label="Active contracts" value={contracts.data?.length ?? "–"} icon={<Receipt className="size-4" />} />
        <Stat label="Collected" value={money(collected, currency)} icon={<Check className="size-4" />} />
        <Stat label="Outstanding" value={money(outstanding, currency)} icon={<Receipt className="size-4" />} hint={`${dueSoon.length} due within 3 days`} />
        <Stat
          label="Overdue"
          value={overdue.length}
          tone={overdue.length ? "warn" : "default"}
          icon={<Receipt className="size-4" />}
          hint={money(overdue.reduce((s, i) => s + Number(i.amount), 0), currency)}
        />
      </section>
      <ErrorNote message={error ?? contracts.error} />

      {contracts.loading && !contracts.data ? (
        <Spinner />
      ) : contracts.data?.length ? (
        <div className="space-y-4">
          {contracts.data.map((c) => {
            const paid = c.installments.filter((i) => i.status === "PAID").length;
            return (
              <Card key={c.id}>
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3.5">
                  <div>
                    <div className="font-semibold text-ink">
                      {clientName(c.clients)} · <span className="font-mono text-sm">{c.contract_number}</span>
                    </div>
                    <div className="text-xs text-muted">
                      {c.properties?.name ?? "Property"} · total {money(c.total_price, currency)} · {money(c.monthly_installment, currency)}/month
                      {c.bank_details ? ` · ${c.bank_details}` : ""}
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="h-2 w-32 overflow-hidden rounded-full bg-subtle">
                      <div className="h-full bg-brand" style={{ width: `${(paid / Math.max(c.installments.length, 1)) * 100}%` }} />
                    </div>
                    <span className="text-xs text-muted tabular-nums">
                      {paid}/{c.installments.length} paid
                    </span>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[640px] text-sm">
                    <thead className="text-left text-xs uppercase tracking-wide text-muted">
                      <tr className="border-b border-line">
                        <th className="px-5 py-2">#</th>
                        <th className="px-3 py-2">Due date</th>
                        <th className="px-3 py-2">Amount</th>
                        <th className="px-3 py-2">Status</th>
                        <th className="px-3 py-2">Last reminder</th>
                        <th className="px-5 py-2" />
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">
                      {c.installments.map((i) => {
                        const state = installmentState(i, today);
                        return (
                          <tr key={i.id} className={cx(state === "OVERDUE" && "bg-red-50/50")}>
                            <td className="px-5 py-2 tabular-nums text-muted">{i.sequence_no}</td>
                            <td className="px-3 py-2">{dateOnly(i.due_date)}</td>
                            <td className="px-3 py-2 tabular-nums">{money(i.amount, currency)}</td>
                            <td className="px-3 py-2">
                              <Badge value={state === "DUE_SOON" ? "PENDING" : state} label={state === "DUE_SOON" ? "due soon" : undefined} />
                            </td>
                            <td className="px-3 py-2 text-xs text-muted">{i.last_reminded_at ? dateTime(i.last_reminded_at, info?.timezone) : "—"}</td>
                            <td className="px-5 py-2 text-right">
                              <Button variant={i.status === "PAID" ? "ghost" : "secondary"} className="px-2.5 py-1 text-xs" loading={busy === i.id} onClick={() => toggle(i)}>
                                {i.status === "PAID" ? (
                                  <>
                                    <RotateCcw className="size-3.5" /> Undo
                                  </>
                                ) : (
                                  <>
                                    <Check className="size-3.5" /> Mark paid
                                  </>
                                )}
                              </Button>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </Card>
            );
          })}
        </div>
      ) : (
        <Card>
          <Empty icon={<Receipt className="size-5" />} title="No contracts yet">
            Record a sale from a client&apos;s record in the Phonebook to generate their installment schedule.
          </Empty>
        </Card>
      )}
    </>
  );
}
