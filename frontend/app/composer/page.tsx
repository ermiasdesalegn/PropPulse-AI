"use client";

import {
  Building,
  CheckCircle2,
  ChevronRight,
  Database,
  ExternalLink,
  History,
  Inbox,
  Megaphone,
  Send,
  SendHorizontal,
  Sparkles,
  Users,
} from "lucide-react";
import { useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DeliveryBadges,
  Empty,
  ErrorNote,
  Field,
  PageHeader,
  cx,
  inputClass,
} from "@/components/ui";
import { api } from "@/lib/api";
import { dateTime, money } from "@/lib/format";
import { useApi, useIntegrations } from "@/lib/hooks";
import type { Delivery, Property } from "@/lib/types";

interface Parsed {
  announcement_type: string;
  property_name: string;
  location: string | null;
  price: number | null;
  price_per_sqm: number | null;
  bedrooms: number | null;
  area_sqm: number | null;
  down_payment: string | null;
  payment_plan: string | null;
  construction_status: string | null;
  description: string | null;
  discount_percent: number | null;
  key_change: string;
}

interface Preview {
  parsed: Parsed;
  existing_property: boolean;
  ad_copy: string;
  matched_leads: { id: string; name: string | null; reasons: string[]; channels: string[] }[];
}

interface PublishResult {
  announcement_id: string;
  property: Property;
  property_created: boolean;
  ad_copy: string;
  channel_message_id: number | null;
  channel_error: string | null;
  deliveries: (Delivery & { client_id: string; name: string | null; reasons?: string[] })[];
  delivered_count: number;
  extraction?: Parsed;
}

interface Announcement {
  id: string;
  source: string;
  created_at: string;
  matched_count: number;
  channel_message_id: number | null;
  parsed: Parsed | null;
  properties: { name: string } | null;
}

const PRESETS = [
  {
    id: "preset-1",
    tag: "📩 Preset 1",
    label: "5% Price Drop Memo (Bole Skyline 3BR)",
    text: `Subject: Urgent Price Update — Bole Skyline Residences
From: management@proppulse.com

Sales Team,
Effective immediately, we are offering a 5% promotional price drop on our remaining 2-bedroom luxury units at Bole Skyline Residences (Bole, Addis Ababa).
The updated total price is now ETB 9,310,000 (reduced from ETB 9,800,000). Down payment is 30% with the balance spread across 36 monthly installments. Construction is 75% complete with handover scheduled for Q3 2027.
Please reach out to all active leads in Bole with matching budgets immediately.`,
  },
  {
    id: "preset-2",
    tag: "🏢 Preset 2",
    label: "New Listing Launch (Kazanchis Luxury Penthouse)",
    text: `Subject: Official New Property Launch — Kazanchis Luxury Penthouse
From: developments@proppulse.com

We are proud to announce the launch of the Kazanchis Luxury Penthouse in Kazanchis, Addis Ababa.
- Unit Type: 4-bedroom executive penthouse (280 m²)
- Total Price: ETB 18,500,000 (approx. ETB 66,000/m²)
- Payment Plan: 25% down payment, balance over 48 monthly installments
- Construction Status: Under construction — 30% complete, handover planned for Q2 2028
- Highlights: Panoramic city skyline view, private elevator access, concierge service, and 2 underground parking bays.`,
  },
  {
    id: "preset-3",
    tag: "💳 Preset 3",
    label: "Flexible Payment Plan Update (CMC Family Villas)",
    text: `Subject: Revised Financing Structure — CMC Garden Villas
From: sales-director@proppulse.com

To accelerate final closings for CMC Garden Villas (CMC, Addis Ababa), management has authorized an ultra-flexible financing update:
- Property: CMC Garden Villas (4-bedroom standalone luxury villas, 300 m²)
- Total Price: ETB 21,500,000
- Revised Payment Plan: Down payment reduced to 20% (down from 40%), with the balance restructured across 60 monthly installments.
- Construction Status: 100% completed — ready for immediate handover and move-in.`,
  },
];

const PARSED_FIELDS: { key: keyof Parsed; label: string; numeric?: boolean; wide?: boolean }[] = [
  { key: "property_name", label: "Property name" },
  { key: "location", label: "Location" },
  { key: "price", label: "Price", numeric: true },
  { key: "price_per_sqm", label: "Price / m²", numeric: true },
  { key: "bedrooms", label: "Bedrooms", numeric: true },
  { key: "area_sqm", label: "Area m²", numeric: true },
  { key: "down_payment", label: "Down payment" },
  { key: "discount_percent", label: "Discount %", numeric: true },
  { key: "payment_plan", label: "Payment plan", wide: true },
  { key: "construction_status", label: "Construction status", wide: true },
  { key: "key_change", label: "What's new (used in lead messages)", wide: true },
];

