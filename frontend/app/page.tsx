"use client";

import {
  Activity as ActivityIcon,
  AlertTriangle,
  ArrowRight,
  Building2,
  CalendarDays,
  CalendarClock,
  ExternalLink,
  Handshake,
  Megaphone,
  MessageSquareText,
  Send,
  UserCheck,
  Users,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ActivityFeed } from "@/components/ActivityFeed";
import { Badge, Button, Card, CardHeader, Empty, ErrorNote, PageHeader, Spinner, Stat, cx } from "@/components/ui";
import { api } from "@/lib/api";
import { compactMoney, dateTime, clientName } from "@/lib/format";
import { useApi, useIntegrations } from "@/lib/hooks";
import type { Activity, Appointment, CronSummary, Stats } from "@/lib/types";

const FILTERS = [
  { key: "", label: "All" },
  { key: "conversation", label: "Chats" },
  { key: "tool_call", label: "Tool calls" },
  { key: "appointment_booked", label: "Bookings" },
  { key: "lead_broadcast", label: "Broadcasts" },
  { key: "installment_reminder", label: "Payments" },
];

export default function CommandCenter() {
  const info = useIntegrations();
  const currency = info?.currency ?? "ETB";
  const [filter, setFilter] = useState("");
  const stats = useApi<Stats>("api/admin/stats", 15000);
  const activity = useApi<Activity[]>(`api/admin/activity?limit=40${filter ? `&kind=${filter}` : ""}`, 4000);
  const appointments = useApi<Appointment[]>("api/admin/appointments?days_back=0&days_ahead=14", 30000);
  const [running, setRunning] = useState(false);
  const [runResult, setRunResult] = useState<string | null>(null);

  async function runProactive() {
    setRunning(true);
    setRunResult(null);
    try {
      const summary = await api<CronSummary>("api/cron/daily-proactive-run", { method: "POST" });
      setRunResult(
        `Sent ${summary.appointment_reminders.length} meeting and ${summary.installment_reminders.length} installment reminder(s).`,
      );
      activity.reload();
      stats.reload();
    } catch (e) {
      setRunResult((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const s = stats.data;
  const upcoming = (appointments.data ?? []).filter((a) => a.status === "SCHEDULED").slice(0, 6);

  const leadsCount = s?.clients_by_status?.LEAD ?? 0;
  const qualCount = s?.clients_by_status?.QUALIFIED ?? 0;
  const visitCount = s?.clients_by_status?.SITE_VISIT_BOOKED ?? 0;
  const buyerCount = s?.clients_by_status?.CLOSED_BUYER ?? 0;
  const totalPipeline = Math.max(1, leadsCount + qualCount + visitCount + buyerCount);
  const leadsPct = Math.round((leadsCount / totalPipeline) * 100);
  const qualPct = Math.round((qualCount / totalPipeline) * 100);
  const visitPct = Math.round((visitCount / totalPipeline) * 100);
  const buyerPct = Math.round((buyerCount / totalPipeline) * 100);

  const pipelineStages = [
    {
      key: "LEAD",
      label: "1. Inbound Lead",
      desc: "Captured via Web / Ads",
      count: leadsCount,
      pct: leadsPct,
      color: "bg-sky-500",
      textColor: "text-sky-600 dark:text-sky-400",
      bgLight: "bg-sky-500/10",
      icon: Users,
    },
    {
      key: "QUALIFIED",
      label: "2. AI Qualified",
      desc: "Budget & Criteria Verified",
      count: qualCount,
      pct: qualPct,
      color: "bg-indigo-500",
      textColor: "text-indigo-600 dark:text-indigo-400",
      bgLight: "bg-indigo-500/10",
      icon: UserCheck,
    },
    {
      key: "SITE_VISIT_BOOKED",
      label: "3. Visiting (Booked)",
      desc: "Site Visit / Call Scheduled",
      count: visitCount,
      pct: visitPct,
      color: "bg-amber-500",
      textColor: "text-amber-600 dark:text-amber-400",
      bgLight: "bg-amber-500/10",
      icon: CalendarDays,
    },
    {
      key: "CLOSED_BUYER",
      label: "4. Closed Buyer",
      desc: "Contract & Installments Active",
      count: buyerCount,
      pct: buyerPct,
      color: "bg-emerald-500",
      textColor: "text-emerald-600 dark:text-emerald-400",
      bgLight: "bg-emerald-500/10",
      icon: Handshake,
    },
  ];

  const botUsername = info?.bot_username ?? "PropPulse1_bot";
  const channelLink = info?.channel_link ?? "https://t.me/+3N90TiMJ79M2NTU0";

  return (
    <>
      <PageHeader
        title="Sales Command Center"
        subtitle={`${info?.agent_name ?? "Your AI sales executive"} is working 24/7 across Telegram, email and your calendar.`}
        actions={
          <>
            <Link href="/composer">
              <Button variant="secondary">
                <Megaphone className="size-4" /> New announcement
              </Button>
            </Link>
            <Button onClick={runProactive} loading={running}>
              <CalendarClock className="size-4" /> Run daily reminders
            </Button>
          </>
        }
      />
      {runResult && <div className="mb-4 rounded-lg border border-line bg-surface px-4 py-2.5 text-sm text-ink">{runResult}</div>}
      <ErrorNote message={stats.error} />

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-6">
        <Stat label="Leads" value={s?.clients_by_status.LEAD ?? "–"} icon={<Users className="size-4" />} hint={`${s?.clients_total ?? 0} contacts total`} />
        <Stat label="Qualified" value={s?.clients_by_status.QUALIFIED ?? "–"} icon={<UserCheck className="size-4" />} />
        <Stat label="Visits booked" value={s?.clients_by_status.SITE_VISIT_BOOKED ?? "–"} icon={<CalendarDays className="size-4" />} hint={`${s?.appointments_next_7_days ?? 0} meetings next 7 days`} />
        <Stat label="Buyers" value={s?.clients_by_status.CLOSED_BUYER ?? "–"} icon={<Handshake className="size-4" />} />
        <Stat label="Inventory" value={s?.properties_available ?? "–"} icon={<Building2 className="size-4" />} hint="available listings" />
        <Stat
          label="Overdue"
          value={s?.installments_overdue ?? "–"}
          icon={<AlertTriangle className="size-4" />}
          tone={s && s.installments_overdue > 0 ? "warn" : "default"}
          hint={s ? `${compactMoney(s.overdue_amount, currency)} · ${s.installments_due_soon} due ≤3 days` : undefined}
        />
      </section>

      {/* Visual Sales Pipeline Funnel (SRS Section 5.1) */}
      <Card className="mt-6 p-5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-line pb-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="size-2 rounded-full bg-brand animate-pulse" />
              <h3 className="text-sm font-semibold text-ink">Autonomous Sales Pipeline Funnel</h3>
              <span className="rounded-full bg-brand-soft px-2 py-0.5 text-[10px] font-semibold text-brand">
                SRS Lifecycle Stages
              </span>
            </div>
            <p className="mt-0.5 text-xs text-muted">
              Real-time conversion flow across the 4 customer lifecycle stages from initial ad contact to closed contract
            </p>
          </div>
          <div className="text-xs text-muted">
            Total active leads: <span className="font-semibold text-ink">{s?.clients_total ?? 0}</span>
          </div>
        </div>

        {/* Horizontal Pipeline Stages */}
        <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {pipelineStages.map((st, i) => {
            const Icon = st.icon;
            return (
              <div
                key={st.key}
                className="relative flex flex-col justify-between rounded-xl border border-line bg-surface p-4 transition-all hover:border-brand/40 hover:shadow-sm"
              >
                <div>
                  <div className="flex items-center justify-between">
                    <span className={cx("grid size-8 place-items-center rounded-lg", st.bgLight, st.textColor)}>
                      <Icon className="size-4" />
                    </span>
                    <span className="rounded-md bg-subtle px-2 py-0.5 text-xs font-semibold text-ink">
                      {st.pct}%
                    </span>
                  </div>
                  <div className="mt-3">
                    <div className="text-xs font-semibold text-ink">{st.label}</div>
                    <div className="text-[11px] text-muted">{st.desc}</div>
                  </div>
                </div>
                <div className="mt-3 flex items-baseline justify-between border-t border-line/60 pt-2">
                  <span className="text-2xl font-bold tracking-tight text-ink">{st.count}</span>
                  <span className="text-[11px] text-muted">leads</span>
                </div>
                {i < pipelineStages.length - 1 && (
                  <div className="absolute -right-3.5 top-1/2 hidden -translate-y-1/2 z-10 lg:block">
                    <div className="grid size-6 place-items-center rounded-full border border-line bg-surface text-muted shadow-sm">
                      <ArrowRight className="size-3" />
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Segmented Funnel Progress Bar */}
        <div className="mt-4">
          <div className="flex h-2.5 w-full overflow-hidden rounded-full bg-subtle">
            {pipelineStages.map((st) => (
              <div
                key={st.key}
                style={{ width: `${Math.max(st.pct, st.count > 0 ? 5 : 0)}%` }}
                className={cx("h-full transition-all duration-500", st.color)}
                title={`${st.label}: ${st.count} (${st.pct}%)`}
              />
            ))}
          </div>
        </div>
      </Card>

      <div className="mt-6 grid gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Live agent activity"
            icon={<ActivityIcon className="size-4 text-brand" />}
            actions={<span className="flex items-center gap-1.5 text-xs text-muted"><span className="size-2 animate-pulse rounded-full bg-emerald-500" />live</span>}
          />
          <div className="flex gap-1.5 overflow-x-auto border-b border-line px-5 py-2.5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                onClick={() => setFilter(f.key)}
                className={cx(
                  "shrink-0 rounded-full px-3 py-1 text-xs font-medium",
                  filter === f.key ? "bg-brand text-white" : "bg-subtle text-muted hover:text-ink",
                )}
              >
                {f.label}
              </button>
            ))}
          </div>
          {activity.loading && !activity.data ? (
            <Spinner />
          ) : activity.data?.length ? (
            <div className="max-h-[640px] overflow-y-auto">
              <ActivityFeed items={activity.data} />
            </div>
          ) : (
            <Empty icon={<MessageSquareText className="size-5" />} title="No activity yet">
              Message the Telegram bot or try the <Link className="text-brand underline" href="/chat">test chat</Link> to see the agent work.
            </Empty>
          )}
        </Card>

        <div className="space-y-6">
          {/* Evaluator Quick-Access Card & QR Code (SRS Section 5.2) */}
          <Card className="p-5">
            <div className="flex items-center justify-between border-b border-line pb-3">
              <div>
                <h3 className="text-sm font-semibold text-ink">Evaluator Quick-Access</h3>
                <p className="text-xs text-muted">Scan or click to test live agent</p>
              </div>
              <span className="flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                <span className="size-1.5 rounded-full bg-emerald-500 animate-pulse" /> Live 24/7
              </span>
            </div>

            <div className="mt-4 flex flex-col items-center sm:flex-row sm:items-start gap-4">
              <div className="relative size-28 shrink-0 overflow-hidden rounded-xl border border-line bg-white p-1.5 shadow-sm">
                <img
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=160x160&data=https://t.me/${botUsername}&margin=4`}
                  alt={`QR code for @${botUsername}`}
                  className="size-full object-contain"
                />
              </div>
              <div className="flex-1 space-y-2 text-center sm:text-left">
                <div className="text-xs text-muted">
                  Scan QR with your phone camera or use the direct buttons below:
                </div>
                <div className="flex flex-col gap-1.5 pt-1">
                  <a
                    href={`https://t.me/${botUsername}`}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center justify-center gap-1.5 rounded-lg bg-brand px-3 py-2 text-xs font-semibold text-white shadow hover:bg-brand-strong transition-colors"
                  >
                    <Send className="size-3.5" /> Chat @{botUsername}
                  </a>
                  {channelLink && (
                    <a
                      href={channelLink}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center justify-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-1.5 text-xs font-medium text-ink hover:bg-subtle transition-colors"
                    >
                      <Megaphone className="size-3.5 text-brand" /> Ad Channel <ExternalLink className="size-3 text-muted" />
                    </a>
                  )}
                </div>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Upcoming meetings" icon={<CalendarDays className="size-4 text-brand" />} />
            {upcoming.length ? (
              <ul className="divide-y divide-line">
                {upcoming.map((a) => (
                  <li key={a.id} className="px-5 py-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-ink">{clientName(a.clients)}</span>
                      <Badge value={a.type} label={a.type === "SITE_VISIT" ? "site visit" : "call"} />
                    </div>
                    <div className="mt-0.5 text-xs text-muted">
                      {dateTime(a.start_at, info?.timezone)}
                      {a.properties?.name ? ` · ${a.properties.name}` : ""}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty icon={<CalendarDays className="size-5" />} title="No meetings in the next 14 days" />
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
