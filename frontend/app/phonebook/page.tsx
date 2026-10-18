"use client";

import { Bot, FileSignature, Plus, Search, Send, Users } from "lucide-react";
import { useState } from "react";
import {
  Badge,
  Button,
  Card,
  Drawer,
  Empty,
  ErrorNote,
  Field,
  PageHeader,
  STATUS_LABELS,
  Spinner,
  cx,
  inputClass,
} from "@/components/ui";
import { api } from "@/lib/api";
import { clientName, compactMoney, dateOnly, dateTime, money, timeAgo, todayISO } from "@/lib/format";
import { useApi, useIntegrations } from "@/lib/hooks";
import type { Appointment, Client, ClientStatus, Contract, Message, Property } from "@/lib/types";

const STATUSES: ClientStatus[] = ["LEAD", "QUALIFIED", "SITE_VISIT_BOOKED", "CLOSED_BUYER"];

export default function PhonebookPage() {
  const info = useIntegrations();
  const currency = info?.currency ?? "ETB";
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (query) params.set("q", query);
  const clients = useApi<Client[]>(`api/admin/clients?${params}`, 15000);
  const [selected, setSelected] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  return (
    <>
      <PageHeader
        title="Phonebook CRM"
        subtitle="Every lead and buyer, auto-captured from conversations: budgets, preferences and contact details."
        actions={
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> Add contact
          </Button>
        }
      />

      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line px-5 py-3">
          <form
            className="relative min-w-56 flex-1"
            onSubmit={(e) => {
              e.preventDefault();
              setQuery(q.trim());
            }}
          >
            <Search className="absolute top-2.5 left-3 size-4 text-faint" />
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              onBlur={() => setQuery(q.trim())}
              placeholder="Search name, phone, email, location…"
              className={cx(inputClass, "pl-9")}
            />
          </form>
          <div className="flex flex-wrap gap-1.5">
            {["", ...STATUSES].map((s) => (
              <button
                key={s || "all"}
                onClick={() => setStatus(s)}
                className={cx(
                  "rounded-full px-3 py-1 text-xs font-medium",
                  status === s ? "bg-brand text-white" : "bg-subtle text-muted hover:text-ink",
                )}
              >
                {s ? STATUS_LABELS[s as ClientStatus] : "All"}
              </button>
            ))}
          </div>
        </div>
        <ErrorNote message={clients.error} />
        {clients.loading && !clients.data ? (
          <Spinner />
        ) : clients.data?.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-xs font-medium uppercase tracking-wide text-muted">
                <tr className="border-b border-line">
                  <th className="px-5 py-2.5">Client</th>
                  <th className="px-3 py-2.5">Contact</th>
                  <th className="px-3 py-2.5">Budget</th>
                  <th className="px-3 py-2.5">Looking for</th>
                  <th className="px-3 py-2.5">Status</th>
                  <th className="px-5 py-2.5 text-right">Last contact</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {clients.data.map((c) => (
                  <tr key={c.id} onClick={() => setSelected(c.id)} className="cursor-pointer hover:bg-subtle/60">
                    <td className="px-5 py-3">
                      <div className="font-medium text-ink">{clientName(c)}</div>
                      <div className="text-xs text-muted">
                        {c.telegram_chat_id ? "Telegram" : c.web_session_id ? "Web chat" : "Manual"}
                        {c.properties?.name ? ` · interested in ${c.properties.name}` : ""}
                      </div>
                    </td>
                    <td className="px-3 py-3 text-muted">
                      <div>{c.phone ?? "—"}</div>
                      <div className="text-xs">{c.email ?? ""}</div>
                    </td>
                    <td className="px-3 py-3 tabular-nums text-ink">
                      {c.budget_max || c.budget_min
                        ? `${compactMoney(c.budget_min, currency)} – ${compactMoney(c.budget_max, currency)}`
                        : "—"}
                    </td>
                    <td className="px-3 py-3 text-muted">
                      {[c.preferred_bedrooms ? `${c.preferred_bedrooms} bd` : null, c.preferred_location].filter(Boolean).join(" · ") || "—"}
                    </td>
                    <td className="px-3 py-3">
                      <Badge value={c.status} />
                    </td>
                    <td className="px-5 py-3 text-right text-xs text-muted">
                      {c.last_contact_at ? timeAgo(c.last_contact_at) : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <Empty icon={<Users className="size-5" />} title="No contacts found">
            Leads appear here automatically when people message the bot.
          </Empty>
        )}
      </Card>

      <Drawer open={!!selected} onClose={() => setSelected(null)} title="Client record">
        {selected && <ClientDetail id={selected} currency={currency} timezone={info?.timezone} onChanged={clients.reload} />}
      </Drawer>
      <Drawer open={creating} onClose={() => setCreating(false)} title="Add contact">
        <ClientForm
          onSaved={(c) => {
            setCreating(false);
            clients.reload();
            setSelected(c.id);
          }}
        />
      </Drawer>
    </>
  );
}

function ClientForm({ client, onSaved }: { client?: Client; onSaved: (c: Client) => void }) {
  const [form, setForm] = useState({
    full_name: client?.full_name ?? "",
    phone: client?.phone ?? "",
    email: client?.email ?? "",
    budget_min: client?.budget_min?.toString() ?? "",
    budget_max: client?.budget_max?.toString() ?? "",
    preferred_location: client?.preferred_location ?? "",
    preferred_bedrooms: client?.preferred_bedrooms?.toString() ?? "",
    status: client?.status ?? "LEAD",
    notes: client?.notes ?? "",
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  async function save() {
    setSaving(true);
    setError(null);
    const num = (v: string) => (v.trim() === "" ? null : Number(v));
    const body = {
      ...form,
      email: form.email.trim() || null,
      phone: form.phone.trim() || null,
      full_name: form.full_name.trim() || null,
      preferred_location: form.preferred_location.trim() || null,
      notes: form.notes.trim() || null,
      budget_min: num(form.budget_min),
      budget_max: num(form.budget_max),
      preferred_bedrooms: num(form.preferred_bedrooms),
    };
    try {
      const saved = client
        ? await api<Client>(`api/admin/clients/${client.id}`, { method: "PATCH", body })
        : await api<Client>("api/admin/clients", { body });
      onSaved(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-2 gap-3">
      <Field label="Full name">
        <input className={inputClass} value={form.full_name} onChange={set("full_name")} />
      </Field>
      <Field label="Status">
        <select className={inputClass} value={form.status} onChange={set("status")}>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {STATUS_LABELS[s]}
            </option>
          ))}
        </select>
      </Field>
      <Field label="Phone">
        <input className={inputClass} value={form.phone} onChange={set("phone")} />
      </Field>
      <Field label="Email">
        <input className={inputClass} type="email" value={form.email} onChange={set("email")} />
      </Field>
      <Field label="Budget min">
        <input className={inputClass} inputMode="numeric" value={form.budget_min} onChange={set("budget_min")} />
      </Field>
      <Field label="Budget max">
        <input className={inputClass} inputMode="numeric" value={form.budget_max} onChange={set("budget_max")} />
      </Field>
      <Field label="Preferred location">
        <input className={inputClass} value={form.preferred_location} onChange={set("preferred_location")} />
      </Field>
      <Field label="Bedrooms">
        <input className={inputClass} inputMode="numeric" value={form.preferred_bedrooms} onChange={set("preferred_bedrooms")} />
      </Field>
      <Field label="Notes" className="col-span-2">
        <textarea className={inputClass} rows={3} value={form.notes} onChange={set("notes")} />
      </Field>
      <div className="col-span-2 space-y-2">
        <ErrorNote message={error} />
        <Button onClick={save} loading={saving}>
          {client ? "Save changes" : "Add contact"}
        </Button>
      </div>
    </div>
  );
}

interface ClientDetailData {
  client: Client;
  messages: Message[];
  appointments: Appointment[];
  contracts: Contract[];
}

function ClientDetail({
  id,
  currency,
  timezone,
  onChanged,
}: {
  id: string;
  currency: string;
  timezone?: string;
  onChanged: () => void;
}) {
  const detail = useApi<ClientDetailData>(`api/admin/clients/${id}`);
  const [tab, setTab] = useState<"profile" | "conversation" | "deals">("profile");

  if (!detail.data) return detail.error ? <ErrorNote message={detail.error} /> : <Spinner />;
  const { client, messages, appointments, contracts } = detail.data;
  const refresh = () => {
    detail.reload();
    onChanged();
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-3">
        <div className="text-lg font-semibold text-ink">{clientName(client)}</div>
        <Badge value={client.status} />
        {client.telegram_username && <span className="text-sm text-muted">@{client.telegram_username}</span>}
      </div>
      <div className="flex gap-1 border-b border-line">
        {(["profile", "conversation", "deals"] as const).map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={cx(
              "-mb-px border-b-2 px-3 py-2 text-sm font-medium capitalize",
              tab === t ? "border-brand text-brand" : "border-transparent text-muted hover:text-ink",
            )}
          >
            {t === "deals" ? "Meetings & contracts" : t}
          </button>
        ))}
      </div>

      {tab === "profile" && <ClientForm key={client.updated_at} client={client} onSaved={refresh} />}

      {tab === "conversation" && (
        <div className="space-y-2.5">
          {messages.filter((m) => m.role !== "tool").length === 0 && <p className="text-sm text-muted">No messages yet.</p>}
          {messages.map((m) =>
            m.role === "tool" ? null : (
              <div key={m.id} className={cx("flex gap-2", m.role === "user" ? "" : "flex-row-reverse")}>
                <div
                  className={cx(
                    "max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2 text-sm",
                    m.role === "user" ? "bg-surface text-ink ring-1 ring-line" : "bg-brand-soft text-ink",
                  )}
                >
                  {m.role === "assistant" && <Bot className="mb-1 size-3.5 text-brand" />}
                  {m.content}
                  <div className="mt-1 text-[11px] text-faint">
                    {m.channel} · {dateTime(m.created_at, timezone)}
                  </div>
                </div>
              </div>
            ),
          )}
        </div>
      )}

      {tab === "deals" && (
        <div className="space-y-5">
          <section>
            <h3 className="mb-2 text-sm font-semibold text-ink">Appointments</h3>
            {appointments.length ? (
              <ul className="space-y-2">
                {appointments.map((a) => (
                  <li key={a.id} className="flex items-center justify-between rounded-lg bg-surface px-3 py-2 text-sm ring-1 ring-line">
                    <span>
                      {a.type === "SITE_VISIT" ? "Site visit" : "Phone call"} · {dateTime(a.start_at, timezone)}
                      {a.properties?.name ? ` · ${a.properties.name}` : ""}
                    </span>
                    <Badge value={a.status} />
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-sm text-muted">No appointments.</p>
            )}
          </section>
          <section>
            <h3 className="mb-2 text-sm font-semibold text-ink">Contracts</h3>
            {contracts.map((c) => {
              const paid = c.installments.filter((i) => i.status === "PAID").length;
              return (
                <div key={c.id} className="mb-2 rounded-lg bg-surface px-3 py-2 text-sm ring-1 ring-line">
                  <div className="font-medium text-ink">
                    {c.contract_number} · {c.properties?.name ?? "Property"}
                  </div>
                  <div className="text-muted">
                    {money(c.monthly_installment, currency)}/month · {paid}/{c.installments.length} installments paid
                  </div>
                </div>
              );
            })}
            <NewContractForm client={client} currency={currency} onCreated={refresh} />
          </section>
        </div>
      )}
    </div>
  );
}

function NewContractForm({ client, currency, onCreated }: { client: Client; currency: string; onCreated: () => void }) {
  const properties = useApi<Property[]>("api/admin/properties");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(() => ({
    property_id: client.interested_property_id ?? "",
    contract_number: `PP-${new Date().getFullYear()}-${Math.floor(1000 + Math.random() * 9000)}`,
    total_price: "",
    down_payment_amount: "",
    monthly_installment: "",
    months: "12",
    first_due_date: todayISO(),
    bank_details: "Commercial Bank of Ethiopia — Acc. 1000123456789 — PropPulse Developments PLC",
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const set = (key: keyof typeof form) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  if (!open) {
    return (
      <Button variant="secondary" onClick={() => setOpen(true)}>
        <FileSignature className="size-4" /> Record a sale & payment schedule
      </Button>
    );
  }

  async function save() {
    setSaving(true);
    setError(null);
    try {
      await api("api/admin/contracts", {
        body: {
          client_id: client.id,
          property_id: form.property_id || null,
          contract_number: form.contract_number,
          total_price: Number(form.total_price),
          down_payment_amount: form.down_payment_amount ? Number(form.down_payment_amount) : null,
          monthly_installment: Number(form.monthly_installment),
          months: Number(form.months),
          first_due_date: form.first_due_date,
          bank_details: form.bank_details || null,
        },
      });
      setOpen(false);
      onCreated();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="mt-3 grid grid-cols-2 gap-3 rounded-lg bg-surface p-4 ring-1 ring-line">
      <Field label="Property" className="col-span-2">
        <select className={inputClass} value={form.property_id} onChange={set("property_id")}>
          <option value="">—</option>
          {properties.data?.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} ({money(p.price, currency)})
            </option>
          ))}
        </select>
      </Field>
      <Field label="Contract number">
        <input className={inputClass} value={form.contract_number} onChange={set("contract_number")} />
      </Field>
      <Field label={`Total price (${currency})`}>
        <input className={inputClass} inputMode="numeric" value={form.total_price} onChange={set("total_price")} />
      </Field>
      <Field label="Down payment paid">
        <input className={inputClass} inputMode="numeric" value={form.down_payment_amount} onChange={set("down_payment_amount")} />
      </Field>
      <Field label="Monthly installment">
        <input className={inputClass} inputMode="numeric" value={form.monthly_installment} onChange={set("monthly_installment")} />
      </Field>
      <Field label="Number of months">
        <input className={inputClass} inputMode="numeric" value={form.months} onChange={set("months")} />
      </Field>
      <Field label="First due date">
        <input className={inputClass} type="date" value={form.first_due_date} onChange={set("first_due_date")} />
      </Field>
      <Field label="Bank details (shown on invoices)" className="col-span-2">
        <input className={inputClass} value={form.bank_details} onChange={set("bank_details")} />
      </Field>
      <div className="col-span-2 space-y-2">
        <ErrorNote message={error} />
        <p className="text-xs text-muted">
          First due {dateOnly(form.first_due_date)}. Saving marks this client as a buyer and enables automated installment reminders.
        </p>
        <div className="flex gap-2">
          <Button onClick={save} loading={saving} disabled={!form.total_price || !form.monthly_installment}>
            <Send className="size-4" /> Create contract
          </Button>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
        </div>
      </div>
    </div>
  );
}