export default function ComposerPage() {
  const info = useIntegrations();
  const currency = info?.currency ?? "ETB";
  const history = useApi<Announcement[]>("api/admin/announcements");
  const [raw, setRaw] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [adCopy, setAdCopy] = useState("");
  const [postToChannel, setPostToChannel] = useState(true);
  const [notifyLeads, setNotifyLeads] = useState(true);
  const [busy, setBusy] = useState<"analyze" | "publish" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PublishResult | null>(null);

  async function analyze() {
    setBusy("analyze");
    setError(null);
    setResult(null);
    try {
      const p = await api<Preview>("api/ingest/announcement/preview", { body: { raw_text: raw } });
      setPreview(p);
      setParsed(p.parsed);
      setAdCopy(p.ad_copy);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  async function publish() {
    setBusy("publish");
    setError(null);
    try {
      const r = await api<PublishResult>("api/ingest/announcement", {
        body: { raw_text: raw, parsed, ad_copy: adCopy, post_to_channel: postToChannel, notify_leads: notifyLeads },
      });
      setResult(r);
      setPreview(null);
      history.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(null);
    }
  }

  function updateField(field: (typeof PARSED_FIELDS)[number], value: string) {
    if (!parsed) return;
    const next = field.numeric ? (value.trim() === "" ? null : Number(value)) : value || null;
    setParsed({ ...parsed, [field.key]: next });
  }

  return (
    <>
      <PageHeader
        title="Ad & Broadcast Composer"
        subtitle="Ingest raw company announcements. Gemini extracts the facts, updates Supabase inventory, publishes rich channel ads and broadcasts to matching leads."
      />
      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          {/* 1. Ingestion Form with One-Click Preset Buttons */}
          <Card>
            <CardHeader title="1 · Company announcement ingestion" icon={<Inbox className="size-4 text-brand" />} />
            <div className="space-y-4 p-5">
              <div>
                <span className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Evaluator 1-Click Presets:
                </span>
                <div className="mt-2 grid gap-2 sm:grid-cols-3">
                  {PRESETS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setRaw(p.text)}
                      className={cx(
                        "flex flex-col items-start gap-1 rounded-xl border p-2.5 text-left transition-all",
                        raw === p.text
                          ? "border-brand bg-brand-soft/60 shadow-sm"
                          : "border-line bg-surface hover:border-brand/40 hover:bg-subtle/60"
                      )}
                    >
                      <span className="rounded bg-brand/10 px-1.5 py-0.5 text-[10px] font-bold text-brand">
                        {p.tag}
                      </span>
                      <span className="text-xs font-medium leading-snug text-ink">{p.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <textarea
                className={cx(inputClass, "font-sans leading-relaxed")}
                rows={8}
                value={raw}
                onChange={(e) => setRaw(e.target.value)}
                placeholder="Paste an internal memo, price drop announcement, or new listing email…"
              />

              <div className="flex flex-wrap items-center justify-between gap-3">
                <Button onClick={analyze} loading={busy === "analyze"} disabled={raw.trim().length < 10}>
                  <Sparkles className="size-4" /> Analyze with Gemini 2.5 Flash
                </Button>
                {raw && (
                  <button
                    onClick={() => {
                      setRaw("");
                      setPreview(null);
                      setResult(null);
                    }}
                    className="text-xs text-muted hover:text-ink"
                  >
                    Clear text
                  </button>
                )}
              </div>
              <ErrorNote message={error} />
            </div>
          </Card>

          {/* 2. Review Extracted Data & Ad Copy */}
          {preview && parsed && (
            <Card>
              <CardHeader
                title="2 · Review extracted entities & ad copy"
                icon={<Sparkles className="size-4 text-brand" />}
                actions={
                  <span className="flex gap-1.5">
                    <Badge value="SCHEDULED" label={parsed.announcement_type.replaceAll("_", " ").toLowerCase()} />
                    <Badge
                      value={preview.existing_property ? "PENDING" : "AVAILABLE"}
                      label={preview.existing_property ? "Updates existing inventory" : "New listing created"}
                    />
                  </span>
                }
              />
              <div className="grid grid-cols-2 gap-3 p-5">
                {PARSED_FIELDS.map((f) => (
                  <Field key={f.key} label={f.label} className={f.wide ? "col-span-2" : undefined}>
                    <input
                      className={inputClass}
                      inputMode={f.numeric ? "decimal" : undefined}
                      value={(parsed[f.key] ?? "").toString()}
                      onChange={(e) => updateField(f, e.target.value)}
                    />
                  </Field>
                ))}
                <Field label="Telegram channel ad copy (AI generated)" className="col-span-2">
                  <textarea
                    className={cx(inputClass, "font-sans leading-relaxed")}
                    rows={9}
                    value={adCopy}
                    onChange={(e) => setAdCopy(e.target.value)}
                  />
                </Field>
                <div className="col-span-2 flex flex-wrap gap-4 text-sm text-ink">
                  <label className="flex items-center gap-2 font-medium">
                    <input
                      type="checkbox"
                      checked={postToChannel}
                      onChange={(e) => setPostToChannel(e.target.checked)}
                      className="size-4 rounded border-line text-brand focus:ring-brand/20"
                    />{" "}
                    Post to Telegram channel ({info?.channel_id ?? "@property_channel"})
                  </label>
                  <label className="flex items-center gap-2 font-medium">
                    <input
                      type="checkbox"
                      checked={notifyLeads}
                      onChange={(e) => setNotifyLeads(e.target.checked)}
                      className="size-4 rounded border-line text-brand focus:ring-brand/20"
                    />{" "}
                    Message {preview.matched_leads.length} matching lead(s)
                  </label>
                </div>
                <div className="col-span-2 pt-2">
                  <Button onClick={publish} loading={busy === "publish"}>
                    <Send className="size-4" /> Publish to Channel & Broadcast
                  </Button>
                </div>
              </div>
            </Card>
          )}

          {/* 3. End-to-End Execution Pipeline Summary Card */}
          {result && (
            <Card className="border-emerald-200 bg-emerald-50/20 shadow-md">
              <CardHeader
                title="End-to-End Workflow 1 Execution Pipeline"
                icon={<CheckCircle2 className="size-5 text-emerald-600" />}
                actions={
                  <span className="rounded-full bg-emerald-100 px-2.5 py-0.5 text-xs font-semibold text-emerald-800">
                    Workflow Complete ✓
                  </span>
                }
              />
              <div className="space-y-5 p-5 text-sm">
                {/* Step 1: Extracted Entities */}
                <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-brand">
                    <span className="flex size-5 items-center justify-center rounded-full bg-brand text-white text-[11px]">1</span>
                    <span>AI Extracted Entities (Structured Output)</span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2 text-xs">
                    <span className="rounded-lg bg-subtle px-2.5 py-1 text-ink">
                      <strong>Property:</strong> {result.property.name}
                    </span>
                    <span className="rounded-lg bg-subtle px-2.5 py-1 text-ink">
                      <strong>Location:</strong> {result.property.location || "Addis Ababa"}
                    </span>
                    <span className="rounded-lg bg-subtle px-2.5 py-1 text-ink">
                      <strong>Price:</strong> {money(result.property.price, currency)}
                    </span>
                    <span className="rounded-lg bg-subtle px-2.5 py-1 text-ink">
                      <strong>Bedrooms:</strong> {result.property.bedrooms ?? "—"}
                    </span>
                    <span className="rounded-lg bg-subtle px-2.5 py-1 text-ink">
                      <strong>Down Payment:</strong> {result.property.down_payment || "—"}
                    </span>
                    {result.extraction?.key_change && (
                      <span className="rounded-lg bg-amber-50 px-2.5 py-1 text-amber-800 font-medium">
                        <strong>Change:</strong> {result.extraction.key_change}
                      </span>
                    )}
                  </div>
                </div>

                {/* Step 2: Supabase Inventory Action */}
                <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-sky-700">
                    <span className="flex size-5 items-center justify-center rounded-full bg-sky-600 text-white text-[11px]">2</span>
                    <span>Supabase Inventory Database Action</span>
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-ink">
                      Status:{" "}
                      <strong className={result.property_created ? "text-emerald-700" : "text-sky-700"}>
                        {result.property_created ? "New Property Created" : "Existing Property Record Updated"}
                      </strong>{" "}
                      · <span className="font-mono text-muted">ID: {result.property.id.slice(0, 13)}…</span>
                    </span>
                    <Badge value="AVAILABLE" label="Inventory Synced" />
                  </div>
                </div>

                {/* Step 3: Telegram Channel Post */}
                <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
                  <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-indigo-700">
                    <span className="flex size-5 items-center justify-center rounded-full bg-indigo-600 text-white text-[11px]">3</span>
                    <span>Telegram Channel Ad Published</span>
                  </div>
                  <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs">
                    <span className="text-ink">
                      {result.channel_message_id ? (
                        <span className="text-emerald-700 font-semibold">
                          Posted to Channel ✓ (Message #{result.channel_message_id})
                        </span>
                      ) : result.channel_error ? (
                        <span className="text-amber-700">Channel status: {result.channel_error}</span>
                      ) : (
                        <span className="text-muted">Channel posting skipped</span>
                      )}
                    </span>
                    <span className="text-xs text-muted">
                      Target: <strong>{info?.channel_id ?? "@property_channel"}</strong>
                    </span>
                  </div>
                </div>

                {/* Step 4: Targeted Leads Broadcast */}
                <div className="rounded-xl border border-line bg-surface p-4 shadow-sm">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-emerald-700">
                      <span className="flex size-5 items-center justify-center rounded-full bg-emerald-600 text-white text-[11px]">4</span>
                      <span>Targeted Phonebook Leads Notified ({result.delivered_count} / {result.deliveries.length})</span>
                    </div>
                  </div>
                  {result.deliveries.length > 0 ? (
                    <ul className="mt-3 divide-y divide-line rounded-lg border border-line text-xs">
                      {result.deliveries.map((d) => (
                        <li key={d.client_id} className="flex flex-wrap items-center justify-between gap-2 p-3">
                          <div>
                            <div className="font-semibold text-ink">{d.name ?? "Lead"}</div>
                            {d.reasons && (
                              <div className="text-[11px] text-muted">
                                Matched: {d.reasons.join(" · ")}
                              </div>
                            )}
                          </div>
                          <DeliveryBadges telegram={d.telegram} email={d.email} />
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-xs text-muted italic">
                      No matching leads in Phonebook CRM for this criteria.
                    </p>
                  )}
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* Right Column: Previews & History */}
        <div className="space-y-6 lg:col-span-2">
          {preview && (
            <Card className="overflow-hidden">
              <CardHeader title="Telegram Channel Post Preview" icon={<Megaphone className="size-4 text-brand" />} />
              <div className="bg-[#e6ebee] p-4">
                <div className="rounded-xl rounded-bl-sm bg-white p-3.5 text-sm whitespace-pre-wrap leading-relaxed text-ink shadow-sm">
                  {adCopy}
                </div>
                <div className="mt-2 grid gap-1.5">
                  <div className="flex items-center justify-center gap-1.5 rounded-lg bg-white/90 py-2 text-center text-xs font-semibold text-sky-700 shadow-sm">
                    <span>💬 Chat & Book Site Visit</span>
                  </div>
                  <div className="flex items-center justify-center gap-1.5 rounded-lg bg-white/90 py-2 text-center text-xs font-semibold text-sky-700 shadow-sm">
                    <span>💰 Request Payment Plan</span>
                  </div>
                </div>
              </div>
            </Card>
          )}

          {preview && (
            <Card>
              <CardHeader
                title={`Matching Phonebook Leads (${preview.matched_leads.length})`}
                icon={<Users className="size-4 text-brand" />}
              />
              {preview.matched_leads.length ? (
                <ul className="divide-y divide-line text-xs">
                  {preview.matched_leads.map((l) => (
                    <li key={l.id} className="px-5 py-3">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-ink">{l.name ?? "Lead"}</span>
                        <span className="rounded bg-subtle px-1.5 py-0.5 text-[10px] text-muted font-mono">
                          {l.channels.join(" + ") || "demo route"}
                        </span>
                      </div>
                      <div className="mt-0.5 text-muted">{l.reasons.join(" · ")}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="px-5 py-4 text-xs text-muted">
                  No saved leads currently match this listing&apos;s budget and location.
                </p>
              )}
            </Card>
          )}

          <Card>
            <CardHeader title="Recent Announcements" icon={<History className="size-4 text-brand" />} />
            {history.data?.length ? (
              <ul className="divide-y divide-line text-xs">
                {history.data.slice(0, 10).map((a) => (
                  <li key={a.id} className="px-5 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate font-semibold text-ink">
                        {a.properties?.name ?? a.parsed?.property_name}
                      </span>
                      <Badge value={a.source === "email" ? "QUALIFIED" : "LEAD"} label={a.source} />
                    </div>
                    <div className="mt-1 text-muted">
                      {a.parsed?.key_change} · <strong>{a.matched_count}</strong> lead(s) notified ·{" "}
                      {dateTime(a.created_at, info?.timezone)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty icon={<Megaphone className="size-5" />} title="No announcements yet" />
            )}
            <p className="border-t border-line px-5 py-3 text-xs text-muted">
              Inbound emails also auto-trigger this workflow: POST to{" "}
              <code className="rounded bg-subtle px-1 py-0.5 font-mono">/api/ingest/email-webhook?token=…</code>
            </p>
          </Card>
        </div>
      </div>
    </>
  );
}
