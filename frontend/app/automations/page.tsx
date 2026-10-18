"use client";

import { BellRing, CalendarClock, Eye, Mail, MessageSquare, Play, Receipt, Timer } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, CardHeader, DeliveryBadges, Drawer, Empty, ErrorNote, PageHeader, Spinner } from "@/components/ui";
import { api } from "@/lib/api";
import { clientName, dateTime, money, timeAgo } from "@/lib/format";
import { useApi, useIntegrations } from "@/lib/hooks";
import type { Activity, Appointment, CronSummary } from "@/lib/types";

interface PreviewModalData {
  title: string;
  client: string;
  type: "meeting" | "installment";
  whenOrAmount: string;
  telegram: string;
  email: string;
  preview_text?: string;
  preview_email_subject?: string;
  preview_email_html?: string;
}

export default function AutomationsPage() {
  const info = useIntegrations();
  const currency = info?.currency ?? "ETB";
  const runs = useApi<Activity[]>("api/admin/activity?kind=cron_run&limit=10");
  const appointments = useApi<Appointment[]>("api/admin/appointments?days_back=0&days_ahead=30");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latest, setLatest] = useState<CronSummary | null>(null);
  const [selectedPreview, setSelectedPreview] = useState<PreviewModalData | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      const res = await api<CronSummary>("api/cron/daily-proactive-run", { method: "POST" });
      setLatest(res);
      runs.reload();
      appointments.reload();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const shown = latest ?? (runs.data?.[0]?.payload as CronSummary | undefined) ?? null;

  return (
    <>
      <PageHeader
        title="Proactive Automations"
        subtitle="Every morning Cloud Scheduler calls /api/cron/daily-proactive-run: 24-hour meeting reminders and installment invoices for buyers due within 3 days or overdue."
        actions={
          <Button onClick={run} loading={running}>
            <Play className="size-4" /> Run now
          </Button>
        }
      />
      <ErrorNote message={error} />

      <div className="grid gap-6 lg:grid-cols-3">
        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader
              title={shown ? `Latest run · ${dateTime(shown.ran_at, info?.timezone)} (${shown.trigger})` : "Latest run"}
              icon={<Timer className="size-4 text-brand" />}
            />
            {runs.loading && !shown ? (
              <Spinner />
            ) : shown ? (
              <div className="divide-y divide-line">
                <section className="px-5 py-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <BellRing className="size-4 text-amber-600" /> Meeting reminders ({shown.appointment_reminders.length})
                    </h3>
                    {shown.appointment_reminders.length > 0 && (
                      <span className="text-xs text-muted italic">Click any reminder to preview message</span>
                    )}
                  </div>
                  {shown.appointment_reminders.length ? (
                    <ul className="space-y-1.5 text-sm">
                      {shown.appointment_reminders.map((r) => (
                        <li
                          key={r.appointment_id}
                          onClick={() =>
                            setSelectedPreview({
                              title: "Meeting Reminder Payload",
                              client: r.client ?? "Client",
                              type: "meeting",
                              whenOrAmount: r.when,
                              telegram: r.telegram,
                              email: r.email,
                              preview_text: r.preview_text,
                              preview_email_subject: r.preview_email_subject,
                              preview_email_html: r.preview_email_html,
                            })
                          }
                          className="group flex cursor-pointer flex-wrap items-center justify-between gap-2 rounded-lg p-2 transition-colors hover:bg-subtle"
                        >
                          <span className="flex items-center gap-2 text-ink">
                            <Eye className="size-3.5 text-muted opacity-0 transition-opacity group-hover:opacity-100" />
                            <span>
                              {r.client ?? "Client"} · <span className="text-muted">{r.when}</span>
                            </span>
                          </span>
                          {r.error ? (
                            <Badge value={`error: ${r.error}`} />
                          ) : (
                            <DeliveryBadges telegram={r.telegram} email={r.email} />
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted">No meetings in the next 24 hours needed a reminder.</p>
                  )}
                </section>
                <section className="px-5 py-4">
                  <div className="mb-2 flex items-center justify-between">
                    <h3 className="flex items-center gap-2 text-sm font-semibold text-ink">
                      <Receipt className="size-4 text-amber-700" /> Installment reminders ({shown.installment_reminders.length})
                    </h3>
                    {shown.installment_reminders.length > 0 && (
                      <span className="text-xs text-muted italic">Click any reminder to preview message</span>
                    )}
                  </div>
                  {shown.installment_reminders.length ? (
                    <ul className="space-y-1.5 text-sm">
                      {shown.installment_reminders.map((r) => (
                        <li
                          key={r.installment_id}
                          onClick={() =>
                            setSelectedPreview({
                              title: "Installment Invoice Payload",
                              client: r.client ?? "Buyer",
                              type: "installment",
                              whenOrAmount: `${r.contract} · ${money(r.amount, currency)} (${r.status})`,
                              telegram: r.telegram,
                              email: r.email,
                              preview_text: r.preview_text,
                              preview_email_subject: r.preview_email_subject,
                              preview_email_html: r.preview_email_html,
                            })
                          }
                          className="group flex cursor-pointer flex-wrap items-center justify-between gap-2 rounded-lg p-2 transition-colors hover:bg-subtle"
                        >
                          <span className="flex items-center gap-2 text-ink">
                            <Eye className="size-3.5 text-muted opacity-0 transition-opacity group-hover:opacity-100" />
                            <span>
                              {r.client ?? "Buyer"} · {r.contract} · {money(r.amount, currency)}{" "}
                              <span className={r.status?.startsWith("overdue") ? "text-red-600" : "text-muted"}>
                                ({r.status})
                              </span>
                            </span>
                          </span>
                          {r.error ? (
                            <Badge value={`error: ${r.error}`} />
                          ) : (
                            <DeliveryBadges telegram={r.telegram} email={r.email} />
                          )}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-sm text-muted">No installments due within 3 days or overdue (or already reminded today).</p>
                  )}
                </section>
              </div>
            ) : (
              <Empty icon={<Timer className="size-5" />} title="No runs yet">
                Click <strong>Run now</strong> to trigger the daily job on demand.
              </Empty>
            )}
          </Card>

          <Card>
            <CardHeader title="Run history" icon={<CalendarClock className="size-4 text-brand" />} />
            {runs.data?.length ? (
              <ul className="divide-y divide-line">
                {runs.data.map((r) => (
                  <li key={r.id} className="flex justify-between gap-3 px-5 py-2.5 text-sm">
                    <span className="text-ink">{r.summary}</span>
                    <span className="shrink-0 text-xs text-muted">{timeAgo(r.created_at)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="px-5 py-4 text-sm text-muted">Nothing yet.</p>
            )}
          </Card>
        </div>

        <Card className="self-start">
          <CardHeader title="Scheduled meetings (30 days)" icon={<CalendarClock className="size-4 text-brand" />} />
          {appointments.data?.length ? (
            <ul className="divide-y divide-line">
              {appointments.data.map((a) => (
                <li key={a.id} className="px-5 py-2.5 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-ink">{clientName(a.clients)}</span>
                    <Badge value={a.status} />
                  </div>
                  <div className="text-xs text-muted">
                    {a.type === "SITE_VISIT" ? "Site visit" : "Call"} · {dateTime(a.start_at, info?.timezone)}
                    {a.properties?.name ? ` · ${a.properties.name}` : ""}
                  </div>
                  <div className="text-xs text-faint">
                    {a.reminder_sent_at ? `reminded ${timeAgo(a.reminder_sent_at)}` : "reminder pending"}
                    {a.calendar_event_id ? " · on Google Calendar" : ""}
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <Empty icon={<CalendarClock className="size-5" />} title="No upcoming meetings" />
          )}
        </Card>
      </div>

      <Drawer
        open={Boolean(selectedPreview)}
        onClose={() => setSelectedPreview(null)}
        title={
          <div className="flex items-center gap-2">
            <span>{selectedPreview?.title}</span>
            <span className="text-xs font-normal text-muted">— {selectedPreview?.client}</span>
          </div>
        }
      >
        {selectedPreview && (
          <div className="space-y-6">
            <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-line bg-surface p-4">
              <div>
                <div className="text-sm font-semibold text-ink">{selectedPreview.client}</div>
                <div className="text-xs text-muted">{selectedPreview.whenOrAmount}</div>
              </div>
              <DeliveryBadges telegram={selectedPreview.telegram} email={selectedPreview.email} />
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <MessageSquare className="size-4 text-sky-600" />
                <span>Telegram Message Dispatched</span>
              </div>
              <div className="rounded-xl border border-sky-100 bg-sky-50/60 p-4 font-sans text-sm leading-relaxed text-slate-800 whitespace-pre-wrap shadow-inner">
                {selectedPreview.preview_text || (
                  <span className="italic text-muted">No Telegram payload available.</span>
                )}
              </div>
            </div>

            <div className="space-y-3">
              <div className="flex items-center gap-2 text-sm font-semibold text-ink">
                <Mail className="size-4 text-emerald-600" />
                <span>Email Invoice Dispatched</span>
              </div>
              <div className="overflow-hidden rounded-xl border border-line bg-white shadow-sm">
                {selectedPreview.preview_email_subject && (
                  <div className="border-b border-line bg-subtle px-4 py-2.5 text-xs font-medium text-slate-700">
                    <span className="text-muted">Subject: </span>
                    <span className="font-semibold text-ink">{selectedPreview.preview_email_subject}</span>
                  </div>
                )}
                <div className="overflow-x-auto p-4 text-sm">
                  {selectedPreview.preview_email_html ? (
                    <div
                      className="prose prose-sm max-w-none"
                      dangerouslySetInnerHTML={{ __html: selectedPreview.preview_email_html }}
                    />
                  ) : (
                    <span className="italic text-muted">No email payload available.</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        )}
      </Drawer>
    </>
  );
}
